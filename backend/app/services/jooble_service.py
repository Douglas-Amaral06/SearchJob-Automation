import logging

import httpx
from app.config import JOOBLE_API_KEY
from app.services.adzuna_service import normalizar_modalidade
from app.utils.pcd import vaga_eh_pcd

logger = logging.getLogger(__name__)


def montar_payloads_jooble(cargo: str, cidade: str, estado: str, pagina: int):
    return [
        {
            "keywords": cargo,
            "location": cidade,
            "radius": "80",
            "page": str(pagina),
            "ResultOnPage": 20,
            "SearchMode": 1,
            "companysearch": "false",
        },
        {
            "keywords": cargo,
            "location": f"{cidade}, {estado}",
            "radius": "80",
            "page": str(pagina),
            "ResultOnPage": 20,
            "SearchMode": 1,
            "companysearch": "false",
        },
        {
            "keywords": f"{cargo} {cidade}",
            "location": "Brasil",
            "radius": "80",
            "page": str(pagina),
            "ResultOnPage": 20,
            "SearchMode": 1,
            "companysearch": "false",
        },
        {
            "keywords": cargo,
            "location": "São Paulo",
            "radius": "80",
            "page": str(pagina),
            "ResultOnPage": 20,
            "SearchMode": 1,
            "companysearch": "false",
        },
    ]


async def buscar_vagas_jooble(
    cargo: str,
    cidade: str,
    estado: str,
    modalidade: str,
    pagina: int = 1,
    max_dias: int | None = None,
    incluir_pcd: bool = False,
):
    url = f"https://jooble.org/api/{JOOBLE_API_KEY}"

    try:
        data = {"totalCount": 0, "jobs": []}
        payload_usado = None

        async with httpx.AsyncClient(timeout=20) as client:
            for payload in montar_payloads_jooble(cargo, cidade, estado, pagina):
                response = await client.post(url, json=payload)

                response.raise_for_status()
                data = response.json()
                payload_usado = payload

                if data.get("jobs"):
                    break

        vagas = []

        for item in data.get("jobs", []):
            titulo = item.get("title", "Título não informado")
            descricao = item.get("snippet", "") or item.get("description", "")
            texto_vaga = f"{titulo} {descricao}"

            eh_pcd = vaga_eh_pcd(texto_vaga)

            if eh_pcd and not incluir_pcd:
                continue

            url_candidatura = item.get("link")

            if not url_candidatura:
                continue

            vagas.append({
                "id_externo": str(item.get("id") or url_candidatura),
                "titulo": titulo,
                "empresa": item.get("company") or "Empresa não informada",
                "local": item.get("location") or f"{cidade}, {estado}",
                "modalidade": normalizar_modalidade(texto_vaga, modalidade),
                "url_candidatura": url_candidatura,
                "data_publicacao": item.get("updated"),
                "candidatura_simplificada": False,
                "ja_candidatado": False,
                "eh_pcd": eh_pcd,
                "fonte": "Jooble",
            })

        return {
            "fonte": "Jooble",
            "total_fonte": data.get("totalCount", 0),
            "vagas": vagas,
            "debug": {
                "payload_usado": payload_usado,
            },
        }

    except httpx.HTTPStatusError as error:
        logger.warning("Jooble respondeu HTTP %s", error.response.status_code)
    except httpx.RequestError as error:
        logger.warning("Erro de conexão com Jooble: %s", error)
    except Exception as error:
        logger.exception("Erro inesperado na Jooble: %s", error)

    return {
        "fonte": "Jooble",
        "total_fonte": 0,
        "vagas": [],
    }
