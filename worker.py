# worker.py
import asyncio
import os
from cache import set_cached, get_cached
from scraper import scrape_vcloud
import logging

logger = logging.getLogger("worker")
logging.basicConfig(level=logging.INFO)

# Example episodes to pre-warm (in real life: from DB)
# Format: list of dicts: {"source":"vcloud", "url": "..."}
TO_PREFETCH = []  # fill from your DB: episodes with vcloud url

PREFETCH_INTERVAL = int(os.getenv("PREFETCH_INTERVAL_SECONDS", 15*60))  # every 15 min

async def prefetch_loop():
    while True:
        if not TO_PREFETCH:
            await asyncio.sleep(5)
            continue
        for item in TO_PREFETCH:
            try:
                key = f"linkcache:{item['source']}:{item['url']}"
                cached = await get_cached(key)
                # Always refresh if older than TTL or not exists
                links = await scrape_vcloud(item['url'])
                if links:
                    await set_cached(key, links, ttl=PREFETCH_INTERVAL + 60)
                    logger.info("Prefetched %s", item['url'])
            except Exception as e:
                logger.exception("Prefetch error: %s", e)
        await asyncio.sleep(PREFETCH_INTERVAL)

if __name__ == "__main__":
    asyncio.run(prefetch_loop())
