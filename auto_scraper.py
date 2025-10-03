# auto_scraper.py - Fixed version with proper __init__ and indentation
import asyncio
import logging
# auto_scraper.py - Fix datetime imports and usage
from datetime import datetime, timezone
from db import episodes_collection, cache_collection, set_cached, get_episode
from scraper import scrape_vcloud

logger = logging.getLogger("auto_scraper")

CHECK_INTERVAL = 300  # Check every 5 minutes
MIN_SERVERS_REQUIRED = 9
CACHE_TTL = 3600 # 6 hours cache (instead of 1 hour)

class SimpleAutoScraper:
    def __init__(self):
        """FIXED: Proper __init__ method (was init before)"""
        self.running = False
        logger.info("SimpleAutoScraper initialized")

    # In the find_expired_episodes method:
    async def find_expired_episodes(self):
        """Find episodes with expired cache"""
        expired_episodes = []
        
        cursor = episodes_collection.find({})
        async for episode_doc in cursor:
            episode_id = episode_doc["_id"]
            
            cache_doc = await cache_collection.find_one({"_id": episode_id})
            
            if not cache_doc:
                expired_episodes.append(episode_id)
                logger.info(f"Episode {episode_id} has no cache - scheduling scrape")
            else:
                expire_time = cache_doc.get("expireAt")
                if expire_time and expire_time <= datetime.now(timezone.utc):  # FIXED
                    expired_episodes.append(episode_id)
                    logger.info(f"Episode {episode_id} cache expired - scheduling scrape")
                    
        return expired_episodes
        


    async def auto_scrape_episode(self, episode_id: str):
        """Auto-scrape a single expired episode"""
        try:
            logger.info(f"Auto-scraping expired episode: {episode_id}")
            
            episode_doc = await get_episode(episode_id)
            if not episode_doc:
                return False
            
            master_links = episode_doc.get("master", {})
            if not master_links:
                return False
            
            scraped_results = {}
            total_servers = 0
            
            for quality, vcloud_url in master_links.items():
                try:
                    servers = await scrape_vcloud(vcloud_url)
                    if servers:
                        scraped_results[quality] = servers
                        total_servers += len(servers)
                        logger.info(f"Auto-scraped {quality}p: {len(servers)} servers")
                    else:
                        scraped_results[quality] = {}
                except Exception as e:
                    logger.error(f"Failed to auto-scrape {quality}p: {e}")
                    scraped_results[quality] = {}
            
            if scraped_results:
                await set_cached(episode_id, scraped_results, ttl=CACHE_TTL)
                logger.info(f"Auto-scrape completed for {episode_id}: {total_servers} servers")
                return True
            
        except Exception as e:
            logger.exception(f"Auto-scrape failed for {episode_id}: {e}")
        
        return False

    async def run_auto_scraper(self):
        """FIXED: Proper indentation - this is a class method"""
        self.running = True
        logger.info("Starting simple auto-scraper for expired links")
        
        while self.running:
            try:
                expired_episodes = await self.find_expired_episodes()
                
                if expired_episodes:
                    logger.info(f"Found {len(expired_episodes)} expired episodes to scrape")
                    
                    # Limit to 2 concurrent scrapes to avoid overload
                    semaphore = asyncio.Semaphore(1)
                    
                    async def scrape_with_limit(ep_id):
                        async with semaphore:
                            return await self.auto_scrape_episode(ep_id)
                    
                    tasks = [scrape_with_limit(ep_id) for ep_id in expired_episodes]
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                await asyncio.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.exception(f"Auto-scraper error: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop the auto-scraper"""
        self.running = False
        logger.info("Auto-scraper stopped")


# Global instance
auto_scraper = SimpleAutoScraper()


async def count_servers_in_links(links_dict):
    """Count total servers in cached links"""
    if not links_dict:
        return 0
    total = 0
    for quality, servers in links_dict.items():
        if isinstance(servers, dict):
            total += len(servers)
    return total


async def check_episode_servers(episode_id: str):
    """Check if episode has enough servers"""
    cache_doc = await cache_collection.find_one({"_id": episode_id})
    
    if not cache_doc:
        return {
            "server_count": 0,
            "needs_force_scrape": True,
            "message": "No cached servers found. Please use Force Scrape."
        }
    
    links = cache_doc.get("links", {})
    server_count = await count_servers_in_links(links)
    
    if server_count < MIN_SERVERS_REQUIRED:
        return {
            "server_count": server_count,
            "needs_force_scrape": True,
            "message": f"Only {server_count} servers available (minimum: {MIN_SERVERS_REQUIRED}). If some servers are missing then please use Force Scrape in the right corner."
        }
    
    return {
        "server_count": server_count,
        "needs_force_scrape": False,
        "message": f"{server_count} servers available"
    }