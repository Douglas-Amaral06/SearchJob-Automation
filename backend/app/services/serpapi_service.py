import httpx
from app.config import SERPAPI_API_KEY
from app.services.adzuna_service import normalizar_modalidade, vaga_eh_pcd


def extrair_url_candidatura_serpapi(item: dict) -> str | None:
    apply_options = item.get("apply_options") or []

    if apply_options:
        return apply_options[0].get("link")

    related_links = item.get("related_links") or []

    if related_links:
        return related_links[0].get("link")

    return item.get("share_link")


async def buscar_vagas_serpapi(
    cargo: str,
    cidade: str,
    estado: str,
    modalidade: str,
    pagina: int = 1,
    max_dias: int | None = None,
    incluir_pcd: bool = False,
):
    url = "https://serpapi.com/search.json"

    query = f"{cargo} {cidade} {estado} {modalidade}"

    params = {
    "engine": "google_jobs",
    "q": f"{cargo} em {cidade} {estado} {modalidade}",
    "hl": "pt-br",
    "gl": "br",
    "location": "Brazil",
    "api_key": SERPAPI_API_KEY,
}

    # Paginação da SerpApi/Google Jobs geralmente usa next_page_token.
    # Por enquanto, mantemos página 1 para evitar quebrar o fluxo.
    if pagina > 1:
        return {
            "fonte": "SerpApi Google Jobs",
            "total_fonte": 0,
            "vagas": [],
        }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        vagas = []

        for item in data.get("jobs_results", []):
            titulo = item.get("title", "Título não informado")
            descricao = item.get("description", "")
            texto_vaga = f"{titulo} {descricao}"

            eh_pcd = vaga_eh_pcd(texto_vaga)

            if eh_pcd and not incluir_pcd:
                continue

            url_candidatura = extrair_url_candidatura_serpapi(item)

            if not url_candidatura:
                continue

            empresa = item.get("company_name", "Empresa não informada")
            local = item.get("location", f"{cidade}, {estado}")

            vagas.append({
                "id_externo": item.get("job_id") or url_candidatura,
                "titulo": titulo,
                "empresa": empresa,
                "local": local,
                "modalidade": normalizar_modalidade(texto_vaga, modalidade),
                "url_candidatura": url_candidatura,
                "data_publicacao": item.get("detected_extensions", {}).get("posted_at"),
                "candidatura_simplificada": False,
                "ja_candidatado": False,
                "eh_pcd": eh_pcd,
                "fonte": "SerpApi Google Jobs",
            })

        return {
            "fonte": "SerpApi Google Jobs",
            "total_fonte": len(vagas),
            "vagas": vagas,
        }

    except httpx.HTTPStatusError as error:
        print(f"Erro HTTP SerpApi: {error.response.status_code}")
    except httpx.RequestError as error:
        print("Erro de conexão com SerpApi")
    except Exception as error:
        print("Erro inesperado na SerpApi")

    return {
        "fonte": "SerpApi Google Jobs",
        "total_fonte": 0,
        "vagas": [],
    }
