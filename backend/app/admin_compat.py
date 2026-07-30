"""Camada estável entre a interface Streamlit e os recursos administrativos."""

from __future__ import annotations

from inspect import signature
from typing import Any

from app import user_resume


MENSAGEM_INDISPONIVEL = (
    "A gestão de usuários está temporariamente indisponível. "
    "Reinicie o aplicativo para concluir a atualização."
)


def _obter_funcao_segura(nome: str):
    funcao = getattr(user_resume, nome, None)
    if not callable(funcao):
        return None
    try:
        if "session_token" not in signature(funcao).parameters:
            return None
    except (TypeError, ValueError):
        return None
    return funcao


def listar_usuarios_admin(
    administrador_id: int,
    busca: str = "",
    status: str = "todos",
    pagina: int = 1,
    limite: int = 25,
    session_token: str | None = None,
) -> dict[str, Any]:
    funcao = _obter_funcao_segura("listar_usuarios_admin")
    if funcao is None:
        return {"status": "erro", "mensagem": MENSAGEM_INDISPONIVEL}
    return funcao(
        administrador_id=administrador_id,
        busca=busca,
        status=status,
        pagina=pagina,
        limite=limite,
        session_token=session_token,
    )


def definir_banimento_usuario(
    administrador_id: int,
    usuario_id: int,
    banir: bool,
    motivo: str,
    codigo_2fa: str,
    session_token: str | None = None,
) -> dict[str, Any]:
    funcao = _obter_funcao_segura("definir_banimento_usuario")
    if funcao is None:
        return {"status": "erro", "mensagem": MENSAGEM_INDISPONIVEL}
    return funcao(
        administrador_id=administrador_id,
        usuario_id=usuario_id,
        banir=banir,
        motivo=motivo,
        codigo_2fa=codigo_2fa,
        session_token=session_token,
    )
