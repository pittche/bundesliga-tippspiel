"""
SQLite-Datenbank für das Tippspiel.
Einfach, portabel, keine Server-Installation nötig.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from .types import Team, Match, NewsItem, TeamForm


class Database:
    """SQLite-Datenbank-Wrapper."""

    # Team-Mapping: OpenLigaDB Name -> (Short Name, Understat Name)
    TEAM_MAPPINGS = {
        "FC Bayern München": ("FCB", "Bayern Munich"),
        "Borussia Dortmund": ("BVB", "Borussia Dortmund"),
        "RB Leipzig": ("RBL", "RasenBallsport Leipzig"),
        "Bayer 04 Leverkusen": ("B04", "Bayer Leverkusen"),
        "Eintracht Frankfurt": ("SGE", "Eintracht Frankfurt"),
        "VfL Wolfsburg": ("WOB", "Wolfsburg"),
        "Borussia Mönchengladbach": ("BMG", "Borussia M.Gladbach"),
        "SC Freiburg": ("SCF", "Freiburg"),
        "TSG 1899 Hoffenheim": ("TSG", "Hoffenheim"),
        "1. FSV Mainz 05": ("M05", "Mainz 05"),
        "FC Augsburg": ("FCA", "Augsburg"),
        "VfB Stuttgart": ("VFB", "Stuttgart"),
        "SV Werder Bremen": ("SVW", "Werder Bremen"),
        "1. FC Union Berlin": ("FCU", "Union Berlin"),
        "1. FC Köln": ("KOE", "FC Cologne"),
        "VfL Bochum 1848": ("BOC", "Bochum"),
        "1. FC Heidenheim 1846": ("FCH", "Heidenheim"),
        "SV Darmstadt 98": ("D98", "Darmstadt 98"),
        "FC St. Pauli": ("STP", "St. Pauli"),
        "Holstein Kiel": ("KIE", "Holstein Kiel"),
    }

    def __init__(self, db_path: str = "tippspiel.db"):
        self.db_path = Path(db_path)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        """Context manager für Datenbankverbindungen."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialisiert das Datenbankschema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    short_name TEXT,
                    openliga_id INTEGER,
                    understat_name TEXT,
                    elo_rating REAL DEFAULT 1500.0
                );

                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    season TEXT NOT NULL,
                    matchday INTEGER NOT NULL,
                    home_team_id INTEGER NOT NULL REFERENCES teams(id),
                    away_team_id INTEGER NOT NULL REFERENCES teams(id),
                    match_date DATETIME NOT NULL,
                    home_goals INTEGER,
                    away_goals INTEGER,
                    home_xg REAL,
                    away_xg REAL,
                    finished INTEGER DEFAULT 0,
                    UNIQUE(season, matchday, home_team_id, away_team_id)
                );

                CREATE TABLE IF NOT EXISTS team_form (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER NOT NULL REFERENCES teams(id),
                    calculated_at DATETIME NOT NULL,
                    elo_rating REAL,
                    xg_avg REAL,
                    xga_avg REAL,
                    xg_trend REAL,
                    goals_avg REAL,
                    luck_factor REAL,
                    sentiment_score REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    published_at DATETIME NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    team_id INTEGER REFERENCES teams(id),
                    sentiment_score REAL DEFAULT 0,
                    keywords_found TEXT,
                    link TEXT,
                    UNIQUE(source, title, published_at)
                );

                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL REFERENCES matches(id),
                    calculated_at DATETIME NOT NULL,
                    prob_home REAL NOT NULL,
                    prob_draw REAL NOT NULL,
                    prob_away REAL NOT NULL,
                    recommendation TEXT,
                    confidence TEXT,
                    factors_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season);
                CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
                CREATE INDEX IF NOT EXISTS idx_news_team ON news(team_id);
                CREATE INDEX IF NOT EXISTS idx_news_date ON news(published_at);
            """)

    def init_teams(self):
        """Initialisiert die Teams mit Standard-Mappings."""
        with self._get_conn() as conn:
            for name, (short, understat) in self.TEAM_MAPPINGS.items():
                conn.execute("""
                    INSERT OR IGNORE INTO teams (name, short_name, understat_name, elo_rating)
                    VALUES (?, ?, ?, 1500.0)
                """, (name, short, understat))

    # --- Team-Operationen ---

    def get_team_by_name(self, name: str) -> Optional[Team]:
        """Holt ein Team anhand des Namens."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM teams WHERE name = ? OR short_name = ? OR understat_name = ?",
                (name, name, name)
            ).fetchone()

            if row:
                return Team(
                    id=row["id"],
                    name=row["name"],
                    short_name=row["short_name"] or "",
                    openliga_id=row["openliga_id"] or 0,
                    understat_name=row["understat_name"] or "",
                    elo_rating=row["elo_rating"] or 1500.0
                )
        return None

    def get_team_by_id(self, team_id: int) -> Optional[Team]:
        """Holt ein Team anhand der ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM teams WHERE id = ?", (team_id,)
            ).fetchone()

            if row:
                return Team(
                    id=row["id"],
                    name=row["name"],
                    short_name=row["short_name"] or "",
                    openliga_id=row["openliga_id"] or 0,
                    understat_name=row["understat_name"] or "",
                    elo_rating=row["elo_rating"] or 1500.0
                )
        return None

    def get_all_teams(self) -> list[Team]:
        """Holt alle Teams."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM teams ORDER BY name").fetchall()
            return [
                Team(
                    id=row["id"],
                    name=row["name"],
                    short_name=row["short_name"] or "",
                    openliga_id=row["openliga_id"] or 0,
                    understat_name=row["understat_name"] or "",
                    elo_rating=row["elo_rating"] or 1500.0
                )
                for row in rows
            ]

    def update_team_elo(self, team_id: int, new_elo: float):
        """Aktualisiert das Elo-Rating eines Teams."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE teams SET elo_rating = ? WHERE id = ?",
                (new_elo, team_id)
            )

    def upsert_team(self, name: str, openliga_id: int = None) -> int:
        """Fügt ein Team ein oder holt die ID wenn es existiert."""
        with self._get_conn() as conn:
            # Prüfen ob Team existiert
            row = conn.execute(
                "SELECT id FROM teams WHERE name = ?", (name,)
            ).fetchone()

            if row:
                if openliga_id:
                    conn.execute(
                        "UPDATE teams SET openliga_id = ? WHERE id = ?",
                        (openliga_id, row["id"])
                    )
                return row["id"]

            # Mapping suchen
            short_name = ""
            understat_name = name
            if name in self.TEAM_MAPPINGS:
                short_name, understat_name = self.TEAM_MAPPINGS[name]

            cursor = conn.execute("""
                INSERT INTO teams (name, short_name, understat_name, openliga_id, elo_rating)
                VALUES (?, ?, ?, ?, 1500.0)
            """, (name, short_name, understat_name, openliga_id))

            return cursor.lastrowid

    # --- Match-Operationen ---

    def upsert_match(self, match: Match) -> int:
        """Fügt ein Spiel ein oder aktualisiert es."""
        with self._get_conn() as conn:
            # Prüfen ob Match existiert
            row = conn.execute("""
                SELECT id FROM matches
                WHERE season = ? AND matchday = ? AND home_team_id = ? AND away_team_id = ?
            """, (match.season, match.matchday, match.home_team_id, match.away_team_id)).fetchone()

            if row:
                # Update
                conn.execute("""
                    UPDATE matches SET
                        match_date = ?,
                        home_goals = ?,
                        away_goals = ?,
                        home_xg = ?,
                        away_xg = ?,
                        finished = ?
                    WHERE id = ?
                """, (
                    match.match_date.isoformat(),
                    match.home_goals,
                    match.away_goals,
                    match.home_xg,
                    match.away_xg,
                    1 if match.finished else 0,
                    row["id"]
                ))
                return row["id"]

            # Insert
            cursor = conn.execute("""
                INSERT INTO matches
                    (season, matchday, home_team_id, away_team_id, match_date,
                     home_goals, away_goals, home_xg, away_xg, finished)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match.season,
                match.matchday,
                match.home_team_id,
                match.away_team_id,
                match.match_date.isoformat(),
                match.home_goals,
                match.away_goals,
                match.home_xg,
                match.away_xg,
                1 if match.finished else 0
            ))
            return cursor.lastrowid

    def get_matches_by_season(self, season: str) -> list[Match]:
        """Holt alle Spiele einer Saison."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM matches WHERE season = ? ORDER BY matchday, match_date
            """, (season,)).fetchall()

            return [self._row_to_match(row) for row in rows]

    def get_finished_matches(self, season: str) -> list[Match]:
        """Holt alle beendeten Spiele einer Saison."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM matches
                WHERE season = ? AND finished = 1
                ORDER BY matchday, match_date
            """, (season,)).fetchall()

            return [self._row_to_match(row) for row in rows]

    def get_upcoming_matches(self, limit: int = 10) -> list[Match]:
        """Holt die nächsten anstehenden Spiele."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM matches
                WHERE finished = 0 AND match_date > datetime('now')
                ORDER BY match_date
                LIMIT ?
            """, (limit,)).fetchall()

            return [self._row_to_match(row) for row in rows]

    def get_team_matches(self, team_id: int, limit: int = 10) -> list[Match]:
        """Holt die letzten Spiele eines Teams."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM matches
                WHERE (home_team_id = ? OR away_team_id = ?) AND finished = 1
                ORDER BY match_date DESC
                LIMIT ?
            """, (team_id, team_id, limit)).fetchall()

            return [self._row_to_match(row) for row in rows]

    def _row_to_match(self, row) -> Match:
        """Konvertiert eine DB-Row zu einem Match-Objekt."""
        return Match(
            id=row["id"],
            season=row["season"],
            matchday=row["matchday"],
            home_team_id=row["home_team_id"],
            away_team_id=row["away_team_id"],
            match_date=datetime.fromisoformat(row["match_date"]),
            home_goals=row["home_goals"],
            away_goals=row["away_goals"],
            home_xg=row["home_xg"],
            away_xg=row["away_xg"],
            finished=bool(row["finished"])
        )

    # --- News-Operationen ---

    def save_news(self, news: NewsItem) -> int:
        """Speichert eine News-Meldung."""
        with self._get_conn() as conn:
            try:
                cursor = conn.execute("""
                    INSERT INTO news
                        (published_at, source, title, description, team_id,
                         sentiment_score, keywords_found, link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    news.published_at.isoformat(),
                    news.source,
                    news.title,
                    news.description,
                    news.team_id,
                    news.sentiment_score,
                    ",".join(news.keywords_found),
                    news.link
                ))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # News existiert bereits
                return 0

    def get_team_news(self, team_id: int, limit: int = 10) -> list[NewsItem]:
        """Holt die neuesten News für ein Team."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM news
                WHERE team_id = ?
                ORDER BY published_at DESC
                LIMIT ?
            """, (team_id, limit)).fetchall()

            return [
                NewsItem(
                    id=row["id"],
                    published_at=datetime.fromisoformat(row["published_at"]),
                    source=row["source"],
                    title=row["title"],
                    description=row["description"] or "",
                    team_id=row["team_id"],
                    sentiment_score=row["sentiment_score"] or 0,
                    keywords_found=(row["keywords_found"] or "").split(","),
                    link=row["link"] or ""
                )
                for row in rows
            ]

    def get_recent_news(self, limit: int = 30) -> list[NewsItem]:
        """Holt die neuesten News (alle Teams)."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM news
                ORDER BY published_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [
                NewsItem(
                    id=row["id"],
                    published_at=datetime.fromisoformat(row["published_at"]),
                    source=row["source"],
                    title=row["title"],
                    description=row["description"] or "",
                    team_id=row["team_id"],
                    sentiment_score=row["sentiment_score"] or 0,
                    keywords_found=(row["keywords_found"] or "").split(","),
                    link=row["link"] or ""
                )
                for row in rows
            ]

    # --- Statistiken ---

    def get_table(self, season: str) -> list[dict]:
        """Berechnet die aktuelle Tabelle."""
        teams = self.get_all_teams()
        matches = self.get_finished_matches(season)

        table = {}
        for team in teams:
            table[team.id] = {
                "team_id": team.id,
                "team_name": team.name,
                "short_name": team.short_name,
                "played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_diff": 0,
                "points": 0,
                "elo": team.elo_rating
            }

        for match in matches:
            if match.home_goals is None or match.away_goals is None:
                continue

            home = table.get(match.home_team_id)
            away = table.get(match.away_team_id)

            if not home or not away:
                continue

            home["played"] += 1
            away["played"] += 1
            home["goals_for"] += match.home_goals
            home["goals_against"] += match.away_goals
            away["goals_for"] += match.away_goals
            away["goals_against"] += match.home_goals

            if match.home_goals > match.away_goals:
                home["won"] += 1
                home["points"] += 3
                away["lost"] += 1
            elif match.home_goals < match.away_goals:
                away["won"] += 1
                away["points"] += 3
                home["lost"] += 1
            else:
                home["drawn"] += 1
                away["drawn"] += 1
                home["points"] += 1
                away["points"] += 1

        # Goal difference berechnen
        for team_id in table:
            table[team_id]["goal_diff"] = (
                table[team_id]["goals_for"] - table[team_id]["goals_against"]
            )

        # Sortieren: Punkte > Tordifferenz > Tore
        sorted_table = sorted(
            [t for t in table.values() if t["played"] > 0],
            key=lambda x: (x["points"], x["goal_diff"], x["goals_for"]),
            reverse=True
        )

        # Platzierung hinzufügen
        for i, entry in enumerate(sorted_table, 1):
            entry["position"] = i

        return sorted_table
