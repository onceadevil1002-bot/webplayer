# KDRAMA Player

A web-based video player service for KDRAMA episodes with automatic link scraping and caching capabilities. Built with FastAPI, this service provides a seamless viewing experience with multiple server options and an admin panel for episode management.

## Features

- **Web Player**: HTML5 video player with Video.js for smooth playback
- **Multi-Server Support**: Automatic scraping of video links from multiple servers (PixelDrain, FSL, 10Gbps, etc.)
- **Caching System**: Redis-like caching with MongoDB for scraped links (1-hour TTL)
- **Auto-Scraper**: Background service that automatically refreshes expired cached links
- **Admin Panel**: Web interface for adding, removing, and searching episodes
- **Docker Support**: Containerized deployment with Playwright for reliable scraping
- **CORS Enabled**: Supports cross-origin requests for web integration

## Installation

### Prerequisites

- Python 3.8+
- MongoDB (local or cloud instance)
- Docker (optional, for containerized deployment)

### Local Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd kdrama-player
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables (optional):
```bash
export MONGO_URI="your-mongodb-connection-string"
export MONGO_DB="kdrama"
export PORT="8000"
```

4. Run the server:
```bash
python server.py
```

The server will start on `http://localhost:8000`

### Docker Deployment

1. Build the Docker image:
```bash
docker build -t kdrama-player .
```

2. Run the container:
```bash
docker run -p 8000:8000 \
  -e MONGO_URI="your-mongodb-connection-string" \
  -e MONGO_DB="kdrama" \
  kdrama-player
```

## Usage

### Web Player

Access the player at: `http://localhost:8000/player?show=<show_name>&ep=<episode_number>`

Example: `http://localhost:8000/player?show=TheGlory&ep=1`

The player supports:
- Multiple quality options (480p, 720p, 1080p)
- Multiple servers per quality
- Auto-play highest available quality
- Direct link opening
- VLC integration
- Force scraping for missing servers

### Admin Panel

Access the admin panel at: `http://localhost:8000/admin`

Features:
- Add new episodes with master links
- Remove episodes
- Search episodes by show name
- View episode details

## API Endpoints

### Player Endpoints

- `GET /` - Health check
- `GET /player` - Video player HTML page
- `GET /get_link?show=<show>&ep=<ep>` - Get cached or master links for an episode
- `GET /scrape?show=<show>&ep=<ep>` - Force scrape links for an episode

### Admin Endpoints

- `GET /admin` - Admin panel HTML page
- `POST /admin/add_episode` - Add new episode (form data: show, ep, link480, link720, link1080)
- `POST /admin/remove_episode` - Remove episode (form data: show, ep)
- `GET /admin/search_episode?show=<show>` - Search episodes by show name

### Debug Endpoints

- `GET /debug/episode?show=<show>&ep=<ep>` - Debug episode info (master + cached links)

## Database Schema

### Episodes Collection
```json
{
  "_id": "ShowName:EpisodeNumber",
  "master": {
    "480": "https://vcloud.example.com/480p",
    "720": "https://vcloud.example.com/720p",
    "1080": "https://vcloud.example.com/1080p"
  },
  "createdAt": "2024-01-01T00:00:00Z"
}
```

### Cache Collection
```json
{
  "_id": "ShowName:EpisodeNumber",
  "links": {
    "480": {
      "pixel": "https://pixeldrain.com/...",
      "fsl": "https://fsl.com/..."
    },
    "720": {
      "10gbps": "https://10gbps.com/..."
    }
  },
  "updatedAt": "2024-01-01T00:00:00Z",
  "expireAt": "2024-01-01T01:00:00Z"
}
```

## Environment Variables

- `MONGO_URI` - MongoDB connection string (default: cloud MongoDB instance)
- `MONGO_DB` - Database name (default: "kdrama")
- `PORT` - Server port (default: 8000)

## Architecture

- **server.py**: FastAPI application with endpoints and HTML serving
- **scraper.py**: Link scraping logic using aiohttp and Playwright
- **auto_scraper.py**: Background service for cache refresh
- **db.py**: MongoDB operations for episodes and cache
- **player.html**: Video.js player interface (served inline)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This service is intended for personal use and educational purposes. Please respect copyright laws and content ownership rights when using this software.
