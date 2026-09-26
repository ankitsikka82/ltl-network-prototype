# LTL Network Prototype — Streamlit app

Interactive demo of the freight AI prototype: network map (start here), nightly
KPIs, load plan, cost-driven deviations, control tower, cost-to-serve explorer,
lane scoreboard (good mile vs bad mile), forecast vs actuals, the ontology /
context-engineering layer, methodology, the "Ask the network" conversational
copilot, and data downloads.

All figures are **illustrative sample data**, not carrier operating data.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app reads sample data from `../data/<scenario>/` (base / light / heavy),
so keep the `data/` folder next to `streamlit_app/` (or update `DATA` in app.py).

## The copilot key (Ask the network)

The copilot calls the LLM from *your browser session* — bring your own key:

- **Anthropic** (native): set `ANTHROPIC_API_KEY` in Streamlit secrets
  (⋮ → Settings → Secrets) or paste it in the Connection panel. Any Claude
  model your key can access works.
- **OpenAI-compatible** (OpenAI, Azure, etc.): set `OPENAI_API_KEY` the same
  way, or paste it in the Connection panel and pick your base URL + model.

The key is never committed to the repo; the model only ever sees the scenario
summary the app builds — KPIs, deviations, tower events, lane scoreboard,
cost-to-serve, business rules.

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
