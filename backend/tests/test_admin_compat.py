from app import admin_compat


def test_admin_compat_nao_quebra_import_se_deploy_estiver_dessincronizado(
    monkeypatch,
):
    monkeypatch.delattr(
        admin_compat.user_resume,
        "listar_usuarios_admin",
    )
    monkeypatch.delattr(
        admin_compat.user_resume,
        "definir_banimento_usuario",
    )

    listagem = admin_compat.listar_usuarios_admin(1)
    alteracao = admin_compat.definir_banimento_usuario(
        administrador_id=1,
        usuario_id=2,
        banir=True,
        motivo="Teste de compatibilidade.",
        codigo_2fa="123456",
    )

    assert listagem["status"] == "erro"
    assert alteracao["status"] == "erro"
    assert "temporariamente indisponível" in listagem["mensagem"]
