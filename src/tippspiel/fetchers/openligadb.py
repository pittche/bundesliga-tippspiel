"""
OpenLigaDB Fetcher - Kostenlose Bundesliga-Daten.

Liefert: Spielpläne, Ergebnisse, Tabellen
Keine API-Keys nötig, keine Rate-Limits.
"""

import requests
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class OpenLigaMatch:
    """Rohes Match von OpenLigaDB."""
    match_id: int
    matchday: int
    match_date: datetime
    home_team: str
    away_team: str
    home_team_id: int
    away_team_id: int
    home_goals: Optional[int]
    away_goals: Optional[int]
    finished: bool


class OpenLigaDBFetcher:
    """
    Holt Daten von der kostenlosen OpenLigaDB API.
    Dokumentation: https://api.openligadb.de
    """

    BASE_URL = "https://api.openligadb.de"
    TIMEOUT = 15

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Tippspiel/1.0"
        })

    def get_current_matchday(self, league: str = "bl1") -> list[OpenLigaMatch]:
        """
        Holt den aktuellen Spieltag.

        Args:
            league: Liga-Kürzel (bl1 = 1. Bundesliga, bl2 = 2. Bundesliga)
        """
        url = f"{self.BASE_URL}/getmatchdata/{league}"
        response = self.session.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()

        return [self._parse_match(m) for m in response.json()]

    def get_matchday(
        self,
        matchday: int,
        season: int = 2024,
        league: str = "bl1"
    ) -> list[OpenLigaMatch]:
        """
        Holt einen bestimmten Spieltag.

        Args:
            matchday: Spieltag (1-34)
            season: Saison als Startjahr (2024 = Saison 24/25)
            league: Liga-Kürzel
        """
        url = f"{self.BASE_URL}/getmatchdata/{league}/{season}/{matchday}"
        response = self.session.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()

        return [self._parse_match(m) for m in response.json()]

    def get_season_matches(
        self,
        season: int = 2024,
        league: str = "bl1"
    ) -> list[OpenLigaMatch]:
        """
        Holt alle Spiele einer Saison.

        Args:
            season: Saison als Startjahr
            league: Liga-Kürzel
        """
        url = f"{self.BASE_URL}/getmatchdata/{league}/{season}"
        response = self.session.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()

        return [self._parse_match(m) for m in response.json()]

    def get_table(
        self,
        season: int = 2024,
        league: str = "bl1"
    ) -> list[dict]:
        """
        Holt die aktuelle Tabelle.

        Returns:
            Liste von Team-Einträgen mit Punkten, Toren etc.
        """
        url = f"{self.BASE_URL}/getbltable/{league}/{season}"
        response = self.session.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()

        table = []
        for entry in response.json():
            table.append({
                "position": entry.get("rank", 0),
                "team_name": entry.get("teamName", ""),
                "short_name": entry.get("shortName", ""),
                "team_id": entry.get("teamInfoId", 0),
                "played": entry.get("matches", 0),
                "won": entry.get("won", 0),
                "drawn": entry.get("draw", 0),
                "lost": entry.get("lost", 0),
                "goals_for": entry.get("goals", 0),
                "goals_against": entry.get("opponentGoals", 0),
                "goal_diff": entry.get("goalDiff", 0),
                "points": entry.get("points", 0),
            })

        return table

    def get_teams(
        self,
        season: int = 2024,
        league: str = "bl1"
    ) -> list[dict]:
        """
        Holt alle Teams einer Saison.
        """
        url = f"{self.BASE_URL}/getavailableteams/{league}/{season}"
        response = self.session.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()

        teams = []
        for team in response.json():
            teams.append({
                "id": team.get("teamId", 0),
                "name": team.get("teamName", ""),
                "short_name": team.get("shortName", ""),
                "icon_url": team.get("teamIconUrl", ""),
            })

        return teams

    def get_next_match(self, league: str = "bl1") -> Optional[OpenLigaMatch]:
        """Holt das nächste anstehende Spiel."""
        url = f"{self.BASE_URL}/getnextmatchbyleagueteam/{league}"

        try:
            response = self.session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if data:
                return self._parse_match(data)
        except Exception:
            pass

        return None

    def _parse_match(self, raw: dict) -> OpenLigaMatch:
        """Parst ein rohes Match-Objekt."""

        # Datum parsen
        date_str = raw.get("matchDateTime", "")
        try:
            match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            match_date = datetime.now()

        # Ergebnis extrahieren (Endergebnis hat resultTypeID = 2)
        home_goals = None
        away_goals = None
        finished = raw.get("matchIsFinished", False)

        for result in raw.get("matchResults", []):
            if result.get("resultTypeID") == 2:  # Endergebnis
                home_goals = result.get("pointsTeam1")
                away_goals = result.get("pointsTeam2")
                break

        # Falls kein Endergebnis, versuche Halbzeitergebnis
        if home_goals is None and finished:
            for result in raw.get("matchResults", []):
                if result.get("resultTypeID") == 1:  # Halbzeit
                    home_goals = result.get("pointsTeam1")
                    away_goals = result.get("pointsTeam2")
                    break

        # Team-Infos
        team1 = raw.get("team1", {})
        team2 = raw.get("team2", {})

        return OpenLigaMatch(
            match_id=raw.get("matchID", 0),
            matchday=raw.get("group", {}).get("groupOrderID", 0),
            match_date=match_date,
            home_team=team1.get("teamName", "Unbekannt"),
            away_team=team2.get("teamName", "Unbekannt"),
            home_team_id=team1.get("teamId", 0),
            away_team_id=team2.get("teamId", 0),
            home_goals=home_goals,
            away_goals=away_goals,
            finished=finished
        )


# Direkter Test
if __name__ == "__main__":
    fetcher = OpenLigaDBFetcher()

    print("=== Aktueller Spieltag ===")
    matches = fetcher.get_current_matchday()
    for m in matches[:3]:
        result = f"{m.home_goals}:{m.away_goals}" if m.finished else "- : -"
        print(f"  {m.home_team} vs {m.away_team}: {result}")

    print("\n=== Tabelle ===")
    table = fetcher.get_table()
    for entry in table[:5]:
        print(f"  {entry['position']:2}. {entry['team_name']}: {entry['points']} Pkt")
