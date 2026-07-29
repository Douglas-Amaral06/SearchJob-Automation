import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()


def ler_booleano(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)

    if valor is None:
        return padrao

    return valor.strip().lower() in {
        "1",
        "true",
        "yes",
        "sim",
        "on",
    }


ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

GUPY_ENABLED = ler_booleano("GUPY_ENABLED", False)
JOOBLE_ENABLED = ler_booleano("JOOBLE_ENABLED", True)

GREENHOUSE_ENABLED = ler_booleano("GREENHOUSE_ENABLED", False)
GREENHOUSE_BOARD_TOKENS_STR = os.getenv("GREENHOUSE_BOARD_TOKENS", "").strip()
GREENHOUSE_CACHE_TTL_SECONDS = int(os.getenv("GREENHOUSE_CACHE_TTL_SECONDS", "300"))


def parse_greenhouse_boards() -> list[str]:
    """Parse lista separada por vírgulas de board tokens."""
    if not GREENHOUSE_BOARD_TOKENS_STR:
        return []
    
    return [
        token.strip()
        for token in GREENHOUSE_BOARD_TOKENS_STR.split(",")
        if token.strip()
    ]


GREENHOUSE_BOARD_TOKENS = parse_greenhouse_boards()

# DATABASE
DATABASE_PATH_STR = os.getenv("DATABASE_PATH", "data/search_emprego.db")
# Resolver caminho absoluto baseado no diretório do backend
BASE_DIR = Path(__file__).parent.parent.parent  # ProjetoSearchEmprego
DATABASE_PATH = BASE_DIR / DATABASE_PATH_STR
DATABASE_DIR = DATABASE_PATH.parent


if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
    raise RuntimeError(
        "Credenciais da Adzuna não encontradas. "
        "Configure ADZUNA_APP_ID e ADZUNA_APP_KEY no arquivo backend/.env."
    )