import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


def normalizar_texto(valor: str | None) -> str:
    texto = unicodedata.normalize("NFKD", valor or "")
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    texto = texto.casefold()
    texto = re.sub(r"[^\w\s]", " ", texto)
    return " ".join(texto.split())


def normalizar_url(valor: str | None) -> str:
    if not valor:
        return ""

    try:
        partes = urlsplit(valor.strip())

        # Remove query strings, fragmentos e barra final.
        caminho = partes.path.rstrip("/")

        return urlunsplit(
            (
                partes.scheme.casefold(),
                partes.netloc.casefold(),
                caminho,
                "",
                "",
            )
        )
    except ValueError:
        return valor.strip().casefold()


def remover_vagas_duplicadas(vagas: list[dict]) -> list[dict]:
    vagas_unicas: list[dict] = []
    urls_vistas: set[str] = set()
    identidades_vistas: set[tuple[str, str, str]] = set()

    for vaga in vagas:
        url = normalizar_url(vaga.get("url_candidatura"))

        identidade = (
            normalizar_texto(vaga.get("titulo")),
            normalizar_texto(vaga.get("empresa")),
            normalizar_texto(vaga.get("local")),
        )

        url_duplicada = bool(url) and url in urls_vistas

        identidade_valida = all(identidade)
        identidade_duplicada = (
            identidade_valida and identidade in identidades_vistas
        )

        if url_duplicada or identidade_duplicada:
            continue

        if url:
            urls_vistas.add(url)

        if identidade_valida:
            identidades_vistas.add(identidade)

        vagas_unicas.append(vaga)

    return vagas_unicas