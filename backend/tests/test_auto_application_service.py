from pathlib import Path
from unittest import mock

import pytest

from app.database import criar_conexao, inicializar_banco
from app.services.auto_application_service import (
    atualizar_item_campanha,
    confirmar_login_plataforma,
    listar_campanhas_candidatura,
    listar_itens_campanha,
    listar_logins_campanha,
    salvar_campanha_candidatura,
)


@pytest.fixture
def banco_campanhas(tmp_path: Path):
    banco = tmp_path / "campanhas.db"
    with mock.patch("app.database.DATABASE_PATH", banco):
        with mock.patch("app.database.DATABASE_DIR", banco.parent):
            inicializar_banco()
            conexao = criar_conexao()
            try:
                conexao.executemany(
                    """
                    INSERT INTO usuarios (
                        nome, email, senha_hash, senha_salt, criado_em, atualizado_em
                    )
                    VALUES (?, ?, 'hash', 'salt', ?, ?)
                    """,
                    [
                        ("Ana", "ana@example.com", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
                        ("Bia", "bia@example.com", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
                    ],
                )
                conexao.commit()
            finally:
                conexao.close()
            yield


def _vaga(fonte: str, numero: int) -> dict:
    return {
        "fonte": fonte,
        "id_externo": f"{fonte}-{numero}",
        "titulo": f"Auxiliar Administrativo {numero}",
        "empresa": f"Empresa {numero}",
        "local": "São Paulo, SP",
        "modalidade": "Presencial",
        "url_candidatura": f"https://example.com/{fonte}/{numero}",
    }


def test_campanha_respeita_limite_e_aguarda_login_gupy(banco_campanhas):
    vagas = [
        *[_vaga("Adzuna", numero) for numero in range(4)],
        *[_vaga("Gupy", numero) for numero in range(4)],
    ]
    resultado = salvar_campanha_candidatura(
        usuario_id=1,
        cargo="Auxiliar Administrativo",
        cidade="São Paulo",
        estado="SP",
        modalidade="Presencial",
        incluir_pcd=False,
        plataformas=["Adzuna", "Gupy"],
        limite_vagas=3,
        vagas=vagas,
    )

    assert resultado["status"] == "sucesso"
    assert resultado["total_vagas"] == 3
    assert resultado["aguardando_login"] is True

    campanhas = listar_campanhas_candidatura(1)["campanhas"]
    assert campanhas[0]["status"] == "aguardando_login"
    assert campanhas[0]["limite_vagas"] == 3

    logins = {
        item["plataforma"]: item["status"]
        for item in listar_logins_campanha(1, resultado["campanha_id"])
    }
    assert logins == {"Adzuna": "confirmado", "Gupy": "aguardando"}

    itens = listar_itens_campanha(1, resultado["campanha_id"])["itens"]
    assert len(itens) == 3
    assert {item["fonte"] for item in itens} == {"Adzuna", "Gupy"}


def test_fila_gupy_so_libera_depois_da_confirmacao(banco_campanhas):
    resultado = salvar_campanha_candidatura(
        usuario_id=1,
        cargo="Auxiliar",
        cidade="São Paulo",
        estado="SP",
        modalidade="Presencial",
        incluir_pcd=True,
        plataformas=["Gupy"],
        limite_vagas=5,
        vagas=[_vaga("Gupy", 1)],
    )
    campanha_id = resultado["campanha_id"]
    item = listar_itens_campanha(1, campanha_id)["itens"][0]

    bloqueado = atualizar_item_campanha(1, item["id"], "candidatado")
    assert bloqueado["status"] == "erro"

    confirmado = confirmar_login_plataforma(1, campanha_id, "Gupy")
    assert confirmado["status"] == "sucesso"
    assert listar_campanhas_candidatura(1)["campanhas"][0]["status"] == "pronta"

    atualizado = atualizar_item_campanha(1, item["id"], "candidatado")
    assert atualizado["status"] == "sucesso"
    assert listar_campanhas_candidatura(1)["campanhas"][0]["status"] == "concluida"


def test_usuario_nao_acessa_campanha_de_outra_conta(banco_campanhas):
    resultado = salvar_campanha_candidatura(
        usuario_id=1,
        cargo="Auxiliar",
        cidade="São Paulo",
        estado="SP",
        modalidade="Presencial",
        incluir_pcd=False,
        plataformas=["Adzuna"],
        limite_vagas=1,
        vagas=[_vaga("Adzuna", 1)],
    )

    assert listar_itens_campanha(2, resultado["campanha_id"])["status"] == "erro"
    assert listar_logins_campanha(2, resultado["campanha_id"]) == []


def test_limite_e_reduzido_defensivamente_para_cinquenta(banco_campanhas):
    vagas = [_vaga("Adzuna", numero) for numero in range(60)]
    resultado = salvar_campanha_candidatura(
        usuario_id=1,
        cargo="Auxiliar",
        cidade="São Paulo",
        estado="SP",
        modalidade="Presencial",
        incluir_pcd=False,
        plataformas=["Adzuna"],
        limite_vagas=999,
        vagas=vagas,
    )

    assert resultado["total_vagas"] == 50
    campanha = listar_campanhas_candidatura(1)["campanhas"][0]
    assert campanha["limite_vagas"] == 50


def test_listagem_migra_tabela_antiga_sem_limite_vagas(banco_campanhas):
    conexao = criar_conexao()
    try:
        conexao.execute("DROP TABLE itens_campanha_candidatura")
        conexao.execute("DROP TABLE logins_plataforma_campanha")
        conexao.execute("DROP TABLE campanhas_candidatura")
        conexao.execute("""
            CREATE TABLE campanhas_candidatura (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                cargo TEXT NOT NULL,
                cidade TEXT NOT NULL,
                estado TEXT NOT NULL,
                modalidade TEXT NOT NULL,
                incluir_pcd INTEGER NOT NULL DEFAULT 0,
                plataformas_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pronta',
                total_vagas INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)
        conexao.commit()
    finally:
        conexao.close()

    resultado = listar_campanhas_candidatura(1)

    assert resultado == {"status": "sucesso", "campanhas": []}
    conexao = criar_conexao()
    try:
        colunas = {
            item["name"]
            for item in conexao.execute(
                "PRAGMA table_info(campanhas_candidatura)"
            ).fetchall()
        }
    finally:
        conexao.close()
    assert "limite_vagas" in colunas
