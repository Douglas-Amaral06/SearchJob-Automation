#!/usr/bin/env python3
"""
Investigação dos boards Greenhouse para encontrar vagas brasileiras reais.
"""
import httpx
import json
from datetime import datetime

BOARDS = ["stripe", "figma", "airbnb", "stone", "getnet"]

async def investigar_board(board_token: str):
    """Investiga um board e retorna resumo de vagas."""
    print(f"\n{'='*60}")
    print(f"Board: {board_token}")
    print(f"{'='*60}")
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
            response = await client.get(
                url,
                headers={"User-Agent": "SearchEmprego/1.0 (+http://localhost)"}
            )
            
            if response.status_code != 200:
                print(f"ERROR: HTTP {response.status_code}")
                return None
            
            data = response.json()
            jobs = data.get("jobs", [])
            print(f"Total de vagas: {len(jobs)}")
            
            if not jobs:
                print("Sem vagas neste board")
                return None
            
            # Procurar por vagas brasileiras ou globais
            for idx, job in enumerate(jobs[:20]):  # Verificar primeiras 20
                titulo = job.get("title", "")
                location = job.get("location", {})
                location_name = location.get("name", "") if isinstance(location, dict) else ""
                content = job.get("content", "")
                url_job = job.get("absolute_url", "")
                updated_at = job.get("updated_at", "")
                
                # Verificar se é brasileira ou global
                location_lower = (location_name or "").lower()
                titulo_lower = titulo.lower()
                
                # Heurística: procurar palavras-chave brasileiras ou globais
                eh_brasileira = any(w in location_lower for w in ["brasil", "br", "são paulo", "sp", "rio", "minas", "bahia"])
                eh_global = any(w in location_lower for w in ["worldwide", "global", "remote", "any", "anywhere"])
                
                if eh_brasileira or eh_global or not location_name:
                    print(f"\n  [{idx+1}] {titulo}")
                    print(f"      Local: {location_name or '(não informado)'}")
                    print(f"      URL: {url_job}")
                    print(f"      Data: {updated_at}")
                    
                    # Verificar modalidade nos metadados
                    if "remote" in titulo_lower or "remote" in location_lower:
                        print(f"      Modalidade (detectada): Remoto")
                    elif "on-site" in titulo_lower or "presencial" in location_lower.replace("-", " "):
                        print(f"      Modalidade (detectada): Presencial")
                    else:
                        print(f"      Modalidade (detectada): Não informada")
                    
                    # Mostrar snippet de conteúdo
                    if content:
                        snippet = content[:200].replace("<", "").replace(">", "").replace("\n", " ")
                        print(f"      Snippet: {snippet}...")
                    
                    return {
                        "board": board_token,
                        "titulo": titulo,
                        "local": location_name or "(não informado)",
                        "url": url_job,
                        "data": updated_at,
                    }
            
            print("Nenhuma vaga brasileira ou global encontrada nas primeiras 20")
            return None
    
    except Exception as e:
        print(f"ERROR: {str(e)[:100]}")
        return None


async def main():
    import asyncio
    
    print("Investigando boards Greenhouse...")
    print(f"Boards: {', '.join(BOARDS)}")
    
    vaga_encontrada = None
    
    for board in BOARDS:
        resultado = await investigar_board(board)
        if resultado and not vaga_encontrada:
            vaga_encontrada = resultado
    
    print(f"\n{'='*60}")
    if vaga_encontrada:
        print("VAGA REAL ENCONTRADA PARA VALIDAÇÃO:")
        print(json.dumps(vaga_encontrada, indent=2, ensure_ascii=False))
    else:
        print("NENHUMA VAGA BRASILEIRA/GLOBAL ENCONTRADA")
        print("\nRecomendação: Verificar se boards precisam ser atualizados com tokens mais ativos.")
    
    return vaga_encontrada


if __name__ == "__main__":
    import asyncio
    resultado = asyncio.run(main())
