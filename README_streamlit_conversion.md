# Streamlit conversion for `global-music-taste-explorer`

This folder contains a Streamlit version of the Shiny app from:
`Amro2023/global-music-taste-explorer`

## Files
- `Streamlit_migration/app.py`
- `Streamlit_migration/spotify_api.py`
- `Streamlit_migration/requirements.txt`

## Expected data location
Put these files inside `Streamlit_migration/exports/` or one level above in `exports/`:
- `country_year_summary.parquet`
- `top_tracks_country_year_top500.parquet`
- `artist_country_year_top200.parquet`
- `country_iso3_map.csv`
- `vibe_country_date.parquet` (optional)

## Run locally
```bash
cd Streamlit_migration
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- The conversion preserves the repo's main product surfaces: **World View**, **Explorer**, **Trends**, and **Live Spotify API**.
- It keeps the same schema-normalization pattern used in the Shiny app so it can tolerate `region` vs `country`, `title` vs `track_name`, and `streams` vs `streams_sum`.
- If `.env` is missing Spotify credentials, the app still runs; only the live Spotify tab is limited.
