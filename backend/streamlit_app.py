"""Interface Streamlit do SearchJob Automation.

Esta entrada reutiliza diretamente os serviços e o SQLite do backend.
O FastAPI e o frontend React continuam funcionando de forma independente.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import os
import re
import sys
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import streamlit as st
import qrcode


logger = logging.getLogger(__name__)


def gerar_qr_2fa(uri: str) -> bytes:
    imagem = qrcode.make(uri)
    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    return buffer.getvalue()


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# O executável criado pelo uv no Windows pode iniciar o Streamlit pelo Python
# base sem preservar o site-packages da venv no ScriptRunner.
VENV_SITE_PACKAGES = BACKEND_DIR / ".venv" / "Lib" / "site-packages"
if VENV_SITE_PACKAGES.exists() and str(VENV_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(VENV_SITE_PACKAGES))


def carregar_secrets_no_ambiente() -> None:
    """Expõe somente as configurações conhecidas como variáveis de ambiente."""
    chaves_permitidas = {
        "ADZUNA_APP_ID",
        "ADZUNA_APP_KEY",
        "JOOBLE_API_KEY",
        "SERPAPI_API_KEY",
        "GUPY_ENABLED",
        "JOOBLE_ENABLED",
        "GREENHOUSE_ENABLED",
        "GREENHOUSE_BOARD_TOKENS",
        "GREENHOUSE_CACHE_TTL_SECONDS",
        "JOBICY_ENABLED",
        "JOBICY_CACHE_TTL_SECONDS",
        "REMOTIVE_ENABLED",
        "REMOTIVE_CACHE_TTL_SECONDS",
        "DATABASE_PATH",
        "GEMINI_API_KEY",
        "APP_ENCRYPTION_KEY",
        "APP_BASE_URL",
        "ADMIN_EMAILS",
        "SESSION_TTL_HOURS",
        "LOGIN_MAX_ATTEMPTS",
        "LOGIN_LOCK_MINUTES",
        "MAGIC_LINK_TTL_MINUTES",
        "EMAIL_CODE_TTL_MINUTES",
        "EMAIL_CODE_MAX_ATTEMPTS",
        "EMAIL_CODE_MAX_SENDS_PER_HOUR",
        "EMAIL_CODE_MAX_ACCOUNT_FAILURES",
        "EMAIL_CODE_LOCK_MINUTES",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "SMTP_USE_TLS",
        "SMTP_USE_SSL",
        "ADMIN_BOOTSTRAP_LOGIN",
        "ADMIN_BOOTSTRAP_PASSWORD",
    }

    try:
        for chave in chaves_permitidas:
            if chave not in os.environ and chave in st.secrets:
                os.environ[chave] = str(st.secrets[chave])
    except Exception:
        # Execução local sem secrets.toml: app.config continuará usando backend/.env.
        pass


carregar_secrets_no_ambiente()

from app.database import (  # noqa: E402
    gerar_chave_vaga,
    inicializar_banco,
    listar_candidaturas,
    obter_chaves_candidatadas,
    remover_candidatura,
    salvar_candidatura,
)
from app.services.job_aggregator import buscar_vagas_agregadas  # noqa: E402
from app.services.gemini_resume_service import (  # noqa: E402
    gemini_configurado,
    gerar_curriculo_com_ia,
)
from app.user_resume import (  # noqa: E402
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
    obter_curriculo,
    preparar_2fa_admin,
    preparar_2fa_admin_por_desafio,
    resumo_seguranca_usuario,
    revogar_outras_sessoes,
    revogar_sessao,
    salvar_curriculo,
    solicitar_magic_link,
    solicitar_validacao_email,
    validar_sessao,
)
from app.utils.deduplicador import remover_vagas_duplicadas  # noqa: E402
from app.utils.resume_pdf import gerar_pdf_curriculo  # noqa: E402


st.set_page_config(
    page_title="SearchJob Automation",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
        :root {
            color-scheme: dark;
        }
        .stApp {
            color: #f8fafc;
            background:
                radial-gradient(circle at 12% 8%, rgba(34, 211, 238, .13), transparent 28rem),
                radial-gradient(circle at 88% 18%, rgba(168, 85, 247, .14), transparent 30rem),
                linear-gradient(145deg, #050816 0%, #080d1d 55%, #050816 100%);
            background-attachment: fixed;
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        .block-container {
            max-width: 1120px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
        .hero {
            position: relative;
            overflow: hidden;
            padding: 2rem 2.2rem;
            border-radius: 1.25rem;
            color: #ffffff;
            background:
                radial-gradient(circle at 85% 10%, rgba(34, 211, 238, .32), transparent 18rem),
                linear-gradient(125deg, #111b45 0%, #312e81 52%, #172554 100%);
            border: 1px solid rgba(34, 211, 238, .55);
            box-shadow:
                0 0 28px rgba(34, 211, 238, .16),
                0 18px 55px rgba(0, 0, 0, .35);
            margin-bottom: 1.4rem;
        }
        .hero h1 {
            margin: 0;
            font-size: 2.25rem;
            color: #ffffff;
            text-shadow: 0 0 18px rgba(34, 211, 238, .35);
        }
        .hero p {
            margin: .55rem 0 0;
            color: #dbeafe;
            font-size: 1.02rem;
        }
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 1.4rem;
            border-bottom: 1px solid rgba(148, 163, 184, .25);
        }
        [data-testid="stTabs"] button[role="tab"] {
            color: #cbd5e1;
            font-weight: 700;
        }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            color: #22d3ee;
            text-shadow: 0 0 12px rgba(34, 211, 238, .55);
        }
        .fonte-chip {
            display: inline-block;
            padding: .28rem .65rem;
            margin: 0 .35rem .35rem 0;
            border-radius: 999px;
            background: rgba(34, 211, 238, .12);
            border: 1px solid rgba(34, 211, 238, .42);
            color: #67e8f9;
            font-size: .78rem;
            font-weight: 600;
            box-shadow: 0 0 12px rgba(34, 211, 238, .1);
        }
        .job-meta {
            color: #cbd5e1;
            margin: .15rem 0 .65rem;
        }
        .job-badges span {
            display: inline-block;
            padding: .2rem .55rem;
            margin: 0 .3rem .25rem 0;
            border-radius: 999px;
            background: rgba(168, 85, 247, .14);
            border: 1px solid rgba(192, 132, 252, .4);
            color: #e9d5ff;
            font-size: .75rem;
        }
        div[data-testid="stForm"] {
            background:
                linear-gradient(135deg, rgba(15, 23, 42, .96), rgba(17, 24, 50, .96));
            border: 1px solid rgba(34, 211, 238, .38);
            border-radius: 1rem;
            padding: 1.2rem;
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, .04),
                0 0 24px rgba(34, 211, 238, .1);
        }
        div[data-testid="stForm"] label,
        div[data-testid="stForm"] [data-testid="stWidgetLabel"] p,
        div[data-testid="stForm"] [data-testid="stCheckbox"] p {
            color: #e2e8f0 !important;
            font-weight: 650;
            opacity: 1 !important;
        }
        div[data-testid="stForm"] [data-baseweb="input"],
        div[data-testid="stForm"] [data-baseweb="select"] > div {
            color: #ffffff;
            background: #090f20;
            border-color: rgba(99, 102, 241, .65);
            box-shadow: inset 0 0 12px rgba(99, 102, 241, .08);
        }
        div[data-testid="stForm"] input,
        div[data-testid="stForm"] [data-baseweb="select"] span {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        div[data-testid="stForm"] [data-baseweb="input"]:focus-within,
        div[data-testid="stForm"] [data-baseweb="select"] > div:focus-within {
            border-color: #22d3ee;
            box-shadow: 0 0 0 1px #22d3ee, 0 0 18px rgba(34, 211, 238, .2);
        }
        div[data-testid="stForm"] [data-testid="stCheckbox"] {
            min-height: 2.9rem;
            display: flex;
            align-items: center;
        }
        div[data-testid="stForm"] button[kind="primaryFormSubmit"] {
            color: #04111b;
            font-weight: 800;
            border: 1px solid #67e8f9;
            background: linear-gradient(110deg, #22d3ee, #60a5fa);
            box-shadow: 0 0 18px rgba(34, 211, 238, .25);
            transition: transform .18s ease, box-shadow .18s ease;
        }
        div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover {
            color: #020617;
            border-color: #a5f3fc;
            transform: translateY(-2px);
            box-shadow: 0 0 28px rgba(34, 211, 238, .48);
        }
        .job-card-marker {
            display: none;
        }
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .job-card-marker
        ) {
            position: relative;
            z-index: 1;
            color: #f8fafc;
            background:
                radial-gradient(circle at 100% 0%, rgba(34, 211, 238, .12), transparent 14rem),
                linear-gradient(135deg, rgba(12, 20, 42, .98), rgba(18, 15, 45, .98));
            border: 1px solid rgba(34, 211, 238, .34) !important;
            border-radius: 1rem !important;
            box-shadow:
                0 0 18px rgba(34, 211, 238, .08),
                0 12px 32px rgba(0, 0, 0, .24);
            transition:
                transform .22s cubic-bezier(.2, .8, .2, 1),
                border-color .22s ease,
                box-shadow .22s ease;
            transform-origin: center;
        }
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .job-card-marker
        ):hover {
            z-index: 5;
            transform: scale(1.018);
            border-color: rgba(34, 211, 238, .9) !important;
            box-shadow:
                0 0 16px rgba(34, 211, 238, .35),
                0 0 34px rgba(168, 85, 247, .18),
                0 18px 45px rgba(0, 0, 0, .4);
        }
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .job-card-marker
        ) h3,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .job-card-marker
        ) p,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .job-card-marker
        ) strong {
            color: #f8fafc;
        }
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .job-card-marker
        ) h3 {
            color: #a5f3fc;
            text-shadow: 0 0 14px rgba(34, 211, 238, .2);
        }
        [data-testid="stAlert"] {
            color: #bae6fd;
            background: rgba(8, 47, 73, .7);
            border: 1px solid rgba(56, 189, 248, .38);
        }
        [data-testid="stCaptionContainer"] p {
            color: #94a3b8;
        }
        @media (prefers-reduced-motion: reduce) {
            div[data-testid="stVerticalBlock"]:has(
                > div[data-testid="stElementContainer"] .job-card-marker
            ),
            div[data-testid="stForm"] button[kind="primaryFormSubmit"] {
                transition: none;
            }
            div[data-testid="stVerticalBlock"]:has(
                > div[data-testid="stElementContainer"] .job-card-marker
            ):hover {
                transform: none;
            }
        }
        @media (max-width: 700px) {
            .block-container {
                padding-top: 1rem;
            }
            .hero {
                padding: 1.45rem;
            }
            .hero h1 {
                font-size: 1.75rem;
            }
            div[data-testid="stVerticalBlock"]:has(
                > div[data-testid="stElementContainer"] .job-card-marker
            ):hover {
                transform: scale(1.008);
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def preparar_banco() -> bool:
    inicializar_banco()
    login_admin = os.getenv("ADMIN_BOOTSTRAP_LOGIN", "").strip()
    senha_admin = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")
    if login_admin and senha_admin:
        resultado_admin = criar_admin_inicial(login_admin, senha_admin)
        if resultado_admin.get("status") not in {"sucesso", "existente"}:
            logger.error("Falha ao preparar a conta administrativa inicial")
    return True


def valor_texto(valor: Any, padrao: str) -> str:
    texto = str(valor or "").strip()
    return texto or padrao


def formatar_data(valor: Any) -> str | None:
    if not isinstance(valor, str) or not valor.strip():
        return None

    try:
        data = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
        return data.strftime("%d/%m/%Y")
    except ValueError:
        return None


def identificador_widget(vaga: dict[str, Any]) -> str:
    chave = gerar_chave_vaga(
        valor_texto(vaga.get("fonte"), "desconhecida"),
        valor_texto(vaga.get("id_externo"), vaga.get("url_candidatura", "")),
        valor_texto(vaga.get("url_candidatura"), ""),
    )
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()[:16]


def atualizar_status_candidaturas(vagas: list[dict[str, Any]]) -> None:
    chaves = obter_chaves_candidatadas()
    for vaga in vagas:
        chave = gerar_chave_vaga(
            valor_texto(vaga.get("fonte"), ""),
            valor_texto(vaga.get("id_externo"), vaga.get("url_candidatura", "")),
            valor_texto(vaga.get("url_candidatura"), ""),
        )
        vaga["ja_candidatado"] = chave in chaves


def executar_busca(filtros: dict[str, Any], pagina: int) -> None:
    with st.spinner("Buscando vagas nas fontes disponíveis..."):
        try:
            resultado = asyncio.run(
                buscar_vagas_agregadas(
                    cargo=filtros["cargo"],
                    cidade=filtros["cidade"],
                    estado=filtros["estado"],
                    modalidade=filtros["modalidade"],
                    pagina=pagina,
                    max_dias=filtros["max_dias"],
                    incluir_pcd=filtros["incluir_pcd"],
                )
            )
            vagas = resultado.get("vagas", [])
            atualizar_status_candidaturas(vagas)
            st.session_state.vagas = vagas
            st.session_state.fontes = resultado.get("fontes", [])
            st.session_state.filtros = filtros
            st.session_state.pagina = pagina
            st.session_state.erro_busca = ""
        except Exception as erro:
            st.session_state.erro_busca = (
                "Não foi possível concluir a busca. Confira as credenciais das "
                "fontes e tente novamente."
            )
            st.session_state.vagas = []
            st.session_state.fontes = []
            logger.exception("Falha interna na busca Streamlit")


def _normalizar_tokens(texto: str) -> set[str]:
    normalizado = unicodedata.normalize("NFKD", texto or "")
    normalizado = "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(caractere)
    ).casefold()
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalizado)
        if len(token) >= 3
    }


def calcular_compatibilidade(vaga: dict, curriculo: dict, cargo_busca: str) -> int:
    titulo_tokens = _normalizar_tokens(valor_texto(vaga.get("titulo"), ""))
    cargo_tokens = _normalizar_tokens(cargo_busca)
    habilidades_tokens = _normalizar_tokens(
        " ".join(
            [
                *curriculo.get("habilidades_tecnicas", []),
                *curriculo.get("competencias", []),
                *curriculo.get("palavras_chave", []),
            ]
        )
    )
    pontos_cargo = len(titulo_tokens & cargo_tokens)
    pontos_habilidades = len(titulo_tokens & habilidades_tokens)
    return min(98, 58 + pontos_cargo * 14 + pontos_habilidades * 5)


async def _buscar_por_cargos(
    cargos: list[str],
    filtros: dict[str, Any],
    pagina: int,
) -> list[tuple[str, dict]]:
    resultados = await asyncio.gather(
        *[
            buscar_vagas_agregadas(
                cargo=cargo,
                cidade=filtros["cidade"],
                estado=filtros["estado"],
                modalidade=filtros["modalidade"],
                pagina=pagina,
                max_dias=filtros["max_dias"],
                incluir_pcd=filtros["incluir_pcd"],
            )
            for cargo in cargos
        ]
    )
    return list(zip(cargos, resultados))


def executar_busca_por_curriculo(
    filtros: dict[str, Any],
    pagina: int,
    curriculo_salvo: dict,
) -> None:
    gerado = curriculo_salvo.get("gerado") or {}
    dados = curriculo_salvo.get("dados") or {}
    cargos = [
        str(cargo).strip()
        for cargo in gerado.get("cargos_recomendados", [])
        if str(cargo).strip()
    ]
    if not cargos:
        cargos = [
            cargo.strip()
            for cargo in re.split(
                r"[,;\n]",
                str(dados.get("cargos_desejados", "")),
            )
            if cargo.strip()
        ]
    cargos = list(dict.fromkeys(cargos))[:3]
    if not cargos:
        st.warning(
            "Gere seu currículo inteligente ou informe os cargos desejados antes "
            "de buscar por compatibilidade."
        )
        return

    with st.spinner(
        "Analisando cargos e buscando vagas compatíveis com seu currículo..."
    ):
        try:
            resultados = asyncio.run(
                _buscar_por_cargos(cargos, filtros, pagina)
            )
            vagas_com_cargo: list[dict] = []
            for cargo_consultado, resultado in resultados:
                for vaga in resultado.get("vagas", []):
                    vaga["compatibilidade_curriculo"] = calcular_compatibilidade(
                        vaga,
                        gerado,
                        cargo_consultado,
                    )
                    vagas_com_cargo.append(vaga)

            vagas = remover_vagas_duplicadas(vagas_com_cargo)
            vagas.sort(
                key=lambda vaga: vaga.get("compatibilidade_curriculo", 0),
                reverse=True,
            )
            atualizar_status_candidaturas(vagas)

            fontes = []
            nomes_fontes = sorted(
                {vaga.get("fonte", "Desconhecida") for vaga in vagas}
            )
            for fonte in nomes_fontes:
                total = sum(vaga.get("fonte") == fonte for vaga in vagas)
                fontes.append(
                    {
                        "fonte": fonte,
                        "total_fonte": total,
                        "retornadas": total,
                    }
                )

            st.session_state.vagas = vagas
            st.session_state.fontes = fontes
            st.session_state.filtros = {
                **filtros,
                "cargo": "Currículo: " + ", ".join(cargos),
            }
            st.session_state.pagina = pagina
            st.session_state.erro_busca = ""
            st.session_state.busca_por_curriculo = True
        except Exception as erro:
            st.session_state.erro_busca = (
                "Não foi possível buscar por currículo neste momento."
            )
            logger.exception("Falha interna na busca por currículo")


def renderizar_login() -> None:
    st.markdown(
        """
        <section class="hero">
            <h1>SearchJob Automation</h1>
            <p>Entre para buscar vagas e criar seu currículo inteligente.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.get("mensagem_login"):
        st.success(st.session_state.pop("mensagem_login"))

    desafio_admin = st.session_state.get("desafio_admin_token")
    etapa_admin = st.session_state.get("desafio_admin_etapa")
    if desafio_admin:
        with st.container(border=True):
            st.markdown("### Confirmação adicional")
            if etapa_admin == "configurar":
                configuracao = preparar_2fa_admin_por_desafio(desafio_admin)
                if configuracao.get("status") == "sucesso":
                    st.write(
                        "Cadastre este segredo no Google Authenticator, "
                        "Microsoft Authenticator, Authy ou aplicativo compatível:"
                    )
                    st.image(
                        gerar_qr_2fa(configuracao["uri"]),
                        caption="Escaneie com seu aplicativo autenticador",
                        width=220,
                    )
                    st.code(configuracao["segredo"], language=None)
                    st.caption(
                        "O aplicativo autenticador passará a gerar um novo "
                        "código de seis dígitos aproximadamente a cada 30 segundos."
                    )
                else:
                    st.error(configuracao["mensagem"])
            with st.form("confirmacao-adicional-login"):
                codigo_admin = st.text_input(
                    "Código de 6 dígitos",
                    type="password",
                    max_chars=6,
                )
                confirmar_admin = st.form_submit_button(
                    "Confirmar acesso",
                    type="primary",
                    use_container_width=True,
                )
            if confirmar_admin:
                if etapa_admin == "configurar":
                    resultado_admin = confirmar_2fa_admin_por_desafio(
                        desafio_admin,
                        codigo_admin,
                    )
                else:
                    resultado_admin = concluir_login_admin(
                        desafio_admin,
                        codigo_admin,
                    )
                if resultado_admin.get("status") == "sucesso":
                    st.session_state.session_token = resultado_admin["session_token"]
                    st.session_state.usuario = resultado_admin["usuario"]
                    st.session_state.desafio_admin_token = None
                    st.session_state.desafio_admin_etapa = None
                    st.rerun()
                st.error(resultado_admin["mensagem"])
            if st.button(
                "Cancelar e voltar",
                use_container_width=True,
                key="cancelar-desafio-admin",
            ):
                st.session_state.desafio_admin_token = None
                st.session_state.desafio_admin_etapa = None
                st.rerun()
        return
    magic_token = str(st.query_params.get("magic_token", "")).strip()
    if magic_token:
        with st.container(border=True):
            st.markdown("### Confirmar acesso pelo link")
            codigo_magic = st.text_input(
                "Código 2FA, caso esta seja uma conta administrativa",
                type="password",
                max_chars=6,
                key="codigo-2fa-magic",
            )
            if st.button(
                "Confirmar acesso seguro",
                type="primary",
                use_container_width=True,
            ):
                resultado_magic = consumir_magic_link(magic_token, codigo_magic)
                if resultado_magic.get("status") == "sucesso":
                    st.session_state.session_token = resultado_magic["session_token"]
                    st.session_state.usuario = resultado_magic["usuario"]
                    st.query_params.clear()
                    st.rerun()
                elif resultado_magic.get("status") == "2fa_necessario":
                    st.warning(resultado_magic["mensagem"])
                else:
                    st.error(resultado_magic.get("mensagem", "Link inválido."))

    entrar, cadastrar, link_magico = st.tabs(
        ["Entrar", "Criar conta", "Entrar pelo EMAIL"]
    )

    with entrar:
        with st.form("login-form"):
            email_login = st.text_input(
                "E-mail ou usuário",
                key="email-login",
            )
            senha_login = st.text_input(
                "Senha",
                type="password",
                key="senha-login",
            )
            enviar_login = st.form_submit_button(
                "Entrar",
                type="primary",
                use_container_width=True,
            )
        if enviar_login:
            resultado = autenticar_usuario(
                email_login,
                senha_login,
            )
            if resultado.get("status") == "sucesso":
                st.session_state.session_token = resultado["session_token"]
                st.session_state.usuario = resultado["usuario"]
                st.rerun()
            elif resultado.get("status") in {
                "2fa_configuracao",
                "2fa_necessario",
            }:
                st.session_state.desafio_admin_token = resultado["desafio_token"]
                st.session_state.desafio_admin_etapa = (
                    "configurar"
                    if resultado["status"] == "2fa_configuracao"
                    else "confirmar"
                )
                st.rerun()
            else:
                st.error(resultado.get("mensagem", "Não foi possível entrar."))

    with cadastrar:
        with st.form("cadastro-form"):
            nome_cadastro = st.text_input("Nome completo")
            email_cadastro = st.text_input("E-mail", key="email-cadastro")
            senha_cadastro = st.text_input(
                "Senha com 12+ caracteres, maiúscula, minúscula e número",
                type="password",
                key="senha-cadastro",
            )
            confirmar_senha = st.text_input(
                "Confirme a senha",
                type="password",
            )
            enviar_cadastro = st.form_submit_button(
                "Criar minha conta",
                type="primary",
                use_container_width=True,
            )
        if enviar_cadastro:
            if senha_cadastro != confirmar_senha:
                st.error("As senhas não coincidem.")
            else:
                resultado = criar_usuario(
                    nome_cadastro,
                    email_cadastro,
                    senha_cadastro,
                )
                if resultado.get("status") == "sucesso":
                    login_criado = autenticar_usuario(
                        email_cadastro,
                        senha_cadastro,
                    )
                    if login_criado.get("status") == "sucesso":
                        st.session_state.session_token = login_criado["session_token"]
                        st.session_state.usuario = login_criado["usuario"]
                        solicitar_magic_link(email_cadastro)
                        st.rerun()
                    st.success(
                        "Conta criada. Use a aba Link mágico para verificar o e-mail."
                    )
                else:
                    st.error(
                        resultado.get("mensagem", "Não foi possível criar a conta.")
                    )

    with link_magico:
        st.caption(
            "Enviaremos um link único e temporário para o e-mail cadastrado."
        )
        with st.form("magic-link-form"):
            email_magic = st.text_input(
                "E-mail",
                key="email-magic-link",
            )
            enviar_magic = st.form_submit_button(
                "Enviar link seguro",
                type="primary",
                use_container_width=True,
            )
        if enviar_magic:
            resultado = solicitar_magic_link(email_magic)
            st.success(resultado["mensagem"])


@st.dialog("Meu perfil", width="large")
def renderizar_perfil() -> None:
    usuario = st.session_state.usuario
    resumo = resumo_seguranca_usuario(usuario["id"])
    if not resumo:
        st.error("Não foi possível carregar o perfil.")
        return

    conta, validar, acesso = st.tabs(
        ["Minha conta", "Validar perfil", "Senha e sessões"]
    )

    with conta:
        st.markdown(f"### {resumo['nome']}")
        st.write(f"**E-mail:** {resumo['email']}")
        st.write(
            "**Tipo de conta:** "
            + ("Administrador" if resumo["papel"] == "admin" else "Usuário")
        )
        status_email = (
            "✅ E-mail validado"
            if resumo["email_verificado"]
            else "⚠️ E-mail ainda não validado"
        )
        st.write(status_email)

        with st.form("editar-dados-perfil"):
            novo_nome = st.text_input(
                "Nome de exibição",
                value=resumo["nome"],
                max_chars=120,
            )
            salvar_nome = st.form_submit_button(
                "Salvar dados",
                type="primary",
                use_container_width=True,
            )
        if salvar_nome:
            resultado_nome = atualizar_nome_usuario(usuario["id"], novo_nome)
            if resultado_nome.get("status") == "sucesso":
                st.session_state.usuario["nome"] = resultado_nome["nome"]
                st.success("Perfil atualizado.")
                st.rerun()
            else:
                st.error(resultado_nome["mensagem"])

    with validar:
        st.markdown("### Validar perfil")
        st.write(
            "Enviaremos um código individual para confirmar que você controla "
            f"o endereço **{resumo['email']}**."
        )
        if resumo["email_verificado"]:
            st.success("Seu perfil já está validado.")
        else:
            if st.button(
                "Enviar código de validação",
                type="primary",
                use_container_width=True,
            ):
                resultado_validacao = solicitar_validacao_email(usuario["id"])
                if (
                    resultado_validacao.get("status") == "sucesso"
                    and resultado_validacao.get("enviado")
                ):
                    st.success(resultado_validacao["mensagem"])
                elif resultado_validacao.get("limitado"):
                    st.info(resultado_validacao["mensagem"])
                else:
                    st.error(resultado_validacao["mensagem"])

            st.divider()
            with st.form("confirmar-codigo-validacao"):
                codigo_email = st.text_input(
                    "Código recebido por e-mail",
                    max_chars=6,
                    placeholder="000000",
                    help="O código contém seis números.",
                )
                confirmar_codigo = st.form_submit_button(
                    "Confirmar e validar perfil",
                    type="primary",
                    use_container_width=True,
                )
            if confirmar_codigo:
                resultado_codigo = confirmar_codigo_validacao_email(
                    usuario["id"],
                    codigo_email,
                )
                if resultado_codigo.get("status") == "sucesso":
                    st.session_state.usuario["email_verificado"] = True
                    st.session_state.usuario["papel"] = resultado_codigo.get(
                        "papel",
                        st.session_state.usuario.get("papel", "usuario"),
                    )
                    st.success(resultado_codigo["mensagem"])
                    st.rerun()
                st.error(resultado_codigo["mensagem"])

            st.caption(
                "O código expira em 10 minutos, funciona uma vez e é bloqueado "
                "após cinco tentativas incorretas."
            )

    with acesso:
        st.markdown("### Senha e sessões")
        st.write(f"Sessões ativas: **{resumo['sessoes_ativas']}**")
        if st.button(
            "Encerrar outras sessões",
            use_container_width=True,
        ):
            quantidade = revogar_outras_sessoes(
                usuario["id"],
                st.session_state.session_token,
            )
            st.success(f"{quantidade} outra(s) sessão(ões) encerrada(s).")

        with st.expander("Alterar minha senha"):
            with st.form("alterar-senha-perfil"):
                senha_atual = st.text_input(
                    "Senha atual",
                    type="password",
                )
                nova_senha = st.text_input(
                    "Nova senha",
                    type="password",
                    help="12+ caracteres, com maiúscula, minúscula e número.",
                )
                confirmar_nova_senha = st.text_input(
                    "Confirme a nova senha",
                    type="password",
                )
                salvar_senha = st.form_submit_button(
                    "Alterar senha",
                    type="primary",
                    use_container_width=True,
                )
            if salvar_senha:
                if nova_senha != confirmar_nova_senha:
                    st.error("As novas senhas não coincidem.")
                else:
                    resultado_senha = alterar_senha_usuario(
                        usuario["id"],
                        senha_atual,
                        nova_senha,
                    )
                    if resultado_senha.get("status") == "sucesso":
                        st.session_state.session_token = None
                        st.session_state.usuario = None
                        st.session_state.mensagem_login = (
                            "Senha alterada. Entre novamente com a nova senha."
                        )
                        st.rerun()
                    st.error(resultado_senha["mensagem"])

        if resumo["papel"] == "admin":
            st.divider()
            st.markdown("### Segurança administrativa")
            if resumo["totp_habilitado"]:
                st.success("2FA administrativo está ativo.")
            else:
                st.error("Ative o 2FA antes de usar funções administrativas.")
                configuracao_2fa = preparar_2fa_admin(usuario["id"])
                if configuracao_2fa.get("status") == "sucesso":
                    st.image(
                        gerar_qr_2fa(configuracao_2fa["uri"]),
                        caption="Escaneie com seu aplicativo autenticador",
                        width=220,
                    )
                    st.code(configuracao_2fa["segredo"], language=None)
                    st.caption(
                        "Cadastre o segredo acima em um aplicativo autenticador."
                    )
                    with st.form("confirmar-2fa-admin-perfil"):
                        codigo_confirmacao = st.text_input(
                            "Código de 6 dígitos",
                            type="password",
                            max_chars=6,
                        )
                        confirmar_2fa = st.form_submit_button(
                            "Ativar 2FA",
                            type="primary",
                            use_container_width=True,
                        )
                    if confirmar_2fa:
                        resultado_2fa = confirmar_2fa_admin(
                            usuario["id"],
                            codigo_confirmacao,
                        )
                        if resultado_2fa.get("status") == "sucesso":
                            st.session_state.usuario["totp_habilitado"] = True
                            st.success("2FA ativado.")
                            st.rerun()
                        st.error(resultado_2fa["mensagem"])


def _data_admin(valor: str | None) -> str:
    if not valor:
        return "Nunca"
    try:
        data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        return data.astimezone().strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "Não informado"


def renderizar_painel_admin() -> None:
    usuario_admin = st.session_state.usuario
    if (
        usuario_admin.get("papel") != "admin"
        or not usuario_admin.get("totp_habilitado")
    ):
        st.error("Painel administrativo indisponível.")
        return

    limpar_formulario = st.session_state.pop("admin-limpar-formulario", None)
    if limpar_formulario is not None:
        st.session_state.pop(f"admin-totp-{limpar_formulario}", None)
        st.session_state.pop(f"admin-motivo-{limpar_formulario}", None)

    st.subheader("Gestão de usuários")
    st.caption(
        "Consulte contas, encerre acessos e mantenha um registro auditável "
        "das ações administrativas."
    )

    filtros = st.columns([2, 1])
    busca = filtros[0].text_input(
        "Buscar por nome ou e-mail",
        key="admin-busca-usuario",
        max_chars=120,
    )
    status = filtros[1].selectbox(
        "Status da conta",
        options=["todos", "ativos", "banidos"],
        format_func=lambda valor: {
            "todos": "Todos",
            "ativos": "Ativos",
            "banidos": "Banidos",
        }[valor],
        key="admin-status-usuario",
    )
    filtro_atual = (busca, status)
    if st.session_state.get("admin-filtro-anterior") != filtro_atual:
        st.session_state.pagina_admin = 1
        st.session_state["admin-filtro-anterior"] = filtro_atual

    resultado = listar_usuarios_admin(
        administrador_id=usuario_admin["id"],
        busca=busca,
        status=status,
        pagina=st.session_state.pagina_admin,
        limite=20,
    )
    if resultado.get("status") != "sucesso":
        st.error(resultado.get("mensagem", "Não foi possível carregar os usuários."))
        return

    metricas = resultado["metricas"]
    colunas_metricas = st.columns(5)
    colunas_metricas[0].metric("Cadastrados", metricas["total"])
    colunas_metricas[1].metric("Ativos", metricas["ativos"])
    colunas_metricas[2].metric("Banidos", metricas["banidos"])
    colunas_metricas[3].metric("Verificados", metricas["verificados"])
    colunas_metricas[4].metric("Novos em 7 dias", metricas["novos_7_dias"])

    st.divider()
    usuarios = resultado["usuarios"]
    if not usuarios:
        st.info("Nenhum usuário encontrado com esses filtros.")

    for item in usuarios:
        banido = bool(item["banido_em"])
        with st.container(border=True):
            cabecalho, situacao = st.columns([4, 1])
            with cabecalho:
                st.markdown(f"#### {html.escape(item['nome'])}")
                st.write(f"**E-mail:** {html.escape(item['email'])}")
            with situacao:
                if banido:
                    st.error("BANIDO")
                else:
                    st.success("ATIVO")

            detalhes = st.columns(4)
            detalhes[0].caption(
                "E-mail: "
                + ("validado" if item["email_verificado"] else "não validado")
            )
            detalhes[1].caption(f"Sessões ativas: {item['sessoes_ativas']}")
            detalhes[2].caption(f"Criado: {_data_admin(item['criado_em'])}")
            detalhes[3].caption(
                f"Último acesso: {_data_admin(item['ultimo_acesso'])}"
            )
            if banido:
                st.warning(
                    "Motivo: "
                    f"{html.escape(item['motivo_banimento'] or 'Não informado')} · "
                    f"Desde {_data_admin(item['banido_em'])}"
                )

            rotulo_acao = "Reativar usuário" if banido else "Banir usuário"
            with st.expander(rotulo_acao):
                st.caption(
                    "Por segurança, esta ação exige um código atual do seu "
                    "aplicativo autenticador."
                )
                with st.form(f"admin-banimento-{item['id']}"):
                    motivo = st.text_area(
                        "Motivo administrativo",
                        value=(
                            "Banimento removido após revisão administrativa."
                            if banido
                            else ""
                        ),
                        max_chars=300,
                        height=80,
                        key=f"admin-motivo-{item['id']}",
                    )
                    codigo_2fa = st.text_input(
                        "Código 2FA do administrador",
                        type="password",
                        max_chars=6,
                        key=f"admin-totp-{item['id']}",
                    )
                    confirmar = st.form_submit_button(
                        rotulo_acao,
                        type="primary",
                        use_container_width=True,
                    )
                if confirmar:
                    alteracao = definir_banimento_usuario(
                        administrador_id=usuario_admin["id"],
                        usuario_id=item["id"],
                        banir=not banido,
                        motivo=motivo,
                        codigo_2fa=codigo_2fa,
                    )
                    if alteracao.get("status") == "sucesso":
                        st.success(alteracao["mensagem"])
                        st.session_state["admin-limpar-formulario"] = item["id"]
                        st.rerun()
                    st.error(alteracao["mensagem"])

    total_paginas = max(1, (resultado["total"] + resultado["limite"] - 1) // resultado["limite"])
    anterior, indicador, proxima = st.columns([1, 2, 1])
    with anterior:
        if st.button(
            "← Anterior",
            key="admin-anterior",
            disabled=st.session_state.pagina_admin <= 1,
            use_container_width=True,
        ):
            st.session_state.pagina_admin -= 1
            st.rerun()
    with indicador:
        st.markdown(
            f"<p style='text-align:center;padding-top:.55rem'>"
            f"Página {st.session_state.pagina_admin} de {total_paginas}</p>",
            unsafe_allow_html=True,
        )
    with proxima:
        if st.button(
            "Próxima →",
            key="admin-proxima",
            disabled=st.session_state.pagina_admin >= total_paginas,
            use_container_width=True,
        ):
            st.session_state.pagina_admin += 1
            st.rerun()

    with st.expander("Histórico de ações administrativas"):
        auditoria = resultado.get("auditoria", [])
        if not auditoria:
            st.caption("Nenhuma ação administrativa registrada.")
        for evento in auditoria:
            acao = "Baniu" if evento["acao"] == "banir" else "Reativou"
            st.write(
                f"**{html.escape(evento['administrador_nome'])}** {acao.lower()} "
                f"**{html.escape(evento['usuario_nome'])}** "
                f"({html.escape(evento['usuario_email'])})"
            )
            st.caption(
                f"{_data_admin(evento['criado_em'])} · "
                f"{html.escape(evento['motivo'])}"
            )

    with st.expander("Sugestões para evoluir este painel"):
        st.markdown(
            """
- Relatórios de denúncias e comportamento suspeito.
- Redefinição segura de senha por link temporário, sem o administrador conhecer a senha.
- Exportação dos dados do usuário e exclusão conforme solicitações de privacidade/LGPD.
- Papéis administrativos separados, como suporte, moderador e auditor.
- Alertas de muitos logins, mudanças de localização e tentativas bloqueadas.
- Dashboard de uso: buscas realizadas, candidaturas e fontes mais acessadas.
- Notificação por e-mail quando uma conta for banida ou reativada.
            """
        )


def renderizar_curriculo_gerado(curriculo: dict) -> None:
    st.markdown("### Prévia do currículo")
    st.title(valor_texto(curriculo.get("nome_completo"), "Nome completo"))
    if curriculo.get("titulo_profissional"):
        st.markdown(f"#### {curriculo['titulo_profissional']}")
    contato = " · ".join(
        str(valor)
        for valor in (
            curriculo.get("email"),
            curriculo.get("telefone"),
            curriculo.get("localidade"),
        )
        if valor
    )
    if contato:
        st.caption(contato)

    if curriculo.get("resumo_profissional"):
        st.markdown("#### Resumo profissional")
        st.write(curriculo["resumo_profissional"])

    habilidades = [
        *curriculo.get("habilidades_tecnicas", []),
        *curriculo.get("competencias", []),
    ]
    if habilidades:
        st.markdown("#### Habilidades")
        st.write(" · ".join(habilidades))

    if curriculo.get("experiencias"):
        st.markdown("#### Experiência profissional")
        for experiencia in curriculo["experiencias"]:
            st.markdown(
                f"**{valor_texto(experiencia.get('cargo'), 'Cargo')} — "
                f"{valor_texto(experiencia.get('empresa'), 'Empresa')}**"
            )
            st.caption(
                " · ".join(
                    valor
                    for valor in (
                        experiencia.get("periodo"),
                        experiencia.get("local"),
                    )
                    if valor
                )
            )
            for realizacao in experiencia.get("realizacoes", []):
                st.markdown(f"- {realizacao}")

    if curriculo.get("formacao"):
        st.markdown("#### Formação")
        for formacao in curriculo["formacao"]:
            st.write(
                f"**{valor_texto(formacao.get('curso'), 'Curso')}** — "
                f"{valor_texto(formacao.get('instituicao'), 'Instituição')}"
            )

    st.download_button(
        "Baixar currículo em PDF",
        data=gerar_pdf_curriculo(curriculo),
        file_name="curriculo_profissional.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )


def salvar_vaga(vaga: dict[str, Any]) -> None:
    resultado = salvar_candidatura(
        fonte=valor_texto(vaga.get("fonte"), "Desconhecida"),
        id_externo=valor_texto(
            vaga.get("id_externo"),
            vaga.get("url_candidatura", ""),
        ),
        titulo=valor_texto(vaga.get("titulo"), "Título não informado"),
        empresa=valor_texto(vaga.get("empresa"), "Empresa não informada"),
        local=valor_texto(vaga.get("local"), "Local não informado"),
        url_candidatura=valor_texto(vaga.get("url_candidatura"), ""),
    )
    if resultado.get("status") == "sucesso":
        st.toast("Candidatura salva.", icon="✅")
        atualizar_status_candidaturas(st.session_state.vagas)
        st.rerun()
    else:
        st.error(resultado.get("mensagem", "Não foi possível salvar a candidatura."))


def remover_vaga(vaga: dict[str, Any]) -> None:
    resultado = remover_candidatura(
        fonte=valor_texto(vaga.get("fonte"), "Desconhecida"),
        id_externo=valor_texto(
            vaga.get("id_externo"),
            vaga.get("url_candidatura", ""),
        ),
        url_candidatura=valor_texto(vaga.get("url_candidatura"), ""),
    )
    if resultado.get("status") == "sucesso" and resultado.get("removida"):
        st.toast("Candidatura removida.", icon="🗑️")
        atualizar_status_candidaturas(st.session_state.vagas)
        st.rerun()
    elif resultado.get("status") == "sucesso":
        st.warning("Essa candidatura já havia sido removida.")
    else:
        st.error(resultado.get("mensagem", "Não foi possível remover a candidatura."))


def renderizar_vaga(vaga: dict[str, Any], contexto: str = "busca") -> None:
    titulo = valor_texto(vaga.get("titulo"), "Título não informado")
    empresa = valor_texto(vaga.get("empresa"), "Empresa não informada")
    local = valor_texto(vaga.get("local"), "Local não informado")
    modalidade = valor_texto(vaga.get("modalidade"), "Não informada")
    fonte = valor_texto(vaga.get("fonte"), "Desconhecida")
    url = valor_texto(vaga.get("url_candidatura"), "")
    data = formatar_data(vaga.get("data_publicacao") or vaga.get("candidatado_em"))
    ja_candidatado = bool(vaga.get("ja_candidatado", contexto == "historico"))
    chave = identificador_widget(vaga)
    local_seguro = html.escape(local)
    modalidade_segura = html.escape(modalidade)

    with st.container(border=True):
        st.markdown(
            '<span class="job-card-marker" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        coluna_texto, coluna_acoes = st.columns([4, 1.35], gap="large")
        with coluna_texto:
            st.subheader(titulo)
            st.write(f"**{empresa}**")
            st.markdown(
                f'<p class="job-meta">📍 {local_seguro} &nbsp; • &nbsp; '
                f"{modalidade_segura}</p>",
                unsafe_allow_html=True,
            )
            rotulo_data = "Candidatado em" if contexto == "historico" else "Publicada em"
            if data:
                st.caption(f"{rotulo_data}: {data}")

            badges = [fonte]
            if vaga.get("compatibilidade_curriculo"):
                badges.append(
                    f"{vaga['compatibilidade_curriculo']}% compatível"
                )
            if vaga.get("candidatura_simplificada"):
                badges.append("Candidatura simplificada")
            if ja_candidatado:
                badges.append("Já candidatado")
            st.markdown(
                '<div class="job-badges">'
                + "".join(f"<span>{html.escape(badge)}</span>" for badge in badges)
                + "</div>",
                unsafe_allow_html=True,
            )

        with coluna_acoes:
            if url.startswith(("http://", "https://")):
                st.link_button(
                    "Candidatar-se ↗",
                    url,
                    use_container_width=True,
                )

            if contexto == "busca" and not ja_candidatado:
                if st.button(
                    "Já me candidatei",
                    key=f"salvar-{chave}",
                    use_container_width=True,
                ):
                    salvar_vaga(vaga)
            else:
                if st.button(
                    "Desfazer",
                    key=f"remover-{contexto}-{chave}",
                    use_container_width=True,
                    type="secondary",
                ):
                    remover_vaga(vaga)


def inicializar_estado() -> None:
    valores = {
        "vagas": [],
        "fontes": [],
        "filtros": None,
        "pagina": 1,
        "pagina_historico": 1,
        "pagina_admin": 1,
        "erro_busca": "",
        "busca_por_curriculo": False,
        "usuario": None,
        "session_token": None,
        "desafio_admin_token": None,
        "desafio_admin_etapa": None,
    }
    for chave, valor in valores.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


preparar_banco()
inicializar_estado()

if st.session_state.session_token:
    usuario_validado = validar_sessao(st.session_state.session_token)
    if usuario_validado:
        st.session_state.usuario = usuario_validado
    else:
        st.session_state.session_token = None
        st.session_state.usuario = None

if not st.session_state.usuario:
    renderizar_login()
    st.stop()

st.markdown(
    """
    <section class="hero">
        <h1>SearchJob Automation</h1>
        <p>Busque vagas em vários portais e acompanhe suas candidaturas em um só lugar.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

usuario_coluna, perfil_coluna, sair_coluna = st.columns([5, 1, 1])
with usuario_coluna:
    st.caption(
        f"Conectado como **{st.session_state.usuario['nome']}** "
        f"({st.session_state.usuario['email']})"
    )
with perfil_coluna:
    if st.button("Perfil", use_container_width=True):
        renderizar_perfil()
with sair_coluna:
    if st.button("Sair", use_container_width=True):
        revogar_sessao(st.session_state.session_token)
        st.session_state.session_token = None
        st.session_state.usuario = None
        st.session_state.vagas = []
        st.session_state.filtros = None
        st.rerun()

rotulos_abas = [
    "🔎 Buscar vagas",
    "✨ Currículo Inteligente",
    "📋 Minhas candidaturas",
]
admin_disponivel = (
    st.session_state.usuario.get("papel") == "admin"
    and st.session_state.usuario.get("totp_habilitado")
)
if admin_disponivel:
    rotulos_abas.append("🛡️ Administração")

abas_principais = st.tabs(rotulos_abas)
aba_busca, aba_curriculo, aba_historico = abas_principais[:3]
aba_admin = abas_principais[3] if admin_disponivel else None

with aba_busca:
    curriculo_usuario = obter_curriculo(st.session_state.usuario["id"])
    dados_busca_curriculo = (curriculo_usuario or {}).get("dados") or {}
    primeiro_cargo_curriculo = next(
        (
            cargo.strip()
            for cargo in re.split(
                r"[,;\n]",
                str(dados_busca_curriculo.get("cargos_desejados", "")),
            )
            if cargo.strip()
        ),
        "Auxiliar Administrativo",
    )

    with st.form("formulario_busca"):
        linha_1 = st.columns([2, 1.4, 0.6])
        cargo = linha_1[0].text_input("Cargo", value=primeiro_cargo_curriculo)
        cidade = linha_1[1].text_input(
            "Cidade",
            value=dados_busca_curriculo.get("cidade", "Guarulhos"),
        )
        estado = linha_1[2].text_input(
            "UF",
            value=dados_busca_curriculo.get("estado", "SP"),
            max_chars=2,
        )

        linha_2 = st.columns([1.1, 1.35, 0.8, 1, 1.45])
        modalidade = linha_2[0].selectbox(
            "Modalidade",
            ["Presencial", "Híbrido", "Remoto"],
        )
        periodo = linha_2[1].selectbox(
            "Data de publicação",
            [
                ("Qualquer data", None),
                ("Últimas 24 horas", 1),
                ("Últimas 72 horas", 3),
                ("Últimos 7 dias", 7),
                ("Últimos 15 dias", 15),
                ("Últimos 30 dias", 30),
            ],
            format_func=lambda opcao: opcao[0],
        )
        incluir_pcd = linha_2[2].checkbox("Sou PCD", value=False)
        buscar = linha_2[3].form_submit_button(
            "Buscar vagas",
            type="primary",
            use_container_width=True,
        )
        buscar_por_curriculo = linha_2[4].form_submit_button(
            "Procurar pelo currículo",
            use_container_width=True,
        )

    if buscar or buscar_por_curriculo:
        filtros_busca = {
            "cargo": cargo.strip(),
            "cidade": cidade.strip(),
            "estado": estado.strip().upper(),
            "modalidade": modalidade,
            "max_dias": periodo[1],
            "incluir_pcd": incluir_pcd,
        }
        campos_obrigatorios = [
            filtros_busca["cidade"],
            filtros_busca["estado"],
        ]
        if buscar:
            campos_obrigatorios.append(filtros_busca["cargo"])

        if not all(campos_obrigatorios):
            st.warning("Preencha cargo, cidade e UF para buscar.")
        elif buscar_por_curriculo:
            if not curriculo_usuario:
                st.warning(
                    "Crie seu currículo na aba Currículo Inteligente antes "
                    "de usar esta busca."
                )
            else:
                executar_busca_por_curriculo(
                    filtros_busca,
                    1,
                    curriculo_usuario,
                )
        else:
            st.session_state.busca_por_curriculo = False
            executar_busca(filtros_busca, 1)

    if st.session_state.erro_busca:
        st.error(st.session_state.erro_busca)

    vagas_atuais = st.session_state.vagas
    if st.session_state.filtros:
        atualizar_status_candidaturas(vagas_atuais)
        total = len(vagas_atuais)
        st.markdown(
            f"#### Página {st.session_state.pagina} · {total} "
            f"{'vaga exibida' if total == 1 else 'vagas exibidas'}"
        )
        if st.session_state.busca_por_curriculo:
            st.caption(
                "Resultados combinados e ordenados pelos cargos e competências "
                "do seu currículo."
            )

        if st.session_state.fontes:
            chips = "".join(
                (
                    f'<span class="fonte-chip">'
                    f'{html.escape(valor_texto(item.get("fonte"), "Fonte"))}: '
                    f'{html.escape(str(item.get("retornadas", 0)))}</span>'
                )
                for item in st.session_state.fontes
            )
            st.markdown(chips, unsafe_allow_html=True)

        if not vagas_atuais:
            st.info("Nenhuma vaga encontrada nesta página com os filtros escolhidos.")

        for vaga_atual in vagas_atuais:
            renderizar_vaga(vaga_atual)

        anterior, indicador, proxima = st.columns([1, 2, 1])
        with anterior:
            if st.button(
                "← Página anterior",
                disabled=st.session_state.pagina <= 1,
                use_container_width=True,
            ):
                if st.session_state.busca_por_curriculo and curriculo_usuario:
                    executar_busca_por_curriculo(
                        st.session_state.filtros,
                        st.session_state.pagina - 1,
                        curriculo_usuario,
                    )
                else:
                    executar_busca(
                        st.session_state.filtros,
                        st.session_state.pagina - 1,
                    )
                st.rerun()
        with indicador:
            st.markdown(
                f"<p style='text-align:center;padding-top:.55rem'>"
                f"Página {st.session_state.pagina}</p>",
                unsafe_allow_html=True,
            )
        with proxima:
            if st.button(
                "Próxima página →",
                disabled=not vagas_atuais,
                use_container_width=True,
            ):
                if st.session_state.busca_por_curriculo and curriculo_usuario:
                    executar_busca_por_curriculo(
                        st.session_state.filtros,
                        st.session_state.pagina + 1,
                        curriculo_usuario,
                    )
                else:
                    executar_busca(
                        st.session_state.filtros,
                        st.session_state.pagina + 1,
                    )
                st.rerun()
    else:
        st.info("Preencha os filtros acima para começar.")

with aba_curriculo:
    st.subheader("Currículo Inteligente")
    st.write(
        "Preencha suas informações reais. A IA organizará o conteúdo para ATS "
        "com base nas suas informações e experiências."
    )

    curriculo_salvo = obter_curriculo(st.session_state.usuario["id"])
    dados_atuais = (curriculo_salvo or {}).get("dados") or {}

    with st.form("curriculo-form"):
        st.markdown("#### Dados pessoais")
        pessoais_1 = st.columns(2)
        nome_completo = pessoais_1[0].text_input(
            "Nome completo",
            value=dados_atuais.get(
                "nome_completo",
                st.session_state.usuario["nome"],
            ),
        )
        email_curriculo = pessoais_1[1].text_input(
            "E-mail profissional",
            value=dados_atuais.get(
                "email",
                st.session_state.usuario["email"],
            ),
        )
        pessoais_2 = st.columns(3)
        telefone = pessoais_2[0].text_input(
            "Telefone",
            value=dados_atuais.get("telefone", ""),
        )
        cidade_curriculo = pessoais_2[1].text_input(
            "Cidade",
            value=dados_atuais.get("cidade", ""),
        )
        estado_curriculo = pessoais_2[2].text_input(
            "UF",
            value=dados_atuais.get("estado", ""),
            max_chars=2,
        )
        links = st.columns(2)
        linkedin = links[0].text_input(
            "LinkedIn",
            value=dados_atuais.get("linkedin", ""),
        )
        portfolio = links[1].text_input(
            "Portfólio ou GitHub",
            value=dados_atuais.get("portfolio", ""),
        )

        st.markdown("#### Objetivo e competências")
        cargos_desejados = st.text_input(
            "Cargos desejados",
            value=dados_atuais.get("cargos_desejados", ""),
            help="Separe por vírgulas. Ex.: Auxiliar Administrativo, Assistente Financeiro",
        )
        resumo_base = st.text_area(
            "Resumo sobre você",
            value=dados_atuais.get("resumo_base", ""),
            height=110,
            help="Conte sua área, tempo de experiência, pontos fortes e objetivo.",
        )
        habilidades = st.text_area(
            "Habilidades técnicas e comportamentais",
            value=dados_atuais.get("habilidades", ""),
            height=100,
            help="Ex.: Excel, atendimento, organização, Python, comunicação.",
        )

        st.markdown("#### Experiência profissional")
        experiencias = st.text_area(
            "Experiências",
            value=dados_atuais.get("experiencias", ""),
            height=190,
            help=(
                "Informe cargo, empresa, período e atividades/resultados. "
                "Separe cada experiência com uma linha em branco."
            ),
        )

        st.markdown("#### Formação e desenvolvimento")
        formacao = st.text_area(
            "Formação acadêmica",
            value=dados_atuais.get("formacao", ""),
            height=120,
            help="Curso, instituição, período e situação.",
        )
        cursos = st.text_area(
            "Cursos e certificações",
            value=dados_atuais.get("cursos", ""),
            height=100,
        )
        idiomas = st.text_area(
            "Idiomas",
            value=dados_atuais.get("idiomas", ""),
            height=80,
        )
        projetos = st.text_area(
            "Projetos, trabalho voluntário ou informações complementares",
            value=dados_atuais.get("projetos", ""),
            height=110,
        )

        acoes_curriculo = st.columns(2)
        salvar_rascunho = acoes_curriculo[0].form_submit_button(
            "Salvar informações",
            use_container_width=True,
        )
        gerar_com_ia = acoes_curriculo[1].form_submit_button(
            "Gerar currículo com IA",
            type="primary",
            use_container_width=True,
        )

    if salvar_rascunho or gerar_com_ia:
        dados_formulario = {
            "nome_completo": nome_completo.strip(),
            "email": email_curriculo.strip(),
            "telefone": telefone.strip(),
            "cidade": cidade_curriculo.strip(),
            "estado": estado_curriculo.strip().upper(),
            "linkedin": linkedin.strip(),
            "portfolio": portfolio.strip(),
            "cargos_desejados": cargos_desejados.strip(),
            "resumo_base": resumo_base.strip(),
            "habilidades": habilidades.strip(),
            "experiencias": experiencias.strip(),
            "formacao": formacao.strip(),
            "cursos": cursos.strip(),
            "idiomas": idiomas.strip(),
            "projetos": projetos.strip(),
        }

        if not nome_completo.strip() or not email_curriculo.strip():
            st.error("Nome e e-mail são obrigatórios.")
        elif gerar_com_ia:
            if not gemini_configurado():
                salvar_curriculo(
                    st.session_state.usuario["id"],
                    dados_formulario,
                )
                st.error(
                    "As informações foram salvas, mas falta configurar uma nova "
                    "GEMINI_API_KEY nos Secrets."
                )
            else:
                with st.spinner(
                    "A IA está organizando e otimizando seu currículo..."
                ):
                    try:
                        curriculo_gerado = gerar_curriculo_com_ia(
                            dados_formulario
                        )
                        resultado_salvar = salvar_curriculo(
                            st.session_state.usuario["id"],
                            dados_formulario,
                            curriculo_gerado,
                        )
                        if resultado_salvar.get("status") != "sucesso":
                            st.error(resultado_salvar.get("mensagem"))
                        else:
                            st.success("Currículo criado e salvo na sua conta.")
                            st.rerun()
                    except Exception as erro:
                        logger.exception("Falha interna ao gerar currículo com Gemini")
                        st.error(
                            "Não foi possível gerar o currículo agora. "
                            "Tente novamente em alguns instantes."
                        )
        else:
            resultado_salvar = salvar_curriculo(
                st.session_state.usuario["id"],
                dados_formulario,
            )
            if resultado_salvar.get("status") == "sucesso":
                st.success("Informações salvas.")
                st.rerun()
            else:
                st.error(resultado_salvar.get("mensagem"))

    curriculo_salvo = obter_curriculo(st.session_state.usuario["id"])
    if curriculo_salvo and curriculo_salvo.get("gerado"):
        st.divider()
        renderizar_curriculo_gerado(curriculo_salvo["gerado"])
    elif curriculo_salvo:
        st.info(
            "Seu rascunho está salvo. Configure o Gemini e clique em "
            "“Gerar currículo com Gemini” para criar a versão final e o PDF."
        )

with aba_historico:
    st.subheader("Minhas candidaturas")
    st.caption(
        "Aqui será possível ver as vagas em que se candidatou."
    )

    historico = listar_candidaturas(
        pagina=st.session_state.pagina_historico,
        limite=20,
        status="candidatado",
    )

    if historico.get("status") != "sucesso":
        st.error("Não foi possível carregar o histórico.")
    else:
        candidaturas = historico.get("candidaturas", [])
        total_historico = historico.get("total", 0)
        st.write(f"**{total_historico} candidatura(s) salva(s)**")

        if not candidaturas:
            st.info("Você ainda não marcou nenhuma vaga como candidatado.")

        for candidatura in candidaturas:
            renderizar_vaga(candidatura, contexto="historico")

        total_paginas = max(1, (total_historico + 19) // 20)
        historico_anterior, historico_indicador, historico_proxima = st.columns(
            [1, 2, 1]
        )
        with historico_anterior:
            if st.button(
                "← Anterior",
                key="historico-anterior",
                disabled=st.session_state.pagina_historico <= 1,
                use_container_width=True,
            ):
                st.session_state.pagina_historico -= 1
                st.rerun()
        with historico_indicador:
            st.markdown(
                f"<p style='text-align:center;padding-top:.55rem'>"
                f"Página {st.session_state.pagina_historico} de {total_paginas}</p>",
                unsafe_allow_html=True,
            )
        with historico_proxima:
            if st.button(
                "Próxima →",
                key="historico-proxima",
                disabled=st.session_state.pagina_historico >= total_paginas,
                use_container_width=True,
            ):
                st.session_state.pagina_historico += 1
                st.rerun()

if aba_admin is not None:
    with aba_admin:
        renderizar_painel_admin()
