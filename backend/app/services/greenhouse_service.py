import httpx
import asyncio
import unicodedata
import logging
import time
import re
from datetime import datetime, timezone, timedelta
from app.utils.pcd import vaga_eh_pcd
from app.config import GREENHOUSE_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
MAX_BOARDS_PER_REQUEST = 15

# Mapa de UFs brasileiras
UF_MAP = {
    "sp": "são paulo",
    "rj": "rio de janeiro",
    "mg": "minas gerais",
    "ba": "bahia",
    "pe": "pernambuco",
    "pr": "paraná",
    "sc": "santa catarina",
    "rs": "rio grande do sul",
    "df": "distrito federal",
    "go": "goiás",
    "mt": "mato grosso",
    "ms": "mato grosso do sul",
    "es": "espírito santo",
    "rn": "rio grande do norte",
    "al": "alagoas",
    "ce": "ceará",
    "pb": "paraíba",
    "pi": "piauí",
    "ma": "maranhão",
    "am": "amazonas",
    "pa": "pará",
    "ac": "acre",
    "ap": "amapá",
    "ro": "rondônia",
    "rr": "roraima",
    "to": "tocantins",
}

STOPWORDS = {
    "de", "da", "do", "para", "com", "em", "e", "pessoa", "vaga",
    "profissional", "a", "o", "os", "as", "um", "uma", "uns", "umas"
}


# Cache simples em memória
class GreenhouseCache:
    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.locks = {}
        self.ttl = ttl_seconds
    
    async def get(self, board_token: str):
        if board_token not in self.cache:
            return None
        
        data, timestamp = self.cache[board_token]
        if time.time() - timestamp > self.ttl:
            del self.cache[board_token]
            return None
        
        return data
    
    async def set(self, board_token: str, data):
        self.cache[board_token] = (data, time.time())
    
    async def get_lock(self, board_token: str):
        if board_token not in self.locks:
            self.locks[board_token] = asyncio.Lock()
        return self.locks[board_token]
    
    async def cleanup(self):
        """Remove entradas expiradas."""
        now = time.time()
        expired = [k for k, (_, ts) in self.cache.items() if now - ts > self.ttl]
        for k in expired:
            del self.cache[k]


_cache = GreenhouseCache(GREENHOUSE_CACHE_TTL_SECONDS)


def normalizar_texto_comparacao(texto: str | None) -> str:
    """Normaliza texto: acentos, caixa, espaços."""
    if not texto:
        return ""
    
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower().strip()
    texto = " ".join(texto.split())
    
    return texto


def tokenizar_texto(texto: str | None) -> list[str]:
    """
    Tokeniza texto em palavras completas.
    Remove pontuação e retorna lista de tokens.
    """
    if not texto:
        return []
    
    # Normalizar primeiro
    texto_norm = normalizar_texto_comparacao(texto)
    
    # Substituir pontuação por espaços
    texto_limpo = re.sub(r'[^\w\s]', ' ', texto_norm)
    
    # Extrair tokens
    tokens = texto_limpo.split()
    
    return tokens


def remover_html(html: str | None) -> str:
    """Remove tags HTML do texto."""
    if not html:
        return ""
    try:
        return re.sub(r'<[^>]+>', '', html).strip()
    except:
        return html


def normalizar_data_publicacao(valor: object) -> str | None:
    """
    Normaliza data para UTC em formato ISO 8601.
    Retorna string ISO ou None se inválida.
    """
    # Rejeitar não-string
    if not isinstance(valor, str):
        return None
    
    valor_limpo = valor.strip()
    if not valor_limpo:
        return None
    
    try:
        # Aceitar sufixo Z
        if valor_limpo.endswith("Z"):
            valor_limpo = valor_limpo[:-1] + "+00:00"
        
        # Parsear ISO 8601
        data = datetime.fromisoformat(valor_limpo)
        
        # Converter para UTC
        if data.tzinfo is None:
            # Sem timezone: assumir UTC
            data = data.replace(tzinfo=timezone.utc)
        else:
            # Com timezone: converter para UTC
            data = data.astimezone(timezone.utc)
        
        # Validar se data não é muito futura (tolerância de 24 horas)
        agora_utc = datetime.now(timezone.utc)
        tolerancia_futura = timedelta(hours=24)  # Aceita diferença de relógio/timezone
        
        if data > agora_utc + tolerancia_futura:
            # Data futura além de 24 horas, rejeitar
            return None
        
        # Retornar em formato consistente UTC (com Z)
        # Remover microsegundos se houver e usar formato com Z
        data_sem_micro = data.replace(microsecond=0)
        iso_str = data_sem_micro.isoformat()
        # Garantir que termina com Z
        if iso_str.endswith("+00:00"):
            iso_str = iso_str[:-6] + "Z"
        elif not iso_str.endswith("Z"):
            iso_str += "Z"
        return iso_str
    
    except (ValueError, TypeError, AttributeError):
        return None


def chave_ordenacao_data(vaga: dict) -> tuple:
    """
    Gera chave de ordenação segura para vagas.
    Ordena por: data DESC → fonte → id → url.
    Datas inválidas/ausentes ficam por último.
    """
    data_pub = vaga.get("data_publicacao")
    
    if data_pub:
        try:
            dt = datetime.fromisoformat(data_pub.replace("Z", "+00:00"))
            timestamp = -dt.timestamp()  # Negativo para desc
        except (ValueError, TypeError, AttributeError):
            timestamp = float('inf')
    else:
        timestamp = float('inf')
    
    return (
        timestamp,
        vaga.get("fonte", ""),
        vaga.get("id_externo", ""),
        vaga.get("url_candidatura", ""),
    )


def localizacao_global_generica(localizacao: str) -> bool:
    """
    Verifica se localização é genérica (sem qualificador geográfico).
    """
    loc_norm = normalizar_texto_comparacao(localizacao)
    
    # Termos genéricos puramente remotos (com hyphen ou espaço considerado)
    termos_genericos = {
        "remote", "fully remote", "work remotely", "anywhere",
        "worldwide", "global", "all locations", "fully"
    }
    
    # Remover termos genéricos do texto
    residual = loc_norm
    for termo in termos_genericos:
        # Substituir o termo
        residual = residual.replace(termo, " ")
    
    # Remover hyphens e limpar espaços extras
    residual = residual.replace("-", " ")
    residual = " ".join(residual.split())
    
    # Se residual está vazio ou só tem espaços, é genérico
    return len(residual) == 0


def localizacao_brasileira(localizacao: str, cidade_busca: str, estado_busca: str) -> bool:
    """
    Verifica se localização é brasileira ou compatível com busca.
    """
    loc_norm = normalizar_texto_comparacao(localizacao)
    cidade_norm = normalizar_texto_comparacao(cidade_busca)
    estado_norm = normalizar_texto_comparacao(estado_busca)
    
    # Verificar marcadores brasileiros com token boundaries
    marcadores_brasil = ["brazil", "brasil", "brazilian", "br"]
    for marcador in marcadores_brasil:
        if re.search(r'\b' + re.escape(marcador) + r'\b', loc_norm):
            return True
    
    # Verificar localização brasileira específica
    estado_expandido = UF_MAP.get(estado_norm[:2] if len(estado_norm) >= 2 else "", "")
    
    partes_local = [p.strip() for p in loc_norm.replace(",", ";").split(";")]
    
    for parte in partes_local:
        parte_norm = normalizar_texto_comparacao(parte)
        
        # Verificar cidade (token boundary)
        if re.search(r'\b' + re.escape(cidade_norm) + r'\b', parte_norm):
            return True
        
        # Verificar UF (token boundary)
        if re.search(r'\b' + re.escape(estado_norm) + r'\b', parte_norm):
            return True
        
        if estado_expandido and re.search(r'\b' + re.escape(estado_expandido) + r'\b', parte_norm):
            return True
    
    return False


def localizacao_remota_compativel(localizacao: str, cidade_busca: str, estado_busca: str) -> bool:
    """
    Verifica se localização remota é compatível (allowlist).
    Estratégia: genérico OK, Brasil OK, qualquer coisa diferente REJEITA.
    """
    if not localizacao or localizacao == "Local não informado":
        return True
    
    loc_norm = normalizar_texto_comparacao(localizacao)
    
    # 1. Localização genérica (remote, worldwide, etc.) é aceita
    if localizacao_global_generica(localizacao):
        return True
    
    # 2. Localização brasileira é aceita
    if localizacao_brasileira(localizacao, cidade_busca, estado_busca):
        return True
    
    # 3. América Latina COM Brasil explícito é aceita
    if "latin america" in loc_norm or "latinoamerica" in loc_norm or "latam" in loc_norm:
        if any(re.search(r'\b' + re.escape(m) + r'\b', loc_norm) for m in ["brazil", "brasil", "including"]):
            return True
    
    # 4. Qualquer outro qualificador geográfico é REJEITADO (allowlist)
    # Verificar se contém país/região/localidade
    # Indicadores: tem "region", "country", "area", "zone", ou é uma localidade conhecida
    indicadores_geo = [
        "region", "country", "area", "zone", "usa", "us", "canada", "uk", "europe", 
        "asia", "africa", "apac", "emea", "japan", "singapore", "india", "australia",
        "germany", "france", "spain", "portugal", "mexico", "argentina", "chile", "colombia",
        "new zealand", "south africa", "mars"  # Rejeita até "Mars" conservadoramente
    ]
    
    for indicador in indicadores_geo:
        if re.search(r'\b' + re.escape(indicador) + r'\b', loc_norm):
            return False
    
    # 5. Qualquer localização com conteúdo geográfico desconhecido: REJEITA (conservador)
    # Se tem algo além de termos genéricos e não é Brasil, rejeita
    termos_genericos = ["remote", "fully", "work", "position", "role", "at"]
    residual = loc_norm
    
    for termo in termos_genericos:
        residual = residual.replace(termo, "").strip()
    
    # Se há resíduo (localidade desconhecida), rejeita
    if residual:
        return False
    
    return True


def gerar_variantes_token(token: str) -> set[str]:
    """
    Gera variantes de um token (gênero, número).
    """
    variantes = {token}
    
    # Gênero: -dora/-dor (específico)
    if token.endswith("dora"):
        variantes.add(token[:-4] + "dor")
    elif token.endswith("dor"):
        variantes.add(token[:-3] + "dora")
    
    # Gênero: -a/-o (genérico, só se não -dora/-dor)
    elif token.endswith("a"):
        variantes.add(token[:-1] + "o")
    elif token.endswith("o"):
        variantes.add(token[:-1] + "a")
    
    # Plural: adicionar 'es' para terminos em -or, 'as' para -a, 'os' para -o
    if token.endswith("or"):
        variantes.add(token + "es")
    elif token.endswith("a"):
        variantes.add(token + "s")
    elif token.endswith("o"):
        variantes.add(token + "s")
    elif not token.endswith(("s", "z")):
        variantes.add(token + "s")
    
    return variantes


def tokens_correspondem(tokens_busca: list[str], tokens_titulo: list[str]) -> bool:
    """
    Verifica se todos os tokens de busca estão em tokens do título (com variantes).
    """
    for token_busca in tokens_busca:
        variantes = gerar_variantes_token(token_busca)
        
        if not any(var in tokens_titulo for var in variantes):
            return False
    
    return True


def sequencia_tokens_corresponde(sequencia_busca: list[str], sequencia_titulo: list[str]) -> bool:
    """
    Verifica se sequência de tokens existe no título.
    """
    if not sequencia_busca:
        return True
    
    for i in range(len(sequencia_titulo) - len(sequencia_busca) + 1):
        # Comparar sequência com variantes
        correspondencia = True
        
        for j, token_busca in enumerate(sequencia_busca):
            variantes = gerar_variantes_token(token_busca)
            
            if sequencia_titulo[i + j] not in variantes:
                correspondencia = False
                break
        
        if correspondencia:
            return True
    
    return False


def cargo_matcheia(titulo: str, conteudo: str, cargo_busca: str) -> bool:
    """
    Verifica correspondência de cargo usando tokenização.
    """
    if not cargo_busca.strip():
        return True
    
    # Tokenizar todos
    tokens_titulo = tokenizar_texto(titulo)
    tokens_conteudo = tokenizar_texto(conteudo)
    tokens_cargo = tokenizar_texto(cargo_busca)
    
    # Remover stopwords
    tokens_titulo = [t for t in tokens_titulo if t not in STOPWORDS]
    tokens_conteudo = [t for t in tokens_conteudo if t not in STOPWORDS]
    tokens_cargo = [t for t in tokens_cargo if t not in STOPWORDS]
    
    if not tokens_cargo:
        return True
    
    # Regra 1: Todos os tokens de cargo no título
    if tokens_correspondem(tokens_cargo, tokens_titulo):
        return True
    
    # Regra 2: Sequência de tokens no título
    if sequencia_tokens_corresponde(tokens_cargo, tokens_titulo):
        return True
    
    # Regra 3: Token principal no título + complementares em título/conteúdo
    if len(tokens_cargo) >= 1:
        termo_principal = tokens_cargo[0]
        variantes_principal = gerar_variantes_token(termo_principal)
        
        # Termo principal está no título?
        if any(var in tokens_titulo for var in variantes_principal):
            if len(tokens_cargo) == 1:
                return True
            
            # Verificar complementares
            complementares = tokens_cargo[1:]
            tokens_completos = tokens_titulo + tokens_conteudo
            
            if tokens_correspondem(complementares, tokens_completos):
                return True
    
    return False


def vaga_corresponde_localizacao(
    local_vaga: str,
    cidade_busca: str,
    estado_busca: str,
    modalidade_vaga: str,
) -> bool:
    """
    Verifica se vaga corresponde aos filtros de localização.
    """
    
    # Para Remoto: usar validação allowlist
    if modalidade_vaga == "Remoto":
        return localizacao_remota_compativel(local_vaga, cidade_busca, estado_busca)
    
    # Para Presencial e Híbrido: filtrar por localização específica
    local_norm = normalizar_texto_comparacao(local_vaga)
    cidade_norm = normalizar_texto_comparacao(cidade_busca)
    estado_norm = normalizar_texto_comparacao(estado_busca)
    
    # Se não informado, aceitar (vaga genérica)
    if not local_vaga or local_vaga == "Local não informado":
        return True
    
    # Normalizar UF para nome completo
    estado_expandido = UF_MAP.get(estado_norm[:2] if len(estado_norm) >= 2 else "", "")
    
    # Buscar correspondência com token boundaries
    partes_local = [p.strip() for p in local_norm.replace(",", ";").split(";")]
    
    for parte in partes_local:
        parte_norm = normalizar_texto_comparacao(parte)
        
        # Verificar cidade (token boundary)
        if re.search(r'\b' + re.escape(cidade_norm) + r'\b', parte_norm):
            return True
        
        # Verificar estado (token boundary)
        if re.search(r'\b' + re.escape(estado_norm) + r'\b', parte_norm):
            return True
        
        if estado_expandido and re.search(r'\b' + re.escape(estado_expandido) + r'\b', parte_norm):
            return True
    
    # Se nenhuma correspondência e localização específica informada, rejeitar
    if local_vaga and local_vaga != "Local não informado":
        return False
    
    return True


def detectar_modalidade(titulo: str, conteudo: str, location: str | None) -> str:
    """
    Detecta modalidade com prioridade e tratamento de negações.
    """
    
    titulo_lower = (titulo or "").lower()
    conteudo_lower = (conteudo or "").lower()
    location_lower = (location or "").lower()
    
    # Prioridade 2: Localização
    if "remote" in location_lower or "remoto" in location_lower:
        if "not remote" not in location_lower and "não é remoto" not in location_lower:
            return "Remoto"
    
    # Prioridade 3: Título
    if "hybrid" in titulo_lower or "híbrido" in titulo_lower:
        return "Híbrido"
    if "remote" in titulo_lower or "remoto" in titulo_lower:
        if "not remote" not in titulo_lower and "não é remoto" not in titulo_lower:
            return "Remoto"
    if "on-site" in titulo_lower or "presencial" in titulo_lower:
        return "Presencial"
    
    # Prioridade 4: Início da descrição
    conteudo_inicio = conteudo_lower[:500] if conteudo_lower else ""
    
    if "hybrid" in conteudo_inicio or "híbrido" in conteudo_inicio:
        if "remote" in conteudo_inicio:
            return "Híbrido"
        return "Híbrido"
    
    if "remote" in conteudo_inicio or "remoto" in conteudo_inicio:
        if "not remote" not in conteudo_inicio and "não é remoto" not in conteudo_inicio and "remote work is not available" not in conteudo_inicio:
            return "Remoto"
    
    if "on-site" in conteudo_inicio or "presencial" in conteudo_inicio:
        return "Presencial"
    
    # Prioridade 5: Descrição completa
    if "hybrid" in conteudo_lower or "híbrido" in conteudo_lower:
        return "Híbrido"
    if "remote" in conteudo_lower or "remoto" in conteudo_lower:
        if "not remote" not in conteudo_lower and "não é remoto" not in conteudo_lower and "remote work is not available" not in conteudo_lower:
            return "Remoto"
    if "on-site" in conteudo_lower or "presencial" in conteudo_lower:
        return "Presencial"
    
    return "Não informada"


def construir_local(location_name: str | None) -> str:
    """Constrói localização sem inventar dados."""
    if location_name and location_name.strip():
        return location_name.strip()
    return "Local não informado"


async def buscar_board_greenhouse(board_token: str, client: httpx.AsyncClient) -> list[dict] | None:
    """
    Busca vagas de um board Greenhouse com cache.
    Retorna lista de jobs ou None em erro.
    """
    
    # Tentar obter do cache
    cached = await _cache.get(board_token)
    if cached is not None:
        logger.info(f"Greenhouse: usando cache para {board_token}")
        return cached
    
    # Adquirir lock para evitar requisições duplicadas
    lock = await _cache.get_lock(board_token)
    
    async with lock:
        # Verificar novamente
        cached = await _cache.get(board_token)
        if cached is not None:
            return cached
        
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
            response = await client.get(
                url,
                headers={"User-Agent": "SearchEmprego/1.0 (+http://localhost)"},
                timeout=15
            )
            
            if response.status_code == 404:
                logger.debug(f"Greenhouse {board_token}: 404 não encontrado")
                return []
            
            if response.status_code == 429:
                logger.warning(f"Greenhouse {board_token}: rate limit")
                return []
            
            if response.status_code >= 500:
                logger.warning(f"Greenhouse {board_token}: erro {response.status_code}")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            jobs = data.get("jobs", [])
            if not isinstance(jobs, list):
                return []
            
            # Salvar no cache
            await _cache.set(board_token, jobs)
            logger.debug(f"Greenhouse {board_token}: {len(jobs)} vagas em cache")
            
            return jobs
        
        except httpx.TimeoutException:
            logger.warning(f"Greenhouse {board_token}: timeout")
            return []
        except httpx.RequestError:
            logger.warning(f"Greenhouse {board_token}: erro conexão")
            return []
        except ValueError:
            logger.warning(f"Greenhouse {board_token}: JSON inválido")
            return []
        except Exception as e:
            logger.error(f"Greenhouse {board_token}: erro inesperado: {str(e)[:100]}")
            return []


async def buscar_vagas_greenhouse(
    cargo: str,
    cidade: str,
    estado: str,
    modalidade: str,
    pagina: int = 1,
    max_dias: int | None = None,
    incluir_pcd: bool = False,
    boards: list[str] | None = None,
):
    """
    Busca vagas na Greenhouse consultando múltiplos boards.
    """
    
    if not boards or len(boards) == 0:
        return {
            "fonte": "Greenhouse",
            "total_fonte": 0,
            "vagas": [],
        }
    
    vagas_candidatas = []
    
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Buscar todos os boards em paralelo com concorrência limitada
            semaphore = asyncio.Semaphore(MAX_BOARDS_PER_REQUEST)
            
            async def buscar_board_safe(board_token: str):
                async with semaphore:
                    return await buscar_board_greenhouse(board_token, client)
            
            tasks = [
                buscar_board_safe(board)
                for board in boards[:MAX_BOARDS_PER_REQUEST]
            ]
            resultados = await asyncio.gather(*tasks, return_exceptions=False)
            
            # Coletar todas as vagas candidatas
            for board_idx, resultado in enumerate(resultados):
                if not resultado:
                    continue
                
                for job in resultado:
                    if not isinstance(job, dict):
                        continue
                    
                    titulo = job.get("title", "").strip()
                    if not titulo:
                        continue
                    
                    url_candidatura = job.get("absolute_url", "").strip()
                    if not url_candidatura or not url_candidatura.startswith(("http://", "https://")):
                        continue
                    
                    conteudo = job.get("content", "")
                    conteudo_limpo = remover_html(conteudo)
                    
                    # Filtro de cargo
                    if not cargo_matcheia(titulo, conteudo_limpo, cargo):
                        continue
                    
                    location_obj = job.get("location", {})
                    location_name = (
                        location_obj.get("name", "")
                        if isinstance(location_obj, dict)
                        else ""
                    )
                    local = construir_local(location_name)

                    # Modalidade
                    vaga_modalidade = detectar_modalidade(
                        titulo,
                        conteudo_limpo,
                        location_name,
                    )

                    # Alguns boards não publicam workplaceType. Quando há uma
                    # localização física explícita compatível e nenhum indício
                    # de remoto/híbrido, a vaga pode ser tratada como presencial.
                    if (
                        modalidade == "Presencial"
                        and vaga_modalidade == "Não informada"
                        and local != "Local não informado"
                        and vaga_corresponde_localizacao(
                            local,
                            cidade,
                            estado,
                            "Presencial",
                        )
                    ):
                        vaga_modalidade = "Presencial"
                    
                    # Filtro de modalidade estrito
                    if modalidade != "Presencial":
                        if vaga_modalidade == "Não informada":
                            continue
                        if vaga_modalidade != modalidade:
                            continue
                    else:
                        if vaga_modalidade != "Presencial":
                            continue
                    
                    # Filtro de localização
                    if not vaga_corresponde_localizacao(local, cidade, estado, vaga_modalidade):
                        continue
                    
                    # PCD
                    eh_pcd = vaga_eh_pcd(f"{titulo} {conteudo_limpo}")
                    if eh_pcd and not incluir_pcd:
                        continue
                    
                    # Data: normalizar SEMPRE
                    data_raw = job.get("updated_at")
                    data_normalizada = normalizar_data_publicacao(data_raw)
                    
                    # Filtrar por max_dias se informado
                    if data_normalizada and max_dias:
                        try:
                            data_pub = datetime.fromisoformat(data_normalizada.replace("Z", "+00:00"))
                            data_agora = datetime.now(timezone.utc)
                            dias = (data_agora - data_pub).days
                            
                            if dias > max_dias:
                                continue
                        except (ValueError, TypeError):
                            continue
                    
                    job_id = job.get("id")
                    id_externo = str(job_id) if job_id else url_candidatura
                    
                    # Adicionar vaga
                    vagas_candidatas.append({
                        "id_externo": id_externo,
                        "titulo": titulo,
                        "empresa": boards[board_idx].replace("-", " ").title(),
                        "local": local,
                        "modalidade": vaga_modalidade,
                        "url_candidatura": url_candidatura,
                        "data_publicacao": data_normalizada,
                        "candidatura_simplificada": False,
                        "ja_candidatado": False,
                        "eh_pcd": eh_pcd,
                        "fonte": "Greenhouse",
                        "_board_token": boards[board_idx],
                    })
        
        # Remover duplicatas
        vagas_unicas = []
        urls_vistas = set()
        identidades_vistas = set()
        
        for vaga in vagas_candidatas:
            url_norm = vaga.get("url_candidatura", "").lower()
            identidade = (
                normalizar_texto_comparacao(vaga.get("titulo")),
                normalizar_texto_comparacao(vaga.get("empresa")),
                normalizar_texto_comparacao(vaga.get("local")),
            )
            
            if url_norm in urls_vistas or identidade in identidades_vistas:
                continue
            
            urls_vistas.add(url_norm)
            identidades_vistas.add(identidade)
            vagas_unicas.append(vaga)
        
        # Ordenação determinística
        vagas_unicas.sort(key=chave_ordenacao_data)
        
        # Remover campo interno
        for vaga in vagas_unicas:
            vaga.pop("_board_token", None)
        
        # Paginar
        inicio = (pagina - 1) * PAGE_SIZE
        fim = pagina * PAGE_SIZE
        vagas_pagina = vagas_unicas[inicio:fim]
        
        return {
            "fonte": "Greenhouse",
            "total_fonte": len(vagas_unicas),
            "vagas": vagas_pagina,
        }
    
    except Exception as error:
        logger.error(f"Greenhouse erro geral: {str(error)[:100]}")
        return {
            "fonte": "Greenhouse",
            "total_fonte": 0,
            "vagas": [],
        }


async def limpar_cache_greenhouse():
    """Limpa cache expirado. Usar em testes."""
    await _cache.cleanup()
