"""Criação estruturada de currículos com Gemini 2.5 Flash."""

from __future__ import annotations

import json
import os

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class ExperienciaProfissional(BaseModel):
    cargo: str = ""
    empresa: str = ""
    periodo: str = ""
    local: str = ""
    realizacoes: list[str] = Field(default_factory=list)


class FormacaoAcademica(BaseModel):
    curso: str = ""
    instituicao: str = ""
    periodo: str = ""
    detalhes: str = ""


class CurriculoOtimizado(BaseModel):
    nome_completo: str
    titulo_profissional: str = ""
    email: str = ""
    telefone: str = ""
    localidade: str = ""
    links: list[str] = Field(default_factory=list)
    resumo_profissional: str = ""
    habilidades_tecnicas: list[str] = Field(default_factory=list)
    competencias: list[str] = Field(default_factory=list)
    experiencias: list[ExperienciaProfissional] = Field(default_factory=list)
    formacao: list[FormacaoAcademica] = Field(default_factory=list)
    cursos_certificacoes: list[str] = Field(default_factory=list)
    idiomas: list[str] = Field(default_factory=list)
    projetos: list[str] = Field(default_factory=list)
    cargos_recomendados: list[str] = Field(default_factory=list)
    palavras_chave: list[str] = Field(default_factory=list)


def gemini_configurado() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def gerar_curriculo_com_ia(dados: dict) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não configurada. Adicione uma nova chave nos Secrets."
        )

    prompt = (
        "Crie um currículo profissional em português do Brasil usando somente "
        "os fatos fornecidos. Reescreva com clareza, verbos de ação e foco em "
        "resultados, mas nunca invente empresas, datas, formação, números ou "
        "habilidades. Quando uma informação estiver ausente, use string vazia "
        "ou lista vazia. Recomende de 1 a 3 cargos realistas para busca de vagas "
        "e palavras-chave ATS coerentes com a experiência. Dados do candidato:\n"
        + json.dumps(dados, ensure_ascii=False, indent=2)
    )

    cliente = genai.Client(api_key=api_key)
    resposta = cliente.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "Você é especialista em recrutamento, currículos ATS e mercado "
                "de trabalho brasileiro. Preserve a verdade factual."
            ),
            response_mime_type="application/json",
            response_schema=CurriculoOtimizado,
            temperature=0.2,
        ),
    )

    if isinstance(resposta.parsed, CurriculoOtimizado):
        curriculo = resposta.parsed
    elif resposta.parsed:
        curriculo = CurriculoOtimizado.model_validate(resposta.parsed)
    else:
        curriculo = CurriculoOtimizado.model_validate_json(resposta.text)

    return curriculo.model_dump()
