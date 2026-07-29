from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import REMOTIVE_CACHE_TTL_SECONDS
from app.services.remote_jobs_utils import (
    cargo_remoto_compativel,
    data_dentro_do_periodo,
    localizacao_remota_compativel,
    normalizar_data,
    ordenar_e_paginar,
    remover_html,
    url_publica_valida,
)
from app.utils.pcd import vaga_eh_pcd


logger = logging.getLogger(__name__)
API_URL = "https://remotive.com/api/remote-jobs"
_cache: tuple[list[dict[str, Any]], float] | None = None
_cache_lock: asyncio.Lock | None = None


def _lock() -> asyncio.Lock:
    global _cache_lock
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()
    return _cache_lock


async def _obter_feed() -> list[dict[str, Any]]:
    global _cache
    agora = time.monotonic()
    if _cache and agora - _cache[1] < REMOTIVE_CACHE_TTL_SECONDS:
        return _cache[0]

    async with _lock():
        agora = time.monotonic()
        if _cache and agora - _cache[1] < REMOTIVE_CACHE_TTL_SECONDS:
            return _cache[0]

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resposta = await client.get(
                    API_URL,
                    headers={"User-Agent": "SearchEmprego/1.0"},
                )
                resposta.raise_for_status()
                corpo = resposta.json()
        except (httpx.HTTPError, ValueError) as erro:
            logger.warning("Remotive indisponível: %s", type(erro).__name__)
            return _cache[0] if _cache else []

        jobs = corpo.get("jobs", []) if isinstance(corpo, dict) else []
        jobs_validos = [job for job in jobs if isinstance(job, dict)]
        _cache = (jobs_validos, time.monotonic())
        return jobs_validos


async def buscar_vagas_remotive(
    cargo: str,
    cidade: str,
    estado: str,
    modalidade: str,
    pagina: int = 1,
    max_dias: int | None = None,
    incluir_pcd: bool = False,
) -> dict:
    del cidade, estado
    if modalidade != "Remoto":
        return {"fonte": "Remotive", "total_fonte": 0, "vagas": []}

    vagas: list[dict] = []
    for job in await _obter_feed():
        titulo = str(job.get("title") or "").strip()
        url = str(job.get("url") or "").strip()
        descricao = remover_html(job.get("description"))
        local = str(job.get("candidate_required_location") or "").strip() or "Remoto"

        if not titulo or not url_publica_valida(url):
            continue
        if not cargo_remoto_compativel(titulo, descricao, cargo):
            continue
        if not localizacao_remota_compativel(local):
            continue

        eh_pcd = vaga_eh_pcd(f"{titulo} {descricao}")
        if eh_pcd and not incluir_pcd:
            continue

        data = normalizar_data(job.get("publication_date"))
        if not data_dentro_do_periodo(data, max_dias):
            continue

        id_externo = str(job.get("id") or url)
        vagas.append(
            {
                "id_externo": f"remotive:{id_externo}",
                "titulo": titulo,
                "empresa": str(job.get("company_name") or "Empresa não informada").strip(),
                "local": local,
                "modalidade": "Remoto",
                "url_candidatura": url,
                "data_publicacao": data,
                "candidatura_simplificada": False,
                "ja_candidatado": False,
                "eh_pcd": eh_pcd,
                "fonte": "Remotive",
            }
        )

    total = len(vagas)
    return {
        "fonte": "Remotive",
        "total_fonte": total,
        "vagas": ordenar_e_paginar(vagas, pagina),
    }
