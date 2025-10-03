# db.py
import motor.motor_asyncio
import os
from datetime import datetime, timedelta, timezone

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://kdrama:kdrama@cluster0.2nwrn6k.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
DB_NAME = os.getenv("MONGO_DB", "kdrama")

client = motor.motor_asyncio.AsyncIOMotorClient(
    MONGO_URI,
    tz_aware=True,   # ✅ ensures datetimes come back as timezone-aware
    tzinfo=timezone.utc
)
db = client[DB_NAME]

episodes_collection = db["episodes"]   # permanent episode records (master links)
cache_collection = db["cache"]         # temporary scraped links (expire in ~1hr)
jobs_collection = db["jobs"]           # track transcoding jobs (progress, credits, status)


async def add_episode(ep_id: str, master_links: dict):
    await episodes_collection.update_one(
        {"_id": ep_id},
        {"$set": {"master": master_links, "createdAt": datetime.now(timezone.utc)}},  # ✅ FIXED
        upsert=True
    )

async def get_episode(ep_id: str):
    return await episodes_collection.find_one({"_id": ep_id})


async def get_cached(ep_id: str):
    doc = await cache_collection.find_one({"_id": ep_id})
    if doc:
        return doc.get("links")
    return None


async def set_cached(ep_id: str, links: dict, ttl: int = 3600):
    # Merge new links with existing ones (append mode)
    old_doc = await cache_collection.find_one({"_id": ep_id})
    old_links = old_doc.get("links", {}) if old_doc else {}

    merged = old_links.copy()
    for quality, servers in links.items():
        if quality not in merged:
            merged[quality] = servers
        else:
            merged[quality].update(servers)
    
    print(f"💾 Merging {ep_id}: {sum(len(v) for v in old_links.values())} -> {sum(len(v) for v in merged.values())} total servers")
    
    update_doc = {
        "links": merged,
        "updatedAt": datetime.now(timezone.utc),  # Changed from datetime.now(timezone.utc)
        "expireAt": datetime.now(timezone.utc) + timedelta(seconds=ttl)  # Changed
    }

    print(f"💾 Caching {ep_id}: {sum(len(v) for v in merged.values())} total servers")

    await cache_collection.update_one(
        {"_id": ep_id},
        {"$set": update_doc},
        upsert=True
    )


async def delete_cached(ep_id: str):
    await cache_collection.delete_one({"_id": ep_id})