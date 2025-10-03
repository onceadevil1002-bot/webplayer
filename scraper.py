# scraper.py - Lazy browser version (closes when not needed)
import asyncio
import re
import logging
from typing import Dict
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import random

logger = logging.getLogger("scraper")
logging.basicConfig(level=logging.INFO)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
]

PREFERRED_SERVERS = ["pixel", "fsl", "10gbps", "server"]

# Global playwright reference (NOT browser)
_playwright = None


def set_playwright(playwright):
    """Set global playwright instance from server startup"""
    global _playwright
    _playwright = playwright
    logger.info("Global playwright registered (lazy browser mode)")


async def get_playwright():
    """Get or create playwright instance"""
    global _playwright
    
    if not _playwright:
        _playwright = await async_playwright().start()
        logger.info("Created new playwright instance")
    
    return _playwright


async def try_http_extract(session: aiohttp.ClientSession, vcloud_url: str) -> Dict[str,str]:
    """HTTP extraction with improved reliability"""
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive"
        }
        
        timeout = aiohttp.ClientTimeout(total=20)
        async with session.get(vcloud_url, headers=headers, timeout=timeout, 
                             allow_redirects=True, ssl=False) as resp:
            if resp.status != 200:
                logger.debug(f"HTTP fetch returned {resp.status}")
                return {}
            text = await resp.text()
    except Exception as e:
        logger.debug(f"HTTP fetch error: {e}")
        return {}

    soup = BeautifulSoup(text, "html.parser")

    # Find server links
    links = {}
    for a in soup.select("a"):
        href = a.get("href")
        if not href:
            continue
        href_str = str(href)
        text = str(a.get_text() or "").lower()
        if any(k in text for k in PREFERRED_SERVERS) or any(k in href_str.lower() for k in PREFERRED_SERVERS):
            links[text.strip() or href_str] = urljoin(vcloud_url, href_str)

    # Regex fallback
    if not links:
        for match in re.finditer(r"(https?://[^\s'\"<>]+(?:pixeldrain|fsl|10gbps|pixelserver|vcloud)[^\s'\"<>]*)", text, re.IGNORECASE):
            url = match.group(1)
            links["auto"] = url

    # Validate links
    valid = {}
    if links:
        for name, link in links.items():
            try:
                async with session.head(link, timeout=aiohttp.ClientTimeout(total=10), headers=headers, allow_redirects=True) as h:
                    if h.status in (200, 302, 303, 307):
                        valid[name] = link
                        continue
            except Exception:
                pass

            try:
                range_headers = {**headers, "Range": "bytes=0-1023"}
                async with session.get(link, timeout=aiohttp.ClientTimeout(total=12), headers=range_headers, allow_redirects=True) as g:
                    if g.status in (200, 206, 302, 303):
                        valid[name] = link
            except Exception:
                pass
                
    return valid


async def playwright_extract(vcloud_url: str, timeout=20000) -> Dict[str, str]:
    """
    Playwright extraction using LAZY browser (created per-call, destroyed after)
    This saves ~200MB RAM when not scraping
    """
    browser = None
    context = None
    results = {}
    
    try:
        # Skip Playwright for direct video files
        if vcloud_url.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
            logger.info(f"Skipping Playwright for direct video file")
            return {}
        
        # Get playwright and create TEMPORARY browser
        pw = await get_playwright()
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ]
        )
        logger.info("🚀 Lazy browser launched (will close after scrape)")
        
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        # Block resources
        await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda r: r.abort())
        await page.route("**/ads/**", lambda r: r.abort())
        await page.route("**/analytics/**", lambda r: r.abort())

        await page.goto(vcloud_url, wait_until="domcontentloaded", timeout=timeout)

        # Try clicking buttons
        for t in ["generate", "get link", "download", "create link", "start", "watch"]:
            try:
                btn = await page.query_selector(f"text={t}")
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(1500)
                    break
            except Exception:
                continue

        await page.wait_for_timeout(1500)

        # Extract from anchors
        anchors = await page.query_selector_all("a")
        for a in anchors:
            href = await a.get_attribute("href")
            if href:
                text = (await a.inner_text() or "").lower()
                lowered = (text + " " + href).lower()
                if any(k in lowered for k in PREFERRED_SERVERS) or "pixeldrain" in href or "fsl" in href:
                    results[text.strip() or href] = href

        # Extract from source tags
        for s in await page.query_selector_all("source"):
            src = await s.get_attribute("src")
            if src:
                results[f"source:{src[:30]}"] = src

        # Regex fallback
        html = await page.content()
        for match in re.finditer(r"(https?://[^\s'\"<>]+(?:pixeldrain|fsl|pixel|10gbps|vcloud)[^\s'\"<>]*)", html, re.IGNORECASE):
            results[match.group(1)[:40]] = match.group(1)

        return results

    except Exception as e:
        logger.error(f"Playwright extraction error: {e}")
        return {}
    
    finally:
        # CRITICAL: Always close browser to free memory
        if context:
            try:
                await context.close()
            except Exception as e:
                logger.error(f"Error closing context: {e}")
        
        if browser:
            try:
                await browser.close()
                logger.info("🔒 Lazy browser closed (freed ~200MB)")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")


async def scrape_vcloud(url: str, prefer_fast=True, max_retries=2) -> Dict[str,str]:
    """
    Main scraping orchestrator with lazy browser
    - Tries HTTP first (0 MB overhead)
    - Only launches browser if needed
    - Always closes browser after use
    """
    final_results = {}
    
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"Retry attempt {attempt + 1} for {url}")
            await asyncio.sleep(2)
        
        # Try HTTP extraction first (no browser = 0 MB)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            try:
                http_res = await try_http_extract(session, url)
                if http_res:
                    ordered = {}
                    for k in PREFERRED_SERVERS:
                        for key, link in list(http_res.items()):
                            if k in key.lower() or k in link.lower():
                                ordered[key] = link
                                http_res.pop(key, None)
                    ordered.update(http_res)
                    final_results.update(ordered)
                    logger.info(f"HTTP extraction: found {len(final_results)} servers")
            except Exception as e:
                logger.debug(f"HTTP extraction failed: {e}")

        # Only use Playwright if we need more servers
        if len(final_results) < 2:
            try:
                logger.info("Launching browser for additional scraping...")
                playwright_res = await playwright_extract(url)
                final_results.update(playwright_res)
                logger.info(f"Playwright extraction: added {len(playwright_res)} servers")
            except Exception as e:
                logger.debug(f"Playwright extraction failed: {e}")
        
        if len(final_results) >= 1:
            break
    
    logger.info(f"Scraping completed: found {len(final_results)} servers total")
    return final_results