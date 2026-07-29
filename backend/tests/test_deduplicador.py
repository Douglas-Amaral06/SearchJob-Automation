from app.utils.deduplicador import remover_vagas_duplicadas


def criar_vaga(
    titulo: str,
    empresa: str,
    local: str,
    url: str,
    fonte: str,
):
    return {
        "id_externo": url,
        "titulo": titulo,
        "empresa": empresa,
        "local": local,
        "modalidade": "Presencial",
        "url_candidatura": url,
        "data_publicacao": None,
        "candidatura_simplificada": False,
        "ja_candidatado": False,
        "eh_pcd": False,
        "fonte": fonte,
    }


def test_remove_vagas_com_mesma_identidade():
    vagas = [
        criar_vaga(
            "Auxiliar Administrativo",
            "Empresa Exemplo",
            "Guarulhos, SP",
            "https://adzuna.example/vaga/1?tracking=abc",
            "Adzuna",
        ),
        criar_vaga(
            "Auxiliar Administrativo",
            "Empresa Exemplo",
            "Guarulhos - SP",
            "https://jooble.example/vaga/999",
            "Jooble",
        ),
    ]

    resultado = remover_vagas_duplicadas(vagas)

    assert len(resultado) == 1


def test_remove_urls_iguais_com_parametros_diferentes():
    vagas = [
        criar_vaga(
            "Vaga A",
            "Empresa A",
            "São Paulo",
            "https://example.com/jobs/123?source=adzuna",
            "Adzuna",
        ),
        criar_vaga(
            "Outro título",
            "Outra empresa",
            "Outro local",
            "https://example.com/jobs/123?source=jooble",
            "Jooble",
        ),
    ]

    resultado = remover_vagas_duplicadas(vagas)

    assert len(resultado) == 1


def test_preserva_vagas_diferentes():
    vagas = [
        criar_vaga(
            "Analista",
            "Empresa A",
            "São Paulo",
            "https://example.com/jobs/1",
            "Adzuna",
        ),
        criar_vaga(
            "Analista",
            "Empresa B",
            "São Paulo",
            "https://example.com/jobs/2",
            "Adzuna",
        ),
    ]

    resultado = remover_vagas_duplicadas(vagas)

    assert len(resultado) == 2