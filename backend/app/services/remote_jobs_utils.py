from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.services.greenhouse_service import cargo_matcheia, normalizar_data_publicacao


ALIASES_CARGO = {
    "auxiliar administrativo": ("administrative assistant", "admin assistant"),
    "assistente administrativo": ("administrative assistant", "admin assistant"),
    "atendimento ao cliente": ("customer support", "customer service"),
    "desenvolvedor": ("developer", "software engineer"),
    "desenvolvedora": ("developer", "software engineer"),
    "engenheiro de software": ("software engineer",),
    "engenheira de software": ("software engineer",),
    "analista de dados": ("data analyst",),
    "cientista de dados": ("data scientist",),
    "gerente de projetos": ("project manager",),
    "recursos humanos": ("human resources", "people operations"),
    "vendedor": ("sales representative", "sales"),
    "vendedora": ("sales representative", "sales"),
}

ALIASES_TOKEN = {
    "administrativo": "administrative",
    "administrativa": "administrative",
    "analista": "analyst",
    "atendimento": "support",
    "auxiliar": "assistant",
    "coordenador": "coordinator",
    "coordenadora": "coordinator",
    "dados": "data",
    "desenvolvedor": "developer",
    "desenvolvedora": "developer",
    "engenheiro": "engineer",
    "engenheira": "engineer",
    "financeiro": "financial",
    "financeira": "financial",
    "gerente": "manager",
    "projetos": "projects",
    "suporte": "support",
    "vendas": "sales",
    "vendedor": "sales",
    "vendedora": "sales",
}

TERMOS_GLOBAIS = (
    "anywhere",
    "global",
    "worldwide",
    "world wide",
    "remote",
)
TERMOS_BRASIL = ("brasil", "brazil", "brazilian")
TERMOS_REGIAO_COMPATIVEL = (
    "latam",
    "latin america",
    "south america",
    "americas",
)
REGIOES_INCOMPATIVEIS = (
    "africa only",
    "apac",
    "asia only",
    "australia",
    "canada",
    "europe",
    "european union",
    "india",
    "japan",
    "mexico",
    "new zealand",
    "united kingdom",
    "united states",
    "uk only",
    "us only",
    "usa only",
)


def normalizar_texto(texto: object) -> str:
    if not isinstance(texto, str):
        return ""
    normalizado = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(caractere)
    )
    return " ".join(sem_acentos.casefold().split())


def remover_html(texto: object) -> str:
    if not isinstance(texto, str):
        return ""
    sem_tags = re.sub(r"<[^>]*>", " ", texto)
    return " ".join(html.unescape(sem_tags).split())


def url_publica_valida(valor: object) -> bool:
    if not isinstance(valor, str):
        return False
    try:
        url = urlparse(valor.strip())
    except ValueError:
        return False
    return url.scheme in {"http", "https"} and bool(url.netloc)


def consultas_equivalentes_cargo(cargo: str) -> list[str]:
    cargo_norm = normalizar_texto(cargo)
    if not cargo_norm:
        return []

    consultas = [cargo_norm]
    consultas.extend(ALIASES_CARGO.get(cargo_norm, ()))

    tokens_traduzidos = [
        ALIASES_TOKEN.get(token, token)
        for token in cargo_norm.split()
        if token not in {"de", "da", "do", "das", "dos", "e"}
    ]
    traducao = " ".join(tokens_traduzidos)
    if traducao and traducao != cargo_norm:
        consultas.append(traducao)

    return list(dict.fromkeys(consultas))


def cargo_remoto_compativel(titulo: str, descricao: str, cargo: str) -> bool:
    if not normalizar_texto(cargo):
        return True
    return any(
        cargo_matcheia(titulo, descricao, consulta)
        for consulta in consultas_equivalentes_cargo(cargo)
    )


def localizacao_remota_compativel(localizacao: object) -> bool:
    local_norm = normalizar_texto(localizacao)
    if not local_norm:
        return True

    if any(termo in local_norm for termo in REGIOES_INCOMPATIVEIS):
        return False
    if any(termo in local_norm for termo in TERMOS_BRASIL):
        return True
    if re.search(r"(^|[\s,;/()-])br($|[\s,;/()-])", local_norm):
        return True
    if any(termo in local_norm for termo in TERMOS_REGIAO_COMPATIVEL):
        return True
    if any(termo in local_norm for termo in TERMOS_GLOBAIS):
        return True

    # Uma restrição desconhecida não deve ser apresentada como válida no Brasil.
    return False


def data_dentro_do_periodo(data_normalizada: str | None, max_dias: int | None) -> bool:
    if max_dias is None:
        return True
    if not data_normalizada:
        return False
    try:
        publicada = datetime.fromisoformat(data_normalizada.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    agora = datetime.now(timezone.utc)
    return (agora - publicada).total_seconds() <= max_dias * 86400


def normalizar_data(valor: object) -> str | None:
    return normalizar_data_publicacao(valor)


def ordenar_e_paginar(vagas: list[dict], pagina: int, tamanho: int = 20) -> list[dict]:
    def chave(vaga: dict) -> tuple:
        data = vaga.get("data_publicacao")
        try:
            timestamp = datetime.fromisoformat(
                str(data).replace("Z", "+00:00")
            ).timestamp()
        except (TypeError, ValueError):
            timestamp = float("-inf")
        return (
            -timestamp,
            normalizar_texto(vaga.get("titulo")),
            str(vaga.get("id_externo", "")),
        )

    ordenadas = sorted(vagas, key=chave)
    inicio = max(0, pagina - 1) * tamanho
    return ordenadas[inicio : inicio + tamanho]
