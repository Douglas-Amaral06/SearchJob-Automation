"""Geração do currículo final em PDF."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


def _texto(valor: object) -> str:
    return escape(str(valor or "").strip())


def gerar_pdf_curriculo(curriculo: dict) -> bytes:
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=str(curriculo.get("nome_completo") or "Currículo"),
        author=str(curriculo.get("nome_completo") or ""),
    )

    estilos_base = getSampleStyleSheet()
    nome = ParagraphStyle(
        "Nome",
        parent=estilos_base["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        alignment=TA_CENTER,
        spaceAfter=5,
    )
    titulo = ParagraphStyle(
        "Titulo",
        parent=estilos_base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#2563EB"),
        alignment=TA_CENTER,
        spaceAfter=5,
    )
    contato = ParagraphStyle(
        "Contato",
        parent=estilos_base["Normal"],
        fontSize=8.8,
        leading=12,
        textColor=colors.HexColor("#475569"),
        alignment=TA_CENTER,
        spaceAfter=9,
    )
    secao = ParagraphStyle(
        "Secao",
        parent=estilos_base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1D4ED8"),
        spaceBefore=8,
        spaceAfter=4,
    )
    corpo = ParagraphStyle(
        "Corpo",
        parent=estilos_base["BodyText"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=4,
    )
    item = ParagraphStyle(
        "Item",
        parent=corpo,
        leftIndent=10,
        firstLineIndent=-7,
        bulletIndent=0,
    )

    elementos = [
        Paragraph(_texto(curriculo.get("nome_completo")), nome),
        Paragraph(_texto(curriculo.get("titulo_profissional")), titulo),
    ]
    contato_partes = [
        curriculo.get("email"),
        curriculo.get("telefone"),
        curriculo.get("localidade"),
        *curriculo.get("links", []),
    ]
    contato_final = " | ".join(
        _texto(parte) for parte in contato_partes if str(parte or "").strip()
    )
    if contato_final:
        elementos.append(Paragraph(contato_final, contato))
    elementos.extend(
        [
            HRFlowable(
                width="100%",
                thickness=1,
                color=colors.HexColor("#93C5FD"),
            ),
            Spacer(1, 4),
        ]
    )

    def adicionar_secao(titulo_secao: str, conteudos: list[str]) -> None:
        conteudos_validos = [c for c in conteudos if str(c or "").strip()]
        if not conteudos_validos:
            return
        elementos.append(Paragraph(titulo_secao.upper(), secao))
        for conteudo in conteudos_validos:
            elementos.append(Paragraph(_texto(conteudo), corpo))

    adicionar_secao(
        "Resumo profissional",
        [curriculo.get("resumo_profissional", "")],
    )

    habilidades = [
        *curriculo.get("habilidades_tecnicas", []),
        *curriculo.get("competencias", []),
    ]
    adicionar_secao("Habilidades", [", ".join(habilidades)] if habilidades else [])

    experiencias = curriculo.get("experiencias", [])
    if experiencias:
        elementos.append(Paragraph("EXPERIÊNCIA PROFISSIONAL", secao))
        for experiencia in experiencias:
            cabecalho = " - ".join(
                parte
                for parte in (
                    experiencia.get("cargo", ""),
                    experiencia.get("empresa", ""),
                )
                if parte
            )
            elementos.append(Paragraph(f"<b>{_texto(cabecalho)}</b>", corpo))
            periodo_local = " | ".join(
                parte
                for parte in (
                    experiencia.get("periodo", ""),
                    experiencia.get("local", ""),
                )
                if parte
            )
            if periodo_local:
                elementos.append(Paragraph(_texto(periodo_local), corpo))
            for realizacao in experiencia.get("realizacoes", []):
                elementos.append(Paragraph(f"- {_texto(realizacao)}", item))
            elementos.append(Spacer(1, 3))

    formacoes = curriculo.get("formacao", [])
    if formacoes:
        elementos.append(Paragraph("FORMAÇÃO ACADÊMICA", secao))
        for formacao in formacoes:
            linha = " - ".join(
                parte
                for parte in (
                    formacao.get("curso", ""),
                    formacao.get("instituicao", ""),
                )
                if parte
            )
            elementos.append(Paragraph(f"<b>{_texto(linha)}</b>", corpo))
            detalhes = " | ".join(
                parte
                for parte in (
                    formacao.get("periodo", ""),
                    formacao.get("detalhes", ""),
                )
                if parte
            )
            if detalhes:
                elementos.append(Paragraph(_texto(detalhes), corpo))

    for titulo_secao, chave in (
        ("Cursos e certificações", "cursos_certificacoes"),
        ("Idiomas", "idiomas"),
        ("Projetos", "projetos"),
    ):
        valores = curriculo.get(chave, [])
        adicionar_secao(titulo_secao, [f"- {valor}" for valor in valores])

    documento.build(elementos)
    return buffer.getvalue()
