import pytest

from app.services import job_aggregator
from app.services.job_aggregator import (
    buscar_vagas_agregadas,
    normalizar_cidade_consulta,
)


def test_sp_capital_vira_sao_paulo():
    assert normalizar_cidade_consulta("SP Capital", "SP") == "São Paulo"


def test_sao_paulo_capital_vira_sao_paulo():
    assert normalizar_cidade_consulta("São Paulo Capital", "SP") == "São Paulo"


def test_cidade_comum_e_preservada():
    assert normalizar_cidade_consulta("Guarulhos", "SP") == "Guarulhos"


@pytest.mark.asyncio
async def test_busca_pode_restringir_fontes_da_campanha(monkeypatch):
    chamadas = []

    async def fonte_falsa(**kwargs):
        chamadas.append(kwargs)
        return {"fonte": "Adzuna", "total_fonte": 1, "vagas": []}

    monkeypatch.setattr(job_aggregator, "buscar_vagas_adzuna", fonte_falsa)
    monkeypatch.setattr(job_aggregator, "JOOBLE_ENABLED", True)

    async def jooble_nao_deveria_ser_chamado(**kwargs):
        raise AssertionError("Jooble não foi selecionada")

    monkeypatch.setattr(
        job_aggregator,
        "buscar_vagas_jooble",
        jooble_nao_deveria_ser_chamado,
    )

    await buscar_vagas_agregadas(
        cargo="Auxiliar",
        cidade="São Paulo",
        estado="SP",
        modalidade="Presencial",
        fontes_selecionadas={"Adzuna"},
    )

    assert len(chamadas) == 1
