#!/usr/bin/env python3
"""
Static-Build-Script: Aktualisiert die DB und schreibt JSON-Dateien
nach frontend/data/ fuer das Netlify-Deployment.

Verwendung:
    python update.py            # update + JSON-Export
    python update.py --no-update # nur JSON-Export aus bestehender DB
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from tippspiel.app import TippspielApp


SEASON = "2025"
DB_PATH = ROOT / "tippspiel.db"
DATA_DIR = ROOT / "frontend" / "data"


def export_predictions(app: TippspielApp) -> dict:
    predictions = app.get_predictions()
    return {
        "predictions": [
            {
                "home_team": p.home_team,
                "away_team": p.away_team,
                "prob_home": p.prob_home,
                "prob_draw": p.prob_draw,
                "prob_away": p.prob_away,
                "tip": p.tip,
                "score": str(p.score),
                "confidence": p.confidence,
                "explanation": p.explanation,
            }
            for p in predictions
        ]
    }


def export_table(app: TippspielApp) -> dict:
    return {"table": app.get_table()}


def export_news(app: TippspielApp) -> dict:
    news = app.db.get_recent_news(limit=30)
    return {
        "news": [
            {
                "title": n.title,
                "source": n.source,
                "sentiment": n.sentiment_score,
            }
            for n in news
        ]
    }


def write_json(name: str, data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [OK] {path.relative_to(ROOT)}")


def main() -> None:
    do_update = "--no-update" not in sys.argv

    print(f"DB: {DB_PATH}")
    app = TippspielApp(db_path=str(DB_PATH), season=SEASON)

    if not DB_PATH.exists() or DB_PATH.stat().st_size < 1000:
        print("DB leer - initialisiere...")
        app.initialize()
        do_update = True

    if do_update:
        app.update_all(verbose=True)
    else:
        print("Skip update (--no-update).")

    print("\nSchreibe JSON-Exports...")
    write_json("predictions", export_predictions(app))
    write_json("table", export_table(app))
    write_json("news", export_news(app))
    write_json("meta", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "season": SEASON,
    })
    print("\n[FERTIG]")


if __name__ == "__main__":
    main()
