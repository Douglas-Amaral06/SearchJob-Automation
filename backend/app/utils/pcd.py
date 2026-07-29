"""
Detecção de vagas exclusivas, afirmativas ou reservadas para Pessoas com Deficiência.
Módulo neutro compartilhado entre todas as fontes de vagas.
"""
import re
import unicodedata


def normalizar_texto_pcd(texto: str | None) -> str:
    """
    Normaliza texto removendo acentos, convertendo para minúsculas e espaços múltiplos.
    """
    if not texto:
        return ""
    
    # Converter para minúsculas
    texto = texto.lower().strip()
    
    # Remover acentos
    nfd = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    
    # Remover pontuação desnecessária, manter apenas espaços simples
    sem_acento = re.sub(r"\s+", " ", sem_acento)
    
    return sem_acento


def vaga_eh_pcd(texto: str | None) -> bool:
    """
    Detecta se uma vaga é EXCLUSIVA, RESERVADA, AFIRMATIVA ou DESTINADA especificamente a PCD.
    
    Retorna True apenas quando há forte evidência de exclusividade/afinidade.
    Ignora políticas genéricas de inclusão, diversidade ou benefícios.
    
    Args:
        texto: Título + descrição da vaga
    
    Returns:
        True se vaga é exclusiva/afirmativa/reservada para PCD
        False caso contrário
    """
    
    if not texto or not isinstance(texto, str):
        return False
    
    texto_norm = normalizar_texto_pcd(texto)
    
    if not texto_norm:
        return False
    
    # Padrões que indicam EXCLUSIVIDADE/AFINIDADE explícita
    padroes_exclusivos = [
        # Exclusivo
        r"\bvaga\s+exclusiva\s+(para|a)\s+(pcd|pessoas?\s+com\s+deficiencia)",
        r"\bexclusiva\s+(para|a)\s+(pcd|pessoas?\s+com\s+deficiencia)",
        r"\bpcd\s+exclusiva",
        r"\bvaga\s+pcd\b",
        
        # Afirmativo
        r"\bvaga\s+afirmativa\s+(para|a)\s+(pcd|pessoas?\s+com\s+deficiencia)",
        r"\bvaga\s+afirmativa\s+(para|a)\s+profissiona(?:l|is)\s+com\s+deficiencia",
        r"\boportunidade\s+afirmativa\s+(para|a)\s+(pcd|pessoas?\s+com\s+deficiencia)",
        r"\boportunidade\s+afirmativa\s+(para|a)\s+profissiona(?:l|is)\s+com\s+deficiencia",
        r"\bafirmativa\s+(para|a)\s+(pcd|pessoas?\s+com\s+deficiencia)",
        r"\bafirmativa\s+(para|a)\s+profissiona(?:l|is)\s+com\s+deficiencia",
        
        # Reservado
        r"\bvaga\s+reservada\s+(para|a)\s+(pcd|pessoas?\s+com\s+deficiencia)",
        r"\breservada\s+(para|a)\s+(pcd|pessoas?\s+com\s+deficiencia)",
        
        # Destinado explicitamente
        r"\bvaga\s+destinada\s+exclusivamente\s+a\s+(pcd|pessoas?\s+com\s+deficiencia)",
        r"\besta\s+posicao\s+e\s+destinada\s+especificamente\s+a\s+(pcd|pessoas?\s+com\s+deficiencia)",
        r"\bprocesso\s+seletivo\s+exclusivo\s+(para|a)\s+(pcd|pessoas?\s+com\s+deficiencia)",
        
        # PCD no título com contexto de vaga
        r"\bauxiliar\s+administrativo\s+pcd\b",
        r"\banalista\s+pcd\b",
        r"\bdesenvolvedor\s+pcd\b",
        r"\bvendedor\s+pcd\b",
        r"^pcd\s+-",  # Começa com "PCD -"
    ]
    
    # Verificar padrões exclusivos
    for padrao in padroes_exclusivos:
        if re.search(padrao, texto_norm):
            return True
    
    # Padrões que indicam política genérica de inclusão (IGNORAR)
    padroes_inclusao_generica = [
        r"\bvalorizamos\s+diversidade",
        r"\bpessoas\s+com\s+deficiencia\s+sao\s+bem-vindas",
        r"\btodas?\s+as\s+pessoas\s+podem\s+se\s+candidatar",
        r"\bincluindo\s+pcd",
        r"\bpromovemos\s+inclusao",
        r"\bnao\s+fazemos\s+discriminacao",
        r"\bambiente\s+inclusivo",
        r"\bpcd\s+sao\s+bem-vindas",
        r"\bsao\s+bem-vindas\s+a\s+se\s+candidatar",
        r"\bpolicy\s+diversidade",
        r"\bcomprometidos?\s+com\s+inclusao",
    ]
    
    # Se encontra apenas política genérica, retorna False
    for padrao in padroes_inclusao_generica:
        if re.search(padrao, texto_norm):
            # Mas continua verificando se também tem exclusividade
            pass
    
    # Se menção de benefício (coparticipação, plano de saúde), é política, não exclusividade
    if re.search(r"\b(coparticipacao|coparticipacao|plano\s+de\s+saude|beneficio)", texto_norm):
        # Somente se também tiver exclusividade, marcar como PCD
        for padrao in padroes_exclusivos:
            if re.search(padrao, texto_norm):
                return True
        return False
    
    return False
