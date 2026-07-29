from datetime import datetime, timedelta, timezone

import pytest

from app.services import jobicy_service, remotive_service
from app.services.remote_jobs_utils import (
    cargo_remoto_compativel,
    consultas_equivalentes_cargo,
    localizacao_remota_compativel,
    normalizar_data,
    remover_html,
    url_publica_valida,
)


def data_recente() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()


def test_alias_auxiliar_administrativo_em_ingles():
    assert "administrative assistant" in consultas_equivalentes_cargo(
        "Auxiliar Administrativo"
    )
    assert cargo_remoto_compativel(
        "Administrative Assistant",
        "",
        "Auxiliar Administrativo",
    )


def test_cargo_incompativel_nao_e_aceito_so_pela_descricao():
    assert not cargo_remoto_compativel(
        "Project Manager",
        "Our developer team uses Python.",
        "Desenvolvedor",
    )


@pytest.mark.parametrize(
    "local",
    ["Brazil", "Brasil", "BR", "LATAM", "Latin America", "Worldwide", "Anywhere"],
)
def test_localizacoes_remotas_compativeis_com_brasil(local):
    assert localizacao_remota_compativel(local)


@pytest.mark.parametrize(
    "local",
    ["USA only", "Europe", "Canada", "Japan", "United Kingdom"],
)
def test_restricoes_estrangeiras_sao_rejeitadas(local):
    assert not localizacao_remota_compativel(local)


def test_utilitarios_de_normalizacao():
    assert remover_html("<p>Olá&nbsp;<strong>mundo</strong></p>") == "Olá mundo"
    assert url_publica_valida("https://example.com/job/1")
    assert not url_publica_valida("javascript:alert(1)")
    assert normalizar_data(data_recente()).endswith("Z")


@pytest.mark.asyncio
async def test_jobicy_normaliza_filtra_e_pagina(monkeypatch):
    feed = [
        {
            "id": numero,
            "url": f"https://jobicy.com/jobs/{numero}",
            "jobTitle": "Administrative Assistant",
            "companyName": "Empresa Exemplo",
            "jobGeo": "Brazil",
            "jobDescription": "<p>Rotinas administrativas.</p>",
            "pubDate": data_recente(),
        }
        for numero in range(25)
    ]

    async def feed_falso():
        return feed

    monkeypatch.setattr(jobicy_service, "_obter_feed", feed_falso)
    resultado = await jobicy_service.buscar_vagas_jobicy(
        cargo="Auxiliar Administrativo",
        cidade="São Paulo",
        estado="SP",
        modalidade="Remoto",
        pagina=2,
    )

    assert resultado["fonte"] == "Jobicy"
    assert resultado["total_fonte"] == 25
    assert len(resultado["vagas"]) == 5
    assert all(vaga["modalidade"] == "Remoto" for vaga in resultado["vagas"])
    assert all(vaga["fonte"] == "Jobicy" for vaga in resultado["vagas"])


@pytest.mark.asyncio
async def test_jobicy_nao_consulta_feed_para_modalidade_presencial(monkeypatch):
    async def nao_deveria_ser_chamado():
        raise AssertionError("feed não deveria ser consultado")

    monkeypatch.setattr(jobicy_service, "_obter_feed", nao_deveria_ser_chamado)
    resultado = await jobicy_service.buscar_vagas_jobicy(
        "Auxiliar", "São Paulo", "SP", "Presencial"
    )
    assert resultado["vagas"] == []


@pytest.mark.asyncio
async def test_remotive_rejeita_local_estrangeiro_e_url_invalida(monkeypatch):
    feed = [
        {
            "id": 1,
            "url": "https://remotive.com/remote-jobs/1",
            "title": "Software Developer",
            "company_name": "Brasil Tech",
            "candidate_required_location": "LATAM",
            "description": "Build software.",
            "publication_date": data_recente(),
        },
        {
            "id": 2,
            "url": "https://remotive.com/remote-jobs/2",
            "title": "Software Developer",
            "company_name": "US Tech",
            "candidate_required_location": "USA only",
            "description": "Build software.",
            "publication_date": data_recente(),
        },
        {
            "id": 3,
            "url": "javascript:alert(1)",
            "title": "Software Developer",
            "company_name": "Inválida",
            "candidate_required_location": "Worldwide",
            "description": "Build software.",
            "publication_date": data_recente(),
        },
    ]

    async def feed_falso():
        return feed

    monkeypatch.setattr(remotive_service, "_obter_feed", feed_falso)
    resultado = await remotive_service.buscar_vagas_remotive(
        "Desenvolvedor", "São Paulo", "SP", "Remoto"
    )

    assert resultado["total_fonte"] == 1
    assert resultado["vagas"][0]["empresa"] == "Brasil Tech"
    assert resultado["vagas"][0]["id_externo"] == "remotive:1"


@pytest.mark.asyncio
async def test_remotive_aplica_filtro_de_data(monkeypatch):
    antiga = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

    async def feed_falso():
        return [
            {
                "id": 1,
                "url": "https://remotive.com/remote-jobs/1",
                "title": "Data Analyst",
                "company_name": "Empresa",
                "candidate_required_location": "Worldwide",
                "description": "",
                "publication_date": antiga,
            }
        ]

    monkeypatch.setattr(remotive_service, "_obter_feed", feed_falso)
    resultado = await remotive_service.buscar_vagas_remotive(
        "Analista de Dados",
        "",
        "",
        "Remoto",
        max_dias=7,
    )
    assert resultado["vagas"] == []
