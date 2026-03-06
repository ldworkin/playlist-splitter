#!/usr/bin/env python3
"""
Spotify Playlist Splitter — Streamlit Web App
Uses Claude to intelligently split a large playlist into themed sub-playlists.
"""

import json
import time
import requests
import urllib.parse
import streamlit as st

# ─── CONFIG ──────────────────────────────────────────────────────────────────

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SCOPES = "playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-6"

SPOTIFY_CLIENT_ID = st.secrets["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = st.secrets["SPOTIFY_CLIENT_SECRET"]
ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]

DEFAULT_ID = "5Eee1iOXo44hJIIWLzmVFr"


# ─── SPOTIFY HELPERS ─────────────────────────────────────────────────────────

def spotify_get(endpoint, token):
    resp = requests.get(
        f"{SPOTIFY_API_BASE}{endpoint}",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()


def fetch_playlist_tracks(playlist_id, token):
    tracks = []
    url = f"/playlists/{playlist_id}/items?limit=100"
    while url:
        if url.startswith("/"):
            data = spotify_get(url, token)
        else:
            data = requests.get(url, headers={"Authorization": f"Bearer {token}"}).json()
        for item in data.get("items", []):
            track = item.get("item") or item.get("track")
            if track and track.get("id"):
                tracks.append(track)
        url = data.get("next")
        time.sleep(0.05)
    return tracks


def fetch_artist_genres(artist_ids, token):
    genres = {}
    for i in range(0, len(artist_ids), 50):
        batch = artist_ids[i:i + 50]
        try:
            data = spotify_get(f"/artists?ids={','.join(batch)}", token)
            for artist in data.get("artists", []):
                if artist:
                    genres[artist["id"]] = artist.get("genres", [])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                return genres  # Extended Access not available, skip genres
            raise
        time.sleep(0.1)
    return genres


def create_playlist(name, description, token):
    resp = requests.post(
        f"{SPOTIFY_API_BASE}/me/playlists",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"name": name, "description": description, "public": False}
    )
    resp.raise_for_status()
    return resp.json()["id"]


def add_tracks_to_playlist(playlist_id, track_ids, token):
    uris = [f"spotify:track:{tid}" for tid in track_ids]
    for i in range(0, len(uris), 100):
        resp = requests.post(
            f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/items",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"uris": uris[i:i + 100]}
        )
        resp.raise_for_status()
        time.sleep(0.1)


def search_track(query, token):
    resp = requests.get(
        f"{SPOTIFY_API_BASE}/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": query, "type": "track", "limit": 1}
    )
    resp.raise_for_status()
    items = resp.json().get("tracks", {}).get("items", [])
    return items[0] if items else None


def parse_playlist_id(url_or_id):
    if "spotify.com/playlist/" in url_or_id:
        part = url_or_id.split("spotify.com/playlist/")[1]
        return part.split("?")[0].split("/")[0]
    return url_or_id.strip()


# ─── CLAUDE HELPERS ───────────────────────────────────────────────────────────

def ask_claude(messages):
    resp = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={"model": CLAUDE_MODEL, "max_tokens": 4096, "messages": messages}
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def build_track_list_for_llm(tracks, artist_genres):
    lines = []
    for i, t in enumerate(tracks):
        artists = t.get("artists", [])
        artist_names = ", ".join(a["name"] for a in artists)
        primary_artist_id = artists[0]["id"] if artists else None
        genres = artist_genres.get(primary_artist_id, [])
        genre_str = f" [{', '.join(genres[:3])}]" if genres else ""
        year = (t.get("album", {}).get("release_date") or "")[:4]
        year_str = f" ({year})" if year else ""
        lines.append(f"{i + 1}. \"{t['name']}\" – {artist_names}{year_str}{genre_str}")
    return "\n".join(lines)


def parse_proposals(raw):
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array found in Claude response:\n{raw}")
    return json.loads(raw[start:end + 1])


def render_proposals(proposals, tracks):
    for i, group in enumerate(proposals):
        track_nums = group.get("track_numbers", [])
        group_tracks = [tracks[n - 1] for n in track_nums if 1 <= n <= len(tracks)]
        with st.expander(f"**{i + 1}. {group['name']}** — {len(group_tracks)} tracks", expanded=True):
            st.caption(group.get("description", ""))
            for t in group_tracks:
                artists = ", ".join(a["name"] for a in t.get("artists", []))
                st.write(f"• \"{t['name']}\" – {artists}")


def suggest_additions(group, all_tracks):
    track_list = "\n".join(
        f"- \"{t['name']}\" by {', '.join(a['name'] for a in t.get('artists', []))}"
        for t in group["resolved_tracks"]
    )
    full_library = "\n".join(
        f"- \"{t['name']}\" by {', '.join(a['name'] for a in t.get('artists', []))}"
        for t in all_tracks
    )
    prompt = f"""You are a music expert. Here is a playlist called "{group['name']}":

{group['description']}

Current tracks in this playlist:
{track_list}

For broader context, here is the user's full original playlist (to give you a sense of their overall taste):
{full_library}

Suggest 8–10 additional songs that would fit well in this specific playlist. They must not already appear anywhere in the original playlist above.
Respond with ONLY a JSON array of strings in the format "Artist - Title", no markdown, no explanation.
Example: ["Lorde - Royals", "Lana Del Rey - Summertime Sadness"]"""

    raw = ask_claude([{"role": "user", "content": prompt}])
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        return []
    return json.loads(raw[start:end + 1])


# ─── APP ──────────────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "step": "auth",
        "token": None,
        "user_display_name": None,
        "tracks": None,
        "artist_genres": None,
        "playlist_info": None,
        "messages": [],
        "proposals": None,
        "approved": None,
        "suggestions_data": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset():
    for k in ["token", "user_display_name", "tracks", "artist_genres", "playlist_info",
              "proposals", "approved"]:
        st.session_state[k] = None
    st.session_state.messages = []
    st.session_state.suggestions_data = {}
    st.session_state.step = "auth"


def main():
    st.set_page_config(page_title="Spotify Playlist Splitter", page_icon="🎧", layout="centered")
    st.title("🎧 Spotify Playlist Splitter")
    st.caption("Split any playlist into themed sub-playlists using Claude AI")

    init_state()

    # Handle OAuth callback (Spotify redirects back with ?code=...)
    params = st.query_params
    if "code" in params and st.session_state.step == "auth":
        with st.spinner("Authenticating with Spotify..."):
            try:
                resp = requests.post(SPOTIFY_TOKEN_URL, data={
                    "grant_type": "authorization_code",
                    "code": params["code"],
                    "redirect_uri": REDIRECT_URI,
                    "client_id": SPOTIFY_CLIENT_ID,
                    "client_secret": SPOTIFY_CLIENT_SECRET,
                })
                resp.raise_for_status()
                token = resp.json()["access_token"]
                user = requests.get(
                    f"{SPOTIFY_API_BASE}/me",
                    headers={"Authorization": f"Bearer {token}"}
                ).json()
                st.session_state.token = token
                st.session_state.user_display_name = user.get("display_name", user.get("id", "User"))
                st.session_state.step = "playlist"
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                return

    # ── STEP: auth ────────────────────────────────────────────────────────────
    if st.session_state.step == "auth":
        st.write("Connect your Spotify account to get started.")

        auth_params = {
            "client_id": SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        }
        auth_url = f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"
        st.link_button("Connect to Spotify", auth_url, type="primary")
        return

    # ── STEP: playlist ────────────────────────────────────────────────────────
    if st.session_state.step == "playlist":
        st.success(f"Logged in as {st.session_state.user_display_name}")

        playlist_input = st.text_input(
            "Spotify playlist URL or ID",
            placeholder=f"Leave blank to use default playlist"
        )

        if st.button("Analyze Playlist", type="primary"):
            playlist_id = parse_playlist_id(playlist_input.strip()) if playlist_input.strip() else DEFAULT_ID

            try:
                with st.spinner("Fetching playlist..."):
                    info = spotify_get(f"/playlists/{playlist_id}", st.session_state.token)
                    tracks = fetch_playlist_tracks(playlist_id, st.session_state.token)

                if not tracks:
                    st.error("No tracks found in that playlist.")
                    return

                with st.spinner(f"Fetching genre data for {len(tracks)} tracks..."):
                    all_artist_ids = list({
                        a["id"] for t in tracks for a in t.get("artists", []) if a.get("id")
                    })
                    artist_genres = fetch_artist_genres(all_artist_ids, st.session_state.token)

                with st.spinner(f"Asking Claude to analyze {len(tracks)} tracks..."):
                    track_list = build_track_list_for_llm(tracks, artist_genres)
                    system_prompt = f"""You are a music expert helping organize a Spotify playlist of {len(tracks)} songs into logical sub-playlists.

Here is the full track list (format: "Title" – Artist (Year) [genres]):

{track_list}

When proposing or revising groupings, respond with ONLY a JSON array, no markdown, no explanation outside the JSON. Format:
[
  {{
    "name": "Playlist Name",
    "description": "A short description of the vibe/theme (1-2 sentences)",
    "reasoning": "Why these tracks belong together",
    "track_numbers": [1, 3, 7, 12, ...]
  }},
  ...
]

Track numbers refer to the numbered list above (1-indexed). Every track should appear in exactly one group. Every group must have at least 5 tracks."""

                    initial_request = """Please analyze these tracks and propose 3–5 sub-playlists that group them in a meaningful way.
Consider: genre, era/decade, mood/energy, tempo, subgenre, or thematic similarity.
Every track should appear in exactly one group. Each group must have at least 5 tracks."""

                    messages = [{"role": "user", "content": f"{system_prompt}\n\n{initial_request}"}]
                    raw = ask_claude(messages)
                    messages.append({"role": "assistant", "content": raw})
                    proposals = parse_proposals(raw)

                st.session_state.playlist_info = info
                st.session_state.tracks = tracks
                st.session_state.artist_genres = artist_genres
                st.session_state.messages = messages
                st.session_state.proposals = proposals
                st.session_state.step = "reviewing"
                st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")
        return

    # ── STEP: reviewing ───────────────────────────────────────────────────────
    if st.session_state.step == "reviewing":
        info = st.session_state.playlist_info
        tracks = st.session_state.tracks

        st.subheader(f"Proposals for \"{info['name']}\" ({len(tracks)} tracks)")
        render_proposals(st.session_state.proposals, tracks)

        st.divider()
        feedback = st.text_area(
            "Give feedback to Claude to revise, or leave blank and click Accept",
            key="feedback_input",
            height=100
        )

        col1, col2, col3 = st.columns([3, 3, 1])
        with col1:
            revise = st.button("Revise with Claude", type="secondary", use_container_width=True)
        with col2:
            accept = st.button("Accept & Create Playlists", type="primary", use_container_width=True)
        with col3:
            if st.button("Exit", use_container_width=True):
                reset()
                st.rerun()

        if revise:
            if not feedback.strip():
                st.warning("Enter some feedback first.")
            else:
                with st.spinner("Asking Claude to revise..."):
                    try:
                        msgs = st.session_state.messages
                        msgs.append({"role": "user", "content": feedback.strip()})
                        raw = ask_claude(msgs)
                        msgs.append({"role": "assistant", "content": raw})
                        st.session_state.messages = msgs
                        st.session_state.proposals = parse_proposals(raw)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error from Claude: {e}")

        if accept:
            with st.spinner("Creating playlists on Spotify..."):
                try:
                    source_name = info["name"]
                    approved = []
                    for group in st.session_state.proposals:
                        track_nums = group.get("track_numbers", [])
                        group_tracks = [tracks[n - 1] for n in track_nums if 1 <= n <= len(tracks)]
                        description = f"{group['description']} (split from \"{source_name}\" by Playlist Splitter)"
                        pid = create_playlist(group["name"], description, st.session_state.token)
                        track_ids = [t["id"] for t in group_tracks if t.get("id")]
                        add_tracks_to_playlist(pid, track_ids, st.session_state.token)
                        approved.append({**group, "resolved_tracks": group_tracks, "spotify_id": pid})

                    st.session_state.approved = approved
                    st.session_state.step = "suggestions"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating playlists: {e}")
        return

    # ── STEP: suggestions ─────────────────────────────────────────────────────
    if st.session_state.step == "suggestions":
        approved = st.session_state.approved

        st.success(f"Created {len(approved)} playlists!")
        for group in approved:
            pid = group["spotify_id"]
            n = len(group["resolved_tracks"])
            st.write(f"**{group['name']}** — {n} tracks — [Open in Spotify](https://open.spotify.com/playlist/{pid})")

        st.divider()
        st.subheader("Song Suggestions (optional)")
        st.write("Want Claude to suggest additional songs for any of your new playlists?")

        playlist_names = [g["name"] for g in approved]
        selected_names = st.multiselect("Select playlists to get suggestions for", playlist_names)

        if st.button("Get Suggestions", type="primary", disabled=not selected_names):
            selected_groups = [g for g in approved if g["name"] in selected_names]
            suggestions_data = dict(st.session_state.suggestions_data)

            for group in selected_groups:
                with st.spinner(f"Getting suggestions for \"{group['name']}\"..."):
                    suggestions = suggest_additions(group, st.session_state.tracks)
                    found = []
                    for suggestion in suggestions:
                        track = search_track(suggestion, st.session_state.token)
                        if track:
                            found.append(track)
                    suggestions_data[group["name"]] = found

            st.session_state.suggestions_data = suggestions_data
            st.rerun()

        # Display suggestions and let user pick tracks to add
        if st.session_state.suggestions_data:
            st.divider()
            for group in approved:
                name = group["name"]
                found = st.session_state.suggestions_data.get(name)
                if found is None:
                    continue

                st.subheader(f"Suggestions for \"{name}\"")
                if not found:
                    st.write("No suggestions found.")
                    continue

                track_labels = [
                    f"\"{t['name']}\" – {', '.join(a['name'] for a in t.get('artists', []))}"
                    for t in found
                ]
                selected_labels = st.multiselect(
                    "Select tracks to add",
                    track_labels,
                    key=f"sel_{name}"
                )

                if st.button(f"Add selected to \"{name}\"", key=f"add_{name}"):
                    to_add_ids = [
                        found[track_labels.index(label)]["id"]
                        for label in selected_labels
                    ]
                    if to_add_ids:
                        with st.spinner("Adding tracks..."):
                            add_tracks_to_playlist(group["spotify_id"], to_add_ids, st.session_state.token)
                        st.success(f"Added {len(to_add_ids)} track(s) to \"{name}\"!")
                    else:
                        st.warning("Select at least one track.")

        st.divider()
        if st.button("Start Over"):
            reset()
            st.rerun()
        return


if __name__ == "__main__":
    main()
