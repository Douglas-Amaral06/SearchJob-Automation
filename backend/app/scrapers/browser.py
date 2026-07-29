import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright


async def abrir_navegador(headless: bool = True):
    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )

    context = await browser.new_context(
        locale="pt-BR",
        viewport={"width": 1366, "height": 768},
    )

    page = await context.new_page()

    return playwright, browser, context, page