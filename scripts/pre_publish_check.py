"""Bloqueia arquivos sensíveis e segredos antes de publicar o repositório."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
LIMITE_TEXTO = 2 * 1024 * 1024

NOMES_PROIBIDOS = {
    ".env",
    ".env.local",
    "secrets.toml",
    "credentials.toml",
}
SUFIXOS_PROIBIDOS = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
    ".log",
    ".dump",
}
DIRETORIOS_PROIBIDOS = {
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "data",
    "backups",
    "exports",
}

PADROES_SEGREDO = {
    "chave Google/Gemini": re.compile(r"\b(?:AIza|AQ\.)[A-Za-z0-9_-]{20,}\b"),
    "token GitHub": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "access key AWS": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "chave privada": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

ATRIBUICOES_SENSIVEIS = re.compile(
    r"""(?ix)
    \b(
        GEMINI_API_KEY|ADZUNA_APP_KEY|JOOBLE_API_KEY|SERPAPI_API_KEY|
        SMTP_PASSWORD|APP_ENCRYPTION_KEY|ADMIN_BOOTSTRAP_PASSWORD
    )\s*[=:]\s*["']([^"' \r\n][^"'\r\n]{10,})["']
    """
)
PLACEHOLDERS = {
    "sua_chave",
    "sua_nova_chave",
    "sua_nova_chave_gemini",
    "senha-smtp",
    "use-uma-senha-nova-e-forte",
    "uma-senha-nova-e-forte",
    "gere-um-segredo-aleatorio-com-pelo-menos-32-caracteres",
}


def arquivos_candidatos() -> list[Path]:
    comando = [
        "git",
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    ]
    try:
        resultado = subprocess.run(
            comando,
            cwd=RAIZ,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        print("ERRO: inicialize o Git antes de executar a auditoria.")
        raise SystemExit(2)

    caminhos = [
        RAIZ / item.decode("utf-8", errors="surrogateescape")
        for item in resultado.stdout.split(b"\0")
        if item
    ]
    return [caminho for caminho in caminhos if caminho.is_file()]


def caminho_proibido(caminho: Path) -> bool:
    relativo = caminho.relative_to(RAIZ)
    nome = caminho.name.casefold()
    partes = {parte.casefold() for parte in relativo.parts}
    return (
        nome in NOMES_PROIBIDOS
        or caminho.suffix.casefold() in SUFIXOS_PROIBIDOS
        or bool(partes & DIRETORIOS_PROIBIDOS)
        or nome.endswith((".db-wal", ".db-shm", ".sqlite-wal", ".sqlite-shm"))
    )


def verificar_texto(caminho: Path) -> list[str]:
    if caminho.stat().st_size > LIMITE_TEXTO:
        return []
    try:
        texto = caminho.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    problemas = [
        descricao
        for descricao, padrao in PADROES_SEGREDO.items()
        if padrao.search(texto)
    ]
    for correspondencia in ATRIBUICOES_SENSIVEIS.finditer(texto):
        valor = correspondencia.group(2).strip()
        if valor.casefold() not in PLACEHOLDERS:
            problemas.append(
                f"valor literal em {correspondencia.group(1).upper()}"
            )
    return problemas


def main() -> int:
    problemas: list[str] = []
    for caminho in arquivos_candidatos():
        relativo = caminho.relative_to(RAIZ).as_posix()
        if caminho_proibido(caminho):
            problemas.append(f"{relativo}: arquivo sensível não pode ser publicado")
            continue
        for descricao in verificar_texto(caminho):
            problemas.append(f"{relativo}: possível {descricao}")

    if problemas:
        print("PUBLICAÇÃO BLOQUEADA:")
        for problema in sorted(set(problemas)):
            print(f"- {problema}")
        print("Remova o segredo/arquivo; não ignore nem contorne este bloqueio.")
        return 1

    print("Auditoria aprovada: nenhum segredo ou arquivo sensível será publicado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
