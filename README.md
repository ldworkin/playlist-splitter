# 🎧 Spotify Playlist Splitter

Uses Claude AI to intelligently split a large Spotify playlist into themed sub-playlists by genre, mood, era, and more. Built with Streamlit.

---

## Setup

### 1. Install dependencies
```bash
pip install streamlit requests
```

### 2. Create a Spotify Developer App

1. Go to https://developer.spotify.com/dashboard
2. Click **Create App**
3. Fill in any name/description
4. Set **Redirect URI** to: `http://127.0.0.1:8501`
5. Save — then copy your **Client ID** and **Client Secret**

### 3. Get an Anthropic API Key

Get one at https://console.anthropic.com

### 4. Configure secrets

Create the file `.streamlit/secrets.toml`:

```toml
SPOTIFY_CLIENT_ID = "your_client_id"
SPOTIFY_CLIENT_SECRET = "your_client_secret"
ANTHROPIC_API_KEY = "your_anthropic_key"
REDIRECT_URI = "http://127.0.0.1:8501"
```

---

## Running locally

```bash
streamlit run app.py
```

The app opens at `http://127.0.0.1:8501`. Make sure to use `127.0.0.1` (not `localhost`) — it must match the redirect URI registered in your Spotify app exactly.

### Flow

1. Click **Connect to Spotify** and log in
2. Paste a playlist URL or ID (or press Analyze to use the default)
3. Claude analyzes the tracks and proposes sub-playlists
4. Review the proposals — type feedback to revise, or click **Accept & Create Playlists**
5. Playlists are created in your Spotify account
6. Optionally, ask Claude to suggest new songs to add to any of the new playlists

---

## Deploying to Streamlit Cloud

1. Push this repo to GitHub (`.streamlit/secrets.toml` is gitignored — don't commit it)
2. Go to https://streamlit.io/cloud and connect your GitHub repo
3. In the app settings, open **Secrets** and paste the contents of your `secrets.toml`
4. Update your Spotify app's redirect URI to the Streamlit Cloud URL (e.g. `https://yourapp.streamlit.app`)
5. Update `REDIRECT_URI` in the Streamlit Cloud secrets to match

---

## Notes

- Works best on playlists of 30–300 tracks
- Created playlists are **private** by default
- Requires a Spotify Developer app in **Development Mode** (supports up to 25 users)
