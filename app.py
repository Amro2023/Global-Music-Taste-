from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from spotify_api import spotify_catalog_search
except Exception:
    spotify_catalog_search = None


APP_DIR = Path(__file__).resolve().parent
EXPORTS = APP_DIR / "exports"
if not EXPORTS.exists():
    EXPORTS = APP_DIR / "Exports"
if not EXPORTS.exists():
    EXPORTS = APP_DIR.parent / "exports"
if not EXPORTS.exists():
    EXPORTS = APP_DIR.parent / "Exports"


COUNTRY_TO_SPOTIFY_MARKET = {
    "ARGENTINA": "AR", "AUSTRALIA": "AU", "AUSTRIA": "AT", "BELGIUM": "BE",
    "BOLIVIA": "BO", "BRAZIL": "BR", "BULGARIA": "BG", "CANADA": "CA",
    "CHILE": "CL", "COLOMBIA": "CO", "COSTA RICA": "CR", "CZECH REPUBLIC": "CZ",
    "DENMARK": "DK", "DOMINICAN REPUBLIC": "DO", "ECUADOR": "EC", "EGYPT": "EG",
    "EL SALVADOR": "SV", "ESTONIA": "EE", "FINLAND": "FI", "FRANCE": "FR",
    "GERMANY": "DE", "GREECE": "GR", "GUATEMALA": "GT", "HONDURAS": "HN",
    "HONG KONG": "HK", "HUNGARY": "HU", "ICELAND": "IS", "INDIA": "IN",
    "INDONESIA": "ID", "IRELAND": "IE", "ISRAEL": "IL", "ITALY": "IT",
    "JAPAN": "JP", "LATVIA": "LV", "LITHUANIA": "LT", "LUXEMBOURG": "LU",
    "MALAYSIA": "MY", "MEXICO": "MX", "MOROCCO": "MA", "NETHERLANDS": "NL",
    "NEW ZEALAND": "NZ", "NICARAGUA": "NI", "NORWAY": "NO", "PANAMA": "PA",
    "PARAGUAY": "PY", "PERU": "PE", "PHILIPPINES": "PH", "POLAND": "PL",
    "PORTUGAL": "PT", "ROMANIA": "RO", "RUSSIA": "RU", "SAUDI ARABIA": "SA",
    "SINGAPORE": "SG", "SLOVAKIA": "SK", "SOUTH AFRICA": "ZA", "SOUTH KOREA": "KR",
    "SPAIN": "ES", "SWEDEN": "SE", "SWITZERLAND": "CH", "TAIWAN": "TW",
    "THAILAND": "TH", "TURKEY": "TR", "UKRAINE": "UA", "UNITED ARAB EMIRATES": "AE",
    "UNITED KINGDOM": "GB", "UNITED STATES": "US", "URUGUAY": "UY", "VIETNAM": "VN",
    "GLOBAL": None,
}

DEFAULT_SEARCH_BY_TYPE = {
    "track": "Blinding Lights",
    "artist": "Drake",
    "album": "After Hours",
}

st.set_page_config(page_title="Global Music Taste Explorer", layout="wide")


@st.cache_data(show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    cys = pd.read_parquet(EXPORTS / "country_year_summary.parquet")
    tt = pd.read_parquet(EXPORTS / "top_tracks_country_year_top500.parquet")
    ay = pd.read_parquet(EXPORTS / "artist_country_year_top200.parquet")
    iso = pd.read_csv(EXPORTS / "country_iso3_map.csv")

    cys.columns = cys.columns.str.strip().str.lower()
    tt.columns = tt.columns.str.strip().str.lower()
    ay.columns = ay.columns.str.strip().str.lower()
    iso.columns = iso.columns.str.strip().str.lower()

    cys = cys.rename(columns={"region": "country"})
    if "country" in cys.columns:
        cys["country"] = cys["country"].astype(str).str.upper().str.strip()

    if "total_streams" in cys.columns and "streams_sum" not in cys.columns:
        cys = cys.rename(columns={"total_streams": "streams_sum"})
    if "avg_streams" in cys.columns and "streams_avg" not in cys.columns:
        cys = cys.rename(columns={"avg_streams": "streams_avg"})

    if "country" in iso.columns:
        iso["country"] = iso["country"].astype(str).str.upper().str.strip()

    if "iso3" not in cys.columns and {"country", "iso3"}.issubset(iso.columns):
        cys = cys.merge(iso[["country", "iso3"]].drop_duplicates(), on="country", how="left")

    tt = tt.rename(columns={
        "region": "country",
        "title": "track_name",
        "artist": "artist_name",
        "streams": "streams_sum",
    })
    ay = ay.rename(columns={
        "region": "country",
        "artist": "artist_name",
        "streams": "streams_sum",
    })

    for df in (tt, ay):
        if "country" in df.columns:
            df["country"] = df["country"].astype(str).str.upper().str.strip()

    for df in (cys, tt, ay):
        if "year" in df.columns:
            df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    vibe_path = EXPORTS / "vibe_country_date.parquet"
    vibe = None
    if vibe_path.exists():
        vibe = pd.read_parquet(vibe_path)
        vibe.columns = vibe.columns.str.strip().str.lower()
        if "snapshot_date" in vibe.columns:
            vibe["snapshot_date"] = pd.to_datetime(vibe["snapshot_date"], errors="coerce").dt.date
        if "region" in vibe.columns and "country" not in vibe.columns:
            vibe = vibe.rename(columns={"region": "country"})
        if "country" in vibe.columns:
            vibe["country"] = vibe["country"].astype(str).str.upper().str.strip()
        if "iso3" not in vibe.columns and {"country", "iso3"}.issubset(iso.columns):
            vibe = vibe.merge(iso[["country", "iso3"]].drop_duplicates(), on="country", how="left")

    return cys, tt, ay, vibe


@lru_cache(maxsize=1)
def app_countries() -> list[str]:
    _, tt, _, _ = load_data()
    if "country" not in tt.columns:
        return []
    return sorted(tt["country"].dropna().astype(str).unique().tolist())


def format_big_number(value) -> str:
    if pd.isna(value):
        return "—"
    try:
        value = float(value)
    except Exception:
        return str(value)
    if abs(value) >= 1_000_000_000:
        return f"{value/1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value/1_000:.1f}K"
    return f"{value:,.0f}"


def metric_row(metrics: list[tuple[str, str]]) -> None:
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value)


def choose_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def render_world_view(cys: pd.DataFrame, vibe: pd.DataFrame | None) -> None:
    st.subheader("World View")
    st.caption("Streams mode uses yearly country summaries. Vibe Check uses the daily Top 50 audio-feature snapshot when available.")

    control_cols = st.columns(4)
    map_mode = control_cols[0].radio("Map mode", ["Streams", "Vibe Check"], horizontal=True, key="world_map_mode")

    if map_mode == "Streams":
        years = sorted([int(x) for x in cys["year"].dropna().unique().tolist()])
        year = control_cols[1].selectbox("Year", years, index=len(years) - 1, key="world_year")
        use_log = control_cols[2].toggle("Log scale", value=True, key="world_log_scale")
        topn = control_cols[3].number_input("Top countries callout", min_value=3, max_value=25, value=10, key="world_topn")

        plot_df = cys[cys["year"] == year].copy()
        metric_col = choose_column(plot_df, ["streams_sum", "total_streams", "streams_avg"])
        if metric_col is None:
            st.error("No stream metric was found in country_year_summary.parquet.")
            return

        plot_df = plot_df.dropna(subset=[metric_col, "iso3"]).copy()
        if use_log:
            plot_df["plot_value"] = plot_df[metric_col].clip(lower=1).map(lambda x: np.log10(x))
            color_col = "plot_value"
            color_label = f"log10({metric_col})"
        else:
            color_col = metric_col
            color_label = metric_col

        metric_row([
            ("Countries", f"{plot_df['country'].nunique():,}"),
            ("Total streams", format_big_number(plot_df[metric_col].sum())),
            ("Median country streams", format_big_number(plot_df[metric_col].median())),
        ])

        fig = px.choropleth(
            plot_df,
            locations="iso3",
            color=color_col,
            hover_name="country",
            hover_data={metric_col: ':,', 'iso3': True},
            projection="natural earth",
            title=f"Global music streams by country — {year}",
            labels={color_col: color_label},
        )
        fig.update_layout(height=650, margin=dict(l=0, r=0, t=60, b=0))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(f"**Top {int(topn)} countries by streams**")
        top_df = plot_df[["country", metric_col]].sort_values(metric_col, ascending=False).head(int(topn))
        st.dataframe(top_df.rename(columns={metric_col: "streams"}), use_container_width=True, hide_index=True)

    else:
        if vibe is None or vibe.empty:
            st.info("vibe_country_date.parquet was not found, so Vibe Check is unavailable.")
            return

        feature_options = {
            "vibe_index": "Vibe Index",
            "energy_mean": "Energy",
            "danceability_mean": "Danceability",
            "valence_mean": "Valence",
            "acousticness_mean": "Acousticness",
        }
        available_features = {k: v for k, v in feature_options.items() if k in vibe.columns}
        dates = sorted(vibe["snapshot_date"].dropna().unique().tolist())
        if not dates:
            st.info("No snapshot dates were found in vibe_country_date.parquet.")
            return

        feature = control_cols[1].selectbox(
            "Vibe feature",
            list(available_features.keys()),
            format_func=lambda x: available_features[x],
            key="vibe_feature",
        )
        date_value = control_cols[2].selectbox("Snapshot date", dates, index=len(dates) - 1, key="vibe_snapshot_date")
        topn = control_cols[3].number_input("Top countries callout", min_value=3, max_value=25, value=10, key="vibe_topn")

        plot_df = vibe[vibe["snapshot_date"] == date_value].copy()
        plot_df = plot_df.dropna(subset=[feature, "iso3"]).copy()

        metric_row([
            ("Countries", f"{plot_df['country'].nunique():,}"),
            (available_features[feature], f"{plot_df[feature].mean():.3f}"),
            ("Snapshot date", str(date_value)),
        ])

        fig = px.choropleth(
            plot_df,
            locations="iso3",
            color=feature,
            hover_name="country",
            projection="natural earth",
            title=f"{available_features[feature]} by country — {date_value}",
            labels={feature: available_features[feature]},
        )
        fig.update_layout(height=650, margin=dict(l=0, r=0, t=60, b=0))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(f"**Top {int(topn)} countries by {available_features[feature]}**")
        top_df = plot_df[["country", feature]].sort_values(feature, ascending=False).head(int(topn))
        st.dataframe(top_df.rename(columns={feature: available_features[feature]}), use_container_width=True, hide_index=True)


def render_explorer(cys: pd.DataFrame, tt: pd.DataFrame, ay: pd.DataFrame) -> None:
    st.subheader("Explorer")
    countries = app_countries()
    years = sorted([int(x) for x in tt["year"].dropna().unique().tolist()])

    c1, c2 = st.columns([2, 1])
    default_country_idx = countries.index("UNITED STATES") if "UNITED STATES" in countries else 0
    country = c1.selectbox("Country", countries, index=default_country_idx, key="explorer_country")
    year = c2.selectbox("Year", years, index=len(years) - 1, key="explorer_year")

    tt_sel = tt[(tt["country"] == country) & (tt["year"] == year)].copy()
    ay_sel = ay[(ay["country"] == country) & (ay["year"] == year)].copy()
    cys_sel = cys[(cys["country"] == country) & (cys["year"] == year)].copy()

    track_metric = choose_column(tt_sel, ["streams_sum", "streams", "count"])
    artist_metric = choose_column(ay_sel, ["streams_sum", "streams", "count"])
    dominant_genre_col = choose_column(cys_sel, ["dominant_genre", "top_genre", "genre"])

    metric_row([
        ("Track rows", f"{len(tt_sel):,}"),
        ("Unique artists", f"{tt_sel['artist_name'].nunique() if 'artist_name' in tt_sel.columns else 0:,}"),
        ("Dominant genre", str(cys_sel[dominant_genre_col].iloc[0]) if dominant_genre_col and not cys_sel.empty else "—"),
        ("Total streams", format_big_number(tt_sel[track_metric].sum()) if track_metric else "—"),
    ])

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("**Top tracks**")
        display_cols = [col for col in ["rank", "track_name", "artist_name", track_metric] if col and col in tt_sel.columns]
        display = tt_sel[display_cols].copy()
        if track_metric:
            display = display.sort_values(track_metric, ascending=False)
        st.dataframe(display.head(50), use_container_width=True, hide_index=True)

    with right:
        st.markdown("**Top artists**")
        if ay_sel.empty or not artist_metric:
            st.info("No artist summary data available for this selection.")
        else:
            top_artists = ay_sel[["artist_name", artist_metric]].groupby("artist_name", as_index=False).sum()
            top_artists = top_artists.sort_values(artist_metric, ascending=False).head(15)
            fig = px.bar(top_artists, x=artist_metric, y="artist_name", orientation="h", title=f"Top artists — {country} ({year})")
            fig.update_layout(height=500, yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)


def render_trends(ay: pd.DataFrame) -> None:
    st.subheader("Trends")
    artists = sorted(ay["artist_name"].dropna().astype(str).unique().tolist())
    countries = sorted(ay["country"].dropna().astype(str).unique().tolist())

    c1, c2 = st.columns([2, 2])
    artist = c1.selectbox("Artist", artists, index=0, key="trends_artist")
    default_countries = ["UNITED STATES"] if "UNITED STATES" in countries else countries[:3]
    selected_countries = c2.multiselect("Countries", countries, default=default_countries, key="trends_countries")

    plot_df = ay[ay["artist_name"] == artist].copy()
    if selected_countries:
        plot_df = plot_df[plot_df["country"].isin(selected_countries)]
    metric = choose_column(plot_df, ["streams_sum", "streams", "count", "rank"])

    if plot_df.empty or metric is None:
        st.info("No trend data available for that selection.")
        return

    grouped = plot_df.groupby(["year", "country"], as_index=False)[metric].sum()
    fig = px.line(grouped, x="year", y=metric, color="country", markers=True, title=f"{artist} across countries over time")
    fig.update_layout(height=550)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(grouped.sort_values(["country", "year"]), use_container_width=True, hide_index=True)


def render_catalog_result_card(row: dict, search_type: str, idx: int) -> None:
    cols = st.columns([1, 4])
    with cols[0]:
        if row.get("image_url"):
            st.image(row["image_url"], use_container_width=True)

    with cols[1]:
        st.markdown(f"### {idx}. {row.get('name', 'Unknown')}")
        if search_type == "track":
            st.write(f"**Artist:** {row.get('artist_name', '—')}")
            st.write(f"**Album:** {row.get('album_name', '—')}")
            st.write(f"**Popularity:** {row.get('popularity', '—')}")
        elif search_type == "artist":
            st.write(f"**Genres:** {row.get('genres', '—')}")
            st.write(f"**Popularity:** {row.get('popularity', '—')}")
            st.write(f"**Followers:** {format_big_number(row.get('followers'))}")
        else:
            st.write(f"**Artist:** {row.get('artist_name', '—')}")
            st.write(f"**Release Date:** {row.get('release_date', '—')}")
            st.write(f"**Total Tracks:** {row.get('total_tracks', '—')}")

        if row.get("spotify_url"):
            st.markdown(f"[Open in Spotify]({row['spotify_url']})")
    st.divider()


def render_live_spotify() -> None:
    st.subheader("Spotify Catalog Search")
    st.caption("Reliable Spotify search for tracks, artists, and albums by market, with cover art.")

    if spotify_catalog_search is None:
        st.info("spotify_api.py is unavailable or Spotify credentials are not configured.")
        return

    countries = [c for c in app_countries() if COUNTRY_TO_SPOTIFY_MARKET.get(c)]
    if not countries:
        st.info("No supported countries available for Spotify catalog search.")
        return

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    default_country_idx = countries.index("UNITED STATES") if "UNITED STATES" in countries else 0
    country = c1.selectbox("Country / Market", countries, index=default_country_idx, key="catalog_country")
    search_type = c2.selectbox("Type", ["track", "artist", "album"], key="catalog_type")
    limit = c3.selectbox("Results", [5, 10, 15, 20], index=1, key="catalog_limit")
    show_covers = c4.toggle("Show covers", value=True, key="catalog_show_covers")

    default_query = DEFAULT_SEARCH_BY_TYPE.get(search_type, "Drake")
    query = st.text_input("Search", value=default_query, key="catalog_query")

    market = COUNTRY_TO_SPOTIFY_MARKET.get(country)
    if not market:
        st.warning("No Spotify market mapping found for that country.")
        return

    if not query.strip():
        st.info("Enter a search term to begin.")
        return

    try:
        rows = spotify_catalog_search(
            query=query,
            search_type=search_type,
            market=market,
            limit=limit,
        )
    except Exception as exc:
        st.error(f"Spotify search failed: {exc}")
        return

    if not rows:
        st.warning("No results found.")
        return

    df = pd.DataFrame(rows)

    if show_covers:
        for idx, row in enumerate(rows, start=1):
            render_catalog_result_card(row, search_type, idx)
    else:
        if search_type == "track":
            show_cols = ["name", "artist_name", "album_name", "popularity", "spotify_url"]
        elif search_type == "artist":
            show_cols = ["name", "genres", "popularity", "followers", "spotify_url"]
        else:
            show_cols = ["name", "artist_name", "release_date", "total_tracks", "spotify_url"]

        show_cols = [c for c in show_cols if c in df.columns]
        st.dataframe(df[show_cols], use_container_width=True, hide_index=True)


def main() -> None:
    st.title("Global Music Taste Explorer")
    st.caption("Converted to Streamlit with World View, Explorer, Trends, and Spotify catalog search by market.")

    with st.sidebar:
        st.markdown("### App status")
        st.write(f"Exports folder: `{EXPORTS}`")
        st.write("Expected files:")
        st.code(
            "\\n".join([
                "country_year_summary.parquet",
                "top_tracks_country_year_top500.parquet",
                "artist_country_year_top200.parquet",
                "country_iso3_map.csv",
                "vibe_country_date.parquet  # optional",
                ".env  # required for Spotify catalog search",
            ])
        )

    try:
        cys, tt, ay, vibe = load_data()
    except FileNotFoundError as exc:
        st.error(f"Missing file: {exc}")
        st.stop()

    tab1, tab2, tab3, tab4 = st.tabs(["World View", "Explorer", "Trends", "Spotify Catalog Search"])
    with tab1:
        render_world_view(cys, vibe)
    with tab2:
        render_explorer(cys, tt, ay)
    with tab3:
        render_trends(ay)
    with tab4:
        render_live_spotify()


if __name__ == "__main__":
    main()
