# 🎧 Spotify Playlist Splitter

Uses Claude AI to intelligently split a large Spotify playlist into themed sub-playlists by genre, mood, era, and more.

---

## Setup

### 1. Install dependencies
```bash
pip install requests
```

### 2. Create a Spotify Developer App

1. Go to https://developer.spotify.com/dashboard
2. Click **Create App**
3. Fill in any name/description
4. Set **Redirect URI** to: `http://localhost:8888/callback`
5. Save — then copy your **Client ID** and **Client Secret**

### 3. Get your Anthropic API Key

Get one at https://console.anthropic.com

---

## Usage

### Option A: Set environment variables (recommended)
```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export ANTHROPIC_API_KEY="your_anthropic_key"

python playlist_splitter.py
```

### Option B: Enter keys interactively
```bash
python playlist_splitter.py
# It will prompt you for credentials
```

### Then:
1. Your browser opens for Spotify login — approve the permissions
2. Paste your playlist URL (e.g. `https://open.spotify.com/playlist/37i9dQ...`)
3. Claude analyzes the tracks and proposes sub-playlists
4. Review each proposal: **[a]pprove**, **[r]ename**, or **[s]kip**
5. Approved playlists are created automatically in your Spotify account

---

## Notes

- Works best on playlists of 30–300 tracks
- Very large playlists (300+) may hit Claude's context limits — consider splitting in two passes
- Created playlists are **private** by default
- Requires a Spotify Developer app in **Development Mode** (supports up to 25 users)
