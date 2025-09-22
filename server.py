# server.py (fixed version)
import os
import uvicorn
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from auto_scraper import auto_scraper, check_episode_servers
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from db import (
    episodes_collection,
    add_episode, get_episode,
    get_cached, set_cached, delete_cached
)
from scraper import scrape_vcloud

logger = logging.getLogger("server")
logging.basicConfig(level=logging.INFO)

# --- App & static ---
app = FastAPI()

# Mount static files BEFORE other routes
app.mount("/static", StaticFiles(directory="."), name="static")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------- Player -------------------
@app.get("/player", response_class=HTMLResponse)
async def player_page(show: str = Query(...), ep: int = Query(...)):
    """Serve the player HTML"""
    # Return the fixed HTML content directly
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>KDRAMA Player</title>
  <style>
    /* === KDRAMA Player Custom Styles === */
    body { margin:0; font-family:Arial, sans-serif; background:#111; color:#fff; }
    .topbar { display:flex; justify-content:space-between; align-items:center;
      padding:12px; background:#000; }
    .branding { display:flex; align-items:center; gap:8px; }
    .branding span { background:#2a9df4; padding:6px 10px; border-radius:4px; font-weight:bold; }
    .channel { font-size:18px; font-weight:bold; }
    .btn { background:#222; padding:6px 10px; margin-left:6px; border:1px solid #333;
           border-radius:4px; cursor:pointer; color:#fff; text-decoration:none; display:inline-block; }
    .btn:hover { background:#333; }
    .video-container { max-width:950px; margin:20px auto; }
    .servers, .downloads { max-width:950px; margin:10px auto; }
    .servers button, .downloads button, .downloads a {
      margin:5px; padding:6px 12px; border-radius:6px; background:#333; color:#fff;
      border:none; cursor:pointer; text-decoration:none; display:inline-block;
    }
    .servers button:hover, .downloads button:hover, .downloads a:hover { background:#444; }
    .servers button.active { background:#2a9df4; }
    .error { color:#f66; margin-top:6px; }
    .status { color:#4a9; margin:10px; }
    #videoPlayer { width: 100%; height: 500px; }
  </style>
  <link href="https://vjs.zencdn.net/7.21.1/video-js.css" rel="stylesheet">
</head>
<body>
  <div class="topbar">
    <div class="branding">
      <span>🎬</span>
      <div class="channel">KDRAMA Player</div>
    </div>
    <div class="utils">
      <button class="btn" onclick="openDirect()">Open Direct</button>
      <button class="btn" onclick="openVLC()">Play in VLC</button>
      <button class="btn" onclick="forceScrap()">Force Scrap</button>
      <button class="btn" onclick="refreshPage()">Refresh</button>
    </div>
  </div>

  <div class="video-container">
    <video id="videoPlayer" class="video-js vjs-default-skin" controls preload="auto" width="950" height="500"></video>
  </div>

  <div class="servers">
    <h3>Servers</h3>
    <div id="servers"></div>
    <div id="status" class="status"></div>
  </div>

  <div class="downloads">
    <h3>Download</h3>
    <div id="downloads"></div>
  </div>

  <script src="https://vjs.zencdn.net/7.21.1/video.min.js"></script>
  <script>
    let currentLink = null;
    let player = null;

    async function loadEpisode() {
      try {
        const params = new URLSearchParams(window.location.search);
        const show = params.get("show");
        const ep = params.get("ep");

        if (!show || !ep) {
          document.getElementById("servers").innerText = "❌ Missing show/ep params";
          return;
        }

        document.getElementById("status").innerText = "Loading episode data...";

        const res = await fetch(`/get_link?show=${encodeURIComponent(show)}&ep=${encodeURIComponent(ep)}`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        
        let data = await res.json();
        console.log("Episode data (raw):", data);

        const serversDiv = document.getElementById("servers");
        const downloadsDiv = document.getElementById("downloads");
        const statusDiv = document.getElementById("status");
        
        serversDiv.innerHTML = "";
        downloadsDiv.innerHTML = "";

        // Initialize player once
        if (!player) {
          player = videojs("videoPlayer", {
            fluid: true,
            responsive: true,
            playbackRates: [0.5, 1, 1.25, 1.5, 2]
          });
        }

        // Handle both cached and master responses
        let links = {};
        if (data.status === "cached" && data.links) {
          links = data.links;
          statusDiv.innerText = "✅ Cached links loaded";
        } else if (data.status === "master" && data.links) {
          statusDiv.innerText = "⚠️ Only master links found. Click 'Force Scrap' to get direct links.";
          // Show master links as fallback
          for (const [quality, masterUrl] of Object.entries(data.links)) {
            const btn = document.createElement("button");
            btn.innerText = `${quality}p (Master)`;
            btn.onclick = () => {
              currentLink = masterUrl;
              player.src({ src: masterUrl, type: "video/mp4" });
              player.ready(() => {
                player.play();
              });
            };
            serversDiv.appendChild(btn);
          }
          return;
        } else {
          statusDiv.innerText = "❌ No links found";
          return;
        }

        console.log("Processing links:", links);

        let hasAnyServers = false;

        // Process cached links
        for (const [quality, servers] of Object.entries(links)) {
          console.log(`Processing ${quality}:`, servers);
          
          if (!servers || typeof servers !== 'object') {
            console.log(`Skipping ${quality} - invalid servers data`);
            continue;
          }

          // Create server buttons
          for (const [serverName, link] of Object.entries(servers)) {
            if (!link) continue;
            
            hasAnyServers = true;
            const btn = document.createElement("button");
            btn.innerText = `${quality}p (${serverName})`;
            btn.onclick = () => {
              // Remove active class from all buttons
              document.querySelectorAll('.servers button').forEach(b => b.classList.remove('active'));
              btn.classList.add('active');
              
              currentLink = link;
              console.log("Playing:", link);
              
              player.src({ src: link, type: "video/mp4" });
              player.ready(() => {
                player.play().catch(e => {
                  console.error("Play error:", e);
                  statusDiv.innerText = "❌ Failed to play video. Try another server.";
                });
              });
            };
            serversDiv.appendChild(btn);
          }

          // Create download button (use first available server for that quality)
            // Create download buttons (one for each server)
          for (const [serverName, link] of Object.entries(servers)) {
            if (!link) continue;
            
            const a = document.createElement("a");
            a.href = link;
            a.innerText = `${quality}p (${serverName})`;
            a.className = "btn";
            a.setAttribute("download", "");
            a.target = "_blank";
            downloadsDiv.appendChild(a);
          }
        }

        if (hasAnyServers) {
          // Auto-play highest quality available
          const qualityOrder = ["1080", "720", "480"];
          for (const q of qualityOrder) {
            if (links[q] && Object.keys(links[q]).length > 0) {
              const firstServer = Object.values(links[q])[0];
              if (firstServer) {
                currentLink = firstServer;
                player.src({ src: firstServer, type: "video/mp4" });
                
                // Mark first button as active
                const firstBtn = serversDiv.querySelector('button');
                if (firstBtn) firstBtn.classList.add('active');
                
                console.log("Auto-playing:", firstServer);
                statusDiv.innerText = `✅ Ready to play ${q}p`;
                break;
              }
            }
          }
        } else {
          statusDiv.innerText = "❌ No playable servers found";
        }

      } catch (err) {
        console.error("Load error:", err);
        document.getElementById("status").innerHTML = `❌ Error loading episode: ${err.message}`;
        document.getElementById("servers").innerHTML = `<div class="error">Failed to load episode data</div>`;
      }
    }

    function openDirect() {
      if (currentLink) {
        window.open(currentLink, "_blank");
      } else {
        alert("No video selected");
      }
    }

    function openVLC() {
      if (currentLink) {
        window.location.href = "vlc://" + currentLink;
      } else {
        alert("No video selected");
      }
    }

    async function forceScrap() {
      const params = new URLSearchParams(window.location.search);
      const show = params.get("show");
      const ep = params.get("ep");

      if (!show || !ep) {
        alert("Missing show/ep parameters");
        return;
      }

      document.getElementById("status").innerText = "🔄 Scraping...";

      try {
        const res = await fetch(`/scrape?show=${encodeURIComponent(show)}&ep=${encodeURIComponent(ep)}`);
        const data = await res.json();
        console.log("Force scrape result:", data);

        if (data.status === "ok") {
          document.getElementById("status").innerText = "✅ Scraping complete, reloading...";
          setTimeout(() => loadEpisode(), 1000); // reload with fresh cache
        } else {
          document.getElementById("status").innerText = "❌ Scraping failed";
          alert("Scraping failed: " + (data.message || "Unknown error"));
        }
      } catch (err) {
        console.error("Scrape error:", err);
        document.getElementById("status").innerText = "❌ Scraping error";
        alert("Scraping error: " + err.message);
      }
    }

    function refreshPage() {
      window.location.reload();
    }

    // Auto-run when page loads
    window.addEventListener('DOMContentLoaded', loadEpisode);
  </script>
</body>
</html>'''
    return HTMLResponse(html_content)

# ------------------- Admin Panel -------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """Admin UI page (simple)."""
    html = """
    <html>
    <head>
        <title>Admin Panel</title>
        <style>
            body { font-family: Arial; margin: 24px; background: #f7f7f7; }
            input, button { margin: 5px; padding: 8px; }
            .section { background: white; padding: 16px; margin: 16px 0; border-radius: 8px; }
            .result { margin-top: 10px; padding: 10px; background: #eef; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <h1>📺 Admin Panel</h1>

        <div class="section">
            <h2>Add Episode</h2>
            <form id="addForm">
                Show: <input name="show" required><br>
                Episode: <input name="ep" type="number" required><br>
                480p: <input name="link480"><br>
                720p: <input name="link720"><br>
                1080p: <input name="link1080"><br>
                <button type="submit">Add</button>
            </form>
            <div id="addResult" class="result"></div>
        </div>

        <div class="section">
            <h2>Remove Episode</h2>
            <form id="removeForm">
                Show: <input name="show" required><br>
                Episode: <input name="ep" type="number" required><br>
                <button type="submit">Remove</button>
            </form>
            <div id="removeResult" class="result"></div>
        </div>

        <div class="section">
            <h2>Search</h2>
            <form id="searchForm">
                Show: <input name="show" required><br>
                <button type="submit">Search</button>
            </form>
            <div id="searchResult" class="result"></div>
        </div>

        <script>
        document.getElementById('addForm').onsubmit = async (e) => {
            e.preventDefault();
            let fd = new FormData(e.target);
            let res = await fetch('/admin/add_episode', {method:'POST', body:fd});
            let data = await res.json();
            if(data.status === 'ok'){
                document.getElementById('addResult').innerHTML =
                  "✅ Added<br>Player: <a href='" + data.player_link + "' target='_blank'>" + data.player_link + "</a>";
            } else {
                document.getElementById('addResult').innerText = JSON.stringify(data, null, 2);
            }
        };
        document.getElementById('removeForm').onsubmit = async (e) => {
            e.preventDefault();
            let fd = new FormData(e.target);
            let res = await fetch('/admin/remove_episode', {method:'POST', body:fd});
            let data = await res.json();
            document.getElementById('removeResult').innerText = JSON.stringify(data, null, 2);
        };
        document.getElementById('searchForm').onsubmit = async (e) => {
            e.preventDefault();
            let fd = new FormData(e.target);
            let res = await fetch('/admin/search_episode?show='+fd.get('show'));
            let data = await res.json();
            document.getElementById('searchResult').innerText = JSON.stringify(data, null, 2);
        };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

# ------------------- API -------------------

@app.get("/scrape")
async def scrape_handler(show: str = Query(...), ep: int = Query(...)):
    ep_id = f"{show}:{ep}"
    doc = await get_episode(ep_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Episode not found")

    master = doc.get("master", {})
    scraped = {}

    for q, url in master.items():
        print(f"🔍 Scraping {q}p from {url}")
        try:
            res = await scrape_vcloud(url)
            if res:
                scraped[q] = res
                print(f"✅ {q}p -> {len(res)} servers found")
            else:
                scraped[q] = {}
                print(f"⚠️ {q}p -> no servers found")
        except Exception as e:
            scraped[q] = {}
            print(f"❌ {q}p -> error: {e}")

    await set_cached(ep_id, scraped, ttl=3600)
    return {"status": "ok", "servers": scraped}


@app.get("/get_link")
async def get_link(show: str = Query(...), ep: int = Query(...)):
    ep_id = f"{show}:{ep}"
    
    # Check server count
    server_info = await check_episode_servers(ep_id)
    
    cached = await get_cached(ep_id)
    if cached:
        return {
            "status": "cached", 
            "links": cached,
            "server_info": server_info
        }

    doc = await get_episode(ep_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    return {
        "status": "master", 
        "links": doc.get("master", {}),
        "server_info": server_info
    }

@app.on_event("startup")
async def startup_event():
    logger.info("Starting auto-scraper background task...")
    asyncio.create_task(auto_scraper.run_auto_scraper())

@app.on_event("shutdown") 
async def shutdown_event():
    auto_scraper.stop()
@app.post("/admin/add_episode")
async def admin_add_episode(
    show: str = Form(...), ep: int = Form(...),
    link480: Optional[str] = Form(None),
    link720: Optional[str] = Form(None),
    link1080: Optional[str] = Form(None),
):
    ep_id = f"{show}:{ep}"
    master = {}
    if link480: master["480"] = link480.strip()
    if link720: master["720"] = link720.strip()
    if link1080: master["1080"] = link1080.strip()

    if not master:
        return JSONResponse({"status":"error","msg":"Need at least one link"}, status_code=400)

    await add_episode(ep_id, master)
    return {"status":"ok","episode":ep_id,"player_link":f"/player?show={show}&ep={ep}"}


@app.post("/admin/remove_episode")
async def admin_remove_episode(show: str = Form(...), ep: int = Form(...)):
    ep_id = f"{show}:{ep}"
    res = await episodes_collection.delete_one({"_id": ep_id})
    return {"status": "ok" if res.deleted_count else "not_found", "episode": ep_id}


@app.get("/admin/search_episode")
async def admin_search_episode(show: str):
    cursor = episodes_collection.find({"_id":{"$regex":f"^{show}:"}})
    docs = await cursor.to_list(1000)
    return {"count":len(docs),"episodes":docs}


@app.get("/debug/episode")
async def debug_episode(show: str = Query(...), ep: int = Query(...)):
    """Debug: show episode info with master + cached"""
    ep_id = f"{show}:{ep}"
    doc = await get_episode(ep_id)
    cached = await get_cached(ep_id)
    return {
        "episode": ep_id,
        "master": doc.get("master") if doc else None,
        "cached": cached,
    }

# ------------------- Main -------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))