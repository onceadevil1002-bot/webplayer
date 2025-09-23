# scraper.py - Enhanced version keeping original logic but with reliability improvements
import asyncio
import re
import logging
from typing import Dict, Optional, Tuple, List
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import random

logger = logging.getLogger("scraper")
logging.basicConfig(level=logging.INFO)

# Rotate user agents to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
]

# Keep your original server preferences
PREFERRED_SERVERS = ["pixel", "fsl", "10gbps", "server"]


async def try_http_extract(session: aiohttp.ClientSession, vcloud_url: str) -> Dict[str,str]:
    """
    Enhanced version of your original HTTP extract - SAME LOGIC, better reliability
    """
    try:
        # Use rotating user agents and better headers
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive"
        }
        
        # Increased timeout and handle redirects
        timeout = aiohttp.ClientTimeout(total=20)
        async with session.get(vcloud_url, headers=headers, timeout=timeout, 
                             allow_redirects=True, ssl=False) as resp:
            if resp.status != 200:
                logger.debug("HTTP fetch returned %s", resp.status)
                return {}
            text = await resp.text()
    except Exception as e:
        logger.debug("HTTP fetch error: %s", e)
        return {}

    soup = BeautifulSoup(text, "html.parser")

    # Strategy A: find anchors with server labels (YOUR ORIGINAL LOGIC)
    links = {}
    for a in soup.select("a"):
        href = a.get("href")
        if not href: 
            continue
        text = (a.get_text() or "").lower()
        if any(k in text for k in PREFERRED_SERVERS) or any(k in href.lower() for k in PREFERRED_SERVERS):
            links[text.strip() or href] = urljoin(vcloud_url, href)

    # Strategy B: regex search (YOUR ORIGINAL LOGIC)
    if not links:
        for match in re.finditer(r"(https?://[^\s'\"<>]+(?:pixeldrain|fsl|10gbps|pixelserver|vcloud)[^\s'\"<>]*)", text, re.IGNORECASE):
            url = match.group(1)
            name = "auto"
            links[name] = url

    # Enhanced validation - try multiple validation approaches
    valid = {}
    if links:
        for name, link in links.items():
            # Try 1: HEAD request (your original)
            try:
                async with session.head(link, timeout=10, headers=headers, allow_redirects=True) as h:
                    if h.status in (200, 302, 303, 307):
                        valid[name] = link
                        continue
            except Exception:
                pass
            
            # Try 2: GET with range (more reliable)
            try:
                range_headers = {**headers, "Range": "bytes=0-1023"}
                async with session.get(link, timeout=12, headers=range_headers, allow_redirects=True) as g:
                    if g.status in (200, 206, 302, 303):
                        valid[name] = link
                        continue
            except Exception:
                pass
            
            # Try 3: Basic GET (fallback)
            try:
                async with session.get(link, timeout=15, headers=headers, allow_redirects=True) as g:
                    if g.status in (200, 302, 403):  # 403 might still work for download
                        valid[name] = link
            except Exception:
                continue
                
    return valid


async def playwright_extract(vcloud_url: str, timeout=20000) -> Dict[str,str]:
    """
    Enhanced version of your original Playwright extract - SAME LOGIC, with ad blocking
    """
    results = {}
    try:
        async with async_playwright() as p:
            # Enhanced browser launch with ad blocking
            browser = await p.chromium.launch(
                headless=True, 
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--block-new-web-contents",  # Block popups
                    "--disable-extensions-except=/path/to/ublock",  # Would need uBlock path
                    "--load-extension=/path/to/ublock",
                    "--disable-plugins",
                    "--disable-images",  # Faster loading
                ]
            )
            
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                java_script_enabled=True
            )
            
            page = await context.new_page()
            
            # Block ads, images, and other resource types that slow things down
            await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
            await page.route("**/ads/**", lambda route: route.abort())
            await page.route("**/analytics/**", lambda route: route.abort())
            await page.route("**/tracking/**", lambda route: route.abort())
            await page.route("**/*google*ads*", lambda route: route.abort())
            await page.route("**/*doubleclick*", lambda route: route.abort())
            
            await page.goto(vcloud_url, wait_until="domcontentloaded", timeout=timeout)

            # YOUR ORIGINAL BUTTON CLICKING LOGIC - enhanced
            btn_texts = ["generate", "get link", "download", "create link", "start", "watch"]
            for t in btn_texts:
                try:
                    btn = await page.query_selector(f"button:has-text('{t}')") or await page.query_selector(f"a:has-text('{t}')")
                    if btn:
                        await btn.click(timeout=3000)
                        await page.wait_for_timeout(1500)  # Slightly longer wait
                        break
                except PlaywrightTimeout:
                    continue
                except Exception:
                    continue

            # Wait a bit more for dynamic content
            await page.wait_for_timeout(2000)

            # YOUR ORIGINAL ANCHOR EXTRACTION LOGIC
            anchors = await page.query_selector_all("a")
            for a in anchors:
                href = await a.get_attribute("href")
                text = (await a.inner_text()).lower() if await a.inner_text() else ""
                if not href:
                    continue
                lowered = (text + " " + href).lower()
                if any(k in lowered for k in PREFERRED_SERVERS) or "pixeldrain" in href or "fsl" in href:
                    results[text.strip() or href] = href

            # YOUR ORIGINAL SOURCE TAG LOGIC
            sources = await page.query_selector_all("source")
            for s in sources:
                src = await s.get_attribute("src")
                if src:
                    results[f"source:{src[:30]}"] = src

            # YOUR ORIGINAL REGEX SEARCH
            html = await page.content()
            for match in re.finditer(r"(https?://[^\s'\"<>]+(?:pixeldrain|fsl|pixel|10gbps|vcloud)[^\s'\"<>]*)", html, re.IGNORECASE):
                results[match.group(1)[:40]] = match.group(1)
                
            await browser.close()
    except Exception as e:
        logger.exception("Playwright extraction error: %s", e)
    return results


async def scrape_vcloud(url: str, prefer_fast=True, max_retries=2) -> Dict[str,str]:
    """
    Enhanced version of your original orchestrator - SAME LOGIC, with retry capability
    """
    final_results = {}
    
    # Try up to max_retries times for reliability
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"Retry attempt {attempt + 1} for {url}")
            await asyncio.sleep(2)  # Small delay between retries
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            http_res = {}
            try:
                http_res = await try_http_extract(session, url)
            except Exception as e:
                logger.debug("http_extraction failed: %s", e)

            # YOUR ORIGINAL LOGIC: If we have results, prioritize and return
            if http_res:
                ordered = {}
                for k in PREFERRED_SERVERS:
                    for key, link in list(http_res.items()):
                        if k in key.lower() or k in link.lower():
                            ordered[key] = link
                            http_res.pop(key, None)
                ordered.update(http_res)
                final_results.update(ordered)

        # YOUR ORIGINAL FALLBACK: try Playwright if HTTP didn't work well
        if len(final_results) < 2:  # If we don't have enough servers, try playwright
            try:
                playwright_res = await playwright_extract(url)
                final_results.update(playwright_res)
            except Exception as e:
                logger.debug("playwright_extraction failed: %s", e)
        
        # If we have good results, break
        if len(final_results) >= 1:
            break
    
    logger.info(f"Scraping completed: found {len(final_results)} servers")
    return final_results