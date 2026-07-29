import httpx
from app.config import ADZUNA_APP_ID, ADZUNA_APP_KEY
from app.utils.pcd import vaga_eh_pcd


def normalizar_modalidade(texto: str, modalidade_padrao: str) -> str:
    texto_lower = (texto or "").lower()

    if "remoto" in texto_lower or "home office" in texto_lower:
        return "Remoto"

    if "híbrido" in texto_lower or "hibrido" in texto_lower:
        return "Híbrido"

    return modalidade_padrao


async def buscar_vagas_adzuna(
    cargo: str,
    cidade: str,
    estado: str,
    modalidade: str,
    pagina: int = 1,
    max_dias: int | None = None,
    incluir_pcd: bool = False,
):
    url = f"https://api.adzuna.com/v1/api/jobs/br/search/{pagina}"

    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": cargo,
        "where": f"{cidade}, {estado}",
        "results_per_page": 20,
        "content-type": "application/json",
    }

    if max_dias:
        params["max_days_old"] = max_dias

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        vagas = []

        for item in data.get("results", []):
            titulo = item.get("title", "Título não informado")
            descricao = item.get("description", "")
            texto_vaga = f"{titulo} {descricao}"

            eh_pcd = vaga_eh_pcd(texto_vaga)

            if eh_pcd and not incluir_pcd:
                continue

            empresa = item.get("company", {}).get("display_name", "Empresa não informada")
            local = item.get("location", {}).get("display_name", f"{cidade}, {estado}")
            url_candidatura = item.get("redirect_url")

            if not url_candidatura:
                continue

            vagas.append({
                "id_externo": str(item.get("id")),
                "titulo": titulo,
                "empresa": empresa,
                "local": local,
                "modalidade": normalizar_modalidade(texto_vaga, modalidade),
                "url_candidatura": url_candidatura,
                "data_publicacao": item.get("created"),
                "candidatura_simplificada": False,
                "ja_candidatado": False,
                "eh_pcd": eh_pcd,
                "fonte": "Adzuna",
            })

        return {
            "fonte": "Adzuna",
            "total_fonte": data.get("count", 0),
            "vagas": vagas,
        }

    except httpx.HTTPStatusError as error:
        print(f"Erro HTTP Adzuna: {error.response.status_code}")
    except httpx.RequestError as error:
        print("Erro de conexão com Adzuna")
    except Exception as error:
        print("Erro inesperado na Adzuna")

    return {
        "fonte": "Adzuna",
        "total_fonte": 0,
        "vagas": [],
    }
