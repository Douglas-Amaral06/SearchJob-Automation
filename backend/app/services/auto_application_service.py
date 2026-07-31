"""Campanhas de candidatura assistida, persistentes e vinculadas ao usuário."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from app.config import (
    GREENHOUSE_BOARD_TOKENS,
    GREENHOUSE_ENABLED,
    GUPY_ENABLED,
    JOBICY_ENABLED,
    JOOBLE_ENABLED,
    REMOTIVE_ENABLED,
)
from app.database import (
    criar_conexao,
    gerar_chave_vaga,
    validar_url_candidatura,
)
from app.services.job_aggregator import buscar_vagas_agregadas


FONTES_SUPORTADAS = (
    "Adzuna",
    "Jooble",
    "Gupy",
    "Greenhouse",
    "Jobicy",
    "Remotive",
)
PLATAFORMAS_COM_LOGIN_CENTRAL = {
    "Gupy": "https://portal.gupy.io/",
}
STATUS_ITEM_VALIDOS = {"pendente", "candidatado", "ignorado"}


def _agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fontes_disponiveis_candidatura() -> list[str]:
    fontes = ["Adzuna"]
    if JOOBLE_ENABLED:
        fontes.append("Jooble")
    if GUPY_ENABLED:
        fontes.append("Gupy")
    if GREENHOUSE_ENABLED and GREENHOUSE_BOARD_TOKENS:
        fontes.append("Greenhouse")
    if JOBICY_ENABLED:
        fontes.append("Jobicy")
    if REMOTIVE_ENABLED:
        fontes.append("Remotive")
    return fontes


def plataforma_exige_login_central(plataforma: str) -> bool:
    return plataforma in PLATAFORMAS_COM_LOGIN_CENTRAL


def url_login_plataforma(plataforma: str) -> str | None:
    return PLATAFORMAS_COM_LOGIN_CENTRAL.get(plataforma)


def _normalizar_plataformas(plataformas: list[str] | tuple[str, ...]) -> list[str]:
    disponiveis = set(fontes_disponiveis_candidatura())
    recebidas = {str(item).strip().casefold() for item in plataformas}
    return [
        fonte
        for fonte in FONTES_SUPORTADAS
        if fonte in disponiveis and fonte.casefold() in recebidas
    ]


def _selecionar_vagas_diversificadas(
    vagas: list[dict[str, Any]],
    plataformas: list[str],
    limite: int,
) -> list[dict[str, Any]]:
    filas: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    plataformas_permitidas = {item.casefold() for item in plataformas}
    chaves_vistas: set[str] = set()

    for vaga in vagas:
        fonte = str(vaga.get("fonte") or "").strip()
        url = str(vaga.get("url_candidatura") or "").strip()
        id_externo = str(vaga.get("id_externo") or url).strip()
        if fonte.casefold() not in plataformas_permitidas:
            continue
        if not validar_url_candidatura(url):
            continue
        chave = gerar_chave_vaga(fonte, id_externo, url)
        if chave in chaves_vistas:
            continue
        chaves_vistas.add(chave)
        filas[fonte].append(vaga)

    selecionadas: list[dict[str, Any]] = []
    while len(selecionadas) < limite:
        adicionou = False
        for plataforma in plataformas:
            if filas[plataforma] and len(selecionadas) < limite:
                selecionadas.append(filas[plataforma].popleft())
                adicionou = True
        if not adicionou:
            break
    return selecionadas


def _validar_usuario_ativo(usuario_id: int) -> bool:
    conexao = criar_conexao()
    try:
        registro = conexao.execute(
            """
            SELECT id
            FROM usuarios
            WHERE id = ? AND banido_em IS NULL
            """,
            (usuario_id,),
        ).fetchone()
        return registro is not None
    finally:
        conexao.close()


def salvar_campanha_candidatura(
    usuario_id: int,
    cargo: str,
    cidade: str,
    estado: str,
    modalidade: str,
    incluir_pcd: bool,
    plataformas: list[str],
    limite_vagas: int,
    vagas: list[dict[str, Any]],
) -> dict[str, Any]:
    cargo_limpo = " ".join((cargo or "").split())[:120]
    cidade_limpa = " ".join((cidade or "").split())[:100]
    estado_limpo = " ".join((estado or "").split()).upper()[:2]
    modalidade_limpa = modalidade if modalidade in {
        "Presencial",
        "Híbrido",
        "Remoto",
    } else "Presencial"
    plataformas_validas = _normalizar_plataformas(plataformas)
    limite_seguro = max(1, min(50, int(limite_vagas or 10)))

    if not _validar_usuario_ativo(usuario_id):
        return {"status": "erro", "mensagem": "Usuário não autorizado."}
    if not cargo_limpo or not cidade_limpa or len(estado_limpo) != 2:
        return {
            "status": "erro",
            "mensagem": "Informe cargo, cidade e UF para criar a campanha.",
        }
    if not plataformas_validas:
        return {
            "status": "erro",
            "mensagem": "Selecione pelo menos uma plataforma disponível.",
        }

    vagas_selecionadas = _selecionar_vagas_diversificadas(
        vagas,
        plataformas_validas,
        limite_seguro,
    )
    agora = _agora_utc()
    aguardando_login = any(
        plataforma_exige_login_central(item)
        for item in plataformas_validas
    )
    status_campanha = "aguardando_login" if aguardando_login else "pronta"

    conexao = criar_conexao()
    try:
        conexao.execute("BEGIN IMMEDIATE")
        cursor = conexao.execute(
            """
            INSERT INTO campanhas_candidatura (
                usuario_id, cargo, cidade, estado, modalidade, incluir_pcd,
                plataformas_json, limite_vagas, status, total_vagas,
                criado_em, atualizado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usuario_id,
                cargo_limpo,
                cidade_limpa,
                estado_limpo,
                modalidade_limpa,
                int(bool(incluir_pcd)),
                json.dumps(plataformas_validas, ensure_ascii=False),
                limite_seguro,
                status_campanha,
                len(vagas_selecionadas),
                agora,
                agora,
            ),
        )
        campanha_id = int(cursor.lastrowid)

        for plataforma in plataformas_validas:
            exige_login = plataforma_exige_login_central(plataforma)
            conexao.execute(
                """
                INSERT INTO logins_plataforma_campanha (
                    campanha_id, plataforma, status, confirmado_em, atualizado_em
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    campanha_id,
                    plataforma,
                    "aguardando" if exige_login else "confirmado",
                    None if exige_login else agora,
                    agora,
                ),
            )

        for vaga in vagas_selecionadas:
            fonte = str(vaga.get("fonte") or "").strip()
            url = str(vaga.get("url_candidatura") or "").strip()
            id_externo = str(vaga.get("id_externo") or url).strip()
            conexao.execute(
                """
                INSERT OR IGNORE INTO itens_campanha_candidatura (
                    campanha_id, chave_vaga, fonte, id_externo, titulo,
                    empresa, local, modalidade, url_candidatura, status,
                    criado_em, atualizado_em
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?)
                """,
                (
                    campanha_id,
                    gerar_chave_vaga(fonte, id_externo, url),
                    fonte,
                    id_externo,
                    str(vaga.get("titulo") or "Título não informado")[:200],
                    str(vaga.get("empresa") or "Empresa não informada")[:200],
                    str(vaga.get("local") or "Local não informado")[:200],
                    str(vaga.get("modalidade") or "Não informada")[:40],
                    url,
                    agora,
                    agora,
                ),
            )
        conexao.commit()
        return {
            "status": "sucesso",
            "campanha_id": campanha_id,
            "total_vagas": len(vagas_selecionadas),
            "aguardando_login": aguardando_login,
            "mensagem": (
                "Campanha criada. Confirme o login nas plataformas indicadas."
                if aguardando_login
                else "Campanha criada e pronta para continuar."
            ),
        }
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


async def preparar_campanha_candidatura(
    usuario_id: int,
    cargo: str,
    cidade: str,
    estado: str,
    modalidade: str,
    incluir_pcd: bool,
    plataformas: list[str],
    limite_vagas: int,
    max_dias: int | None = 30,
) -> dict[str, Any]:
    plataformas_validas = _normalizar_plataformas(plataformas)
    if not plataformas_validas:
        return {
            "status": "erro",
            "mensagem": "Selecione pelo menos uma plataforma disponível.",
        }
    resultado = await buscar_vagas_agregadas(
        cargo=cargo,
        cidade=cidade,
        estado=estado,
        modalidade=modalidade,
        pagina=1,
        max_dias=max_dias,
        incluir_pcd=incluir_pcd,
        fontes_selecionadas=set(plataformas_validas),
    )
    return salvar_campanha_candidatura(
        usuario_id=usuario_id,
        cargo=cargo,
        cidade=cidade,
        estado=estado,
        modalidade=modalidade,
        incluir_pcd=incluir_pcd,
        plataformas=plataformas_validas,
        limite_vagas=limite_vagas,
        vagas=resultado.get("vagas", []),
    )


def listar_campanhas_candidatura(
    usuario_id: int,
    limite: int = 10,
) -> dict[str, Any]:
    limite_seguro = max(1, min(30, int(limite or 10)))
    conexao = criar_conexao()
    try:
        registros = conexao.execute(
            """
            SELECT
                c.*,
                SUM(CASE WHEN i.status = 'pendente' THEN 1 ELSE 0 END)
                    AS pendentes,
                SUM(CASE WHEN i.status = 'candidatado' THEN 1 ELSE 0 END)
                    AS candidatadas,
                SUM(CASE WHEN i.status = 'ignorado' THEN 1 ELSE 0 END)
                    AS ignoradas
            FROM campanhas_candidatura AS c
            LEFT JOIN itens_campanha_candidatura AS i
                ON i.campanha_id = c.id
            WHERE c.usuario_id = ?
            GROUP BY c.id
            ORDER BY c.id DESC
            LIMIT ?
            """,
            (usuario_id, limite_seguro),
        ).fetchall()
        campanhas = []
        for registro in registros:
            item = dict(registro)
            item["plataformas"] = json.loads(item.pop("plataformas_json"))
            for chave in ("pendentes", "candidatadas", "ignoradas"):
                item[chave] = int(item[chave] or 0)
            campanhas.append(item)
        return {"status": "sucesso", "campanhas": campanhas}
    finally:
        conexao.close()


def listar_logins_campanha(
    usuario_id: int,
    campanha_id: int,
) -> list[dict[str, Any]]:
    conexao = criar_conexao()
    try:
        registros = conexao.execute(
            """
            SELECT l.plataforma, l.status, l.confirmado_em
            FROM logins_plataforma_campanha AS l
            JOIN campanhas_candidatura AS c ON c.id = l.campanha_id
            WHERE l.campanha_id = ? AND c.usuario_id = ?
            ORDER BY l.plataforma
            """,
            (campanha_id, usuario_id),
        ).fetchall()
        return [dict(item) for item in registros]
    finally:
        conexao.close()


def confirmar_login_plataforma(
    usuario_id: int,
    campanha_id: int,
    plataforma: str,
) -> dict[str, Any]:
    plataforma_limpa = str(plataforma or "").strip()
    agora = _agora_utc()
    conexao = criar_conexao()
    try:
        conexao.execute("BEGIN IMMEDIATE")
        cursor = conexao.execute(
            """
            UPDATE logins_plataforma_campanha
            SET status = 'confirmado', confirmado_em = ?, atualizado_em = ?
            WHERE campanha_id = ?
              AND plataforma = ?
              AND EXISTS (
                  SELECT 1
                  FROM campanhas_candidatura AS c
                  WHERE c.id = logins_plataforma_campanha.campanha_id
                    AND c.usuario_id = ?
              )
            """,
            (agora, agora, campanha_id, plataforma_limpa, usuario_id),
        )
        if cursor.rowcount != 1:
            conexao.rollback()
            return {"status": "erro", "mensagem": "Plataforma não encontrada."}
        pendentes = conexao.execute(
            """
            SELECT COUNT(*)
            FROM logins_plataforma_campanha
            WHERE campanha_id = ? AND status = 'aguardando'
            """,
            (campanha_id,),
        ).fetchone()[0]
        if pendentes == 0:
            conexao.execute(
                """
                UPDATE campanhas_candidatura
                SET status = 'pronta', atualizado_em = ?
                WHERE id = ? AND usuario_id = ?
                """,
                (agora, campanha_id, usuario_id),
            )
        conexao.commit()
        return {
            "status": "sucesso",
            "mensagem": "Login confirmado. A fila dessa plataforma foi liberada.",
        }
    finally:
        conexao.close()


def listar_itens_campanha(
    usuario_id: int,
    campanha_id: int,
) -> dict[str, Any]:
    conexao = criar_conexao()
    try:
        campanha = conexao.execute(
            """
            SELECT id, status
            FROM campanhas_candidatura
            WHERE id = ? AND usuario_id = ?
            """,
            (campanha_id, usuario_id),
        ).fetchone()
        if not campanha:
            return {"status": "erro", "mensagem": "Campanha não encontrada."}
        registros = conexao.execute(
            """
            SELECT
                i.*,
                l.status AS status_login
            FROM itens_campanha_candidatura AS i
            JOIN logins_plataforma_campanha AS l
                ON l.campanha_id = i.campanha_id
               AND l.plataforma = i.fonte
            WHERE i.campanha_id = ?
            ORDER BY
                CASE i.status
                    WHEN 'pendente' THEN 0
                    WHEN 'candidatado' THEN 1
                    ELSE 2
                END,
                i.id
            """,
            (campanha_id,),
        ).fetchall()
        return {
            "status": "sucesso",
            "campanha_status": campanha["status"],
            "itens": [dict(item) for item in registros],
        }
    finally:
        conexao.close()


def atualizar_item_campanha(
    usuario_id: int,
    item_id: int,
    novo_status: str,
) -> dict[str, Any]:
    if novo_status not in STATUS_ITEM_VALIDOS - {"pendente"}:
        return {"status": "erro", "mensagem": "Status inválido."}
    agora = _agora_utc()
    conexao = criar_conexao()
    try:
        conexao.execute("BEGIN IMMEDIATE")
        item = conexao.execute(
            """
            SELECT i.campanha_id, l.status AS status_login
            FROM itens_campanha_candidatura AS i
            JOIN campanhas_candidatura AS c ON c.id = i.campanha_id
            JOIN logins_plataforma_campanha AS l
                ON l.campanha_id = i.campanha_id
               AND l.plataforma = i.fonte
            WHERE i.id = ? AND c.usuario_id = ?
            """,
            (item_id, usuario_id),
        ).fetchone()
        if not item:
            conexao.rollback()
            return {"status": "erro", "mensagem": "Vaga não encontrada."}
        if item["status_login"] != "confirmado":
            conexao.rollback()
            return {
                "status": "erro",
                "mensagem": "Confirme o login da plataforma antes de continuar.",
            }
        conexao.execute(
            """
            UPDATE itens_campanha_candidatura
            SET status = ?, atualizado_em = ?
            WHERE id = ?
            """,
            (novo_status, agora, item_id),
        )
        pendentes = conexao.execute(
            """
            SELECT COUNT(*)
            FROM itens_campanha_candidatura
            WHERE campanha_id = ? AND status = 'pendente'
            """,
            (item["campanha_id"],),
        ).fetchone()[0]
        if pendentes == 0:
            conexao.execute(
                """
                UPDATE campanhas_candidatura
                SET status = 'concluida', atualizado_em = ?
                WHERE id = ?
                """,
                (agora, item["campanha_id"]),
            )
        conexao.commit()
        return {"status": "sucesso"}
    finally:
        conexao.close()
