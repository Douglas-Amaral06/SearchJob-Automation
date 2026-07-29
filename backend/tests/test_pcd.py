"""
Testes para detecção de vagas exclusivas/afirmativas para PCD.
"""
import pytest
from app.utils.pcd import vaga_eh_pcd


class TestVagaPCD:
    """Testes para detecção de vagas PCD."""
    
    # === DEVE RETORNAR TRUE ===
    
    def test_vaga_exclusiva_para_pcd(self):
        assert vaga_eh_pcd("Vaga exclusiva para PCD")
    
    def test_vaga_exclusiva_para_pessoas_com_deficiencia(self):
        assert vaga_eh_pcd("Vaga exclusiva para pessoas com deficiência")
    
    def test_oportunidade_afirmativa_pcd(self):
        assert vaga_eh_pcd("Oportunidade afirmativa para PCD")
    
    def test_vaga_afirmativa_pessoas_com_deficiencia(self):
        assert vaga_eh_pcd("Vaga afirmativa para pessoas com deficiência")

    def test_vaga_afirmativa_profissional_com_deficiencia(self):
        assert vaga_eh_pcd(
            "Vaga afirmativa para Profissional com Deficiência"
        )

    def test_vaga_afirmativa_profissionais_com_deficiencia(self):
        assert vaga_eh_pcd(
            "Vaga afirmativa para profissionais com deficiência"
        )
    
    def test_vaga_reservada_pcd(self):
        assert vaga_eh_pcd("Vaga reservada para PCD")
    
    def test_vaga_reservada_pessoas_deficiencia(self):
        assert vaga_eh_pcd("Vaga reservada para pessoas com deficiência")
    
    def test_vaga_destinada_exclusivamente_pcd(self):
        assert vaga_eh_pcd("Vaga destinada exclusivamente a pessoas com deficiência")
    
    def test_processo_seletivo_exclusivo_pcd(self):
        assert vaga_eh_pcd("Processo seletivo exclusivo para PCD")
    
    def test_titulo_auxiliar_administrativo_pcd(self):
        assert vaga_eh_pcd("Auxiliar Administrativo PCD")
    
    def test_titulo_analista_pcd(self):
        assert vaga_eh_pcd("Analista PCD")
    
    def test_titulo_desenvolvedor_pcd(self):
        assert vaga_eh_pcd("Desenvolvedor PCD")
    
    def test_titulo_começa_com_pcd(self):
        assert vaga_eh_pcd("PCD - Vendedor")
    
    def test_maiuscula_minuscula(self):
        assert vaga_eh_pcd("VAGA EXCLUSIVA PARA PCD")
    
    def test_com_acentos(self):
        assert vaga_eh_pcd("Vaga exclusiva para pessoas com deficiência")
    
    def test_com_pontuacao(self):
        assert vaga_eh_pcd("Vaga exclusiva para PCD.")
    
    def test_afirmativa_a_maiuscula(self):
        assert vaga_eh_pcd("Vaga Afirmativa A PCD")
    
    # === DEVE RETORNAR FALSE ===
    
    def test_valorizamos_diversidade(self):
        assert not vaga_eh_pcd("Valorizamos diversidade e inclusão")
    
    def test_pessoas_com_deficiencia_bem_vindas(self):
        assert not vaga_eh_pcd("Pessoas com deficiência são bem-vindas")
    
    def test_todas_pessoas_podem_se_candidatar(self):
        assert not vaga_eh_pcd("Todas as pessoas podem se candidatar, incluindo PCD")
    
    def test_empresa_promove_inclusao(self):
        assert not vaga_eh_pcd("Nossa empresa promove inclusão de pessoas com deficiência")
    
    def test_beneficio_coparticipacao(self):
        assert not vaga_eh_pcd("Benefício com coparticipação")
    
    def test_plano_saude_coparticipacao(self):
        assert not vaga_eh_pcd("Plano de saúde com coparticipação (exceto para PCD)")
    
    def test_ambiente_inclusivo(self):
        assert not vaga_eh_pcd("Ambiente inclusivo")
    
    def test_nao_discriminacao(self):
        assert not vaga_eh_pcd("Não fazemos discriminação por deficiência")
    
    def test_pcd_bem_vinda_generico(self):
        assert not vaga_eh_pcd("PCD bem-vinda a se candidatar")
    
    def test_policy_diversidade(self):
        assert not vaga_eh_pcd("Policy de diversidade: PCD bem-vindo")
    
    def test_texto_vazio(self):
        assert not vaga_eh_pcd("")
    
    def test_none(self):
        assert not vaga_eh_pcd(None)
    
    def test_apenas_espacos(self):
        assert not vaga_eh_pcd("   ")
    
    def test_stone_company_politica_inclusiva(self):
        """Stone company menciona deficiência em contexto de inclusão, não exclusividade."""
        texto = """
        Sobre a Stone:
        Somos uma empresa de inclusão.
        Todas as vagas stone também são destinadas a pessoas com deficiência.
        Benefício com coparticipação (exceto para profissionais com deficiência).
        """
        assert not vaga_eh_pcd(texto)
    
    def test_stone_politica_com_exclusividade(self):
        """Se Stone tivesse vaga exclusiva, seria detectada."""
        texto = """
        Vaga exclusiva para PCD
        Benefício com coparticipação (exceto para profissionais com deficiência).
        """
        assert vaga_eh_pcd(texto)
    
    def test_multiplas_mencoes_inclusao_sem_exclusividade(self):
        texto = """
        Procuramos um desenvolvedor.
        Pessoas com deficiência são bem-vindas.
        Não fazemos discriminação.
        """
        assert not vaga_eh_pcd(texto)
    
    def test_titulo_com_palavra_pcd_mas_generico(self):
        """PCD em contexto genérico, não exclusivo."""
        assert not vaga_eh_pcd("Programa de inclusão PCD - Candidatos abertos")
    
    def test_titulo_vendedor_sem_pcd(self):
        assert not vaga_eh_pcd("Vendedor")
    
    def test_descricao_menciona_pcd_como_bonus(self):
        assert not vaga_eh_pcd("Vaga de Desenvolvedor. Oferecemos ambiente inclusivo para PCD.")
    
    def test_case_insensitive(self):
        assert vaga_eh_pcd("vaga EXCLUSIVA para pcd")
    
    def test_com_espacos_multiplos(self):
        assert vaga_eh_pcd("Vaga   exclusiva   para   PCD")
