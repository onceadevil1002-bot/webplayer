# auto_scraper.py - Simple auto-scraper for expired links only
import asyncio
import logging
from datetime import datetime, timedelta
from db import episodes_collection, cache_collection, set_cached, get_episode
from scraper import scrape_vcloud

logger = logging.getLogger("auto_scraper")

CHECK_INTERVAL = 300  # Check every 5 minutes
MIN_SERVERS_REQUIRED = 9

class SimpleAutoScraper:
    def __init__(self):
        self.running = False

    async def find_expired_episodes(self):
        """Find episodes with expired cache"""
        expired_episodes = []
        
        # Get all episodes with master links
        cursor = episodes_collection.find({})
        async for episode_doc in cursor:
            episode_id = episode_doc["_id"]
            
            # Check if cache is expired
            cache_doc = await cache_collection.find_one({"_id": episode_id})
            
            if not cache_doc:
                # No cache at all - needs scraping
                expired_episodes.append(episode_id)
                logger.info(f"Episode {episode_id} has no cache - scheduling scrape")
            else:
                # Check if expired
                expire_time = cache_doc.get("expireAt")
                if expire_time and expire_time <= datetime.utcnow():
                    expired_episodes.append(episode_id)
                    logger.info(f"Episode {episode_id} cache expired - scheduling scrape")
        
        return expired_episodes

    async def auto_scrape_episode(self, episode_id: str):
        """Auto-scrape a single expired episode"""
        try:
            logger.info(f"Auto-scraping expired episode: {episode_id}")
            
            # Get master links
            episode_doc = await get_episode(episode_id)
            if not episode_doc:
                return False
            
            master_links = episode_doc.get("master", {})
            if not master_links:
                return False
            
            # Scrape each quality
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
            
            # Store results
            if scraped_results:
                await set_cached(episode_id, scraped_results, ttl=3600)
                logger.info(f"Auto-scrape completed for {episode_id}: {total_servers} servers")
                return True
            
        except Exception as e:
            logger.exception(f"Auto-scrape failed for {episode_id}: {e}")
        
        return False

    async def run_auto_scraper(self):
        """Main auto-scraper loop"""
        self.running = True
        logger.info("Starting simple auto-scraper for expired links")
        
        while self.running:
            try:
                # Find expired episodes
                expired_episodes = await self.find_expired_episodes()
                
                if expired_episodes:
                    logger.info(f"Found {len(expired_episodes)} expired episodes to scrape")
                    
                    # Scrape expired episodes (limit to 2 concurrent)
                    semaphore = asyncio.Semaphore(2)
                    
                    async def scrape_with_limit(ep_id):
                        async with semaphore:
                            return await self.auto_scrape_episode(ep_id)
                    
                    tasks = [scrape_with_limit(ep_id) for ep_id in expired_episodes]
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Wait before next check
                await asyncio.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.exception(f"Auto-scraper error: {e}")
                await asyncio.sleep(60)

    def stop(self):
        self.running = False

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