# Bundesliga Tippspiel

Hybrid-Prognosemodell für die Fußball-Bundesliga: kombiniert Elo-Rating, xG-basierte Form und Sentiment aus deutschen Sport-RSS-Feeds.

**Live-Demo:** *(Netlify-URL nach Deploy hier eintragen)*

## Architektur

- **Backend** (`src/tippspiel/`, `update.py`): Python-Pipeline, die Spielpläne (OpenLigaDB), xG-Daten (football-data.co.uk) und News-RSS einliest, Elo + Form berechnet, Prognosen generiert und in einer SQLite-DB persistiert.
- **Frontend** (`frontend/`): Statisches HTML/CSS/JS, lädt vorberechnete JSON-Snapshots aus `frontend/data/`.
- **Deploy**: Netlify hostet ausschließlich den `frontend/`-Ordner. Daten werden via GitHub Action nightly aktualisiert und ins Repo committed.

```
┌─────────────────────────────────────────────────┐
│  GitHub Action (nightly cron)                   │
│  └─ python update.py                            │
│     ├─ tippspiel.db    (SQLite, im Repo)        │
│     └─ frontend/data/  (JSON-Snapshots)         │
│  └─ git commit + push                           │
└──────────────────┬──────────────────────────────┘
                   │ Push triggert Netlify
                   ▼
┌─────────────────────────────────────────────────┐
│  Netlify deployt frontend/ statisch             │
└─────────────────────────────────────────────────┘
```

## Lokal ausführen

### Voraussetzungen
- Python 3.9+
- `pip install -r requirements.txt`

### Daten aktualisieren + JSONs schreiben
```powershell
python update.py
```

### Frontend lokal testen
```powershell
cd frontend
python -m http.server 8000
# → http://localhost:8000
```

### Alternativ: Original-Webserver (Update-Button funktioniert dort)
```powershell
python webapp.py
```

## Deployment auf Netlify

1. Repo auf GitHub pushen (`main`-Branch).
2. Auf netlify.com → **Add new site → Import an existing project** → GitHub-Repo auswählen.
3. Build-Settings werden automatisch aus `netlify.toml` gezogen (`publish = "frontend"`, kein Build-Command).
4. Deploy. Fertig.

## Update-Workflow

Die GitHub Action in `.github/workflows/update.yml` läuft täglich um 05:00 UTC und:

1. Checkt Repo aus.
2. Installiert Dependencies.
3. Führt `python update.py` aus.
4. Committet veränderte JSONs (und `tippspiel.db`) zurück.
5. Push triggert automatisch Netlify-Rebuild.

Manueller Trigger: GitHub-UI → Actions → "Nightly data update" → Run workflow.

## Projektstruktur

```
.
├── frontend/              # Netlify-Publish-Root
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── data/              # vom Build erzeugt: predictions.json, table.json, news.json, meta.json
├── src/tippspiel/         # Backend-Module
│   ├── analysis/          # Elo, Form, Sentiment
│   ├── fetchers/          # OpenLigaDB, football-data, RSS-News
│   ├── models/            # SQLite-Schema, Domain-Types
│   ├── app.py             # Orchestrierung (TippspielApp)
│   └── predictor.py
├── docs/                  # Konzept, Spezifikation, Prototyp-Beschreibung
├── update.py              # Static-Build-Script
├── webapp.py              # Lokaler Devserver mit Live-API (optional)
├── tippspiel.py           # CLI
├── tippspiel.db           # SQLite-DB (committet)
├── netlify.toml
└── requirements.txt
```

## Datenquellen

| Quelle | Zweck | Kosten |
|---|---|---|
| [OpenLigaDB](https://www.openligadb.de/) | Spielplan + Ergebnisse | kostenlos |
| [football-data.co.uk](https://www.football-data.co.uk/) | xG, erweiterte Match-Statistik | kostenlos (CSV) |
| Kicker / Sport1 RSS | News + Sentiment-Input | kostenlos |

Konzeptionelle Tiefe (Soft-Factors, NLP, Modellaufbau): siehe `docs/Bundesliga_Tippspiel_Beschriebung.txt` und `docs/Kostenloser_Ansatz.md`.

## Lizenz

Privat. Kein Re-Use ohne Rücksprache.
