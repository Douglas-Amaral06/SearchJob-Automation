"""
Script de investigação para descobrir como o portal.gupy.io busca vagas.
Uso exclusivo para descoberta de endpoints, não para produção.
"""

import asyncio
import sys
from playwright.async_api import async_playwright


async def investigar_gupy_portal():
    """Investiga o portal público da Gupy para encontrar endpoint de busca."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        # Registrar todas as requisições XHR/fetch
        requisicoes_capturadas = []
        
        async def handle_route(route):
            """Captura todas as requisições."""
            if "api" in route.request.url or "search" in route.request.url:
                requisicoes_capturadas.append({
                    "url": route.request.url,
                    "metodo": route.request.method,
                    "headers": dict(route.request.headers),
                })
            await route.continue_()
        
        await context.route("**/*", handle_route)
        page = await context.new_page()
        
        # Acessar o portal e buscar vagas
        query = "desenvolvedor sao paulo"
        url = f"https://portal.gupy.io/job-search/term={query}"
        
        print(f"Acessando: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        
        print(f"\n✓ Página carregada")
        print(f"Total de requisições capturadas: {len(requisicoes_capturadas)}")
        
        # Filtrar apenas APIs interessantes
        apis_interessantes = [r for r in requisicoes_capturadas if "api" in r["url"].lower()]
        
        print(f"\nRequisições de API encontradas:")
        for i, req in enumerate(apis_interessantes, 1):
            print(f"\n{i}. {req['metodo']} {req['url']}")
        
        await browser.close()
        
        return apis_interessantes


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(investigar_gupy_portal())
