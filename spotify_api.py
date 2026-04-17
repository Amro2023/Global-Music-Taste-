from __future__ import annotations

import base64
import os
from typing import Any, Optional

import pandas as pd
import requests

try:
    import streamlit as st
except Exception:
    st = None


TOKEN_URL = "https://accounts.spotify.com/api/token"
SEARCH_URL = "https://api.spotify.com/v1/search"


def _get_secret(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value:
        return value

    if st is not None:
        try:
            return st.secrets[name]
        except Exception:
            return None

    return None


def _get_access_token() -> str:
    client_id = _get_secret("SPOTIFY_CLIENT_ID")
    client_secret = _get_secret("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            "Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET. "
            "Set them in local .env or Streamlit secrets."
        )

    creds = f"{client_id}:{client_secret}"
    basic = base64.b64encode(creds.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials"}

    resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    resp.raise_for_status()

    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise ValueError("Spotify token response did not include access_token.")
    return token


def spotify_get(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = _get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _safe_image_url(images: list[Any] | None) -> str | None:
    if not images:
        return None
    for img in images:
        if isinstance(img, dict) and img.get("url"):
            return img["url"]
    return None


def spotify_catalog_search(
    query: str,
    search_type: str = "track",
    market: str = "US",
    limit: int = 10,
) -> list[dict[str, Any]]:
    query = str(query).strip()
    if not query:
        return []

    search_type = str(search_type).strip().lower()
    if search_type not in {"track", "artist", "album"}:
        raise ValueError("search_type must be one of: track, artist, album")

    limit = max(1, min(int(limit), 20))

    params = {
        "q": query,
        "type": search_type,
        "market": market,
        "limit": limit,
    }

    data = spotify_get(SEARCH_URL, params=params)

    bucket_map = {
        "track": "tracks",
        "artist": "artists",
        "album": "albums",
    }
    bucket = bucket_map[search_type]
    items = data.get(bucket, {}).get("items", []) or []

    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        if search_type == "track":
            album = item.get("album") or {}
            album_images = album.get("images") or []
            artists = item.get("artists") or []
            artist_names = ", ".join(
                a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")
            )
            rows.append(
                {
                    "name": item.get("name"),
                    "artist_name": artist_names,
                    "album_name": album.get("name"),
                    "popularity": item.get("popularity"),
                    "spotify_url": (item.get("external_urls") or {}).get("spotify"),
                    "image_url": _safe_image_url(album_images),
                }
            )

        elif search_type == "artist":
            artist_images = item.get("images") or []
            genres = item.get("genres") or []
            rows.append(
                {
                    "name": item.get("name"),
                    "genres": ", ".join(genres) if genres else "—",
                    "popularity": item.get("popularity"),
                    "followers": (item.get("followers") or {}).get("total"),
                    "spotify_url": (item.get("external_urls") or {}).get("spotify"),
                    "image_url": _safe_image_url(artist_images),
                }
            )

        elif search_type == "album":
            album_images = item.get("images") or []
            artists = item.get("artists") or []
            artist_names = ", ".join(
                a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")
            )
            rows.append(
                {
                    "name": item.get("name"),
                    "artist_name": artist_names,
                    "release_date": item.get("release_date"),
                    "total_tracks": item.get("total_tracks"),
                    "spotify_url": (item.get("external_urls") or {}).get("spotify"),
                    "image_url": _safe_image_url(album_images),
                }
            )

    return rows
