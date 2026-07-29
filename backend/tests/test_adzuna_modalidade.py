import pytest

from app.services.adzuna_service import (
    modalidade_adzuna_compativel,
    normalizar_modalidade,
)


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("Vaga 100% remota", "Remoto"),
        ("Modelo híbrido em São Paulo", "Híbrido"),
        ("Trabalho presencial", "Presencial"),
        ("Descrição sem modalidade", "Não informada"),
    ],
)
def test_detecta_modalidade_adzuna(texto, esperada):
    assert normalizar_modalidade(texto) == esperada


def test_busca_remota_rejeita_vaga_hibrida():
    aceita, detectada = modalidade_adzuna_compativel(
        "Desenvolvedor em modelo híbrido",
        "Remoto",
    )
    assert not aceita
    assert detectada == "Híbrido"


def test_busca_remota_rejeita_modalidade_nao_informada():
    aceita, detectada = modalidade_adzuna_compativel(
        "Desenvolvedor Python",
        "Remoto",
    )
    assert not aceita
    assert detectada == "Não informada"


def test_busca_presencial_aceita_nao_informada_como_presencial():
    aceita, detectada = modalidade_adzuna_compativel(
        "Auxiliar administrativo em São Paulo",
        "Presencial",
    )
    assert aceita
    assert detectada == "Presencial"
