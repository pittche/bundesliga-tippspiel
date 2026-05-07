"""
Understat Fetcher - Kostenlose xG-Daten.

Understat liefert Expected Goals (xG) für alle Bundesliga-Spiele.
Die Daten sind als JSON in <script>-Tags eingebettet, daher kein
komplexes Selenium nötig - einfaches HTML-Parsing reicht.
"""

import requests
import json
import re
import time
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class UnderstatMatch:
    """Ein Spiel mit xG-Daten von Understat."""
    understat_id: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_xg: float
    away_xg: float
    match_date: datetime
    finished: bool


class UnderstatFetcher:
    """
    Scraped xG-Daten von Understat.com.

    Die Daten liegen als JSON in Script-Tags vor.
    Rate-Limiting: 1 Request pro 2 Sekunden empfohlen.
    """

    BASE_URL = "https://understat.com"

    # Mapping: OpenLigaDB Name -> Understat Name
    TEAM_MAPPING = {
        "FC Bayern München": "Bayern Munich",
        "Borussia Dortmund": "Borussia Dortmund",
        "RB Leipzig": "RasenBallsport Leipzig",
        "Bayer 04 Leverkusen": "Bayer Leverkusen",
        "Eintracht Frankfurt": "Eintracht Frankfurt",
        "VfL Wolfsburg": "Wolfsburg",
        "Borussia Mönchengladbach": "Borussia M.Gladbach",
        "SC Freiburg": "Freiburg",
        "TSG 1899 Hoffenheim": "Hoffenheim",
        "1. FSV Mainz 05": "Mainz 05",
        "FC Augsburg": "Augsburg",
        "VfB Stuttgart": "Stuttgart",
        "SV Werder Bremen": "Werder Bremen",
        "1. FC Union Berlin": "Union Berlin",
        "1. FC Köln": "FC Cologne",
        "VfL Bochum 1848": "Bochum",
        "1. FC Heidenheim 1846": "Heidenheim",
        "SV Darmstadt 98": "Darmstadt 98",
        "FC St. Pauli": "St. Pauli",
        "Holstein Kiel": "Holstein Kiel",
    }

    # Reverse Mapping für Lookup
    REVERSE_MAPPING = {v: k for k, v in TEAM_MAPPING.items()}

    def __init__(self, delay: float = 2.0):
        """
        Args:
            delay: Sekunden zwischen Requests (Rate-Limiting)
        """
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })
        self._last_request = 0

    def _wait_for_rate_limit(self):
        """Wartet falls nötig um Rate-Limit einzuhalten."""
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()

    def get_league_matches(self, season: str = "2024") -> list[UnderstatMatch]:
        """
        Holt alle Spiele einer Bundesliga-Saison mit xG-Daten.

        Args:
            season: Saison als Jahr (2024 = Saison 24/25)

        Returns:
            Liste von UnderstatMatch mit xG-Werten
        """
        self._wait_for_rate_limit()

        url = f"{self.BASE_URL}/league/Bundesliga/{season}"

        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Fehler beim Abruf von Understat: {e}")
            return []

        # JSON aus datesData extrahieren
        # Format: var datesData = JSON.parse('...')
        pattern = r"var\s+datesData\s*=\s*JSON\.parse\('(.+?)'\)"
        match = re.search(pattern, response.text)

        if not match:
            print("Konnte datesData nicht in Understat-Seite finden")
            return []

        # Escaped JSON dekodieren
        json_str = match.group(1)
        # Unicode-Escapes dekodieren (\\x -> \x)
        json_str = json_str.encode().decode("unicode_escape")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON-Parsing fehlgeschlagen: {e}")
            return []

        return self._parse_matches(data)

    def get_team_stats(self, team: str, season: str = "2024") -> Optional[dict]:
        """
        Holt detaillierte Statistiken für ein Team.

        Args:
            team: Teamname (Understat-Format)
            season: Saison

        Returns:
            Dict mit Team-Statistiken oder None
        """
        self._wait_for_rate_limit()

        # Team-URL-Name erstellen (Leerzeichen -> Underscore)
        team_url = team.replace(" ", "_")
        url = f"{self.BASE_URL}/team/{team_url}/{season}"

        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Fehler beim Abruf von Team {team}: {e}")
            return None

        # statisticsData extrahieren
        pattern = r"var\s+statisticsData\s*=\s*JSON\.parse\('(.+?)'\)"
        match = re.search(pattern, response.text)

        if not match:
            return None

        json_str = match.group(1).encode().decode("unicode_escape")

        try:
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError:
            return None

    def _parse_matches(self, raw_data: list) -> list[UnderstatMatch]:
        """Parst die rohen Understat-Daten zu UnderstatMatch-Objekten."""
        matches = []

        for match in raw_data:
            try:
                # Datum parsen
                date_str = match.get("datetime", "")
                try:
                    match_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    match_date = datetime.now()

                # Goals und xG extrahieren
                goals = match.get("goals", {})
                xg = match.get("xG", {})

                home_goals = int(goals.get("h", 0))
                away_goals = int(goals.get("a", 0))
                home_xg = float(xg.get("h", 0))
                away_xg = float(xg.get("a", 0))

                # Teams
                home_team = match.get("h", {}).get("title", "Unknown")
                away_team = match.get("a", {}).get("title", "Unknown")

                # Status
                is_result = match.get("isResult", False)

                matches.append(UnderstatMatch(
                    understat_id=str(match.get("id", "")),
                    home_team=home_team,
                    away_team=away_team,
                    home_goals=home_goals,
                    away_goals=away_goals,
                    home_xg=round(home_xg, 2),
                    away_xg=round(away_xg, 2),
                    match_date=match_date,
                    finished=is_result
                ))

            except (KeyError, ValueError, TypeError) as e:
                print(f"Fehler beim Parsen eines Matches: {e}")
                continue

        return matches

    def map_to_openliga_name(self, understat_name: str) -> str:
        """Mapped Understat-Teamnamen auf OpenLigaDB-Namen."""
        return self.REVERSE_MAPPING.get(understat_name, understat_name)

    def map_from_openliga_name(self, openliga_name: str) -> str:
        """Mapped OpenLigaDB-Teamnamen auf Understat-Namen."""
        return self.TEAM_MAPPING.get(openliga_name, openliga_name)

    def get_xg_for_match(
        self,
        home_team: str,
        away_team: str,
        matches: list[UnderstatMatch]
    ) -> Optional[tuple[float, float]]:
        """
        Findet xG-Daten für ein bestimmtes Spiel.

        Args:
            home_team: Heimteam (OpenLigaDB-Name)
            away_team: Auswärtsteam (OpenLigaDB-Name)
            matches: Liste von UnderstatMatch

        Returns:
            Tuple (home_xg, away_xg) oder None
        """
        home_understat = self.map_from_openliga_name(home_team)
        away_understat = self.map_from_openliga_name(away_team)

        for match in matches:
            if match.home_team == home_understat and match.away_team == away_understat:
                return (match.home_xg, match.away_xg)

        return None


# Direkter Test
if __name__ == "__main__":
    fetcher = UnderstatFetcher(delay=1.0)

    print("=== Understat Bundesliga 2024/25 ===")
    matches = fetcher.get_league_matches("2024")

    print(f"\nGefunden: {len(matches)} Spiele")

    # Letzte 5 beendete Spiele
    finished = [m for m in matches if m.finished]
    print(f"Davon beendet: {len(finished)}")

    print("\n--- Letzte 5 Spiele mit xG ---")
    for m in finished[-5:]:
        print(
            f"  {m.home_team} {m.home_goals}:{m.away_goals} {m.away_team} "
            f"(xG: {m.home_xg:.2f} - {m.away_xg:.2f})"
        )

    # xG-Differenz zeigen (wer hat "Glück" gehabt?)
    print("\n--- xG-Analyse (Glück/Pech) ---")
    for m in finished[-5:]:
        home_luck = m.home_goals - m.home_xg
        away_luck = m.away_goals - m.away_xg
        home_indicator = "+" if home_luck > 0.5 else ("-" if home_luck < -0.5 else "~")
        away_indicator = "+" if away_luck > 0.5 else ("-" if away_luck < -0.5 else "~")
        print(
            f"  {m.home_team}: {home_luck:+.2f} {home_indicator} | "
            f"{m.away_team}: {away_luck:+.2f} {away_indicator}"
        )
