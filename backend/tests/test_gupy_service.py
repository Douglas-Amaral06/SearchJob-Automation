import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from app.services.gupy_service import (
    interpretar_workplace_type,
    normalizar_texto_comparacao,
    normalizar_uf,
    normalizar_cidade_busca,
    construir_local,
    vaga_matcheia_filtros,
)


class TestInterpretarWorkplaceType:
    def test_remote_variations(self):
        assert interpretar_workplace_type("remote") == "Remoto"
        assert interpretar_workplace_type("remoto") == "Remoto"
        assert interpretar_workplace_type("home office") == "Remoto"
        assert interpretar_workplace_type("REMOTE") == "Remoto"

    def test_hybrid_variations(self):
        assert interpretar_workplace_type("hybrid") == "Híbrido"
        assert interpretar_workplace_type("híbrido") == "Híbrido"
        assert interpretar_workplace_type("hibrido") == "Híbrido"
        assert interpretar_workplace_type("HYBRID") == "Híbrido"

    def test_on_site_variations(self):
        assert interpretar_workplace_type("on-site") == "Presencial"
        assert interpretar_workplace_type("onsite") == "Presencial"
        assert interpretar_workplace_type("on site") == "Presencial"
        assert interpretar_workplace_type("presencial") == "Presencial"
        assert interpretar_workplace_type("PRESENCIAL") == "Presencial"

    def test_unknown_values(self):
        assert interpretar_workplace_type("unknown") == "Não informada"
        assert interpretar_workplace_type(None) == "Não informada"
        assert interpretar_workplace_type("") == "Não informada"


class TestNormalizarTextoComparacao:
    def test_accent_removal(self):
        assert normalizar_texto_comparacao("São Paulo") == "sao paulo"
        assert normalizar_texto_comparacao("São Paulo") == normalizar_texto_comparacao(
            "Sao Paulo"
        )

    def test_case_insensitive(self):
        assert normalizar_texto_comparacao("SP") == normalizar_texto_comparacao("sp")

    def test_whitespace_handling(self):
        assert normalizar_texto_comparacao("  São Paulo  ") == "sao paulo"

    def test_none_and_empty(self):
        assert normalizar_texto_comparacao(None) == ""
        assert normalizar_texto_comparacao("") == ""


class TestNormalizacaoLocalizacao:
    def test_nome_completo_do_estado_equivale_a_sigla(self):
        assert normalizar_uf("São Paulo") == "sp"
        assert normalizar_uf("SP") == "sp"

    def test_sp_capital_equivale_a_sao_paulo(self):
        assert normalizar_cidade_busca("SP Capital", "SP") == "sao paulo"
        assert normalizar_cidade_busca("São Paulo Capital", "SP") == "sao paulo"

    def test_vaga_com_estado_por_extenso_aceita_busca_por_sigla(self):
        vaga = {
            "city": "São Paulo",
            "state": "São Paulo",
            "workplaceType": "on-site",
        }
        assert vaga_matcheia_filtros(
            vaga,
            "São Paulo",
            "SP",
            "Presencial",
        )

    def test_sp_capital_aceita_cidade_sao_paulo(self):
        vaga = {
            "city": "São Paulo",
            "state": "São Paulo",
            "workplaceType": "on-site",
        }
        assert vaga_matcheia_filtros(
            vaga,
            "SP Capital",
            "SP",
            "Presencial",
        )


class TestConstruirLocal:
    def test_city_and_state(self):
        assert construir_local("São Paulo", "SP") == "São Paulo, SP"

    def test_city_only(self):
        assert construir_local("São Paulo", None) == "São Paulo"

    def test_state_only(self):
        assert construir_local(None, "SP") == "SP"

    def test_none_both(self):
        assert construir_local(None, None) == "Local não informado"

    def test_empty_strings(self):
        assert construir_local("", "") == "Local não informado"

    def test_whitespace_only(self):
        assert construir_local("   ", "   ") == "Local não informado"


class TestVagaMatcheiaFiltros:
    def test_remoto_aceita_remoto(self):
        vaga = {
            "city": "São Paulo",
            "state": "SP",
            "workplaceType": "remote",
        }
        assert vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Remoto")

    def test_remoto_rejeita_presencial(self):
        vaga = {
            "city": "São Paulo",
            "state": "SP",
            "workplaceType": "on-site",
        }
        assert not vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Remoto")

    def test_remoto_rejeita_hibrido(self):
        vaga = {
            "city": "São Paulo",
            "state": "SP",
            "workplaceType": "hybrid",
        }
        assert not vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Remoto")

    def test_remoto_rejeita_nao_informada(self):
        vaga = {
            "city": "São Paulo",
            "state": "SP",
            "workplaceType": None,
        }
        assert not vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Remoto")

    def test_hibrido_aceita_hibrido(self):
        vaga = {
            "city": "São Paulo",
            "state": "SP",
            "workplaceType": "hybrid",
        }
        assert vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Híbrido")

    def test_hibrido_rejeita_remoto(self):
        vaga = {
            "city": "São Paulo",
            "state": "SP",
            "workplaceType": "remote",
        }
        assert not vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Híbrido")

    def test_presencial_aceita_presencial(self):
        vaga = {
            "city": "São Paulo",
            "state": "SP",
            "workplaceType": "on-site",
        }
        assert vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Presencial")

    def test_presencial_rejeita_remoto(self):
        vaga = {
            "city": "São Paulo",
            "state": "SP",
            "workplaceType": "remote",
        }
        assert not vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Presencial")

    def test_presencial_rejeita_nao_informada(self):
        vaga = {
            "city": "São Paulo",
            "state": "SP",
            "workplaceType": None,
        }
        assert not vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Presencial")

    def test_remoto_com_localidade_diferente_removido(self):
        vaga = {
            "city": "Rio de Janeiro",
            "state": "RJ",
            "workplaceType": "on-site",
        }
        assert not vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Presencial")

    def test_remoto_com_localidade_diferente_aceito(self):
        vaga = {
            "city": "Rio de Janeiro",
            "state": "RJ",
            "workplaceType": "remote",
        }
        assert vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Remoto")

    def test_remoto_sem_localidade(self):
        vaga = {
            "city": "",
            "state": "",
            "workplaceType": "remote",
        }
        assert vaga_matcheia_filtros(vaga, "Sao Paulo", "SP", "Remoto")

    def test_presencial_sem_cidade_e_rejeitado(self):
        vaga = {
            "city": "",
            "state": "",
            "workplaceType": "on-site",
        }
        assert not vaga_matcheia_filtros(
            vaga,
            "Sao Paulo",
            "SP",
            "Presencial",
        )

    def test_accents_normalized_comparacao(self):
        vaga = {
            "city": "Sao Paulo",
            "state": "SP",
            "workplaceType": "presencial",
        }
        assert vaga_matcheia_filtros(vaga, "São Paulo", "SP", "Presencial")
