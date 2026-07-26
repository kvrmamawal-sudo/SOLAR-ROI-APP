# Deploying the Siklab Solar ROI Explorer

## 1. Repo structure
Create a public GitHub repo with this layout:

```
your-repo/
├── app.py
├── requirements.txt
└── artifacts/
    ├── hourly_reference_profile.parquet
    ├── tariff_model.pkl
    ├── export_rate_model.pkl
    ├── macro_constants.json
    └── capex_rates.json
```

The `artifacts/` folder is exactly what Cell 8 of the Colab blueprint produces
(`artifacts.zip` — unzip it into your repo root).

## 2. Deploy on Streamlit Community Cloud (free)
1. Push the repo to GitHub.
2. Go to https://share.streamlit.io → "New app".
3. Point it at your repo, branch, and `app.py`.
4. Deploy — first build takes 1–3 minutes, then it's live at a `*.streamlit.app` URL.
5. Any future `git push` auto-redeploys.

## 3. Notes
- `tariff_model.pkl` / `export_rate_model.pkl` aren't called by the current `app.py`
  (the shock slider uses the simpler CAGR + shock-% approach for transparency to
  end users). They're included so a future "custom Brent/coal/PHP scenario" input
  can call `tariff_model.predict([[brent, coal, usd_php, cpi]])` directly — swap that
  in if you want fully macro-driven (rather than %-shock) stress testing.
- All figures are synthetic-data-driven and clearly labeled as educational/illustrative
  in the app's disclaimer section.
