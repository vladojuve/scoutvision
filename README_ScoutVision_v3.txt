SCOUTVISION — StatsBomb Event Lab v3

Files:
- app.py: Streamlit application
- requirements.txt: Python dependencies

Run locally:
  python -m pip install -r requirements.txt
  streamlit run app.py

Deploy to Streamlit Community Cloud:
1. Upload app.py and requirements.txt to a GitHub repository.
2. In Streamlit Community Cloud choose the repository and app.py.
3. Deploy.

Modules:
- Current leagues 2026/27 (Open Matchday source)
- StatsBomb Event Lab (single-match events, maps, lineups, CSV)
- Player Scout & Compare (aggregate selected matches, player comparison, metric explorer, CSV exports)

Data notes:
- Open Matchday coverage depends on the source repository.
- StatsBomb Open Data only covers selected competitions/seasons/matches.
- Player Scout & Compare uses only the selected match sample. It does not claim season totals, true minutes, per-90 rates, or population percentiles.
- StatsBomb coordinates are in the source's 120x80 pitch convention.
- Cite Hudl/StatsBomb as required by the repository terms when publishing analyses.
