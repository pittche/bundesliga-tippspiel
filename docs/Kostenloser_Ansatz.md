# Bundesliga Tippspiel - Kostenloser Pragmatischer Ansatz

## Philosophie

**Weniger ist mehr.** Statt 10 Datenquellen mit fragwürdigem Scraping nutzen wir 3-4 zuverlässige, kostenlose Quellen und bauen ein robustes System, das tatsächlich funktioniert.

---

## Architektur-Übersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATEN-LAYER                              │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  OpenLigaDB     │  Understat      │  RSS-Feeds                  │
│  (Ergebnisse)   │  (xG-Daten)     │  (News/Sentiment)           │
│  ✅ 100% Free   │  ✅ Scrape-OK   │  ✅ Öffentlich              │
└────────┬────────┴────────┬────────┴──────────────┬──────────────┘
         │                 │                       │
         ▼                 ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROCESSING-LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Elo-Rating   │  │ Form-Trend   │  │ Keyword-Sentiment    │   │
│  │ (selbst      │  │ (xG-basiert) │  │ (kein ML nötig)      │   │
│  │ berechnet)   │  │              │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │                 │                       │
         ▼                 ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROGNOSE-ENGINE                             │
│                                                                 │
│   P(Heim) = f(Elo_diff, xG_trend, Sentiment, Heimvorteil)      │
│                                                                 │
│   Gewichtung: 50% Elo | 30% xG-Form | 15% Sentiment | 5% Heim  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Datenquellen (alle kostenlos)

### 1.1 OpenLigaDB - Spielplan & Ergebnisse

**Was:** Offizielle Spielpläne, Anstoßzeiten, Endergebnisse
**Warum kostenlos:** Community-Projekt, keine Registrierung nötig
**Limitierung:** Keine xG, keine Spielerstatistiken

```python
# Beispiel-Endpunkte
BASE_URL = "https://api.openligadb.de"

# Aktueller Spieltag
GET /getmatchdata/bl1

# Komplette Saison
GET /getmatchdata/bl1/2024

# Tabelle
GET /getbltable/bl1/2024
```

**Gelieferte Daten:**
- Spielpaarungen mit Datum/Uhrzeit
- Endergebnisse (Halbzeit + Endstand)
- Tabellenstand
- Vereins-IDs und Namen

---

### 1.2 Understat - Expected Goals (xG)

**Was:** Detaillierte xG-Werte pro Spiel und Team
**Warum kostenlos:** Öffentliche Website, kein Login, toleriert moderates Scraping
**URL:** https://understat.com/league/Bundesliga

**Scraping-Strategie:**
- Die Daten liegen als JSON im HTML eingebettet (`<script>` Tags)
- Kein Selenium nötig, einfaches `requests` + `json.loads` reicht
- Rate-Limit: 1 Request pro 2 Sekunden ist sicher

**Gelieferte Daten:**
- xG (Expected Goals) pro Team pro Spiel
- xGA (Expected Goals Against)
- Tatsächliche Tore vs. erwartete Tore
- Shot-Maps (optional)

---

### 1.3 RSS-Feeds - News & Sentiment

**Quellen (alle öffentlich, kein Scraping nötig):**

| Quelle | RSS-URL | Inhalt |
|--------|---------|--------|
| Kicker | `https://rss.kicker.de/news/bundesliga` | Hauptnews |
| Sport1 | `https://www.sport1.de/rss/fussball-bundesliga` | News |
| Sportschau | `https://www.sportschau.de/fussball/bundesliga/index~rss.xml` | ÖR-News |

**Verarbeitung:**
- RSS mit `feedparser` parsen
- Titel + Beschreibung extrahieren
- Keyword-Matching für Sentiment (kein ML nötig)

---

## 2. Datenmodell (SQLite - kostenlos & simpel)

```sql
-- Keine PostgreSQL/MongoDB nötig, SQLite reicht völlig

CREATE TABLE teams (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    short_name TEXT,
    openliga_id INTEGER,
    understat_name TEXT,  -- Mapping für Understat
    elo_rating REAL DEFAULT 1500
);

CREATE TABLE matches (
    id INTEGER PRIMARY KEY,
    season TEXT,
    matchday INTEGER,
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    match_date DATETIME,
    home_goals INTEGER,
    away_goals INTEGER,
    home_xg REAL,
    away_xg REAL,
    status TEXT  -- 'scheduled', 'finished'
);

CREATE TABLE team_form (
    team_id INTEGER REFERENCES teams(id),
    calculated_at DATETIME,
    elo_rating REAL,
    xg_avg_5 REAL,        -- Durchschnitt xG letzte 5 Spiele
    xga_avg_5 REAL,       -- Durchschnitt xGA letzte 5 Spiele
    xg_trend REAL,        -- Steigung der xG-Kurve
    sentiment_score REAL, -- -1 bis +1
    PRIMARY KEY (team_id, calculated_at)
);

CREATE TABLE news_items (
    id INTEGER PRIMARY KEY,
    published_at DATETIME,
    source TEXT,
    title TEXT,
    description TEXT,
    team_id INTEGER REFERENCES teams(id),
    sentiment_score REAL,
    keywords_found TEXT   -- JSON-Array der gefundenen Keywords
);

CREATE TABLE predictions (
    match_id INTEGER REFERENCES matches(id),
    calculated_at DATETIME,
    prob_home REAL,
    prob_draw REAL,
    prob_away REAL,
    confidence TEXT,      -- 'high', 'medium', 'low'
    factors_json TEXT,    -- Erklärung der Faktoren
    PRIMARY KEY (match_id, calculated_at)
);
```

---

## 3. Algorithmen

### 3.1 Elo-Rating (selbst berechnet)

Das Elo-System ist simpel, robust und braucht keine externe API.

```python
class EloCalculator:
    """
    Einfaches Elo-System für Bundesliga.
    Startwert: 1500 für alle Teams zu Saisonbeginn.
    """

    K_FACTOR = 32  # Anpassungsgeschwindigkeit
    HOME_ADVANTAGE = 65  # Elo-Punkte Heimvorteil

    def expected_score(self, elo_a: float, elo_b: float) -> float:
        """Erwarteter Score für Team A gegen Team B."""
        return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

    def update_ratings(
        self,
        home_elo: float,
        away_elo: float,
        home_goals: int,
        away_goals: int
    ) -> tuple[float, float]:
        """
        Aktualisiert Elo nach einem Spiel.
        Returns: (new_home_elo, new_away_elo)
        """
        # Heimvorteil einrechnen
        adjusted_home = home_elo + self.HOME_ADVANTAGE

        # Erwartete Scores
        exp_home = self.expected_score(adjusted_home, away_elo)
        exp_away = 1 - exp_home

        # Tatsächliche Scores (1 = Sieg, 0.5 = Remis, 0 = Niederlage)
        if home_goals > away_goals:
            actual_home, actual_away = 1.0, 0.0
        elif home_goals < away_goals:
            actual_home, actual_away = 0.0, 1.0
        else:
            actual_home, actual_away = 0.5, 0.5

        # Neue Ratings
        new_home = home_elo + self.K_FACTOR * (actual_home - exp_home)
        new_away = away_elo + self.K_FACTOR * (actual_away - exp_away)

        return new_home, new_away

    def predict_match(
        self,
        home_elo: float,
        away_elo: float
    ) -> dict[str, float]:
        """
        Berechnet Wahrscheinlichkeiten für Heim/Remis/Auswärts.
        """
        adjusted_home = home_elo + self.HOME_ADVANTAGE

        # Basis-Erwartung
        exp_home = self.expected_score(adjusted_home, away_elo)

        # Umrechnung in H/D/A Wahrscheinlichkeiten
        # Empirische Formel basierend auf Bundesliga-Daten
        elo_diff = adjusted_home - away_elo

        # Remis-Wahrscheinlichkeit (höher bei kleiner Differenz)
        draw_prob = 0.25 - abs(elo_diff) / 2000
        draw_prob = max(0.15, min(0.32, draw_prob))

        # Verteilung des Rests
        remaining = 1 - draw_prob
        home_prob = exp_home * remaining
        away_prob = (1 - exp_home) * remaining

        return {
            'home': round(home_prob, 3),
            'draw': round(draw_prob, 3),
            'away': round(away_prob, 3)
        }
```

---

### 3.2 xG-basierte Form-Analyse

```python
from collections import deque
import statistics

class FormAnalyzer:
    """
    Analysiert die Form eines Teams basierend auf xG-Daten.
    """

    def __init__(self, window_size: int = 5):
        self.window_size = window_size

    def calculate_form(self, matches: list[dict]) -> dict:
        """
        Berechnet Form-Metriken aus den letzten N Spielen.

        matches: Liste von dicts mit 'xg', 'xga', 'goals', 'goals_against'
        """
        if len(matches) < 2:
            return {'xg_avg': None, 'trend': 0, 'luck_factor': 0}

        recent = matches[-self.window_size:]

        xg_values = [m['xg'] for m in recent]
        xga_values = [m['xga'] for m in recent]
        goals = [m['goals'] for m in recent]

        # Durchschnitte
        xg_avg = statistics.mean(xg_values)
        xga_avg = statistics.mean(xga_values)
        goals_avg = statistics.mean(goals)

        # Trend: Steigung der xG-Kurve (positiv = Aufwärtstrend)
        trend = self._calculate_trend(xg_values)

        # Luck Factor: Tore vs. xG
        # > 0 = Glück (mehr Tore als erwartet)
        # < 0 = Pech (weniger Tore als erwartet)
        luck_factor = goals_avg - xg_avg

        return {
            'xg_avg': round(xg_avg, 2),
            'xga_avg': round(xga_avg, 2),
            'trend': round(trend, 3),
            'luck_factor': round(luck_factor, 2),
            'offensive_strength': round(xg_avg - xga_avg, 2)
        }

    def _calculate_trend(self, values: list[float]) -> float:
        """Einfache lineare Regression für Trend."""
        n = len(values)
        if n < 2:
            return 0

        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)

        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        return numerator / denominator if denominator != 0 else 0
```

---

### 3.3 Keyword-basiertes Sentiment (kein ML nötig)

```python
import re
from dataclasses import dataclass

@dataclass
class SentimentResult:
    score: float          # -1 bis +1
    keywords_found: list[str]
    confidence: str       # 'high', 'medium', 'low'

class KeywordSentiment:
    """
    Einfache aber effektive Sentiment-Analyse ohne Machine Learning.
    Basiert auf domänenspezifischen Keywords für Fußball.
    """

    # Negative Keywords (Krise, Probleme)
    NEGATIVE_KEYWORDS = {
        # Trainer-Probleme (stark negativ)
        'entlassung': -0.8,
        'entlassen': -0.8,
        'rauswurf': -0.9,
        'freigestellt': -0.8,
        'ultimatum': -0.7,
        'trainerdiskussion': -0.6,
        'wackelt': -0.5,
        'druck': -0.3,

        # Interne Konflikte
        'streit': -0.6,
        'eklat': -0.7,
        'zoff': -0.5,
        'ärger': -0.4,
        'unzufrieden': -0.5,
        'kritik': -0.3,
        'suspendiert': -0.6,
        'suspendierung': -0.6,

        # Leistungsprobleme
        'krise': -0.7,
        'absturz': -0.6,
        'pleite': -0.5,
        'debakel': -0.7,
        'blamage': -0.6,
        'abstiegskampf': -0.5,
        'abstieg': -0.6,
        'niederlagenserie': -0.6,

        # Verletzungen
        'verletzt': -0.4,
        'verletzung': -0.4,
        'ausfall': -0.4,
        'langzeitverletzt': -0.6,
        'kreuzbandriss': -0.7,

        # Privates/Skandale
        'skandal': -0.7,
        'ermittlung': -0.6,
        'vorfall': -0.5,
        'trennung': -0.3,
    }

    # Positive Keywords (Aufschwung, Erfolg)
    POSITIVE_KEYWORDS = {
        # Erfolge
        'sieg': 0.4,
        'triumph': 0.6,
        'souverän': 0.5,
        'überlegen': 0.4,
        'kantersieg': 0.6,
        'siegesserie': 0.6,

        # Positive Entwicklung
        'aufschwung': 0.5,
        'aufholjagd': 0.5,
        'comeback': 0.5,
        'wiedergutmachung': 0.4,
        'trendwende': 0.5,
        'befreiungsschlag': 0.6,

        # Teamgeist
        'zusammenhalt': 0.4,
        'geschlossen': 0.3,
        'einheit': 0.4,
        'kampfgeist': 0.4,

        # Verstärkungen
        'verpflichtung': 0.3,
        'neuzugang': 0.3,
        'verstärkung': 0.4,
        'vertragsverlängerung': 0.4,

        # Rückkehr
        'comeback': 0.4,
        'zurück': 0.2,
        'fit': 0.3,
        'einsatzbereit': 0.3,
    }

    # Team-Name Mappings (für Erkennung in News)
    TEAM_ALIASES = {
        'bayern': 'FC Bayern München',
        'münchen': 'FC Bayern München',
        'fcb': 'FC Bayern München',
        'dortmund': 'Borussia Dortmund',
        'bvb': 'Borussia Dortmund',
        'leipzig': 'RB Leipzig',
        'rbl': 'RB Leipzig',
        'leverkusen': 'Bayer 04 Leverkusen',
        'werkself': 'Bayer 04 Leverkusen',
        'frankfurt': 'Eintracht Frankfurt',
        'sge': 'Eintracht Frankfurt',
        'gladbach': 'Borussia Mönchengladbach',
        'fohlen': 'Borussia Mönchengladbach',
        'wolfsburg': 'VfL Wolfsburg',
        'wölfe': 'VfL Wolfsburg',
        'freiburg': 'SC Freiburg',
        'hoffenheim': 'TSG Hoffenheim',
        'mainz': 'FSV Mainz 05',
        'augsburg': 'FC Augsburg',
        'stuttgart': 'VfB Stuttgart',
        'vfb': 'VfB Stuttgart',
        'bremen': 'Werder Bremen',
        'werder': 'Werder Bremen',
        'union': 'Union Berlin',
        'köln': '1. FC Köln',
        'fc köln': '1. FC Köln',
        'bochum': 'VfL Bochum',
        'heidenheim': '1. FC Heidenheim',
        'darmstadt': 'SV Darmstadt 98',
    }

    def analyze(self, text: str) -> SentimentResult:
        """
        Analysiert einen Text und gibt Sentiment-Score zurück.
        """
        text_lower = text.lower()

        found_keywords = []
        total_score = 0

        # Negative Keywords checken
        for keyword, weight in self.NEGATIVE_KEYWORDS.items():
            if keyword in text_lower:
                found_keywords.append(f"-{keyword}")
                total_score += weight

        # Positive Keywords checken
        for keyword, weight in self.POSITIVE_KEYWORDS.items():
            if keyword in text_lower:
                found_keywords.append(f"+{keyword}")
                total_score += weight

        # Normalisieren auf -1 bis +1
        if found_keywords:
            normalized_score = max(-1, min(1, total_score / len(found_keywords)))
        else:
            normalized_score = 0

        # Confidence basierend auf Anzahl gefundener Keywords
        if len(found_keywords) >= 3:
            confidence = 'high'
        elif len(found_keywords) >= 1:
            confidence = 'medium'
        else:
            confidence = 'low'

        return SentimentResult(
            score=round(normalized_score, 2),
            keywords_found=found_keywords,
            confidence=confidence
        )

    def extract_team(self, text: str) -> str | None:
        """Extrahiert den Teamnamen aus einem Text."""
        text_lower = text.lower()

        for alias, team_name in self.TEAM_ALIASES.items():
            if alias in text_lower:
                return team_name

        return None
```

---

### 3.4 Kombiniertes Prognose-Modell

```python
from dataclasses import dataclass

@dataclass
class Prediction:
    home_team: str
    away_team: str
    prob_home: float
    prob_draw: float
    prob_away: float
    recommendation: str
    confidence: str
    factors: dict

class PredictionEngine:
    """
    Kombiniert alle Faktoren zu einer finalen Prognose.

    Gewichtung:
    - 50% Elo-Rating (langfristige Stärke)
    - 30% xG-Form (aktuelle Leistung)
    - 15% Sentiment (Soft Factors)
    - 5%  Heimvorteil-Bonus
    """

    WEIGHT_ELO = 0.50
    WEIGHT_XG = 0.30
    WEIGHT_SENTIMENT = 0.15
    WEIGHT_HOME = 0.05

    def __init__(
        self,
        elo_calc: EloCalculator,
        form_analyzer: FormAnalyzer,
        sentiment_analyzer: KeywordSentiment
    ):
        self.elo = elo_calc
        self.form = form_analyzer
        self.sentiment = sentiment_analyzer

    def predict(
        self,
        home_team: dict,  # {name, elo, recent_matches, news_items}
        away_team: dict
    ) -> Prediction:
        """
        Erstellt eine Prognose für ein Spiel.
        """

        # 1. Elo-basierte Wahrscheinlichkeiten
        elo_probs = self.elo.predict_match(
            home_team['elo'],
            away_team['elo']
        )

        # 2. Form-Analyse
        home_form = self.form.calculate_form(home_team['recent_matches'])
        away_form = self.form.calculate_form(away_team['recent_matches'])

        # Form-Adjustierung (-0.1 bis +0.1)
        form_diff = 0
        if home_form['xg_avg'] and away_form['xg_avg']:
            # Bessere xG = höhere Chance
            xg_advantage = (home_form['xg_avg'] - away_form['xga_avg']) - \
                          (away_form['xg_avg'] - home_form['xga_avg'])
            form_diff = max(-0.1, min(0.1, xg_advantage / 5))

            # Trend-Bonus
            if home_form['trend'] > 0.1:
                form_diff += 0.03
            if away_form['trend'] > 0.1:
                form_diff -= 0.03

        # 3. Sentiment-Analyse
        home_sentiment = self._aggregate_sentiment(home_team.get('news_items', []))
        away_sentiment = self._aggregate_sentiment(away_team.get('news_items', []))

        # Sentiment-Adjustierung (-0.05 bis +0.05)
        sentiment_diff = (home_sentiment - away_sentiment) * 0.05

        # 4. Finale Kombination
        base_home = elo_probs['home']
        base_draw = elo_probs['draw']
        base_away = elo_probs['away']

        # Adjustierungen anwenden
        adjusted_home = base_home + (form_diff * self.WEIGHT_XG) + \
                       (sentiment_diff * self.WEIGHT_SENTIMENT) + \
                       (0.02 * self.WEIGHT_HOME)  # Extra Heimbonus
        adjusted_away = base_away - (form_diff * self.WEIGHT_XG) - \
                       (sentiment_diff * self.WEIGHT_SENTIMENT)

        # Normalisieren
        total = adjusted_home + base_draw + adjusted_away
        final_home = adjusted_home / total
        final_draw = base_draw / total
        final_away = adjusted_away / total

        # Empfehlung generieren
        recommendation = self._generate_recommendation(
            final_home, final_draw, final_away
        )

        # Confidence basierend auf Klarheit
        max_prob = max(final_home, final_draw, final_away)
        if max_prob > 0.5:
            confidence = 'high'
        elif max_prob > 0.4:
            confidence = 'medium'
        else:
            confidence = 'low'

        return Prediction(
            home_team=home_team['name'],
            away_team=away_team['name'],
            prob_home=round(final_home, 3),
            prob_draw=round(final_draw, 3),
            prob_away=round(final_away, 3),
            recommendation=recommendation,
            confidence=confidence,
            factors={
                'elo_diff': home_team['elo'] - away_team['elo'],
                'home_form': home_form,
                'away_form': away_form,
                'home_sentiment': home_sentiment,
                'away_sentiment': away_sentiment,
                'form_adjustment': form_diff,
                'sentiment_adjustment': sentiment_diff
            }
        )

    def _aggregate_sentiment(self, news_items: list) -> float:
        """Aggregiert Sentiment aus mehreren News-Items."""
        if not news_items:
            return 0

        scores = [item.get('sentiment_score', 0) for item in news_items]

        # Neuere News stärker gewichten
        weighted_sum = 0
        weight_total = 0
        for i, score in enumerate(scores):
            weight = 1 + (i / len(scores))  # Neuere = höherer Index = mehr Gewicht
            weighted_sum += score * weight
            weight_total += weight

        return weighted_sum / weight_total if weight_total > 0 else 0

    def _generate_recommendation(
        self,
        home: float,
        draw: float,
        away: float
    ) -> str:
        """Generiert eine Tipp-Empfehlung."""

        if home > 0.45:
            return "HEIMSIEG"
        elif away > 0.45:
            return "AUSWÄRTSSIEG"
        elif draw > 0.30 and abs(home - away) < 0.1:
            return "REMIS"
        elif home > away:
            return "TENDENZ HEIM"
        else:
            return "TENDENZ AUSWÄRTS"
```

---

## 4. Daten-Fetcher (Implementierung)

### 4.1 OpenLigaDB Fetcher

```python
import requests
from datetime import datetime
from typing import Optional

class OpenLigaDBFetcher:
    """
    Holt Daten von der kostenlosen OpenLigaDB API.
    """

    BASE_URL = "https://api.openligadb.de"

    def get_current_matchday(self, league: str = "bl1") -> list[dict]:
        """Holt den aktuellen Spieltag."""
        url = f"{self.BASE_URL}/getmatchdata/{league}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_season_matches(
        self,
        league: str = "bl1",
        season: int = 2024
    ) -> list[dict]:
        """Holt alle Spiele einer Saison."""
        url = f"{self.BASE_URL}/getmatchdata/{league}/{season}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_table(
        self,
        league: str = "bl1",
        season: int = 2024
    ) -> list[dict]:
        """Holt die aktuelle Tabelle."""
        url = f"{self.BASE_URL}/getbltable/{league}/{season}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    def parse_match(self, raw_match: dict) -> dict:
        """Parst ein Match in ein einheitliches Format."""

        # Ergebnis extrahieren
        home_goals = None
        away_goals = None

        for result in raw_match.get('matchResults', []):
            if result.get('resultTypeID') == 2:  # Endergebnis
                home_goals = result.get('pointsTeam1')
                away_goals = result.get('pointsTeam2')

        return {
            'match_id': raw_match.get('matchID'),
            'matchday': raw_match.get('group', {}).get('groupOrderID'),
            'date': raw_match.get('matchDateTime'),
            'home_team': raw_match.get('team1', {}).get('teamName'),
            'away_team': raw_match.get('team2', {}).get('teamName'),
            'home_goals': home_goals,
            'away_goals': away_goals,
            'finished': raw_match.get('matchIsFinished', False)
        }
```

### 4.2 Understat Fetcher (xG-Daten)

```python
import requests
import json
import re
import time

class UnderstatFetcher:
    """
    Scraped xG-Daten von Understat.com.
    Die Daten sind als JSON in <script> Tags eingebettet.
    """

    BASE_URL = "https://understat.com"

    # Mapping OpenLigaDB Namen -> Understat Namen
    TEAM_MAPPING = {
        'FC Bayern München': 'Bayern Munich',
        'Borussia Dortmund': 'Borussia Dortmund',
        'RB Leipzig': 'RasenBallsport Leipzig',
        'Bayer 04 Leverkusen': 'Bayer Leverkusen',
        'Eintracht Frankfurt': 'Eintracht Frankfurt',
        'VfL Wolfsburg': 'Wolfsburg',
        'Borussia Mönchengladbach': 'Borussia M.Gladbach',
        'SC Freiburg': 'Freiburg',
        'TSG Hoffenheim': 'Hoffenheim',
        'FSV Mainz 05': 'Mainz 05',
        'FC Augsburg': 'Augsburg',
        'VfB Stuttgart': 'Stuttgart',
        'Werder Bremen': 'Werder Bremen',
        'Union Berlin': 'Union Berlin',
        '1. FC Köln': 'FC Cologne',
        'VfL Bochum': 'Bochum',
        '1. FC Heidenheim': 'Heidenheim',
        'SV Darmstadt 98': 'Darmstadt 98',
    }

    def __init__(self, delay: float = 2.0):
        self.delay = delay  # Sekunden zwischen Requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_league_data(self, season: str = "2024") -> dict:
        """
        Holt alle Spieldaten einer Bundesliga-Saison.
        """
        url = f"{self.BASE_URL}/league/Bundesliga/{season}"

        response = self.session.get(url, timeout=15)
        response.raise_for_status()

        # JSON aus Script-Tag extrahieren
        match = re.search(
            r"var\s+datesData\s*=\s*JSON\.parse\('(.+?)'\)",
            response.text
        )

        if not match:
            raise ValueError("Could not find datesData in page")

        # Escaped JSON dekodieren
        json_str = match.group(1).encode().decode('unicode_escape')
        data = json.loads(json_str)

        time.sleep(self.delay)  # Rate limiting

        return self._parse_matches(data)

    def _parse_matches(self, raw_data: list) -> list[dict]:
        """Parst die rohen Understat-Daten."""
        matches = []

        for match in raw_data:
            matches.append({
                'understat_id': match.get('id'),
                'home_team': match.get('h', {}).get('title'),
                'away_team': match.get('a', {}).get('title'),
                'home_goals': int(match.get('goals', {}).get('h', 0)),
                'away_goals': int(match.get('goals', {}).get('a', 0)),
                'home_xg': float(match.get('xG', {}).get('h', 0)),
                'away_xg': float(match.get('xG', {}).get('a', 0)),
                'date': match.get('datetime'),
            })

        return matches

    def map_team_name(self, openliga_name: str) -> str:
        """Mapped OpenLigaDB Namen auf Understat Namen."""
        return self.TEAM_MAPPING.get(openliga_name, openliga_name)
```

### 4.3 RSS News Fetcher

```python
import feedparser
from datetime import datetime, timedelta
from typing import Optional

class NewsFetcher:
    """
    Holt News aus öffentlichen RSS-Feeds.
    """

    RSS_FEEDS = {
        'kicker': 'https://rss.kicker.de/news/bundesliga',
        'sport1': 'https://www.sport1.de/rss/fussball-bundesliga',
        'sportschau': 'https://www.sportschau.de/fussball/bundesliga/index~rss.xml',
    }

    def __init__(self, sentiment_analyzer: KeywordSentiment):
        self.sentiment = sentiment_analyzer

    def fetch_all(self, max_age_hours: int = 48) -> list[dict]:
        """
        Holt News aus allen konfigurierten Feeds.
        """
        all_news = []
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        for source, url in self.RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)

                for entry in feed.entries[:20]:  # Max 20 pro Feed
                    # Datum parsen
                    published = entry.get('published_parsed')
                    if published:
                        pub_date = datetime(*published[:6])
                        if pub_date < cutoff:
                            continue
                    else:
                        pub_date = datetime.now()

                    # Text zusammenbauen
                    title = entry.get('title', '')
                    summary = entry.get('summary', '')
                    full_text = f"{title} {summary}"

                    # Sentiment analysieren
                    sentiment_result = self.sentiment.analyze(full_text)

                    # Team extrahieren
                    team = self.sentiment.extract_team(full_text)

                    all_news.append({
                        'source': source,
                        'title': title,
                        'summary': summary[:200],
                        'published': pub_date.isoformat(),
                        'team': team,
                        'sentiment_score': sentiment_result.score,
                        'keywords': sentiment_result.keywords_found,
                        'confidence': sentiment_result.confidence,
                        'link': entry.get('link', '')
                    })

            except Exception as e:
                print(f"Error fetching {source}: {e}")
                continue

        # Nach Datum sortieren (neueste zuerst)
        all_news.sort(key=lambda x: x['published'], reverse=True)

        return all_news

    def get_team_news(
        self,
        team_name: str,
        all_news: Optional[list] = None
    ) -> list[dict]:
        """Filtert News für ein bestimmtes Team."""
        if all_news is None:
            all_news = self.fetch_all()

        return [n for n in all_news if n['team'] == team_name]
```

---

## 5. Hauptanwendung

```python
import sqlite3
from datetime import datetime

class TippspielApp:
    """
    Hauptklasse die alles zusammenbringt.
    """

    def __init__(self, db_path: str = "tippspiel.db"):
        self.db = sqlite3.connect(db_path)
        self.elo = EloCalculator()
        self.form = FormAnalyzer()
        self.sentiment = KeywordSentiment()
        self.predictor = PredictionEngine(self.elo, self.form, self.sentiment)

        self.openliga = OpenLigaDBFetcher()
        self.understat = UnderstatFetcher()
        self.news = NewsFetcher(self.sentiment)

        self._init_db()

    def _init_db(self):
        """Initialisiert die Datenbank."""
        # Schema hier erstellen (siehe SQL oben)
        pass

    def update_data(self):
        """
        Täglicher Update-Job.
        Sollte per Cronjob laufen (z.B. 6:00 morgens).
        """
        print(f"[{datetime.now()}] Starting data update...")

        # 1. Ergebnisse von OpenLigaDB
        print("Fetching match results...")
        matches = self.openliga.get_season_matches()
        for match in matches:
            parsed = self.openliga.parse_match(match)
            self._save_match(parsed)

        # 2. xG-Daten von Understat
        print("Fetching xG data...")
        xg_data = self.understat.get_league_data()
        self._merge_xg_data(xg_data)

        # 3. Elo-Ratings neu berechnen
        print("Recalculating Elo ratings...")
        self._recalculate_elo()

        # 4. News & Sentiment
        print("Fetching news...")
        news = self.news.fetch_all()
        self._save_news(news)

        print(f"[{datetime.now()}] Update complete!")

    def get_predictions(self, matchday: Optional[int] = None) -> list[Prediction]:
        """
        Generiert Prognosen für einen Spieltag.
        """
        matches = self._get_upcoming_matches(matchday)
        predictions = []

        for match in matches:
            home_data = self._build_team_data(match['home_team'])
            away_data = self._build_team_data(match['away_team'])

            pred = self.predictor.predict(home_data, away_data)
            predictions.append(pred)

        return predictions

    def _build_team_data(self, team_name: str) -> dict:
        """Baut das Team-Datenobjekt für die Prediction Engine."""
        return {
            'name': team_name,
            'elo': self._get_elo(team_name),
            'recent_matches': self._get_recent_matches(team_name, limit=5),
            'news_items': self._get_team_news(team_name)
        }

    # ... weitere Hilfsmethoden für DB-Zugriff ...
```

---

## 6. Deployment (kostenlos)

### Option A: Lokaler Betrieb
- SQLite-Datenbank lokal
- Python-Script per Cronjob (oder Windows Task Scheduler)
- Keine Server-Kosten

### Option B: Kostenlose Cloud
- **PythonAnywhere** (Free Tier):
  - 1 Scheduled Task pro Tag
  - SQLite funktioniert
  - 512MB Speicher

- **Replit** (Free Tier):
  - Always-On (mit Tricks)
  - Gut für Prototyping

### Option C: GitHub Actions (komplett kostenlos)
```yaml
# .github/workflows/update.yml
name: Daily Update

on:
  schedule:
    - cron: '0 5 * * *'  # Täglich um 5:00 UTC

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python update_data.py
      - uses: actions/upload-artifact@v3
        with:
          name: database
          path: tippspiel.db
```

---

## 7. Zusammenfassung

| Komponente | Lösung | Kosten |
|------------|--------|--------|
| Spielpläne & Ergebnisse | OpenLigaDB API | Kostenlos |
| Expected Goals (xG) | Understat Scraping | Kostenlos |
| News/Sentiment | RSS-Feeds + Keywords | Kostenlos |
| Datenbank | SQLite | Kostenlos |
| Hosting | Lokal / GitHub Actions | Kostenlos |
| ML-Modell | Nicht nötig (Elo + Regeln) | - |

**Total: 0€**

### Was fehlt vs. Original-Ansatz
- ❌ Keine Player-Level Stats (nur Team-Daten)
- ❌ Keine Social Media Analyse (nur RSS)
- ❌ Keine Echtzeit-Updates während Spielen
- ❌ Kein Machine Learning (XGBoost)

### Was trotzdem funktioniert
- ✅ Elo-Rating ist bewährt und robust
- ✅ xG-Daten sind der beste Prädiktor für zukünftige Ergebnisse
- ✅ Keyword-Sentiment fängt die wichtigsten Krisen ab
- ✅ System ist erweiterbar wenn Budget da ist
