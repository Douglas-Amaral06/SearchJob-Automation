from io import BytesIO
from pathlib import Path
from unittest import mock

import pytest
from pypdf import PdfReader

from app.database import inicializar_banco
from app.user_resume import (
    autenticar_usuario,
    criar_usuario,
    obter_curriculo,
    salvar_curriculo,
)
from app.utils.resume_pdf import gerar_pdf_curriculo


@pytest.fixture
def banco_usuario(tmp_path: Path):
    banco = tmp_path / "usuarios.db"
    with mock.patch("app.database.DATABASE_PATH", banco):
        with mock.patch("app.database.DATABASE_DIR", banco.parent):
            inicializar_banco()
            yield


def test_criar_e_autenticar_usuario(banco_usuario):
    criado = criar_usuario("Ana Silva", "ANA@EXAMPLE.COM", "Senha-Segura123")
    assert criado["status"] == "sucesso"
    assert criado["usuario"]["email"] == "ana@example.com"

    login = autenticar_usuario("ana@example.com", "Senha-Segura123")
    assert login["status"] == "sucesso"
    assert login["usuario"]["nome"] == "Ana Silva"

    login_invalido = autenticar_usuario("ana@example.com", "senha-errada")
    assert login_invalido["status"] == "erro"


def test_curriculo_fica_vinculado_ao_usuario(banco_usuario):
    usuario = criar_usuario(
        "Bruno Lima",
        "bruno@example.com",
        "Senha-Segura123",
    )["usuario"]
    dados = {"nome_completo": "Bruno Lima", "habilidades": "Excel"}
    gerado = {
        "nome_completo": "Bruno Lima",
        "titulo_profissional": "Assistente Administrativo",
        "cargos_recomendados": ["Assistente Administrativo"],
    }

    assert salvar_curriculo(usuario["id"], dados, gerado)["status"] == "sucesso"
    salvo = obter_curriculo(usuario["id"])
    assert salvo["dados"]["habilidades"] == "Excel"
    assert salvo["gerado"]["titulo_profissional"] == "Assistente Administrativo"


def test_pdf_curriculo_e_valido():
    pdf = gerar_pdf_curriculo(
        {
            "nome_completo": "Carla Souza",
            "titulo_profissional": "Analista Administrativa",
            "email": "carla@example.com",
            "telefone": "(11) 99999-9999",
            "localidade": "São Paulo, SP",
            "resumo_profissional": "Experiência com rotinas administrativas.",
            "habilidades_tecnicas": ["Excel", "Atendimento"],
            "competencias": ["Organização"],
            "experiencias": [
                {
                    "cargo": "Assistente",
                    "empresa": "Empresa Exemplo",
                    "periodo": "2022 - 2025",
                    "local": "São Paulo",
                    "realizacoes": ["Organização de documentos e relatórios."],
                }
            ],
            "formacao": [],
            "cursos_certificacoes": [],
            "idiomas": ["Português nativo"],
            "projetos": [],
            "links": [],
        }
    )
    assert pdf.startswith(b"%PDF")
    leitor = PdfReader(BytesIO(pdf))
    assert len(leitor.pages) >= 1
    texto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
    assert "Carla Souza" in texto
