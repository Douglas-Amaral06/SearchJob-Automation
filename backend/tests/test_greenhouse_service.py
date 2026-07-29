import pytest
from datetime import datetime, timezone
from app.services.greenhouse_service import (
    remover_html,
    normalizar_texto_comparacao,
    tokenizar_texto,
    cargo_matcheia,
    detectar_modalidade,
    construir_local,
    vaga_corresponde_localizacao,
    gerar_variantes_token,
    tokens_correspondem,
    sequencia_tokens_corresponde,
    normalizar_data_publicacao,
    chave_ordenacao_data,
    localizacao_remota_compativel,
    localizacao_global_generica,
    localizacao_brasileira,
    limpar_cache_greenhouse,
)


class TestRemoverHTML:
    def test_remove_basic_tags(self):
        assert remover_html("<p>Texto</p>") == "Texto"
        resultado = remover_html("<b>bold</b> e <i>italic</i>")
        assert "bold" in resultado and "italic" in resultado

    def test_preserve_text_content(self):
        assert "desenvolvedor" in remover_html("<p>Procuramos desenvolvedor</p>").lower()

    def test_empty_html(self):
        assert remover_html("") == ""
        assert remover_html(None) == ""


class TestNormalizarTextoComparacao:
    def test_accent_removal(self):
        assert normalizar_texto_comparacao("São Paulo") == "sao paulo"

    def test_case_insensitive(self):
        assert normalizar_texto_comparacao("DESENVOLVEDOR") == "desenvolvedor"

    def test_whitespace_handling(self):
        assert normalizar_texto_comparacao("  texto  ") == "texto"


class TestTokenizarTexto:
    def test_tokeniza_simples(self):
        tokens = tokenizar_texto("Desenvolvedor Python")
        assert "desenvolvedor" in tokens
        assert "python" in tokens

    def test_remove_punctuation(self):
        tokens = tokenizar_texto("Desenvolvedor, Python (Senior)")
        assert "desenvolvedor" in tokens
        assert "python" in tokens
        assert "senior" in tokens


class TestGerarVariantesToken:
    def test_genero_dora_dor(self):
        variantes = gerar_variantes_token("desenvolvedor")
        assert "desenvolvedora" in variantes
        assert "desenvolvedor" in variantes

    def test_genero_a_o(self):
        variantes = gerar_variantes_token("coordenadora")
        assert "coordenador" in variantes

    def test_plural(self):
        variantes = gerar_variantes_token("desenvolvedor")
        assert "desenvolvedores" in variantes


class TestTokensCorrespondem:
    def test_tokens_simples(self):
        assert tokens_correspondem(
            ["desenvolvedor"],
            ["desenvolvedor", "python"]
        )

    def test_tokens_com_variantes(self):
        assert tokens_correspondem(
            ["desenvolvedora"],
            ["desenvolvedor", "python"]
        )

    def test_tokens_nao_correspondem(self):
        assert not tokens_correspondem(
            ["analista", "financeiro"],
            ["analista", "dados"]
        )


class TestSequenciaTokensCorresponde:
    def test_sequencia_exata(self):
        assert sequencia_tokens_corresponde(
            ["desenvolvedor", "python"],
            ["pessoa", "desenvolvedor", "python", "senior"]
        )

    def test_sequencia_nao_encontrada(self):
        assert not sequencia_tokens_corresponde(
            ["analista", "financeiro"],
            ["analista", "dados", "financeiro"]
        )


class TestCargoMatcheia:
    def test_exact_match_titulo(self):
        assert cargo_matcheia("Desenvolvedor Python", "", "Desenvolvedor Python")

    def test_partial_match_tokens(self):
        assert cargo_matcheia("Analista Desenvolvedor", "", "Desenvolvedor")

    def test_no_match(self):
        assert not cargo_matcheia("Contador", "", "Desenvolvedor")

    def test_case_insensitive(self):
        assert cargo_matcheia("DESENVOLVEDOR", "", "desenvolvedor")

    def test_gender_variation(self):
        assert cargo_matcheia("Pessoa Desenvolvedora", "", "Desenvolvedor")
        assert cargo_matcheia("Desenvolvedor", "", "Desenvolvedora")

    def test_dados_nao_corresponde_metadados(self):
        """Dados não deve corresponder dentro de metadados (token boundaries)."""
        assert not cargo_matcheia(
            "Especialista em Metadados",
            "",
            "Analista de Dados"
        )

    def test_titulo_incompativel_nao_validado_descricao(self):
        assert not cargo_matcheia(
            "Gerente de Projetos",
            "Supervisará desenvolvedores Python",
            "Desenvolvedor Python"
        )

    def test_termo_principal_permite_complemento(self):
        assert cargo_matcheia(
            "Pessoa Desenvolvedora Backend",
            "Experiência com Python",
            "Desenvolvedor Python"
        )

    def test_analista_financeiro_rejeita_analista_dados(self):
        assert not cargo_matcheia(
            "Analista de Dados",
            "",
            "Analista Financeiro"
        )

    def test_auxiliar_rejeita_desenvolvedor(self):
        assert not cargo_matcheia(
            "Desenvolvedor",
            "Trabalhará com Auxiliar Administrativo",
            "Auxiliar Administrativo"
        )


class TestDetectarModalidade:
    def test_remote_variations(self):
        assert detectar_modalidade("Remote Developer", "", "") == "Remoto"
        assert detectar_modalidade("", "remote position", "") == "Remoto"
        assert detectar_modalidade("", "", "Remote") == "Remoto"

    def test_hybrid_variations(self):
        assert detectar_modalidade("Hybrid Role", "", "") == "Híbrido"

    def test_presencial_variations(self):
        assert detectar_modalidade("On-site Position", "", "") == "Presencial"

    def test_unknown_modalidade(self):
        assert detectar_modalidade("Some Title", "", "") == "Não informada"


class TestConstruirLocal:
    def test_valid_location(self):
        assert construir_local("São Paulo, SP") == "São Paulo, SP"

    def test_empty_location(self):
        assert construir_local("") == "Local não informado"

    def test_none_location(self):
        assert construir_local(None) == "Local não informado"


class TestLocalizacaoGlobalGenerica:
    def test_remote_simples(self):
        assert localizacao_global_generica("Remote")

    def test_fully_remote(self):
        assert localizacao_global_generica("Fully Remote")

    def test_remote_worldwide(self):
        assert localizacao_global_generica("Remote - Worldwide")

    def test_remote_global(self):
        assert localizacao_global_generica("Remote - Global")

    def test_anywhere(self):
        assert localizacao_global_generica("Anywhere")

    def test_remote_com_qualificador(self):
        assert not localizacao_global_generica("Remote - Japan")


class TestLocalizacaoBrasileira:
    def test_remote_brazil(self):
        assert localizacao_brasileira("Remote - Brazil", "Sao Paulo", "SP")

    def test_remote_brasil(self):
        assert localizacao_brasileira("Remote - Brasil", "Sao Paulo", "SP")

    def test_remote_sao_paulo_brasil(self):
        assert localizacao_brasileira("Remote - São Paulo, Brazil", "Sao Paulo", "SP")

    def test_br_token_completo(self):
        assert localizacao_brasileira("Remote - BR", "Sao Paulo", "SP")

    def test_nao_brasileira(self):
        assert not localizacao_brasileira("Remote - Japan", "Sao Paulo", "SP")


class TestLocalizacaoRemataCompativel:
    def test_remote_aceita(self):
        assert localizacao_remota_compativel("Remote", "Sao Paulo", "SP")

    def test_fully_remote_aceita(self):
        assert localizacao_remota_compativel("Fully Remote", "Sao Paulo", "SP")

    def test_remote_worldwide_aceita(self):
        assert localizacao_remota_compativel("Remote - Worldwide", "Sao Paulo", "SP")

    def test_remote_global_aceita(self):
        assert localizacao_remota_compativel("Remote - Global", "Sao Paulo", "SP")

    def test_remote_brazil_aceita(self):
        assert localizacao_remota_compativel("Remote - Brazil", "Sao Paulo", "SP")

    def test_remote_sao_paulo_brazil_aceita(self):
        assert localizacao_remota_compativel("Remote - São Paulo, Brazil", "Sao Paulo", "SP")

    def test_remote_japan_rejeitada(self):
        assert not localizacao_remota_compativel("Remote - Japan", "Sao Paulo", "SP")

    def test_remote_singapore_rejeitada(self):
        assert not localizacao_remota_compativel("Remote - Singapore", "Sao Paulo", "SP")

    def test_remote_south_africa_rejeitada(self):
        assert not localizacao_remota_compativel("Remote - South Africa", "Sao Paulo", "SP")

    def test_remote_new_zealand_rejeitada(self):
        assert not localizacao_remota_compativel("Remote - New Zealand", "Sao Paulo", "SP")

    def test_remote_mars_rejeitada(self):
        assert not localizacao_remota_compativel("Remote - Mars", "Sao Paulo", "SP")

    def test_remote_unknown_region_rejeitada(self):
        assert not localizacao_remota_compativel("Remote - Unknown Region", "Sao Paulo", "SP")

    def test_remote_latam_sem_brasil_rejeitada(self):
        assert not localizacao_remota_compativel("Remote - LATAM", "Sao Paulo", "SP")

    def test_latam_including_brasil_aceita(self):
        assert localizacao_remota_compativel("Remote - LATAM including Brazil", "Sao Paulo", "SP")

    def test_br_nao_confunde_berlin(self):
        """BR como token completo não confunde com Berlin."""
        assert localizacao_remota_compativel("Remote - BR", "Sao Paulo", "SP")

    def test_sp_nao_confunde_spain(self):
        """SP como token completo não confunde com Spain."""
        assert localizacao_remota_compativel("Remote", "Sao Paulo", "SP")

    def test_sp_nao_confunde_springfield(self):
        """SP como token completo não confunde com Springfield."""
        # Springfield contém "field", será rejeitado como residual
        assert not localizacao_remota_compativel("Remote - Springfield", "Sao Paulo", "SP")


class TestVagaCorrespondeLocalizacao:
    def test_presencial_sao_paulo(self):
        assert vaga_corresponde_localizacao(
            "São Paulo, SP",
            "Sao Paulo",
            "SP",
            "Presencial"
        )

    def test_presencial_outro_estado_rejeitada(self):
        assert not vaga_corresponde_localizacao(
            "Rio de Janeiro, RJ",
            "Sao Paulo",
            "SP",
            "Presencial"
        )

    def test_hibrido_sao_paulo(self):
        assert vaga_corresponde_localizacao(
            "São Paulo, Brazil",
            "Sao Paulo",
            "SP",
            "Híbrido"
        )

    def test_remoto_usa_rejeitada(self):
        assert not vaga_corresponde_localizacao(
            "Remote - United States",
            "Sao Paulo",
            "SP",
            "Remoto"
        )


class TestNormalizarDataPublicacao:
    def test_iso_com_z(self):
        """Data em UTC com Z."""
        # Usar data conhecida que não é tão futura
        resultado = normalizar_data_publicacao("2024-07-29T10:30:00Z")
        assert resultado is not None
        assert "2024-07-29T10:30:00Z" == resultado

    def test_iso_com_offset_negativo(self):
        """Data com -03:00 deve ser convertida para UTC (+3 horas)."""
        resultado = normalizar_data_publicacao("2024-07-29T09:00:00-03:00")
        assert resultado is not None
        # 09:00 - 03:00 = 12:00 UTC
        assert "2024-07-29T12:00:00Z" == resultado

    def test_iso_com_offset_positivo(self):
        """Data com +02:00 deve ser convertida para UTC (-2 horas)."""
        resultado = normalizar_data_publicacao("2024-07-29T14:00:00+02:00")
        assert resultado is not None
        # 14:00 + 02:00 = 12:00 UTC
        assert "2024-07-29T12:00:00Z" == resultado

    def test_iso_sem_timezone(self):
        """Data sem timezone deve assumir UTC."""
        resultado = normalizar_data_publicacao("2024-07-29T12:00:00")
        assert resultado is not None
        assert "2024-07-29T12:00:00Z" == resultado

    def test_data_invalida(self):
        assert normalizar_data_publicacao("data invalida") is None

    def test_string_vazia(self):
        assert normalizar_data_publicacao("") is None

    def test_valor_nao_string(self):
        assert normalizar_data_publicacao(12345) is None
        assert normalizar_data_publicacao(None) is None

    def test_data_futura_invalida(self):
        """Data muito futura (além de 24 horas) deve ser None."""
        from datetime import datetime, timezone, timedelta
        agora = datetime.now(timezone.utc)
        # 30 horas no futuro
        futura = agora + timedelta(hours=30)
        resultado = normalizar_data_publicacao(futura.isoformat())
        assert resultado is None

    def test_data_futura_tolerancia(self):
        """Data futura dentro de tolerância (23 horas) é aceita."""
        from datetime import datetime, timezone, timedelta
        agora = datetime.now(timezone.utc)
        # 23 horas no futuro
        futura = agora + timedelta(hours=23)
        resultado = normalizar_data_publicacao(futura.isoformat())
        assert resultado is not None
    
    def test_data_futura_25_horas_rejeitada(self):
        """Data 25 horas no futuro retorna None."""
        from datetime import datetime, timezone, timedelta
        agora = datetime.now(timezone.utc)
        futura = agora + timedelta(hours=25)
        resultado = normalizar_data_publicacao(futura.isoformat())
        assert resultado is None
    
    def test_data_futura_30_dias_rejeitada(self):
        """Data 30 dias no futuro retorna None."""
        from datetime import datetime, timezone, timedelta
        agora = datetime.now(timezone.utc)
        futura = agora + timedelta(days=30)
        resultado = normalizar_data_publicacao(futura.isoformat())
        assert resultado is None


class TestChaveOrdenacaoData:
    def test_ordena_por_data_desc(self):
        vaga_antiga = {
            "data_publicacao": "2026-07-28T10:00:00Z",
            "fonte": "A",
            "id_externo": "1",
            "url_candidatura": "url1"
        }
        vaga_nova = {
            "data_publicacao": "2026-07-29T10:00:00Z",
            "fonte": "A",
            "id_externo": "2",
            "url_candidatura": "url2"
        }
        
        vagas = [vaga_antiga, vaga_nova]
        vagas.sort(key=chave_ordenacao_data)
        
        assert vagas[0]["id_externo"] == "2"
        assert vagas[1]["id_externo"] == "1"

    def test_data_ausente_fica_por_ultimo(self):
        vaga_com_data = {
            "data_publicacao": "2026-07-29T10:00:00Z",
            "fonte": "A",
            "id_externo": "1",
            "url_candidatura": "url1"
        }
        vaga_sem_data = {
            "data_publicacao": None,
            "fonte": "A",
            "id_externo": "2",
            "url_candidatura": "url2"
        }
        
        vagas = [vaga_sem_data, vaga_com_data]
        vagas.sort(key=chave_ordenacao_data)
        
        assert vagas[0]["id_externo"] == "1"
        assert vagas[1]["id_externo"] == "2"


class TestCache:
    @pytest.mark.asyncio
    async def test_cache_cleanup(self):
        await limpar_cache_greenhouse()
