def buscar_vagas_mock(cargo: str, cidade: str, estado: str, modalidade: str):
    return [
        {
            "titulo": f"{cargo} - Urgente",
            "empresa": "Logística & Cia",
            "local": f"{cidade}, {estado}",
            "modalidade": modalidade,
            "url_candidatura": "https://gupy.io/vagas/exemplo123",
            "candidatura_simplificada": False,
            "fonte": "Mock"
        },
        {
            "titulo": f"{cargo} Junior",
            "empresa": "Tech Solutions",
            "local": f"{cidade}, {estado}",
            "modalidade": modalidade,
            "url_candidatura": "https://infojobs.com.br/vaga/exemplo456",
            "candidatura_simplificada": True,
            "fonte": "Mock"
        }
    ]