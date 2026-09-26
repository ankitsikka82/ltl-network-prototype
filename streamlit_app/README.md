# LTL Network Prototype — Streamlit app

Interactive demo of the freight AI prototype: nightly KPIs, network map data,
load plan, cost-driven deviations, cost-to-serve explorer, lane scoreboard
(good mile vs bad mile), forecast vs actuals, methodology, and data downloads.

All figures are **illustrative sample data**, not carrier operating data.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app reads sample data from `../data/<scenario>/` (base / light / heavy),
so keep the `data/` folder next to `streamlit_app/` (or update `DATA` in app.py).

## Host it

- **Streamlit Community Cloud**: push this folder + `data/` to GitHub,
  deploy at share.streamlit.io (free, point it at `streamlit_app/app.py`).
- **Hugging Face Spaces**: new Space → Streamlit SDK, upload the folder.
- **Internal server / VM**: `streamlit run app.py --server.port 8501`,
  reverse-proxy as needed.
- **Docker**: `python:3.12-slim`, pip install requirements, `streamlit run`.

## Regenerate the sample data

```bash
cd ../data_build
python3 build.py        # deterministic (seeded); writes ../data/*
```

See `../data/DATA_DICTIONARY.md` and `../data/ontology.yaml` for schemas
and the context-engineering layer.
