"""Autenticação segura e persistência de currículos por usuário."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlencode

import pyotp
from cryptography.fernet import Fernet, InvalidToken

from app.database import criar_conexao


logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
MENSAGEM_LOGIN_INVALIDO = "E-mail, senha ou código de segurança inválidos."
MENSAGEM_MAGIC_LINK = (
    "Se o e-mail estiver cadastrado, enviaremos um link de acesso temporário."
)


def agora_datetime() -> datetime:
    return datetime.now(timezone.utc)


def agora_utc() -> str:
    return agora_datetime().isoformat().replace("+00:00", "Z")


def _iso(data: datetime) -> str:
    return data.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _data(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _inteiro_ambiente(nome: str, padrao: int, minimo: int, maximo: int) -> int:
    try:
        return max(minimo, min(maximo, int(os.getenv(nome, str(padrao)))))
    except (TypeError, ValueError):
        return padrao


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_identidade(email: str) -> str:
    return hashlib.sha256(email.casefold().encode("utf-8")).hexdigest()


def _emails_admin() -> set[str]:
    return {
        email.strip().casefold()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }


def _usuario_publico(registro: Any) -> dict[str, Any]:
    chaves = set(registro.keys())
    return {
        "id": registro["id"],
        "nome": registro["nome"],
        "email": registro["email"],
        "login": registro["login"] if "login" in chaves else None,
        "papel": registro["papel"],
        "email_verificado": bool(registro["email_verificado"]),
        "totp_habilitado": bool(registro["totp_habilitado"]),
    }


def gerar_hash_senha(senha: str, salt: bytes | None = None) -> tuple[str, str]:
    """Gera impressão digital scrypt com salt aleatório e único."""
    salt_real = salt or secrets.token_bytes(16)
    senha_hash = hashlib.scrypt(
        senha.encode("utf-8"),
        salt=salt_real,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return senha_hash.hex(), salt_real.hex()


def validar_senha(senha: str, hash_esperado: str, salt_hex: str) -> bool:
    try:
        senha_hash, _ = gerar_hash_senha(senha, bytes.fromhex(salt_hex))
        return hmac.compare_digest(senha_hash, hash_esperado)
    except (ValueError, TypeError):
        return False


def _senha_forte(senha: str) -> bool:
    return (
        12 <= len(senha or "") <= 128
        and any(c.islower() for c in senha)
        and any(c.isupper() for c in senha)
        and any(c.isdigit() for c in senha)
    )


def _bloqueio_login(email: str) -> tuple[bool, int]:
    identidade = _hash_identidade(email)
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT bloqueado_ate
            FROM tentativas_login
            WHERE identidade_hash = ?
            """,
            (identidade,),
        ).fetchone()
        bloqueado_ate = _data(registro["bloqueado_ate"]) if registro else None
        if bloqueado_ate and bloqueado_ate > agora_datetime():
            segundos = int((bloqueado_ate - agora_datetime()).total_seconds())
            return True, max(1, segundos)
        return False, 0
    finally:
        conexao.close()


def _registrar_falha_login(email: str) -> None:
    identidade = _hash_identidade(email)
    maximo = _inteiro_ambiente("LOGIN_MAX_ATTEMPTS", 5, 3, 20)
    minutos = _inteiro_ambiente("LOGIN_LOCK_MINUTES", 15, 1, 1440)
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            "SELECT falhas FROM tentativas_login WHERE identidade_hash = ?",
            (identidade,),
        ).fetchone()
        falhas = (registro["falhas"] if registro else 0) + 1
        bloqueado_ate = (
            _iso(agora_datetime() + timedelta(minutes=minutos))
            if falhas >= maximo
            else None
        )
        conexao.execute(
            """
            INSERT INTO tentativas_login
                (identidade_hash, falhas, bloqueado_ate, atualizado_em)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(identidade_hash) DO UPDATE SET
                falhas = excluded.falhas,
                bloqueado_ate = excluded.bloqueado_ate,
                atualizado_em = excluded.atualizado_em
            """,
            (identidade, falhas, bloqueado_ate, agora_utc()),
        )
        conexao.commit()
    finally:
        conexao.close()


def _limpar_falhas_login(email: str) -> None:
    conexao = criar_conexao()
    try:
        conexao.execute(
            "DELETE FROM tentativas_login WHERE identidade_hash = ?",
            (_hash_identidade(email),),
        )
        conexao.commit()
    finally:
        conexao.close()


def criar_sessao(usuario_id: int) -> str:
    """Cria token opaco; apenas seu SHA-256 é persistido."""
    token = secrets.token_urlsafe(48)
    agora = agora_datetime()
    ttl_horas = _inteiro_ambiente("SESSION_TTL_HOURS", 12, 1, 168)
    conexao = criar_conexao()
    try:
        conexao.execute(
            """
            INSERT INTO sessoes_usuario
                (usuario_id, token_hash, criado_em, expira_em, ultimo_uso_em)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                usuario_id,
                _hash_token(token),
                _iso(agora),
                _iso(agora + timedelta(hours=ttl_horas)),
                _iso(agora),
            ),
        )
        conexao.commit()
        return token
    finally:
        conexao.close()


def validar_sessao(token: str | None) -> dict[str, Any] | None:
    if not token or len(token) < 40:
        return None
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT
                u.id, u.nome, u.email, u.papel, u.email_verificado,
                u.totp_habilitado, s.id AS sessao_id, s.expira_em, s.revogado_em
            FROM sessoes_usuario AS s
            JOIN usuarios AS u ON u.id = s.usuario_id
            WHERE s.token_hash = ?
            """,
            (_hash_token(token),),
        ).fetchone()
        if (
            not registro
            or registro["revogado_em"]
            or (_data(registro["expira_em"]) or datetime.min.replace(tzinfo=timezone.utc))
            <= agora_datetime()
        ):
            return None
        conexao.execute(
            "UPDATE sessoes_usuario SET ultimo_uso_em = ? WHERE id = ?",
            (agora_utc(), registro["sessao_id"]),
        )
        conexao.commit()
        return _usuario_publico(registro)
    finally:
        conexao.close()


def revogar_sessao(token: str | None) -> None:
    if not token:
        return
    conexao = criar_conexao()
    try:
        conexao.execute(
            """
            UPDATE sessoes_usuario
            SET revogado_em = ?
            WHERE token_hash = ? AND revogado_em IS NULL
            """,
            (agora_utc(), _hash_token(token)),
        )
        conexao.commit()
    finally:
        conexao.close()


def _criar_desafio_admin(usuario_id: int, finalidade: str) -> str:
    token = secrets.token_urlsafe(48)
    agora = agora_datetime()
    conexao = criar_conexao()
    try:
        conexao.execute(
            """
            UPDATE desafios_admin
            SET usado_em = ?
            WHERE usuario_id = ? AND usado_em IS NULL
            """,
            (_iso(agora), usuario_id),
        )
        conexao.execute(
            """
            INSERT INTO desafios_admin
                (usuario_id, token_hash, finalidade, criado_em, expira_em)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                usuario_id,
                _hash_token(token),
                finalidade,
                _iso(agora),
                _iso(agora + timedelta(minutes=5)),
            ),
        )
        conexao.commit()
        return token
    finally:
        conexao.close()


def _obter_desafio_admin(
    token: str,
    finalidade: str,
) -> dict[str, Any] | None:
    if not token or len(token) < 40:
        return None
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT
                d.id AS desafio_id, d.usuario_id, d.expira_em, d.usado_em,
                u.id, u.nome, u.email, u.login, u.papel, u.email_verificado,
                u.totp_segredo_criptografado, u.totp_habilitado
            FROM desafios_admin AS d
            JOIN usuarios AS u ON u.id = d.usuario_id
            WHERE d.token_hash = ? AND d.finalidade = ?
            """,
            (_hash_token(token), finalidade),
        ).fetchone()
        expiracao = _data(registro["expira_em"]) if registro else None
        if (
            not registro
            or registro["usado_em"]
            or not expiracao
            or expiracao <= agora_datetime()
            or registro["papel"] != "admin"
        ):
            return None
        return dict(registro)
    finally:
        conexao.close()


def _consumir_desafio_admin(desafio_id: int) -> bool:
    conexao = criar_conexao()
    try:
        cursor = conexao.execute(
            """
            UPDATE desafios_admin
            SET usado_em = ?
            WHERE id = ? AND usado_em IS NULL
            """,
            (agora_utc(), desafio_id),
        )
        conexao.commit()
        return cursor.rowcount == 1
    finally:
        conexao.close()


def criar_usuario(nome: str, email: str, senha: str) -> dict[str, Any]:
    nome_limpo = " ".join((nome or "").split())[:120]
    email_limpo = (email or "").strip().casefold()[:254]

    if len(nome_limpo) < 2:
        return {"status": "erro", "mensagem": "Informe seu nome."}
    if not EMAIL_RE.fullmatch(email_limpo):
        return {"status": "erro", "mensagem": "Informe um e-mail válido."}
    if not _senha_forte(senha):
        return {
            "status": "erro",
            "mensagem": (
                "Use ao menos 12 caracteres, incluindo maiúscula, minúscula e número."
            ),
        }

    senha_hash, senha_salt = gerar_hash_senha(senha)
    agora = agora_utc()
    conexao = criar_conexao()
    try:
        cursor = conexao.execute(
            """
            INSERT INTO usuarios
                (
                    nome, email, login, senha_hash, senha_salt, papel,
                    email_verificado, criado_em, atualizado_em
                )
            VALUES (?, ?, NULL, ?, ?, 'usuario', 0, ?, ?)
            """,
            (nome_limpo, email_limpo, senha_hash, senha_salt, agora, agora),
        )
        conexao.commit()
        return {
            "status": "sucesso",
            "usuario": {
                "id": cursor.lastrowid,
                "nome": nome_limpo,
                "email": email_limpo,
                "papel": "usuario",
                "email_verificado": False,
                "totp_habilitado": False,
            },
        }
    except Exception as erro:
        if "UNIQUE constraint failed" in str(erro):
            return {
                "status": "erro",
                "mensagem": "Não foi possível criar a conta com os dados informados.",
            }
        logger.exception("Falha interna ao criar usuário")
        return {"status": "erro", "mensagem": "Não foi possível criar a conta."}
    finally:
        conexao.close()


def criar_admin_inicial(login: str, senha: str) -> dict[str, Any]:
    """Cria uma conta administrativa sem persistir a senha original."""
    login_limpo = (login or "").strip()[:64]
    if not re.fullmatch(r"[A-Za-z0-9_.-]{5,64}", login_limpo):
        return {"status": "erro", "mensagem": "Login administrativo inválido."}
    if not _senha_forte(senha):
        return {"status": "erro", "mensagem": "Senha administrativa fraca."}

    conexao = criar_conexao()
    try:
        existente = conexao.execute(
            "SELECT id FROM usuarios WHERE login = ? COLLATE NOCASE",
            (login_limpo,),
        ).fetchone()
        if existente:
            return {
                "status": "existente",
                "mensagem": "A conta administrativa já existe.",
            }

        senha_hash, senha_salt = gerar_hash_senha(senha)
        agora = agora_utc()
        email_interno = f"{login_limpo.casefold()}@admin.local"
        conexao.execute(
            """
            INSERT INTO usuarios
                (
                    nome, email, login, senha_hash, senha_salt, papel,
                    email_verificado, totp_habilitado, criado_em, atualizado_em
                )
            VALUES (?, ?, ?, ?, ?, 'admin', 1, 0, ?, ?)
            """,
            (
                "Administrador",
                email_interno,
                login_limpo,
                senha_hash,
                senha_salt,
                agora,
                agora,
            ),
        )
        conexao.commit()
        return {"status": "sucesso"}
    except Exception:
        logger.exception("Falha interna ao criar administrador")
        return {"status": "erro", "mensagem": "Não foi possível criar a conta."}
    finally:
        conexao.close()


def _fernet() -> Fernet:
    segredo = os.getenv("APP_ENCRYPTION_KEY", "")
    if len(segredo) < 32:
        raise RuntimeError(
            "APP_ENCRYPTION_KEY deve possuir pelo menos 32 caracteres aleatórios."
        )
    chave = base64.urlsafe_b64encode(hashlib.sha256(segredo.encode("utf-8")).digest())
    return Fernet(chave)


def _descriptografar_totp(valor: str) -> str | None:
    try:
        return _fernet().decrypt(valor.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError, RuntimeError):
        return None


def _codigo_totp_valido(registro: Any, codigo: str) -> bool:
    if not registro["totp_habilitado"]:
        return False
    segredo = _descriptografar_totp(registro["totp_segredo_criptografado"] or "")
    return bool(
        segredo
        and re.fullmatch(r"\d{6}", (codigo or "").strip())
        and pyotp.TOTP(segredo).verify((codigo or "").strip(), valid_window=1)
    )


def autenticar_usuario(
    email: str,
    senha: str,
    codigo_2fa: str = "",
) -> dict[str, Any]:
    email_limpo = (email or "").strip().casefold()[:254]
    if len(senha or "") > 128:
        _registrar_falha_login(email_limpo)
        return {"status": "erro", "mensagem": MENSAGEM_LOGIN_INVALIDO}
    bloqueado, segundos = _bloqueio_login(email_limpo)
    if bloqueado:
        return {
            "status": "bloqueado",
            "mensagem": (
                "Muitas tentativas. Aguarde "
                f"{max(1, (segundos + 59) // 60)} minuto(s) e tente novamente."
            ),
        }

    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT
                id, nome, email, login, senha_hash, senha_salt, papel,
                email_verificado, totp_segredo_criptografado, totp_habilitado
            FROM usuarios
            WHERE email = ? OR login = ? COLLATE NOCASE
            """,
            (email_limpo, email_limpo),
        ).fetchone()

        credencial_valida = bool(
            registro
            and validar_senha(
                senha,
                registro["senha_hash"],
                registro["senha_salt"],
            )
        )
        if not credencial_valida:
            _registrar_falha_login(email_limpo)
            return {"status": "erro", "mensagem": MENSAGEM_LOGIN_INVALIDO}

        if registro["papel"] == "admin":
            if not registro["totp_habilitado"]:
                return {
                    "status": "2fa_configuracao",
                    "desafio_token": _criar_desafio_admin(
                        registro["id"],
                        "configurar_2fa",
                    ),
                }
            if not codigo_2fa:
                return {
                    "status": "2fa_necessario",
                    "desafio_token": _criar_desafio_admin(
                        registro["id"],
                        "login_2fa",
                    ),
                }
            if not _codigo_totp_valido(registro, codigo_2fa):
                _registrar_falha_login(email_limpo)
                return {"status": "erro", "mensagem": MENSAGEM_LOGIN_INVALIDO}

        _limpar_falhas_login(email_limpo)
        return {
            "status": "sucesso",
            "usuario": _usuario_publico(registro),
            "session_token": criar_sessao(registro["id"]),
        }
    finally:
        conexao.close()


def _smtp_configurado() -> bool:
    obrigatorios = ("SMTP_HOST", "SMTP_FROM")
    return all(os.getenv(nome, "").strip() for nome in obrigatorios)


def _enviar_email(
    destinatario: str,
    assunto: str,
    conteudo: str,
) -> bool:
    if not _smtp_configurado():
        logger.warning("E-mail não enviado: SMTP não configurado")
        return False

    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = os.getenv("SMTP_FROM", "")
    mensagem["To"] = destinatario
    mensagem.set_content(conteudo)

    host = os.getenv("SMTP_HOST", "")
    porta = _inteiro_ambiente("SMTP_PORT", 587, 1, 65535)
    usuario = os.getenv("SMTP_USER", "")
    senha = os.getenv("SMTP_PASSWORD", "")
    usar_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "sim",
    }
    usar_ssl = os.getenv("SMTP_USE_SSL", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "sim",
    }
    contexto = ssl.create_default_context()
    try:
        classe_smtp = smtplib.SMTP_SSL if usar_ssl else smtplib.SMTP
        argumentos: dict[str, Any] = {
            "host": host,
            "port": porta,
            "timeout": 10,
        }
        if usar_ssl:
            argumentos["context"] = contexto
        with classe_smtp(**argumentos) as servidor:
            if usar_tls and not usar_ssl:
                servidor.starttls(context=contexto)
            if usuario:
                servidor.login(usuario, senha)
            servidor.send_message(mensagem)
        return True
    except (OSError, smtplib.SMTPException):
        logger.exception("Falha ao enviar e-mail pelo SMTP")
        return False


def _enviar_magic_link(destinatario: str, link: str) -> bool:
    return _enviar_email(
        destinatario,
        "Seu link seguro de acesso ao SearchJob",
        "Use este link único para entrar. Ele expira em poucos minutos:\n\n"
        f"{link}\n\nSe você não solicitou o acesso, ignore esta mensagem.",
    )


def _hash_codigo_validacao(codigo: str, salt: bytes) -> str:
    segredo = os.getenv("APP_ENCRYPTION_KEY", "")
    if len(segredo) < 32:
        raise RuntimeError(
            "APP_ENCRYPTION_KEY deve possuir pelo menos 32 caracteres aleatórios."
        )
    derivado = hashlib.pbkdf2_hmac(
        "sha256",
        codigo.encode("ascii"),
        salt + segredo.encode("utf-8"),
        120_000,
        dklen=32,
    )
    return derivado.hex()


def _enviar_codigo_validacao(destinatario: str, codigo: str, ttl: int) -> bool:
    return _enviar_email(
        destinatario,
        "Código de validação do SearchJob",
        "Seu código individual de validação é:\n\n"
        f"{codigo}\n\n"
        f"Ele expira em {ttl} minutos e pode ser usado somente uma vez. "
        "Se você não solicitou esse código, ignore esta mensagem.",
    )


def solicitar_magic_link(
    email: str,
    *,
    revelar_status_envio: bool = False,
) -> dict[str, Any]:
    """Gera link aleatório, armazena apenas hash e sempre responde genericamente."""
    email_limpo = (email or "").strip().casefold()[:254]
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            "SELECT id, email FROM usuarios WHERE email = ?",
            (email_limpo,),
        ).fetchone()
        if not registro:
            return {
                "status": "sucesso",
                "mensagem": MENSAGEM_MAGIC_LINK,
                "enviado": False,
            }

        base_url = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
        if revelar_status_envio and not _smtp_configurado():
            return {
                "status": "erro",
                "mensagem": (
                    "O serviço de e-mail ainda não está configurado. Preencha "
                    "SMTP_HOST, SMTP_FROM, SMTP_USER e SMTP_PASSWORD nos Secrets."
                ),
                "enviado": False,
            }
        if not base_url.startswith(("https://", "http://localhost")):
            logger.error("APP_BASE_URL inválida; magic link não enviado")
            return {
                "status": "erro" if revelar_status_envio else "sucesso",
                "mensagem": (
                    "APP_BASE_URL não está configurada com uma URL segura."
                    if revelar_status_envio
                    else MENSAGEM_MAGIC_LINK
                ),
                "enviado": False,
            }

        ultimo_link = conexao.execute(
            """
            SELECT criado_em
            FROM magic_links
            WHERE usuario_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (registro["id"],),
        ).fetchone()
        criado_em = _data(ultimo_link["criado_em"]) if ultimo_link else None
        if criado_em and criado_em > agora_datetime() - timedelta(seconds=60):
            return {
                "status": "sucesso",
                "mensagem": (
                    "Um link foi solicitado recentemente. Aguarde um minuto "
                    "antes de tentar novamente."
                    if revelar_status_envio
                    else MENSAGEM_MAGIC_LINK
                ),
                "enviado": True,
                "limitado": True,
            }

        token = secrets.token_urlsafe(48)
        agora = agora_datetime()
        ttl = _inteiro_ambiente("MAGIC_LINK_TTL_MINUTES", 15, 5, 60)
        conexao.execute(
            """
            INSERT INTO magic_links
                (usuario_id, token_hash, finalidade, criado_em, expira_em)
            VALUES (?, ?, 'login', ?, ?)
            """,
            (
                registro["id"],
                _hash_token(token),
                _iso(agora),
                _iso(agora + timedelta(minutes=ttl)),
            ),
        )
        conexao.commit()

        link = f"{base_url}/?{urlencode({'magic_token': token})}"
        enviado = _enviar_magic_link(registro["email"], link)
        if revelar_status_envio and not enviado:
            conexao.execute(
                "DELETE FROM magic_links WHERE token_hash = ? AND usado_em IS NULL",
                (_hash_token(token),),
            )
            conexao.commit()
            return {
                "status": "erro",
                "mensagem": (
                    "O e-mail não foi enviado. Configure SMTP_HOST, SMTP_FROM, "
                    "SMTP_USER e SMTP_PASSWORD nos Secrets e tente novamente."
                ),
                "enviado": False,
            }
        return {
            "status": "sucesso",
            "mensagem": (
                "Link de validação enviado. Verifique também a caixa de spam."
                if revelar_status_envio and enviado
                else MENSAGEM_MAGIC_LINK
            ),
            "enviado": enviado,
        }
    finally:
        conexao.close()


def solicitar_validacao_email(usuario_id: int) -> dict[str, Any]:
    """Cria e envia um código individual; apenas seu hash fica armazenado."""
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            "SELECT email, email_verificado FROM usuarios WHERE id = ?",
            (usuario_id,),
        ).fetchone()
        if not registro:
            return {"status": "erro", "mensagem": "Usuário não encontrado."}
        if registro["email_verificado"]:
            return {
                "status": "sucesso",
                "mensagem": "Seu e-mail já está validado.",
                "enviado": False,
            }

        limite = _obter_limite_validacao(conexao, usuario_id)
        bloqueado_ate = _data(limite["bloqueado_ate"]) if limite else None
        if bloqueado_ate and bloqueado_ate > agora_datetime():
            minutos = max(
                1,
                int((bloqueado_ate - agora_datetime()).total_seconds() + 59) // 60,
            )
            return {
                "status": "bloqueado",
                "mensagem": (
                    f"Validação temporariamente bloqueada. Aguarde {minutos} "
                    "minuto(s)."
                ),
                "enviado": False,
            }
        maximo_envios = _inteiro_ambiente(
            "EMAIL_CODE_MAX_SENDS_PER_HOUR",
            5,
            2,
            20,
        )
        if limite and limite["envios_na_janela"] >= maximo_envios:
            return {
                "status": "bloqueado",
                "mensagem": (
                    "Limite de códigos atingido. Aguarde antes de solicitar outro."
                ),
                "enviado": False,
            }
        if not _smtp_configurado():
            return {
                "status": "erro",
                "mensagem": (
                    "O serviço de e-mail SMTP do site ainda não está configurado."
                ),
                "enviado": False,
            }

        ultimo = conexao.execute(
            """
            SELECT criado_em
            FROM codigos_validacao_email
            WHERE usuario_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (usuario_id,),
        ).fetchone()
        criado_em = _data(ultimo["criado_em"]) if ultimo else None
        if criado_em and criado_em > agora_datetime() - timedelta(seconds=60):
            return {
                "status": "sucesso",
                "mensagem": (
                    "Um código já foi enviado recentemente. Aguarde um minuto."
                ),
                "enviado": True,
                "limitado": True,
            }

        codigo = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_bytes(16)
        try:
            codigo_hash = _hash_codigo_validacao(codigo, salt)
        except RuntimeError as erro:
            return {"status": "erro", "mensagem": str(erro), "enviado": False}

        ttl = _inteiro_ambiente("EMAIL_CODE_TTL_MINUTES", 10, 5, 30)
        agora = agora_datetime()
        conexao.execute(
            """
            UPDATE codigos_validacao_email
            SET usado_em = ?
            WHERE usuario_id = ? AND usado_em IS NULL
            """,
            (_iso(agora), usuario_id),
        )
        cursor = conexao.execute(
            """
            INSERT INTO codigos_validacao_email
                (
                    usuario_id, codigo_hash, codigo_salt, criado_em,
                    expira_em, tentativas
                )
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                usuario_id,
                codigo_hash,
                salt.hex(),
                _iso(agora),
                _iso(agora + timedelta(minutes=ttl)),
            ),
        )
        conexao.commit()

        if not _enviar_codigo_validacao(registro["email"], codigo, ttl):
            conexao.execute(
                "DELETE FROM codigos_validacao_email WHERE id = ?",
                (cursor.lastrowid,),
            )
            conexao.commit()
            return {
                "status": "erro",
                "mensagem": (
                    "Não foi possível enviar o código. Verifique a configuração "
                    "do serviço de e-mail e tente novamente."
                ),
                "enviado": False,
            }
        _registrar_envio_validacao(conexao, usuario_id)
        return {
            "status": "sucesso",
            "mensagem": (
                "Código enviado. Consulte sua caixa de entrada e a pasta de spam."
            ),
            "enviado": True,
        }
    finally:
        conexao.close()


def confirmar_codigo_validacao_email(
    usuario_id: int,
    codigo: str,
) -> dict[str, Any]:
    codigo_limpo = re.sub(r"\D", "", codigo or "")
    if len(codigo_limpo) != 6:
        return {"status": "erro", "mensagem": "Informe o código de 6 dígitos."}

    conexao = criar_conexao()
    try:
        usuario = conexao.execute(
            "SELECT email, email_verificado, papel FROM usuarios WHERE id = ?",
            (usuario_id,),
        ).fetchone()
        if not usuario:
            return {"status": "erro", "mensagem": "Usuário não encontrado."}
        if usuario["email_verificado"]:
            return {"status": "sucesso", "mensagem": "Perfil já validado."}

        limite = _obter_limite_validacao(conexao, usuario_id)
        bloqueado_ate = _data(limite["bloqueado_ate"]) if limite else None
        if bloqueado_ate and bloqueado_ate > agora_datetime():
            return {
                "status": "bloqueado",
                "mensagem": (
                    "Muitas tentativas incorretas. Aguarde antes de tentar novamente."
                ),
            }

        registro = conexao.execute(
            """
            SELECT id, codigo_hash, codigo_salt, expira_em, tentativas
            FROM codigos_validacao_email
            WHERE usuario_id = ? AND usado_em IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (usuario_id,),
        ).fetchone()
        expiracao = _data(registro["expira_em"]) if registro else None
        maximo_tentativas = _inteiro_ambiente(
            "EMAIL_CODE_MAX_ATTEMPTS",
            5,
            3,
            10,
        )
        if (
            not registro
            or not expiracao
            or expiracao <= agora_datetime()
            or registro["tentativas"] >= maximo_tentativas
        ):
            return {
                "status": "erro",
                "mensagem": "Código expirado ou bloqueado. Solicite um novo.",
            }

        try:
            calculado = _hash_codigo_validacao(
                codigo_limpo,
                bytes.fromhex(registro["codigo_salt"]),
            )
        except (ValueError, RuntimeError):
            return {"status": "erro", "mensagem": "Código inválido."}

        if not hmac.compare_digest(calculado, registro["codigo_hash"]):
            tentativas = registro["tentativas"] + 1
            usado_em = agora_utc() if tentativas >= maximo_tentativas else None
            conexao.execute(
                """
                UPDATE codigos_validacao_email
                SET tentativas = ?, usado_em = ?
                WHERE id = ?
                """,
                (tentativas, usado_em, registro["id"]),
            )
            bloqueio_conta = _registrar_falha_validacao(conexao, usuario_id)
            conexao.commit()
            if bloqueio_conta:
                return {
                    "status": "bloqueado",
                    "mensagem": (
                        "Muitas tentativas incorretas. A validação foi "
                        "temporariamente bloqueada."
                    ),
                }
            restantes = max(0, maximo_tentativas - tentativas)
            return {
                "status": "erro",
                "mensagem": (
                    f"Código inválido. {restantes} tentativa(s) restante(s)."
                    if restantes
                    else "Código bloqueado. Solicite um novo."
                ),
            }

        agora = agora_utc()
        papel = (
            "admin"
            if usuario["email"].casefold() in _emails_admin()
            else usuario["papel"]
        )
        conexao.execute(
            """
            UPDATE codigos_validacao_email
            SET usado_em = ?
            WHERE id = ? AND usado_em IS NULL
            """,
            (agora, registro["id"]),
        )
        conexao.execute(
            """
            UPDATE usuarios
            SET email_verificado = 1, papel = ?, atualizado_em = ?
            WHERE id = ?
            """,
            (papel, agora, usuario_id),
        )
        conexao.execute(
            """
            UPDATE limites_validacao_email
            SET falhas_acumuladas = 0, bloqueado_ate = NULL, atualizado_em = ?
            WHERE usuario_id = ?
            """,
            (agora, usuario_id),
        )
        conexao.commit()
        return {
            "status": "sucesso",
            "mensagem": "Perfil validado com sucesso.",
            "papel": papel,
        }
    finally:
        conexao.close()


def _obter_limite_validacao(conexao: Any, usuario_id: int) -> Any:
    """Obtém o limite e reinicia a janela após uma hora."""
    registro = conexao.execute(
        """
        SELECT
            usuario_id, falhas_acumuladas, envios_na_janela,
            janela_iniciada_em, bloqueado_ate
        FROM limites_validacao_email
        WHERE usuario_id = ?
        """,
        (usuario_id,),
    ).fetchone()
    inicio = _data(registro["janela_iniciada_em"]) if registro else None
    if registro and (
        not inicio or inicio <= agora_datetime() - timedelta(hours=1)
    ):
        agora = agora_utc()
        conexao.execute(
            """
            UPDATE limites_validacao_email
            SET
                falhas_acumuladas = 0,
                envios_na_janela = 0,
                janela_iniciada_em = ?,
                bloqueado_ate = NULL,
                atualizado_em = ?
            WHERE usuario_id = ?
            """,
            (agora, agora, usuario_id),
        )
        conexao.commit()
        return conexao.execute(
            """
            SELECT
                usuario_id, falhas_acumuladas, envios_na_janela,
                janela_iniciada_em, bloqueado_ate
            FROM limites_validacao_email
            WHERE usuario_id = ?
            """,
            (usuario_id,),
        ).fetchone()
    return registro


def _registrar_envio_validacao(conexao: Any, usuario_id: int) -> None:
    agora = agora_utc()
    conexao.execute(
        """
        INSERT INTO limites_validacao_email
            (
                usuario_id, falhas_acumuladas, envios_na_janela,
                janela_iniciada_em, atualizado_em
            )
        VALUES (?, 0, 1, ?, ?)
        ON CONFLICT(usuario_id) DO UPDATE SET
            envios_na_janela = limites_validacao_email.envios_na_janela + 1,
            atualizado_em = excluded.atualizado_em
        """,
        (usuario_id, agora, agora),
    )
    conexao.commit()


def _registrar_falha_validacao(conexao: Any, usuario_id: int) -> bool:
    agora = agora_datetime()
    maximo = _inteiro_ambiente(
        "EMAIL_CODE_MAX_ACCOUNT_FAILURES",
        10,
        5,
        30,
    )
    minutos = _inteiro_ambiente(
        "EMAIL_CODE_LOCK_MINUTES",
        15,
        5,
        1440,
    )
    limite = _obter_limite_validacao(conexao, usuario_id)
    falhas = (limite["falhas_acumuladas"] if limite else 0) + 1
    bloqueado_ate = (
        _iso(agora + timedelta(minutes=minutos))
        if falhas >= maximo
        else None
    )
    inicio = limite["janela_iniciada_em"] if limite else _iso(agora)
    envios = limite["envios_na_janela"] if limite else 0
    conexao.execute(
        """
        INSERT INTO limites_validacao_email
            (
                usuario_id, falhas_acumuladas, envios_na_janela,
                janela_iniciada_em, bloqueado_ate, atualizado_em
            )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(usuario_id) DO UPDATE SET
            falhas_acumuladas = excluded.falhas_acumuladas,
            bloqueado_ate = excluded.bloqueado_ate,
            atualizado_em = excluded.atualizado_em
        """,
        (
            usuario_id,
            falhas,
            envios,
            inicio,
            bloqueado_ate,
            _iso(agora),
        ),
    )
    return bloqueado_ate is not None


def atualizar_nome_usuario(usuario_id: int, nome: str) -> dict[str, Any]:
    nome_limpo = " ".join((nome or "").split())[:120]
    if len(nome_limpo) < 2:
        return {"status": "erro", "mensagem": "Informe um nome válido."}
    conexao = criar_conexao()
    try:
        cursor = conexao.execute(
            """
            UPDATE usuarios
            SET nome = ?, atualizado_em = ?
            WHERE id = ?
            """,
            (nome_limpo, agora_utc(), usuario_id),
        )
        conexao.commit()
        if cursor.rowcount != 1:
            return {"status": "erro", "mensagem": "Usuário não encontrado."}
        return {"status": "sucesso", "nome": nome_limpo}
    finally:
        conexao.close()


def alterar_senha_usuario(
    usuario_id: int,
    senha_atual: str,
    nova_senha: str,
) -> dict[str, Any]:
    if not _senha_forte(nova_senha):
        return {
            "status": "erro",
            "mensagem": (
                "A nova senha deve ter de 12 a 128 caracteres, com maiúscula, "
                "minúscula e número."
            ),
        }
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT senha_hash, senha_salt
            FROM usuarios WHERE id = ?
            """,
            (usuario_id,),
        ).fetchone()
        if not registro or not validar_senha(
            senha_atual,
            registro["senha_hash"],
            registro["senha_salt"],
        ):
            return {"status": "erro", "mensagem": "Senha atual inválida."}
        senha_hash, senha_salt = gerar_hash_senha(nova_senha)
        conexao.execute(
            """
            UPDATE usuarios
            SET senha_hash = ?, senha_salt = ?, atualizado_em = ?
            WHERE id = ?
            """,
            (senha_hash, senha_salt, agora_utc(), usuario_id),
        )
        conexao.execute(
            """
            UPDATE sessoes_usuario
            SET revogado_em = ?
            WHERE usuario_id = ? AND revogado_em IS NULL
            """,
            (agora_utc(), usuario_id),
        )
        conexao.commit()
        return {"status": "sucesso"}
    finally:
        conexao.close()


def resumo_seguranca_usuario(usuario_id: int) -> dict[str, Any] | None:
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT
                u.nome, u.email, u.papel, u.email_verificado, u.totp_habilitado,
                (
                    SELECT COUNT(*)
                    FROM sessoes_usuario AS s
                    WHERE s.usuario_id = u.id
                      AND s.revogado_em IS NULL
                      AND s.expira_em > ?
                ) AS sessoes_ativas
            FROM usuarios AS u
            WHERE u.id = ?
            """,
            (agora_utc(), usuario_id),
        ).fetchone()
        return dict(registro) if registro else None
    finally:
        conexao.close()


def revogar_outras_sessoes(usuario_id: int, token_atual: str) -> int:
    conexao = criar_conexao()
    try:
        cursor = conexao.execute(
            """
            UPDATE sessoes_usuario
            SET revogado_em = ?
            WHERE usuario_id = ?
              AND token_hash <> ?
              AND revogado_em IS NULL
            """,
            (agora_utc(), usuario_id, _hash_token(token_atual)),
        )
        conexao.commit()
        return max(0, cursor.rowcount)
    finally:
        conexao.close()


def consumir_magic_link(token: str, codigo_2fa: str = "") -> dict[str, Any]:
    if not token or len(token) < 40:
        return {"status": "erro", "mensagem": "Link inválido ou expirado."}
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT
                m.id AS magic_id, m.expira_em, m.usado_em,
                u.id, u.nome, u.email, u.papel, u.email_verificado,
                u.totp_segredo_criptografado, u.totp_habilitado
            FROM magic_links AS m
            JOIN usuarios AS u ON u.id = m.usuario_id
            WHERE m.token_hash = ?
            """,
            (_hash_token(token),),
        ).fetchone()
        expiracao = _data(registro["expira_em"]) if registro else None
        if (
            not registro
            or registro["usado_em"]
            or not expiracao
            or expiracao <= agora_datetime()
        ):
            return {"status": "erro", "mensagem": "Link inválido ou expirado."}

        if registro["papel"] == "admin" and registro["totp_habilitado"]:
            bloqueado, segundos = _bloqueio_login(registro["email"])
            if bloqueado:
                return {
                    "status": "bloqueado",
                    "mensagem": (
                        "Muitas tentativas. Aguarde "
                        f"{max(1, (segundos + 59) // 60)} minuto(s)."
                    ),
                }
            if not codigo_2fa:
                return {
                    "status": "2fa_necessario",
                    "mensagem": "Informe o código do aplicativo autenticador.",
                }
            if not _codigo_totp_valido(registro, codigo_2fa):
                _registrar_falha_login(registro["email"])
                return {"status": "erro", "mensagem": "Código de segurança inválido."}

        papel = (
            "admin"
            if registro["email"].casefold() in _emails_admin()
            else registro["papel"]
        )
        agora = agora_utc()
        atualizacao = conexao.execute(
            "UPDATE magic_links SET usado_em = ? WHERE id = ? AND usado_em IS NULL",
            (agora, registro["magic_id"]),
        )
        if atualizacao.rowcount != 1:
            conexao.rollback()
            return {"status": "erro", "mensagem": "Link inválido ou expirado."}
        conexao.execute(
            """
            UPDATE usuarios
            SET email_verificado = 1, papel = ?, atualizado_em = ?
            WHERE id = ?
            """,
            (papel, agora, registro["id"]),
        )
        conexao.commit()
        _limpar_falhas_login(registro["email"])
        usuario = {
            **_usuario_publico(registro),
            "papel": papel,
            "email_verificado": True,
        }
        return {
            "status": "sucesso",
            "usuario": usuario,
            "session_token": criar_sessao(registro["id"]),
        }
    finally:
        conexao.close()


def preparar_2fa_admin(usuario_id: int) -> dict[str, Any]:
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT id, nome, email, papel, totp_segredo_criptografado, totp_habilitado
            FROM usuarios WHERE id = ?
            """,
            (usuario_id,),
        ).fetchone()
        if not registro or registro["papel"] != "admin":
            return {"status": "erro", "mensagem": "Operação não autorizada."}
        if registro["totp_habilitado"]:
            return {"status": "erro", "mensagem": "2FA já está habilitado."}

        segredo = (
            _descriptografar_totp(registro["totp_segredo_criptografado"])
            if registro["totp_segredo_criptografado"]
            else None
        )
        if not segredo:
            segredo = pyotp.random_base32()
            criptografado = _fernet().encrypt(segredo.encode("ascii")).decode("ascii")
            conexao.execute(
                """
                UPDATE usuarios
                SET totp_segredo_criptografado = ?, atualizado_em = ?
                WHERE id = ?
                """,
                (criptografado, agora_utc(), usuario_id),
            )
            conexao.commit()
        uri = pyotp.TOTP(segredo).provisioning_uri(
            name=registro["email"],
            issuer_name="SearchJob Automation",
        )
        return {"status": "sucesso", "segredo": segredo, "uri": uri}
    except RuntimeError as erro:
        return {"status": "erro", "mensagem": str(erro)}
    finally:
        conexao.close()


def confirmar_2fa_admin(usuario_id: int, codigo: str) -> dict[str, Any]:
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT papel, totp_segredo_criptografado, totp_habilitado
            FROM usuarios WHERE id = ?
            """,
            (usuario_id,),
        ).fetchone()
        if not registro or registro["papel"] != "admin":
            return {"status": "erro", "mensagem": "Operação não autorizada."}
        segredo = _descriptografar_totp(
            registro["totp_segredo_criptografado"] or ""
        )
        if not segredo or not pyotp.TOTP(segredo).verify(
            (codigo or "").strip(),
            valid_window=1,
        ):
            return {"status": "erro", "mensagem": "Código de segurança inválido."}
        conexao.execute(
            """
            UPDATE usuarios
            SET totp_habilitado = 1, atualizado_em = ?
            WHERE id = ?
            """,
            (agora_utc(), usuario_id),
        )
        conexao.commit()
        return {"status": "sucesso"}
    finally:
        conexao.close()


def preparar_2fa_admin_por_desafio(desafio_token: str) -> dict[str, Any]:
    desafio = _obter_desafio_admin(desafio_token, "configurar_2fa")
    if not desafio:
        return {
            "status": "erro",
            "mensagem": "A autorização expirou. Informe usuário e senha novamente.",
        }
    return preparar_2fa_admin(desafio["usuario_id"])


def confirmar_2fa_admin_por_desafio(
    desafio_token: str,
    codigo: str,
) -> dict[str, Any]:
    desafio = _obter_desafio_admin(desafio_token, "configurar_2fa")
    if not desafio:
        return {
            "status": "erro",
            "mensagem": "A autorização expirou. Informe usuário e senha novamente.",
        }
    resultado = confirmar_2fa_admin(desafio["usuario_id"], codigo)
    if resultado.get("status") != "sucesso":
        _registrar_falha_login(desafio["login"] or desafio["email"])
        return resultado
    if not _consumir_desafio_admin(desafio["desafio_id"]):
        return {"status": "erro", "mensagem": "A autorização já foi utilizada."}
    _limpar_falhas_login(desafio["login"] or desafio["email"])
    return {
        "status": "sucesso",
        "usuario": {
            **_usuario_publico(desafio),
            "totp_habilitado": True,
        },
        "session_token": criar_sessao(desafio["usuario_id"]),
    }


def concluir_login_admin(
    desafio_token: str,
    codigo: str,
) -> dict[str, Any]:
    desafio = _obter_desafio_admin(desafio_token, "login_2fa")
    if not desafio:
        return {
            "status": "erro",
            "mensagem": "A autorização expirou. Informe usuário e senha novamente.",
        }
    identidade = desafio["login"] or desafio["email"]
    bloqueado, segundos = _bloqueio_login(identidade)
    if bloqueado:
        return {
            "status": "bloqueado",
            "mensagem": (
                "Muitas tentativas. Aguarde "
                f"{max(1, (segundos + 59) // 60)} minuto(s)."
            ),
        }
    if not _codigo_totp_valido(desafio, codigo):
        _registrar_falha_login(identidade)
        return {"status": "erro", "mensagem": "Código de segurança inválido."}
    if not _consumir_desafio_admin(desafio["desafio_id"]):
        return {"status": "erro", "mensagem": "A autorização já foi utilizada."}
    _limpar_falhas_login(identidade)
    return {
        "status": "sucesso",
        "usuario": _usuario_publico(desafio),
        "session_token": criar_sessao(desafio["usuario_id"]),
    }


def salvar_curriculo(
    usuario_id: int,
    dados: dict[str, Any],
    curriculo_gerado: dict[str, Any] | None = None,
) -> dict[str, Any]:
    agora = agora_utc()
    dados_json = json.dumps(dados, ensure_ascii=False)
    gerado_json = (
        json.dumps(curriculo_gerado, ensure_ascii=False)
        if curriculo_gerado is not None
        else None
    )
    conexao = criar_conexao()
    try:
        conexao.execute(
            """
            INSERT INTO curriculos
                (usuario_id, dados_json, curriculo_gerado_json, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(usuario_id) DO UPDATE SET
                dados_json = excluded.dados_json,
                curriculo_gerado_json = COALESCE(
                    excluded.curriculo_gerado_json,
                    curriculos.curriculo_gerado_json
                ),
                atualizado_em = excluded.atualizado_em
            """,
            (usuario_id, dados_json, gerado_json, agora, agora),
        )
        conexao.commit()
        return {"status": "sucesso"}
    except Exception:
        logger.exception("Falha interna ao salvar currículo")
        return {"status": "erro", "mensagem": "Não foi possível salvar o currículo."}
    finally:
        conexao.close()


def obter_curriculo(usuario_id: int) -> dict[str, Any] | None:
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT dados_json, curriculo_gerado_json, atualizado_em
            FROM curriculos
            WHERE usuario_id = ?
            """,
            (usuario_id,),
        ).fetchone()
        if not registro:
            return None
        return {
            "dados": json.loads(registro["dados_json"]),
            "gerado": (
                json.loads(registro["curriculo_gerado_json"])
                if registro["curriculo_gerado_json"]
                else None
            ),
            "atualizado_em": registro["atualizado_em"],
        }
    except (json.JSONDecodeError, TypeError):
        return None
    finally:
        conexao.close()
