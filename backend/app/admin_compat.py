"""Camada estável entre a interface Streamlit e os recursos administrativos."""

from __future__ import annotations

from typing import Any

from app import user_resume


MENSAGEM_INDISPONIVEL = (
    "A gestão de usuários está temporariamente indisponível. "
    "Reinicie o aplicativo para concluir a atualização."
)


def listar_usuarios_admin(
    administrador_id: int,
    busca: str = "",
    status: str = "todos",
    pagina: int = 1,
    limite: int = 25,
) -> dict[str, Any]:
    funcao = getattr(user_resume, "listar_usuarios_admin", None)
    if not callable(funcao):
        return {"status": "erro", "mensagem": MENSAGEM_INDISPONIVEL}
    return funcao(
        administrador_id=administrador_id,
        busca=busca,
        status=status,
        pagina=pagina,
        limite=limite,
    )


def definir_banimento_usuario(
    administrador_id: int,
    usuario_id: int,
    banir: bool,
    motivo: str,
    codigo_2fa: str,
) -> dict[str, Any]:
    funcao = getattr(user_resume, "definir_banimento_usuario", None)
    if not callable(funcao):
        return {"status": "erro", "mensagem": MENSAGEM_INDISPONIVEL}
    return funcao(
        administrador_id=administrador_id,
        usuario_id=usuario_id,
        banir=banir,
        motivo=motivo,
        codigo_2fa=codigo_2fa,
    )
