from pathlib import Path
from unittest import mock

import pyotp
import pytest

from app.database import criar_conexao, inicializar_banco
from app.user_resume import (
    alterar_senha_usuario,
    autenticar_usuario,
    atualizar_nome_usuario,
    confirmar_2fa_admin,
    confirmar_codigo_validacao_email,
    confirmar_2fa_admin_por_desafio,
    concluir_login_admin,
    consumir_magic_link,
    criar_admin_inicial,
    criar_usuario,
    definir_banimento_usuario,
    listar_usuarios_admin,
    preparar_2fa_admin,
    preparar_2fa_admin_por_desafio,
    revogar_sessao,
    solicitar_magic_link,
    solicitar_validacao_email,
    validar_sessao,
)


SENHA_FORTE = "Senha-Segura123"


@pytest.fixture
def banco_seguranca(tmp_path: Path, monkeypatch):
    banco = tmp_path / "seguranca.db"
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8501")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "x" * 48)
    with mock.patch("app.database.DATABASE_PATH", banco):
        with mock.patch("app.database.DATABASE_DIR", banco.parent):
            inicializar_banco()
            yield


def criar_admin_com_2fa() -> tuple[dict, pyotp.TOTP]:
    login_admin = "ADMIN_GESTAO"
    senha_admin = "Senha-AdminSegura789"
    assert criar_admin_inicial(login_admin, senha_admin)["status"] == "sucesso"
    primeira_etapa = autenticar_usuario(login_admin, senha_admin)
    configuracao = preparar_2fa_admin_por_desafio(
        primeira_etapa["desafio_token"]
    )
    totp = pyotp.TOTP(configuracao["segredo"])
    acesso = confirmar_2fa_admin_por_desafio(
        primeira_etapa["desafio_token"],
        totp.now(),
    )
    assert acesso["status"] == "sucesso"
    return acesso, totp


def test_senha_eh_hash_com_salt_unico(banco_seguranca):
    criar_usuario("Ana Silva", "ana@example.com", SENHA_FORTE)
    criar_usuario("Bia Silva", "bia@example.com", SENHA_FORTE)
    conexao = criar_conexao()
    try:
        registros = conexao.execute(
            "SELECT email, senha_hash, senha_salt FROM usuarios ORDER BY email"
        ).fetchall()
    finally:
        conexao.close()

    assert len(registros) == 2
    assert all(registro["senha_hash"] != SENHA_FORTE for registro in registros)
    assert registros[0]["senha_salt"] != registros[1]["senha_salt"]
    assert registros[0]["senha_hash"] != registros[1]["senha_hash"]


def test_sql_injection_nao_autentica(banco_seguranca):
    criar_usuario("Ana Silva", "ana@example.com", SENHA_FORTE)
    resultado = autenticar_usuario("' OR 1=1 --", "' OR 1=1 --")
    assert resultado["status"] == "erro"


def test_sessao_usa_token_revogavel(banco_seguranca):
    criar_usuario("Ana Silva", "ana@example.com", SENHA_FORTE)
    login = autenticar_usuario("ana@example.com", SENHA_FORTE)
    token = login["session_token"]

    assert len(token) >= 40
    assert validar_sessao(token)["email"] == "ana@example.com"

    conexao = criar_conexao()
    try:
        sessao = conexao.execute(
            "SELECT token_hash FROM sessoes_usuario"
        ).fetchone()
    finally:
        conexao.close()
    assert sessao["token_hash"] != token

    revogar_sessao(token)
    assert validar_sessao(token) is None


def test_bloqueia_bruteforce(banco_seguranca, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("LOGIN_LOCK_MINUTES", "15")
    criar_usuario("Ana Silva", "ana@example.com", SENHA_FORTE)

    for _ in range(3):
        assert autenticar_usuario("ana@example.com", "Senha-Errada123")[
            "status"
        ] == "erro"

    bloqueado = autenticar_usuario("ana@example.com", SENHA_FORTE)
    assert bloqueado["status"] == "bloqueado"


def test_magic_link_e_unico_e_expira_apos_uso(
    banco_seguranca,
    monkeypatch,
):
    criar_usuario("Ana Silva", "ana@example.com", SENHA_FORTE)
    token = "t" * 64
    monkeypatch.setattr("app.user_resume.secrets.token_urlsafe", lambda _: token)
    monkeypatch.setattr("app.user_resume._enviar_magic_link", lambda *_: True)

    resposta = solicitar_magic_link("ana@example.com")
    assert resposta["status"] == "sucesso"

    primeiro = consumir_magic_link(token)
    assert primeiro["status"] == "sucesso"
    assert primeiro["usuario"]["email_verificado"] is True
    assert consumir_magic_link(token)["status"] == "erro"


def test_admin_exige_totp_no_login(banco_seguranca, monkeypatch):
    email = "admin@example.com"
    monkeypatch.setenv("ADMIN_EMAILS", email)
    criar_usuario("Admin Seguro", email, SENHA_FORTE)

    magic_token = "m" * 64
    tokens = iter([magic_token, "s" * 64, "u" * 64, "v" * 64])
    monkeypatch.setattr(
        "app.user_resume.secrets.token_urlsafe",
        lambda _: next(tokens),
    )
    monkeypatch.setattr("app.user_resume._enviar_magic_link", lambda *_: True)
    solicitar_magic_link(email)
    acesso = consumir_magic_link(magic_token)
    assert acesso["usuario"]["papel"] == "admin"

    configuracao = preparar_2fa_admin(acesso["usuario"]["id"])
    assert configuracao["status"] == "sucesso"
    codigo = pyotp.TOTP(configuracao["segredo"]).now()
    assert confirmar_2fa_admin(acesso["usuario"]["id"], codigo)["status"] == "sucesso"

    sem_codigo = autenticar_usuario(email, SENHA_FORTE)
    assert sem_codigo["status"] == "2fa_necessario"
    login = autenticar_usuario(
        email,
        SENHA_FORTE,
        pyotp.TOTP(configuracao["segredo"]).now(),
    )
    assert login["status"] == "sucesso"


def test_validacao_informa_quando_smtp_esta_ausente(banco_seguranca):
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    resultado = solicitar_validacao_email(usuario["id"])
    assert resultado["status"] == "erro"
    assert resultado["enviado"] is False
    assert "SMTP" in resultado["mensagem"]


def test_validacao_confirma_envio_real_ao_perfil(
    banco_seguranca,
    monkeypatch,
):
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setattr(
        "app.user_resume._enviar_codigo_validacao",
        lambda *_: True,
    )

    resultado = solicitar_validacao_email(usuario["id"])
    assert resultado["status"] == "sucesso"
    assert resultado["enviado"] is True
    assert "enviado" in resultado["mensagem"].lower()


def test_codigo_email_e_hasheado_e_valida_usuario(
    banco_seguranca,
    monkeypatch,
):
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setattr("app.user_resume.secrets.randbelow", lambda _: 8820)
    monkeypatch.setattr(
        "app.user_resume._enviar_codigo_validacao",
        lambda *_: True,
    )

    assert solicitar_validacao_email(usuario["id"])["enviado"] is True
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT codigo_hash, codigo_salt
            FROM codigos_validacao_email
            WHERE usuario_id = ?
            """,
            (usuario["id"],),
        ).fetchone()
    finally:
        conexao.close()
    assert registro["codigo_hash"] != "008820"
    assert "008820" not in registro["codigo_hash"]
    assert len(registro["codigo_salt"]) == 32

    confirmado = confirmar_codigo_validacao_email(usuario["id"], "008820")
    assert confirmado["status"] == "sucesso"
    assert confirmado["mensagem"] == "Perfil validado com sucesso."
    assert confirmar_codigo_validacao_email(usuario["id"], "008820")[
        "status"
    ] == "sucesso"


def test_codigo_email_bloqueia_apos_cinco_erros(
    banco_seguranca,
    monkeypatch,
):
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setattr("app.user_resume.secrets.randbelow", lambda _: 123456)
    monkeypatch.setattr(
        "app.user_resume._enviar_codigo_validacao",
        lambda *_: True,
    )
    solicitar_validacao_email(usuario["id"])

    for _ in range(5):
        resultado = confirmar_codigo_validacao_email(usuario["id"], "000000")
        assert resultado["status"] == "erro"

    bloqueado = confirmar_codigo_validacao_email(usuario["id"], "123456")
    assert bloqueado["status"] == "erro"
    assert "expirado ou bloqueado" in bloqueado["mensagem"].lower()


def test_validacao_bloqueia_conta_por_bruteforce(
    banco_seguranca,
    monkeypatch,
):
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setenv("EMAIL_CODE_MAX_ACCOUNT_FAILURES", "5")
    monkeypatch.setattr("app.user_resume.secrets.randbelow", lambda _: 654321)
    monkeypatch.setattr(
        "app.user_resume._enviar_codigo_validacao",
        lambda *_: True,
    )
    solicitar_validacao_email(usuario["id"])

    ultimo = None
    for _ in range(5):
        ultimo = confirmar_codigo_validacao_email(usuario["id"], "000000")
    assert ultimo["status"] == "bloqueado"

    correto = confirmar_codigo_validacao_email(usuario["id"], "654321")
    assert correto["status"] == "bloqueado"


def test_limita_envios_automatizados_por_hora(
    banco_seguranca,
    monkeypatch,
):
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setenv("EMAIL_CODE_MAX_SENDS_PER_HOUR", "2")
    monkeypatch.setattr(
        "app.user_resume._enviar_codigo_validacao",
        lambda *_: True,
    )

    assert solicitar_validacao_email(usuario["id"])["enviado"] is True
    conexao = criar_conexao()
    try:
        conexao.execute(
            """
            UPDATE codigos_validacao_email
            SET criado_em = '2000-01-01T00:00:00Z'
            WHERE usuario_id = ?
            """,
            (usuario["id"],),
        )
        conexao.commit()
    finally:
        conexao.close()
    assert solicitar_validacao_email(usuario["id"])["enviado"] is True

    bloqueado = solicitar_validacao_email(usuario["id"])
    assert bloqueado["status"] == "bloqueado"
    assert bloqueado["enviado"] is False


def test_perfil_altera_nome_e_senha(banco_seguranca):
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    assert atualizar_nome_usuario(usuario["id"], "Ana Souza") == {
        "status": "sucesso",
        "nome": "Ana Souza",
    }
    nova_senha = "Nova-SenhaSegura456"
    assert alterar_senha_usuario(
        usuario["id"],
        SENHA_FORTE,
        nova_senha,
    )["status"] == "sucesso"
    assert autenticar_usuario("ana@example.com", nova_senha)["status"] == "sucesso"


def test_admin_oculta_2fa_ate_senha_correta(banco_seguranca):
    login_admin = "ADMIN_TESTE"
    senha_admin = "Senha-AdminSegura789"
    assert criar_admin_inicial(login_admin, senha_admin)["status"] == "sucesso"

    senha_errada = autenticar_usuario(login_admin, "Senha-Errada123")
    assert senha_errada["status"] == "erro"
    assert "desafio_token" not in senha_errada

    primeira_etapa = autenticar_usuario(login_admin, senha_admin)
    assert primeira_etapa["status"] == "2fa_configuracao"
    assert len(primeira_etapa["desafio_token"]) >= 40

    configuracao = preparar_2fa_admin_por_desafio(
        primeira_etapa["desafio_token"]
    )
    assert configuracao["status"] == "sucesso"
    codigo = pyotp.TOTP(configuracao["segredo"]).now()
    acesso = confirmar_2fa_admin_por_desafio(
        primeira_etapa["desafio_token"],
        codigo,
    )
    assert acesso["status"] == "sucesso"
    assert acesso["usuario"]["papel"] == "admin"

    revogar_sessao(acesso["session_token"])
    segunda_etapa = autenticar_usuario(login_admin, senha_admin)
    assert segunda_etapa["status"] == "2fa_necessario"
    assert "usuario" not in segunda_etapa

    acesso_novo = concluir_login_admin(
        segunda_etapa["desafio_token"],
        pyotp.TOTP(configuracao["segredo"]).now(),
    )
    assert acesso_novo["status"] == "sucesso"

    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT senha_hash, senha_salt, papel
            FROM usuarios WHERE login = ?
            """,
            (login_admin,),
        ).fetchone()
    finally:
        conexao.close()
    assert registro["senha_hash"] != senha_admin
    assert registro["senha_salt"]
    assert registro["papel"] == "admin"


def test_usuario_comum_nao_acessa_gestao(banco_seguranca):
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    resultado = listar_usuarios_admin(usuario["id"])
    assert resultado["status"] == "erro"
    assert resultado["mensagem"] == "Operação não autorizada."


def test_banimento_revoga_acessos_e_bloqueia_novo_cadastro(
    banco_seguranca,
    monkeypatch,
):
    acesso_admin, totp = criar_admin_com_2fa()
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    login_usuario = autenticar_usuario("ana@example.com", SENHA_FORTE)
    token_usuario = login_usuario["session_token"]

    monkeypatch.setattr("app.user_resume._enviar_magic_link", lambda *_: True)
    assert solicitar_magic_link("ana@example.com")["enviado"] is True
    conexao = criar_conexao()
    try:
        magic_hash = conexao.execute(
            """
            SELECT token_hash FROM magic_links
            WHERE usuario_id = ? AND usado_em IS NULL
            """,
            (usuario["id"],),
        ).fetchone()["token_hash"]
    finally:
        conexao.close()

    resultado = definir_banimento_usuario(
        administrador_id=acesso_admin["usuario"]["id"],
        usuario_id=usuario["id"],
        banir=True,
        motivo="Violação das regras de uso.",
        codigo_2fa=totp.now(),
    )
    assert resultado["status"] == "sucesso"
    assert validar_sessao(token_usuario) is None
    assert autenticar_usuario("ana@example.com", SENHA_FORTE)["status"] == "erro"
    assert criar_usuario(
        "Outra pessoa",
        "ANA@EXAMPLE.COM",
        SENHA_FORTE,
    )["status"] == "erro"

    conexao = criar_conexao()
    try:
        magic = conexao.execute(
            "SELECT usado_em FROM magic_links WHERE token_hash = ?",
            (magic_hash,),
        ).fetchone()
    finally:
        conexao.close()
    assert magic["usado_em"] is not None

    listagem = listar_usuarios_admin(
        acesso_admin["usuario"]["id"],
        status="banidos",
    )
    assert listagem["status"] == "sucesso"
    assert listagem["metricas"]["banidos"] == 1
    assert [item["email"] for item in listagem["usuarios"]] == [
        "ana@example.com"
    ]
    assert "senha_hash" not in listagem["usuarios"][0]
    assert "senha_salt" not in listagem["usuarios"][0]
    assert "totp_segredo_criptografado" not in listagem["usuarios"][0]


def test_desbanimento_restaura_login_e_mantem_auditoria(banco_seguranca):
    acesso_admin, totp = criar_admin_com_2fa()
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    admin_id = acesso_admin["usuario"]["id"]

    assert definir_banimento_usuario(
        admin_id,
        usuario["id"],
        True,
        "Conta usada de forma irregular.",
        totp.now(),
    )["status"] == "sucesso"
    assert definir_banimento_usuario(
        admin_id,
        usuario["id"],
        False,
        "Revisão concluída pelo administrador.",
        totp.now(),
    )["status"] == "sucesso"

    assert autenticar_usuario("ana@example.com", SENHA_FORTE)["status"] == "sucesso"
    listagem = listar_usuarios_admin(admin_id)
    assert [evento["acao"] for evento in listagem["auditoria"][:2]] == [
        "desbanir",
        "banir",
    ]


def test_banimento_exige_2fa_valido_e_nao_aceita_admin(
    banco_seguranca,
):
    acesso_admin, totp = criar_admin_com_2fa()
    usuario = criar_usuario(
        "Ana Silva",
        "ana@example.com",
        SENHA_FORTE,
    )["usuario"]
    admin_id = acesso_admin["usuario"]["id"]

    invalido = definir_banimento_usuario(
        admin_id,
        usuario["id"],
        True,
        "Motivo administrativo válido.",
        "000000",
    )
    assert invalido["status"] == "erro"
    assert autenticar_usuario("ana@example.com", SENHA_FORTE)["status"] == "sucesso"

    contra_admin = definir_banimento_usuario(
        admin_id,
        admin_id,
        True,
        "Tentativa de bloquear administrador.",
        totp.now(),
    )
    assert contra_admin["status"] == "erro"
