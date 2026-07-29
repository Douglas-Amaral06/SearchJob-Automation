import asyncio
import unicodedata
from collections.abc import Awaitable

from app.config import (
    GREENHOUSE_BOARD_TOKENS,
    GREENHOUSE_ENABLED,
    GUPY_ENABLED,
    JOBICY_ENABLED,
    JOOBLE_ENABLED,
    REMOTIVE_ENABLED,
)
from app.services.adzuna_service import buscar_vagas_adzuna
from app.services.gupy_service import buscar_vagas_gupy
from app.services.jooble_service import buscar_vagas_jooble
from app.services.greenhouse_service import buscar_vagas_greenhouse
from app.services.jobicy_service import buscar_vagas_jobicy
from app.services.remotive_service import buscar_vagas_remotive
from app.utils.deduplicador import remover_vagas_duplicadas


def normalizar_cidade_consulta(cidade: str, estado: str) -> str:
    """Converte atalhos usuais da capital para o nome aceito pelas fontes."""
    cidade_limpa = " ".join((cidade or "").split())
    estado_limpo = " ".join((estado or "").split())

    def sem_acentos(texto: str) -> str:
        normalizado = unicodedata.normalize("NFKD", texto)
        return "".join(
            caractere
            for caractere in normalizado
            if not unicodedata.combining(caractere)
        ).casefold()

    cidade_norm = sem_acentos(cidade_limpa)
    estado_norm = sem_acentos(estado_limpo)

    if estado_norm in {"sp", "sao paulo"} and cidade_norm in {
        "sp",
        "sp capital",
        "capital",
        "sao paulo capital",
    }:
        return "São Paulo"

    if cidade_norm.endswith(" capital"):
        return cidade_limpa[: -len(" capital")].strip()

    return cidade_limpa


async def buscar_vagas_agregadas(
    cargo: str,
    cidade: str,
    estado: str,
    modalidade: str,
    pagina: int = 1,
    max_dias: int | None = None,
    incluir_pcd: bool = False,
):
    cidade_consulta = normalizar_cidade_consulta(cidade, estado)

    buscas: list[Awaitable] = [
        buscar_vagas_adzuna(
            cargo=cargo,
            cidade=cidade_consulta,
            estado=estado,
            modalidade=modalidade,
            pagina=pagina,
            max_dias=max_dias,
            incluir_pcd=incluir_pcd,
        )
    ]

    if JOOBLE_ENABLED:
        buscas.append(
            buscar_vagas_jooble(
                cargo=cargo,
                cidade=cidade_consulta,
                estado=estado,
                modalidade=modalidade,
                pagina=pagina,
                max_dias=max_dias,
                incluir_pcd=incluir_pcd,
            )
        )

    if GUPY_ENABLED:
        buscas.append(
            buscar_vagas_gupy(
                cargo=cargo,
                cidade=cidade_consulta,
                estado=estado,
                modalidade=modalidade,
                pagina=pagina,
                max_dias=max_dias,
                incluir_pcd=incluir_pcd,
            )
        )

    if GREENHOUSE_ENABLED and GREENHOUSE_BOARD_TOKENS:
        buscas.append(
            buscar_vagas_greenhouse(
                cargo=cargo,
                cidade=cidade_consulta,
                estado=estado,
                modalidade=modalidade,
                pagina=pagina,
                max_dias=max_dias,
                incluir_pcd=incluir_pcd,
                boards=GREENHOUSE_BOARD_TOKENS,
            )
        )

    if JOBICY_ENABLED:
        buscas.append(
            buscar_vagas_jobicy(
                cargo=cargo,
                cidade=cidade_consulta,
                estado=estado,
                modalidade=modalidade,
                pagina=pagina,
                max_dias=max_dias,
                incluir_pcd=incluir_pcd,
            )
        )

    if REMOTIVE_ENABLED:
        buscas.append(
            buscar_vagas_remotive(
                cargo=cargo,
                cidade=cidade_consulta,
                estado=estado,
                modalidade=modalidade,
                pagina=pagina,
                max_dias=max_dias,
                incluir_pcd=incluir_pcd,
            )
        )

    resultados = await asyncio.gather(
        *buscas,
        return_exceptions=True,
    )

    vagas: list[dict] = []
    fontes: list[dict] = []

    for resultado in resultados:
        if isinstance(resultado, Exception):
            print(f"Erro em uma fonte: {resultado}")
            continue

        vagas_da_fonte = resultado.get("vagas", [])

        vagas.extend(vagas_da_fonte)

        fontes.append(
            {
                "fonte": resultado.get("fonte", "Desconhecida"),
                "total_fonte": resultado.get("total_fonte", 0),
                "retornadas": len(vagas_da_fonte),
            }
        )

    vagas = remover_vagas_duplicadas(vagas)

    return {
        "vagas": vagas,
        "fontes": fontes,
    }
