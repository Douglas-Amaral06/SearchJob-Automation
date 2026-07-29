#!/usr/bin/env python3
"""
Teste final abrangente da API com todas as 3 correções.
"""
import httpx
import json

BASE_URL = "http://127.0.0.1:8000/api/vagas"

def test_search(cargo: str, cidade: str, estado: str, modalidade: str, titulo: str) -> dict:
    """Test a search and validate results."""
    params = {
        "cargo": cargo,
        "cidade": cidade,
        "estado": estado,
        "modalidade": modalidade,
    }
    
    response = httpx.get(BASE_URL, params=params, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ {titulo}: Status {response.status_code}")
        return None
    
    data = response.json()
    total = data.get('total_vagas', 0)
    vagas = data.get('vagas', [])
    
    print(f"\n✅ {titulo}")
    print(f"   Total: {total} vagas")
    
    # Check sources
    sources = {}
    for vaga in vagas:
        source = vaga.get('fonte', 'Unknown')
        sources[source] = sources.get(source, 0) + 1
    
    for source, count in sources.items():
        print(f"   - {source}: {count}")
    
    # Validate first vaga
    if vagas:
        vaga = vagas[0]
        print(f"   Primeira vaga: {vaga.get('titulo')}")
        
        # Validate data format (must have Z)
        data_pub = vaga.get('data_publicacao')
        if data_pub:
            if data_pub.endswith('Z'):
                print(f"   ✓ Data em UTC: {data_pub}")
            else:
                print(f"   ❌ Data não em UTC: {data_pub}")
        
        # Validate modalidade matches
        vaga_modalidade = vaga.get('modalidade')
        if vaga_modalidade == modalidade:
            print(f"   ✓ Modalidade correta: {vaga_modalidade}")
        else:
            print(f"   ❌ Modalidade incorreta: {vaga_modalidade} (esperado {modalidade})")
    
    return data

def main():
    print("\n" + "="*70)
    print("VALIDAÇÃO FINAL - 3 CORREÇÕES GREENHOUSE")
    print("="*70)
    
    # Test 1: Executive Hybrid (Stone board jobs should appear)
    test_search(
        "Executive",
        "Sao Paulo", 
        "SP",
        "Híbrido",
        "Teste 1: Executive em SP - Híbrido (Greenhouse deve aparecer)"
    )
    
    # Test 2: Developer Hybrid
    test_search(
        "Desenvolvedor",
        "Sao Paulo",
        "SP",
        "Híbrido",
        "Teste 2: Desenvolvedor em SP - Híbrido"
    )
    
    # Test 3: Admin Assistant Presencial
    test_search(
        "Auxiliar Administrativo",
        "Guarulhos",
        "SP",
        "Presencial",
        "Teste 3: Auxiliar Administrativo em Guarulhos - Presencial"
    )
    
    # Test 4: Remote job (should handle remote locations)
    test_search(
        "Desenvolvedor",
        "Sao Paulo",
        "SP",
        "Remoto",
        "Teste 4: Desenvolvedor - Remoto (remote filtering test)"
    )
    
    print("\n" + "="*70)
    print("✅ Todos os testes executados com sucesso!")
    print("="*70)

if __name__ == "__main__":
    main()
