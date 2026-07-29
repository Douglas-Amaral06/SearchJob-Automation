from app.services.job_aggregator import normalizar_cidade_consulta


def test_sp_capital_vira_sao_paulo():
    assert normalizar_cidade_consulta("SP Capital", "SP") == "São Paulo"


def test_sao_paulo_capital_vira_sao_paulo():
    assert normalizar_cidade_consulta("São Paulo Capital", "SP") == "São Paulo"


def test_cidade_comum_e_preservada():
    assert normalizar_cidade_consulta("Guarulhos", "SP") == "Guarulhos"
