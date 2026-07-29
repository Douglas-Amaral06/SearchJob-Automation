"""
Testes para persistência SQLite de candidaturas.
"""
import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest import mock

# Mock DATABASE_PATH antes de importar
with mock.patch("app.config.DATABASE_PATH"):
    from app.database import (
        gerar_chave_vaga,
        validar_url_candidatura,
        criar_conexao,
        inicializar_banco,
        salvar_candidatura,
        listar_candidaturas,
        remover_candidatura,
        obter_chaves_candidatadas,
    )


@pytest.fixture
def temp_db():
    """Cria um banco temporário para testes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        with mock.patch("app.database.DATABASE_PATH", db_path):
            with mock.patch("app.database.DATABASE_DIR", db_path.parent):
                inicializar_banco()
                yield db_path


class TestGerarChaveVaga:
    def test_chave_com_id_externo(self):
        chave = gerar_chave_vaga("Adzuna", "12345", "http://example.com")
        assert "adzuna" in chave
        assert "12345" in chave
    
    def test_chave_sem_id_externo(self):
        chave = gerar_chave_vaga("Gupy", None, "http://example.com/job")
        assert "gupy" in chave
        assert len(chave) > 6
    
    def test_chave_consistente(self):
        chave1 = gerar_chave_vaga("Greenhouse", "789", "http://example.com")
        chave2 = gerar_chave_vaga("Greenhouse", "789", "http://other.com")
        assert chave1 == chave2

    def test_ids_parecidos_nao_geram_mesma_chave(self):
        chave_123 = gerar_chave_vaga("Adzuna", "123", "https://example.com/123")
        chave_1234 = gerar_chave_vaga("Adzuna", "1234", "https://example.com/1234")

        assert chave_123 != chave_1234


class TestValidarUrlCandidatura:
    def test_url_https_valida(self):
        assert validar_url_candidatura("https://example.com/vaga/123") is True

    def test_url_com_esquema_invalido(self):
        assert validar_url_candidatura("javascript:alert(1)") is False


class TestSalvarCandidatura:
    def test_salvar_nova(self, temp_db):
        resultado = salvar_candidatura(
            fonte="Adzuna",
            id_externo="123",
            titulo="Desenvolvedor",
            empresa="Tech Corp",
            local="São Paulo, SP",
            url_candidatura="http://example.com/job/123",
        )
        
        assert resultado["status"] == "sucesso"
        assert resultado["resultado"] == "criado"
    
    def test_salvar_duplicada_idempotente(self, temp_db):
        # Salvar primeira vez
        resultado1 = salvar_candidatura(
            fonte="Gupy",
            id_externo="456",
            titulo="Analista",
            empresa="Data Co",
            local="Rio de Janeiro",
            url_candidatura="http://gupy.com/job/456",
        )
        
        # Salvar segunda vez - deve ser idempotente
        resultado2 = salvar_candidatura(
            fonte="Gupy",
            id_externo="456",
            titulo="Analista",
            empresa="Data Co",
            local="Rio de Janeiro",
            url_candidatura="http://gupy.com/job/456",
        )
        
        assert resultado1["resultado"] == "criado"
        assert resultado2["resultado"] == "atualizado"
    
    def test_chave_unica_por_fonte(self, temp_db):
        salvar_candidatura(
            fonte="Greenhouse",
            id_externo="789",
            titulo="Product Manager",
            empresa="Stone",
            local="São Paulo",
            url_candidatura="http://stone.com/job/789",
        )
        
        # Salvar com mesmo id mas fonte diferente - deve ser permitido
        resultado = salvar_candidatura(
            fonte="Adzuna",
            id_externo="789",
            titulo="Product Manager",
            empresa="Other",
            local="São Paulo",
            url_candidatura="http://adzuna.com/job/789",
        )
        
        assert resultado["status"] == "sucesso"


class TestListarCandidaturas:
    def test_listar_vazio(self, temp_db):
        resultado = listar_candidaturas()
        assert resultado["status"] == "sucesso"
        assert resultado["total"] == 0
        assert resultado["candidaturas"] == []
    
    def test_listar_com_dados(self, temp_db):
        salvar_candidatura("Adzuna", "1", "Dev", "Corp1", "SP", "http://1.com")
        salvar_candidatura("Gupy", "2", "Analista", "Corp2", "RJ", "http://2.com")
        
        resultado = listar_candidaturas()
        assert resultado["total"] == 2
        assert len(resultado["candidaturas"]) == 2
    
    def test_listar_paginado(self, temp_db):
        for i in range(35):
            salvar_candidatura("Adzuna", str(i), f"Job {i}", "Corp", "SP", f"http://{i}.com")
        
        pag1 = listar_candidaturas(pagina=1, limite=20)
        pag2 = listar_candidaturas(pagina=2, limite=20)
        
        assert pag1["total"] == 35
        assert len(pag1["candidaturas"]) == 20
        assert len(pag2["candidaturas"]) == 15
    
    def test_filtrar_por_fonte(self, temp_db):
        salvar_candidatura("Adzuna", "1", "Dev", "Corp1", "SP", "http://1.com")
        salvar_candidatura("Gupy", "2", "Analista", "Corp2", "RJ", "http://2.com")
        salvar_candidatura("Gupy", "3", "Dev", "Corp3", "SP", "http://3.com")
        
        resultado = listar_candidaturas(fonte="Gupy")
        assert resultado["total"] == 2
        assert all(c["fonte"] == "Gupy" for c in resultado["candidaturas"])
    
    def test_ordenacao_recente_primeiro(self, temp_db):
        salvar_candidatura("Adzuna", "1", "Job1", "Corp", "SP", "http://1.com")
        salvar_candidatura("Adzuna", "2", "Job2", "Corp", "SP", "http://2.com")
        
        resultado = listar_candidaturas()
        # Mais recente deve vir primeiro
        assert resultado["candidaturas"][0]["id_externo"] == "2"


class TestRemoverCandidatura:
    def test_remover_existente(self, temp_db):
        salvar_candidatura("Adzuna", "1", "Dev", "Corp", "SP", "http://1.com")
        
        resultado = remover_candidatura(fonte="Adzuna", id_externo="1")
        assert resultado["status"] == "sucesso"
        assert resultado["removida"] is True
        
        # Verificar se foi removida
        vagas = listar_candidaturas()
        assert vagas["total"] == 0
    
    def test_remover_inexistente_idempotente(self, temp_db):
        resultado = remover_candidatura(fonte="Adzuna", id_externo="999")
        # Deve ser idempotente
        assert resultado["status"] == "sucesso"
        assert resultado["removida"] is False

    def test_remocao_por_id_exato(self, temp_db):
        salvar_candidatura("Adzuna", "123", "Dev", "Corp", "SP", "https://example.com/123")
        salvar_candidatura("Adzuna", "1234", "Dev", "Corp", "SP", "https://example.com/1234")

        resultado = remover_candidatura(fonte="Adzuna", id_externo="123")
        restantes = listar_candidaturas()

        assert resultado["removida"] is True
        assert restantes["total"] == 1
        assert restantes["candidaturas"][0]["id_externo"] == "1234"
    
    def test_remover_por_url(self, temp_db):
        """Remover por URL sem id_externo - salvar e remover usando URL como chave."""
        url = "http://example.com/job/123"
        # Salvar sem id_externo (simular vaga que só tem URL)
        salvar_candidatura("Greenhouse", "", "PM", "Stone", "SP", url)

        resultado = remover_candidatura(fonte="Greenhouse", url_candidatura=url)
        assert resultado["removida"] is True


class TestObterChavesCandidatadas:
    def test_obter_chaves_vazio(self, temp_db):
        chaves = obter_chaves_candidatadas()
        assert chaves == set()
    
    def test_obter_chaves_com_dados(self, temp_db):
        salvar_candidatura("Adzuna", "1", "Dev", "Corp", "SP", "http://1.com")
        salvar_candidatura("Gupy", "2", "Analista", "Corp", "RJ", "http://2.com")
        
        chaves = obter_chaves_candidatadas()
        assert len(chaves) == 2
        assert any("adzuna" in c.lower() for c in chaves)
        assert any("gupy" in c.lower() for c in chaves)
    
    def test_obter_chaves_por_fonte(self, temp_db):
        salvar_candidatura("Adzuna", "1", "Dev", "Corp", "SP", "http://1.com")
        salvar_candidatura("Gupy", "2", "Analista", "Corp", "RJ", "http://2.com")
        salvar_candidatura("Gupy", "3", "Dev", "Corp", "SP", "http://3.com")
        
        chaves_gupy = obter_chaves_candidatadas(fonte="Gupy")
        assert len(chaves_gupy) == 2


class TestTimestamps:
    def test_timestamps_utc_com_z(self, temp_db):
        salvar_candidatura("Adzuna", "1", "Dev", "Corp", "SP", "http://1.com")
        
        vagas = listar_candidaturas()
        candidatura = vagas["candidaturas"][0]
        
        # Verificar que timestamps terminam com Z
        assert candidatura["criado_em"].endswith("Z")
        assert candidatura["atualizado_em"].endswith("Z")
        assert candidatura["candidatado_em"].endswith("Z")
