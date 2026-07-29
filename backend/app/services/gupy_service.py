import httpx
import unicodedata
import re
from datetime import datetime
from app.utils.pcd import vaga_eh_pcd

PAGE_SIZE = 20
MAX_REQUESTS = 5
MAX_CANDIDATES = 100

UF_POR_NOME = {
    "acre": "ac",
    "alagoas": "al",
    "amapa": "ap",
    "amazonas": "am",
    "bahia": "ba",
    "ceara": "ce",
    "distrito federal": "df",
    "espirito santo": "es",
    "goias": "go",
    "maranhao": "ma",
    "mato grosso": "mt",
    "mato grosso do sul": "ms",
    "minas gerais": "mg",
    "para": "pa",
    "paraiba": "pb",
    "parana": "pr",
    "pernambuco": "pe",
    "piaui": "pi",
    "rio de janeiro": "rj",
    "rio grande do norte": "rn",
    "rio grande do sul": "rs",
    "rondonia": "ro",
    "roraima": "rr",
    "santa catarina": "sc",
    "sao paulo": "sp",
    "sergipe": "se",
    "tocantins": "to",
}


def normalizar_texto_comparacao(texto: str | None) -> str:
    """Normaliza texto para comparação removendo acentos e caixa."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def normalizar_uf(estado: str | None) -> str:
    """Converte tanto nome completo quanto sigla para uma UF comparável."""
    estado_norm = normalizar_texto_comparacao(estado)
    return UF_POR_NOME.get(estado_norm, estado_norm)


def normalizar_cidade_busca(cidade: str | None, estado: str | None) -> str:
    """Aceita formas usuais como 'SP Capital' e 'São Paulo Capital'."""
    cidade_norm = normalizar_texto_comparacao(cidade)
    estado_uf = normalizar_uf(estado)

    if estado_uf == "sp" and cidade_norm in {
        "sp",
        "sp capital",
        "capital",
        "sao paulo capital",
    }:
        return "sao paulo"

    if cidade_norm.endswith(" capital"):
        cidade_norm = cidade_norm.removesuffix(" capital").strip()

    return cidade_norm


def interpretar_workplace_type(workplace_type: str | None) -> str:
    """Converte workplaceType da Gupy para modalidade padrão."""
    if not workplace_type:
        return "Não informada"
    
    workplace_lower = (workplace_type or "").lower().strip()
    
    if workplace_lower in ("remote", "remoto", "home office"):
        return "Remoto"
    
    if workplace_lower in ("hybrid", "híbrido", "hibrido"):
        return "Híbrido"
    
    if workplace_lower in ("on-site", "onsite", "on site", "presencial"):
        return "Presencial"
    
    return "Não informada"


def mapear_modalidade_para_workplace(modalidade: str) -> str | None:
    """Mapeia modalidade do usuário para workplaceType da API."""
    if modalidade == "Remoto":
        return "remote"
    elif modalidade == "Híbrido":
        return "hybrid"
    elif modalidade == "Presencial":
        return "on-site"
    return None


def construir_local(city: str | None, state: str | None) -> str:
    """Constrói localização sem inventar dados."""
    parts = []
    
    if city and city.strip():
        parts.append(city.strip())
    
    if state and state.strip():
        parts.append(state.strip())
    
    if parts:
        return ", ".join(parts)
    
    return "Local não informado"


def vaga_matcheia_filtros(
    vaga: dict,
    cidade_busca: str,
    estado_busca: str,
    modalidade_busca: str,
) -> bool:
    """Valida se vaga passa nos filtros locais defensivos."""
    vaga_city = vaga.get("city", "").strip()
    vaga_state = vaga.get("state", "").strip()
    
    # Normalizar para comparação
    cidade_norm = normalizar_cidade_busca(cidade_busca, estado_busca)
    estado_norm = normalizar_uf(estado_busca)
    vaga_city_norm = normalizar_texto_comparacao(vaga_city)
    vaga_state_norm = normalizar_uf(vaga_state)
    
    workplace_type = vaga.get("workplaceType", "")
    vaga_modalidade = interpretar_workplace_type(workplace_type)

    # Uma vaga presencial/híbrida sem cidade pode pertencer a qualquer lugar
    # do país e não deve passar por uma busca municipal específica.
    if cidade_norm and not vaga_city_norm and vaga_modalidade != "Remoto":
        return False
    
    # Se a vaga tem cidade explícita e é diferente da busca, remover (exceto remoto)
    if vaga_city_norm and vaga_city_norm != cidade_norm:
        if vaga_modalidade != "Remoto":
            return False
    
    # Se a vaga tem estado explícito e é diferente da busca, remover (exceto remoto)
    if vaga_state_norm and vaga_state_norm != estado_norm:
        if vaga_modalidade != "Remoto":
            return False
    
    # Filtro de modalidade: estrita quando modalidade específica foi pedida
    if modalidade_busca != "Presencial":  # "Presencial" é default
        if vaga_modalidade == "Não informada":
            return False
        if vaga_modalidade != modalidade_busca:
            return False
    else:
        # Modalidade Presencial: aceita apenas Presencial explícita
        if vaga_modalidade != "Presencial":
            return False
    
    return True


async def buscar_vagas_gupy(
    cargo: str,
    cidade: str,
    estado: str,
    modalidade: str,
    pagina: int = 1,
    max_dias: int | None = None,
    incluir_pcd: bool = False,
):
    """
    Busca vagas na Gupy com paginação interna limitada.
    Endpoint: https://employability-portal.gupy.io/api/v1/jobs
    """
    
    url = "https://employability-portal.gupy.io/api/v1/jobs"
    vagas_validas = []
    total_fonte = 0
    requisicoes = 0
    candidatas_processadas = 0
    offset_inicial = (pagina - 1) * PAGE_SIZE
    offset_atual = offset_inicial
    
    # Mapear modalidade para filtro do endpoint
    workplace_filter = mapear_modalidade_para_workplace(modalidade)
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            while len(vagas_validas) < PAGE_SIZE and requisicoes < MAX_REQUESTS:
                params = {
                    "jobName": cargo,
                    "limit": PAGE_SIZE,
                    "offset": offset_atual,
                }
                
                # Adicionar filtro workplaceType se aplicável
                if workplace_filter:
                    params["workplaceType"] = workplace_filter
                
                try:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    requisicoes += 1
                except (httpx.TimeoutException, httpx.RequestError):
                    print("Timeout ou erro de conexão Gupy")
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        print("Gupy: Autenticação necessária")
                    elif e.response.status_code == 403:
                        print("Gupy: Acesso proibido")
                    elif e.response.status_code == 429:
                        print("Gupy: Rate limit atingido")
                    elif e.response.status_code >= 500:
                        print("Gupy: Indisponível temporariamente")
                    break
                except ValueError:
                    print("Erro decodificando JSON da Gupy")
                    break
                
                # Validar estrutura
                if not isinstance(data, dict):
                    break
                
                items = data.get("data", [])
                if not isinstance(items, list):
                    break
                
                if not items:
                    if total_fonte == 0:
                        total_fonte = data.get("pagination", {}).get("total", 0)
                    break
                
                if total_fonte == 0:
                    total_fonte = data.get("pagination", {}).get("total", 0)
                
                for item in items:
                    if candidatas_processadas >= MAX_CANDIDATES:
                        break
                    
                    candidatas_processadas += 1
                    
                    if not isinstance(item, dict):
                        continue
                    
                    # Validar campos obrigatórios
                    titulo = item.get("name", "").strip()
                    if not titulo:
                        continue
                    
                    url_candidatura = item.get("jobUrl", "").strip()
                    if not url_candidatura or not url_candidatura.startswith(("http://", "https://")):
                        continue
                    
                    # Extrair ID seguramente
                    item_id = item.get("id")
                    if item_id is None:
                        id_externo = url_candidatura
                    else:
                        id_externo = str(item_id)
                    
                    if not id_externo:
                        continue
                    
                    # Filtros defensivos locais
                    if not vaga_matcheia_filtros(item, cidade, estado, modalidade):
                        continue
                    
                    # Verificar PCD
                    descricao = item.get("description", "")
                    texto_vaga = f"{titulo} {descricao}"
                    eh_pcd = vaga_eh_pcd(texto_vaga)
                    
                    if eh_pcd and not incluir_pcd:
                        continue
                    
                    # Verificar data
                    data_publicacao = item.get("publishedDate")
                    if data_publicacao and max_dias:
                        try:
                            data_pub = datetime.fromisoformat(
                                data_publicacao.replace("Z", "+00:00")
                            )
                            data_agora = datetime.now(data_pub.tzinfo)
                            dias = (data_agora - data_pub).days
                            
                            if dias > max_dias:
                                continue
                        except (ValueError, TypeError):
                            data_publicacao = None
                    
                    # Normalizar modalidade
                    workplace_type = item.get("workplaceType")
                    vaga_modalidade = interpretar_workplace_type(workplace_type)
                    
                    # Construir local sem inventar
                    local = construir_local(
                        item.get("city"),
                        item.get("state"),
                    )
                    
                    empresa = item.get("careerPageName", "").strip()
                    if not empresa:
                        empresa = "Empresa não informada"
                    
                    vagas_validas.append({
                        "id_externo": id_externo,
                        "titulo": titulo,
                        "empresa": empresa,
                        "local": local,
                        "modalidade": vaga_modalidade,
                        "url_candidatura": url_candidatura,
                        "data_publicacao": data_publicacao,
                        "candidatura_simplificada": False,
                        "ja_candidatado": False,
                        "eh_pcd": eh_pcd,
                        "fonte": "Gupy",
                    })
                    
                    if len(vagas_validas) >= PAGE_SIZE:
                        break
                
                if candidatas_processadas >= MAX_CANDIDATES or len(vagas_validas) >= PAGE_SIZE:
                    break
                
                offset_atual += PAGE_SIZE
        
        return {
            "fonte": "Gupy",
            "total_fonte": total_fonte,
            "vagas": vagas_validas[:PAGE_SIZE],
        }
    
    except Exception as error:
        print(f"Erro inesperado na Gupy: {str(error)[:100]}")
        return {
            "fonte": "Gupy",
            "total_fonte": 0,
            "vagas": [],
        }
