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
from inspect import signature
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
from app.services.auto_application_service import (  # noqa: E402
    atualizar_item_campanha,
    confirmar_login_plataforma,
    fontes_disponiveis_candidatura,
    listar_campanhas_candidatura,
    listar_itens_campanha,
    listar_logins_campanha,
    plataforma_exige_login_central,
    preparar_campanha_candidatura,
    url_login_plataforma,
)
from app.services.gemini_resume_service import (  # noqa: E402
    gemini_configurado,
    gerar_curriculo_com_ia,
)
from app.admin_compat import (  # noqa: E402
    definir_banimento_usuario,
    listar_usuarios_admin,
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
            color-scheme: light;
        }
        .stApp {
            color: #163247;
            background:
                radial-gradient(circle at 8% 4%, rgba(103, 232, 249, .28), transparent 26rem),
                radial-gradient(circle at 94% 16%, rgba(186, 230, 253, .48), transparent 30rem),
                linear-gradient(150deg, #ffffff 0%, #f5fcff 48%, #ecfaff 100%);
            background-attachment: fixed;
        }
        [data-testid="stHeader"] {
            background: rgba(247, 252, 255, .88);
            backdrop-filter: blur(12px);
        }
        .block-container {
            max-width: 1160px;
            padding-top: 2.35rem;
            padding-bottom: 4rem;
        }
        .hero {
            position: relative;
            overflow: hidden;
            padding: 2.35rem 2.5rem;
            border-radius: 1.5rem;
            color: #123047;
            background:
                radial-gradient(circle at 92% 8%, rgba(34, 211, 238, .3), transparent 20rem),
                radial-gradient(circle at 72% 100%, rgba(125, 211, 252, .25), transparent 18rem),
                linear-gradient(125deg, rgba(255, 255, 255, .98), rgba(224, 247, 255, .98));
            border: 1px solid rgba(6, 182, 212, .3);
            box-shadow:
                0 0 30px rgba(34, 211, 238, .13),
                0 18px 50px rgba(14, 116, 144, .11);
            margin-bottom: 1.55rem;
        }
        .hero::after {
            content: "";
            position: absolute;
            width: 9rem;
            height: 9rem;
            right: 2.2rem;
            top: 50%;
            transform: translateY(-50%);
            border-radius: 50%;
            background:
                radial-gradient(circle, rgba(255,255,255,.9) 0 7%, transparent 8%),
                radial-gradient(circle, rgba(34,211,238,.24), rgba(125,211,252,.08) 58%, transparent 60%);
            box-shadow: 0 0 42px rgba(34, 211, 238, .2);
            pointer-events: none;
        }
        .hero > * {
            position: relative;
            z-index: 1;
        }
        .hero-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            margin-bottom: .75rem;
            padding: .34rem .72rem;
            border-radius: 999px;
            color: #0e7490;
            background: rgba(207, 250, 254, .78);
            border: 1px solid rgba(6, 182, 212, .22);
            font-size: .79rem;
            font-weight: 800;
            letter-spacing: .04em;
            text-transform: uppercase;
        }
        .hero h1 {
            margin: 0;
            max-width: 760px;
            font-size: clamp(2rem, 4vw, 2.75rem);
            line-height: 1.08;
            letter-spacing: -.035em;
            color: #123047;
        }
        .hero p {
            max-width: 720px;
            margin: .8rem 0 0;
            color: #476579;
            font-size: 1.05rem;
            line-height: 1.65;
        }
        .turbo-callout {
            position: relative;
            overflow: hidden;
            margin: .25rem 0 1.2rem;
            padding: 1.25rem 1.4rem;
            border-radius: 1.15rem;
            color: #164e63;
            background:
                radial-gradient(circle at 96% 10%, rgba(34, 211, 238, .28), transparent 10rem),
                linear-gradient(125deg, #ecfeff, #e0f7ff);
            border: 1px solid rgba(6, 182, 212, .32);
            box-shadow: 0 10px 28px rgba(14, 116, 144, .09);
        }
        .turbo-callout h3 {
            margin: 0 0 .3rem;
            color: #075d75;
            font-size: 1.2rem;
        }
        .turbo-callout p {
            max-width: 780px;
            margin: 0;
            color: #527184;
            line-height: 1.55;
        }
        .turbo-status {
            display: inline-block;
            margin: 0 .3rem .25rem 0;
            padding: .24rem .6rem;
            border: 1px solid #9fe5ef;
            border-radius: 999px;
            color: #0e7490;
            background: #e2faff;
            font-size: .76rem;
            font-weight: 800;
        }
        .turbo-login-ok {
            color: #166534;
            background: #ecfdf5;
            border-color: #a7f3d0;
        }
        .turbo-login-wait {
            color: #9a5b07;
            background: #fffbeb;
            border-color: #fde68a;
        }
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 1.4rem;
            border-bottom: 1px solid #cfeaf3;
        }
        [data-testid="stTabs"] button[role="tab"] {
            color: #587486;
            font-weight: 700;
        }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            color: #0787a4;
        }
        .fonte-chip {
            display: inline-block;
            padding: .28rem .65rem;
            margin: 0 .35rem .35rem 0;
            border-radius: 999px;
            background: #e2f9ff;
            border: 1px solid #9ee8f5;
            color: #0e7490;
            font-size: .78rem;
            font-weight: 600;
            box-shadow: 0 0 12px rgba(34, 211, 238, .1);
        }
        .job-meta {
            color: #527184;
            margin: .15rem 0 .65rem;
        }
        .job-badges span {
            display: inline-block;
            padding: .2rem .55rem;
            margin: 0 .3rem .25rem 0;
            border-radius: 999px;
            background: #e0f7ff;
            border: 1px solid #a5e6f2;
            color: #0c7188;
            font-size: .75rem;
        }
        div[data-testid="stForm"] {
            background:
                linear-gradient(145deg, rgba(255, 255, 255, .98), rgba(239, 251, 255, .98));
            border: 1px solid rgba(6, 182, 212, .24);
            border-radius: 1.2rem;
            padding: 1.35rem;
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, .9),
                0 12px 36px rgba(14, 116, 144, .09);
        }
        div[data-testid="stForm"] label,
        div[data-testid="stForm"] [data-testid="stWidgetLabel"] p,
        div[data-testid="stForm"] [data-testid="stCheckbox"] p {
            color: #294b60 !important;
            font-weight: 650;
            opacity: 1 !important;
        }
        div[data-testid="stForm"] [data-baseweb="input"],
        div[data-testid="stForm"] [data-baseweb="select"] > div {
            color: #163247;
            background: #ffffff;
            border-color: #b8dde8;
            box-shadow: inset 0 1px 3px rgba(14, 116, 144, .04);
        }
        div[data-testid="stForm"] input,
        div[data-testid="stForm"] [data-baseweb="select"] span {
            color: #163247 !important;
            -webkit-text-fill-color: #163247 !important;
        }
        div[data-testid="stForm"] [data-baseweb="input"]:focus-within,
        div[data-testid="stForm"] [data-baseweb="select"] > div:focus-within {
            border-color: #06b6d4;
            box-shadow: 0 0 0 2px rgba(6, 182, 212, .16), 0 0 18px rgba(34, 211, 238, .12);
        }
        div[data-testid="stForm"] [data-testid="stCheckbox"] {
            min-height: 2.9rem;
            display: flex;
            align-items: center;
        }
        div[data-testid="stForm"] button[kind="primaryFormSubmit"] {
            color: #083344;
            font-weight: 800;
            border: 1px solid #62d9eb;
            border-radius: .7rem;
            background: linear-gradient(110deg, #9beaf5, #7dd3fc);
            box-shadow: 0 8px 22px rgba(14, 165, 233, .17);
            transition: transform .18s ease, box-shadow .18s ease;
        }
        div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover {
            color: #083344;
            border-color: #22d3ee;
            transform: translateY(-2px);
            box-shadow: 0 0 24px rgba(34, 211, 238, .32), 0 10px 26px rgba(14, 116, 144, .15);
        }
        .stButton > button,
        .stLinkButton > a,
        [data-testid="stDownloadButton"] > button {
            border-radius: .7rem;
            border-color: #b4dce7;
            color: #155e75;
            background: rgba(255, 255, 255, .9);
            font-weight: 700;
            transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
        }
        .stButton > button:hover,
        .stLinkButton > a:hover,
        [data-testid="stDownloadButton"] > button:hover {
            color: #0e7490;
            border-color: #67dcea;
            transform: translateY(-1px);
            box-shadow: 0 8px 22px rgba(14, 116, 144, .12);
        }
        .stButton > button[kind="primary"],
        .stLinkButton > a[kind="primary"] {
            color: #083344;
            border-color: #62d9eb;
            background: linear-gradient(110deg, #9beaf5, #7dd3fc);
            box-shadow: 0 8px 22px rgba(14, 165, 233, .17);
        }
        .stButton > button[kind="primary"]:hover,
        .stLinkButton > a[kind="primary"]:hover {
            color: #083344;
            border-color: #22d3ee;
            box-shadow: 0 0 24px rgba(34, 211, 238, .3);
        }
        [data-testid="stMetric"] {
            padding: .8rem;
            border: 1px solid #c9eaf2;
            border-radius: .9rem;
            background: rgba(255, 255, 255, .75);
        }
        .job-card-marker {
            display: none;
        }
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .job-card-marker
        ) {
            position: relative;
            z-index: 1;
            color: #163247;
            background:
                radial-gradient(circle at 100% 0%, rgba(103, 232, 249, .3), transparent 15rem),
                linear-gradient(135deg, rgba(239, 252, 255, .99), rgba(218, 246, 255, .98));
            border: 1px solid rgba(6, 182, 212, .38) !important;
            border-radius: 1.15rem !important;
            box-shadow:
                0 0 18px rgba(34, 211, 238, .1),
                0 12px 30px rgba(14, 116, 144, .1);
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
            transform: translateY(-3px) scale(1.018);
            border-color: rgba(6, 182, 212, .88) !important;
            box-shadow:
                0 0 18px rgba(34, 211, 238, .3),
                0 0 36px rgba(56, 189, 248, .2),
                0 20px 42px rgba(14, 116, 144, .16);
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
            color: #163247;
        }
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .job-card-marker
        ) h3 {
            color: #075d75;
        }
        [data-testid="stAlert"] {
            color: #164e63;
            background: rgba(224, 247, 255, .82);
            border: 1px solid rgba(14, 165, 233, .24);
            border-radius: .85rem;
        }
        [data-testid="stCaptionContainer"] p {
            color: #658294;
        }
        [data-testid="stExpander"] {
            border-color: #c9e8f1;
            border-radius: 1rem;
            background: rgba(255, 255, 255, .94);
        }
        [data-testid="stDialog"] [role="dialog"] {
            color: #e6faff;
            border: 1px solid rgba(103, 232, 249, .62);
            border-radius: 1.35rem;
            background:
                radial-gradient(circle at 95% 4%, rgba(34, 211, 238, .22), transparent 18rem),
                linear-gradient(145deg, #082f49 0%, #0c4a6e 55%, #083344 100%);
            box-shadow:
                0 0 36px rgba(34, 211, 238, .22),
                0 28px 80px rgba(2, 20, 32, .42);
        }
        [data-testid="stDialog"] h1,
        [data-testid="stDialog"] h2,
        [data-testid="stDialog"] h3,
        [data-testid="stDialog"] h4 {
            color: #ecfeff;
        }
        [data-testid="stDialog"] .turbo-callout {
            color: #dffbff;
            background:
                radial-gradient(circle at 96% 10%, rgba(103, 232, 249, .2), transparent 11rem),
                linear-gradient(125deg, rgba(8, 47, 73, .92), rgba(14, 116, 144, .72));
            border-color: rgba(103, 232, 249, .5);
            box-shadow: 0 12px 30px rgba(2, 20, 32, .22);
        }
        [data-testid="stDialog"] .turbo-callout h3 {
            color: #ecfeff !important;
        }
        [data-testid="stDialog"] .turbo-callout p {
            color: #c9f4fb !important;
        }
        [data-testid="stDialog"] [data-testid="stCaptionContainer"] p,
        [data-testid="stDialog"] > div p {
            color: #c9edf6;
        }
        [data-testid="stDialog"] div[data-testid="stForm"] {
            background: linear-gradient(145deg, #f7fdff, #e7f8fd);
            border-color: rgba(103, 232, 249, .56);
        }
        [data-testid="stDialog"] div[data-testid="stForm"] label,
        [data-testid="stDialog"] div[data-testid="stForm"]
            [data-testid="stWidgetLabel"] p,
        [data-testid="stDialog"] div[data-testid="stForm"]
            [data-testid="stCheckbox"] p {
            color: #294b60 !important;
        }
        [data-testid="stDialog"] [data-testid="stMetric"] {
            color: #dffbff;
            background: rgba(8, 47, 73, .76);
            border-color: rgba(103, 232, 249, .45);
        }
        [data-testid="stDialog"] [data-testid="stMetric"] p,
        [data-testid="stDialog"] [data-testid="stMetricValue"] {
            color: #dffbff !important;
        }
        [data-testid="stDialog"] [data-testid="stDataFrame"] {
            overflow: hidden;
            border: 1px solid rgba(103, 232, 249, .42);
            border-radius: .9rem;
            background: #f5fcff;
        }
        hr {
            border-color: #d9edf3 !important;
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
            [data-testid="stHorizontalBlock"] {
                flex-direction: column;
            }
            [data-testid="stHorizontalBlock"] > div {
                width: 100% !important;
                flex: 1 1 100% !important;
            }
            .hero {
                padding: 1.45rem;
            }
            .hero::after {
                width: 6rem;
                height: 6rem;
                right: -1.5rem;
                top: 15%;
                opacity: .55;
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
            <span class="hero-eyebrow">Seu próximo passo começa aqui</span>
            <h1>Uma busca de emprego mais leve e mais inteligente.</h1>
            <p>
                Encontre oportunidades que combinam com você, organize suas
                candidaturas e crie um currículo forte — tudo no mesmo lugar.
            </p>
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


def _executar_funcao_admin_segura(funcao, **argumentos) -> dict[str, Any]:
    """Impede que um módulo antigo em cache derrube o painel após o deploy."""
    try:
        if "session_token" not in signature(funcao).parameters:
            return {
                "status": "erro",
                "mensagem": (
                    "O painel administrativo foi atualizado. Reinicie o "
                    "aplicativo para carregar a versão segura."
                ),
            }
        return funcao(**argumentos)
    except TypeError:
        logger.exception("Versões administrativas incompatíveis durante o deploy")
        return {
            "status": "erro",
            "mensagem": (
                "O painel administrativo está sendo atualizado. Reinicie o "
                "aplicativo e tente novamente."
            ),
        }


def renderizar_painel_admin() -> None:
    usuario_admin = st.session_state.usuario
    sessao_admin = validar_sessao(st.session_state.session_token)
    if (
        not sessao_admin
        or sessao_admin.get("id") != usuario_admin.get("id")
        or sessao_admin.get("papel") != "admin"
        or not sessao_admin.get("totp_habilitado")
        or usuario_admin.get("papel") != "admin"
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

    resultado = _executar_funcao_admin_segura(
        listar_usuarios_admin,
        administrador_id=usuario_admin["id"],
        busca=busca,
        status=status,
        pagina=st.session_state.pagina_admin,
        limite=20,
        session_token=st.session_state.session_token,
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
                    alteracao = _executar_funcao_admin_segura(
                        definir_banimento_usuario,
                        administrador_id=usuario_admin["id"],
                        usuario_id=item["id"],
                        banir=not banido,
                        motivo=motivo,
                        codigo_2fa=codigo_2fa,
                        session_token=st.session_state.session_token,
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


def _rotulo_status_campanha(status: str) -> str:
    return {
        "aguardando_login": "Aguardando login",
        "pronta": "Pronta",
        "pausada": "Pausada",
        "concluida": "Concluída",
    }.get(status, "Em preparação")


def _atualizar_dialog_turbo() -> None:
    try:
        st.rerun(scope="fragment")
    except (TypeError, ValueError):
        st.rerun()


@st.dialog("Candidatura automática", width="large")
def renderizar_painel_candidatura_turbo() -> None:
    usuario_id = st.session_state.usuario["id"]
    plataformas_disponiveis = fontes_disponiveis_candidatura()

    st.markdown(
        """
        <div class="turbo-callout">
            <h3>⚡ Candidatura Turbo</h3>
            <p>
                Escolha o seu objetivo e as plataformas. O SearchJob encontra,
                organiza e acompanha as vagas. O envio final permanece sob sua
                confirmação no site da empresa, sem guardar senhas externas.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    curriculo = obter_curriculo(usuario_id)
    if not curriculo or not curriculo.get("gerado"):
        st.warning(
            "Crie a versão final do seu currículo na aba Currículo Inteligente "
            "antes de iniciar uma campanha."
        )

    with st.form("formulario-candidatura-turbo"):
        linha_objetivo = st.columns([2, 1.4, .6])
        cargo_turbo = linha_objetivo[0].text_input(
            "Qual vaga você procura?",
            placeholder="Ex.: Auxiliar Administrativo",
        )
        cidade_turbo = linha_objetivo[1].text_input(
            "Cidade",
            placeholder="Ex.: São Paulo",
        )
        estado_turbo = linha_objetivo[2].text_input(
            "UF",
            placeholder="SP",
            max_chars=2,
        )

        linha_preferencias = st.columns([1.25, 1, 1])
        modalidade_turbo = linha_preferencias[0].selectbox(
            "Modalidade",
            ["Presencial", "Híbrido", "Remoto"],
            key="turbo-modalidade",
        )
        incluir_pcd_turbo = linha_preferencias[1].checkbox(
            "Somente vagas PCD",
            value=False,
        )
        limite_turbo = int(
            linha_preferencias[2].number_input(
                "Quantidade de candidaturas",
                min_value=1,
                max_value=50,
                value=10,
                step=1,
                help="Mínimo de 1 e máximo de 50 vagas por campanha.",
            )
        )

        plataformas_turbo = st.multiselect(
            "Plataformas",
            options=plataformas_disponiveis,
            default=plataformas_disponiveis,
            help=(
                "A busca usará somente as fontes selecionadas. A Gupy ficará "
                "aguardando até você confirmar que entrou na conta."
            ),
        )
        periodo_turbo = st.selectbox(
            "Período das vagas",
            [
                ("Últimos 7 dias", 7),
                ("Últimos 15 dias", 15),
                ("Últimos 30 dias", 30),
                ("Qualquer data", None),
            ],
            index=2,
            format_func=lambda opcao: opcao[0],
        )
        consentimento_turbo = st.checkbox(
            "Confirmo que revisarei cada vaga antes do envio final.",
            value=False,
        )
        criar_campanha = st.form_submit_button(
            "Criar campanha automática",
            type="primary",
            use_container_width=True,
        )

    if criar_campanha:
        if not curriculo or not curriculo.get("gerado"):
            st.error("Finalize seu currículo antes de criar a campanha.")
        elif not consentimento_turbo:
            st.error("Confirme a revisão das vagas para continuar.")
        elif not cargo_turbo.strip() or not cidade_turbo.strip() or len(
            estado_turbo.strip()
        ) != 2:
            st.error("Informe cargo, cidade e uma UF com duas letras.")
        elif not plataformas_turbo:
            st.error("Selecione pelo menos uma plataforma.")
        else:
            with st.spinner(
                f"Buscando e organizando até {limite_turbo} vagas..."
            ):
                try:
                    resultado_campanha = asyncio.run(
                        preparar_campanha_candidatura(
                            usuario_id=usuario_id,
                            cargo=cargo_turbo,
                            cidade=cidade_turbo,
                            estado=estado_turbo.upper(),
                            modalidade=modalidade_turbo,
                            incluir_pcd=incluir_pcd_turbo,
                            plataformas=plataformas_turbo,
                            limite_vagas=limite_turbo,
                            max_dias=periodo_turbo[1],
                        )
                    )
                except Exception:
                    logger.exception("Falha interna ao preparar campanha")
                    resultado_campanha = {
                        "status": "erro",
                        "mensagem": "Não foi possível preparar a campanha agora.",
                    }

            if resultado_campanha.get("status") == "sucesso":
                st.session_state.campanha_turbo_ativa = resultado_campanha[
                    "campanha_id"
                ]
                st.session_state.pagina_turbo = 1
                st.success(resultado_campanha["mensagem"])
                if resultado_campanha["total_vagas"] == 0:
                    st.info(
                        "A campanha foi salva, mas nenhuma vaga compatível foi "
                        "encontrada nesta busca."
                    )
                _atualizar_dialog_turbo()
            else:
                st.error(resultado_campanha.get("mensagem"))

    campanhas_resultado = listar_campanhas_candidatura(usuario_id)
    campanhas = campanhas_resultado.get("campanhas", [])
    if not campanhas:
        st.info("Você ainda não criou nenhuma campanha de candidatura.")
        return

    st.markdown("#### Visão geral das campanhas")
    tabela_campanhas = [
        {
            "Campanha": f"#{item['id']}",
            "Cargo": item["cargo"],
            "Local": f"{item['cidade']}/{item['estado']}",
            "Plataformas": ", ".join(item["plataformas"]),
            "Status": _rotulo_status_campanha(item["status"]),
            "Limite": item["limite_vagas"],
            "Enviadas": item["candidatadas"],
            "Pendentes": item["pendentes"],
        }
        for item in campanhas
    ]
    st.dataframe(
        tabela_campanhas,
        hide_index=True,
        use_container_width=True,
        height=min(360, 38 + len(tabela_campanhas) * 36),
    )

    campanhas_por_id = {item["id"]: item for item in campanhas}
    campanha_padrao = st.session_state.get("campanha_turbo_ativa")
    if campanha_padrao not in campanhas_por_id:
        campanha_padrao = campanhas[0]["id"]
    ids_campanhas = list(campanhas_por_id)
    indice_campanha = ids_campanhas.index(campanha_padrao)

    campanha_id = st.selectbox(
        "Campanha em exibição",
        options=ids_campanhas,
        index=indice_campanha,
        format_func=lambda identificador: (
            f"#{identificador} · {campanhas_por_id[identificador]['cargo']} · "
            f"{_rotulo_status_campanha(campanhas_por_id[identificador]['status'])}"
        ),
    )
    if campanha_id != st.session_state.get("campanha_turbo_ativa"):
        st.session_state.campanha_turbo_ativa = campanha_id
        st.session_state.pagina_turbo = 1

    campanha = campanhas_por_id[campanha_id]
    metricas_turbo = st.columns(4)
    metricas_turbo[0].metric("Selecionadas", campanha["total_vagas"])
    metricas_turbo[1].metric("Pendentes", campanha["pendentes"])
    metricas_turbo[2].metric("Enviadas", campanha["candidatadas"])
    metricas_turbo[3].metric("Ignoradas", campanha["ignoradas"])
    st.markdown(
        "".join(
            [
                f'<span class="turbo-status">'
                f'{html.escape(_rotulo_status_campanha(campanha["status"]))}</span>',
                f'<span class="turbo-status">Limite: {campanha["limite_vagas"]}</span>',
                f'<span class="turbo-status">'
                f'{html.escape(campanha["cidade"])}, '
                f'{html.escape(campanha["estado"])}</span>',
            ]
        ),
        unsafe_allow_html=True,
    )

    st.markdown("#### Acesso às plataformas")
    logins = listar_logins_campanha(usuario_id, campanha_id)
    for login in logins:
        plataforma = login["plataforma"]
        confirmado = login["status"] == "confirmado"
        classe = "turbo-login-ok" if confirmado else "turbo-login-wait"
        rotulo = "Liberada" if confirmado else "Aguardando login"
        st.markdown(
            f'<span class="turbo-status {classe}">'
            f'{html.escape(plataforma)} · {rotulo}</span>',
            unsafe_allow_html=True,
        )
        if not confirmado and plataforma_exige_login_central(plataforma):
            login_colunas = st.columns([1, 1, 2])
            url_login = url_login_plataforma(plataforma)
            if url_login:
                login_colunas[0].link_button(
                    f"Entrar na {plataforma}",
                    url_login,
                    use_container_width=True,
                )
            if login_colunas[1].button(
                "Já estou logado",
                key=f"confirmar-login-{campanha_id}-{plataforma}",
                use_container_width=True,
            ):
                confirmacao = confirmar_login_plataforma(
                    usuario_id,
                    campanha_id,
                    plataforma,
                )
                if confirmacao.get("status") == "sucesso":
                    st.success(confirmacao["mensagem"])
                    _atualizar_dialog_turbo()
                st.error(confirmacao.get("mensagem"))
            login_colunas[2].caption(
                "Faça o login no mesmo navegador e volte para liberar a fila. "
                "O SearchJob não recebe nem armazena sua senha."
            )

    itens_resultado = listar_itens_campanha(usuario_id, campanha_id)
    if itens_resultado.get("status") != "sucesso":
        st.error(itens_resultado.get("mensagem"))
        return
    itens = itens_resultado["itens"]
    if not itens:
        st.info("Nenhuma vaga foi encontrada para esta campanha.")
        return

    itens_por_pagina = 10
    total_paginas = max(1, (len(itens) + itens_por_pagina - 1) // itens_por_pagina)
    pagina_atual = max(
        1,
        min(total_paginas, int(st.session_state.pagina_turbo or 1)),
    )
    inicio = (pagina_atual - 1) * itens_por_pagina

    st.markdown("#### Fila de candidaturas")
    for item in itens[inicio : inicio + itens_por_pagina]:
        login_liberado = item["status_login"] == "confirmado"
        with st.container(border=True):
            st.markdown(
                '<span class="job-card-marker" aria-hidden="true"></span>',
                unsafe_allow_html=True,
            )
            texto, acoes = st.columns([3.4, 1.35], gap="large")
            with texto:
                st.subheader(item["titulo"])
                st.write(f"**{item['empresa']}**")
                st.caption(
                    f"{item['local']} · {item['modalidade']} · {item['fonte']}"
                )
                st.markdown(
                    f'<span class="turbo-status">'
                    f'{html.escape(item["status"].title())}</span>',
                    unsafe_allow_html=True,
                )
                if not login_liberado:
                    st.warning(
                        f"Entre na {item['fonte']} para liberar esta candidatura."
                    )
            with acoes:
                if login_liberado and item["status"] == "pendente":
                    st.link_button(
                        "Abrir candidatura",
                        item["url_candidatura"],
                        use_container_width=True,
                        type="primary",
                    )
                    if st.button(
                        "Marcar como enviada",
                        key=f"turbo-enviada-{item['id']}",
                        use_container_width=True,
                    ):
                        persistencia = salvar_candidatura(
                            fonte=item["fonte"],
                            id_externo=item["id_externo"],
                            titulo=item["titulo"],
                            empresa=item["empresa"],
                            local=item["local"],
                            url_candidatura=item["url_candidatura"],
                        )
                        if persistencia.get("status") == "sucesso":
                            atualizar_item_campanha(
                                usuario_id,
                                item["id"],
                                "candidatado",
                            )
                            _atualizar_dialog_turbo()
                        st.error(persistencia.get("mensagem"))
                    if st.button(
                        "Ignorar vaga",
                        key=f"turbo-ignorar-{item['id']}",
                        use_container_width=True,
                    ):
                        atualizar_item_campanha(
                            usuario_id,
                            item["id"],
                            "ignorado",
                        )
                        _atualizar_dialog_turbo()
                elif item["status"] == "candidatado":
                    st.success("Candidatura enviada")
                elif item["status"] == "ignorado":
                    st.caption("Vaga ignorada")

    navegacao_turbo = st.columns([1, 2, 1])
    if navegacao_turbo[0].button(
        "← Anterior",
        key="turbo-anterior",
        disabled=pagina_atual <= 1,
        use_container_width=True,
    ):
        st.session_state.pagina_turbo = pagina_atual - 1
        _atualizar_dialog_turbo()
    navegacao_turbo[1].markdown(
        f"<p style='text-align:center;padding-top:.55rem'>"
        f"Página {pagina_atual} de {total_paginas}</p>",
        unsafe_allow_html=True,
    )
    if navegacao_turbo[2].button(
        "Próxima →",
        key="turbo-proxima",
        disabled=pagina_atual >= total_paginas,
        use_container_width=True,
    ):
        st.session_state.pagina_turbo = pagina_atual + 1
        _atualizar_dialog_turbo()


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
        "pagina_turbo": 1,
        "campanha_turbo_ativa": None,
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
        <span class="hero-eyebrow">SearchJob · sua jornada profissional</span>
        <h1>Boas oportunidades, sem complicação.</h1>
        <p>
            Pesquise em vários portais, descubra vagas compatíveis com o seu
            perfil e acompanhe cada candidatura com tranquilidade.
        </p>
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
    chamada_turbo = st.columns([3.5, 1])
    chamada_turbo[0].markdown(
        """
        <div class="turbo-callout">
            <h3>⚡ Nova: Candidatura automática</h3>
            <p>
                Defina o cargo, a localização, PCD, quantidade e plataformas.
                Nós montamos sua fila personalizada.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if chamada_turbo[1].button(
        "Abrir Candidatura Turbo",
        type="primary",
        use_container_width=True,
        key="abrir-painel-turbo",
    ):
        renderizar_painel_candidatura_turbo()

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
