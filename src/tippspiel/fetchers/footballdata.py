"""
Football-Data.co.uk Fetcher - Kostenlose Spielstatistiken.

Football-Data.co.uk bietet CSV-Dateien mit:
- Ergebnissen
- Schuessen (HS/AS)
- Schuessen aufs Tor (HST/AST)
- Ecken, Fouls, Karten
- Wettquoten

Aus den Schuss-Statistiken berechnen wir eine xG-Approximation.
"""

import requests
import csv
from io import StringIO
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class FootballDataMatch:
    """Ein Spiel mit Statistiken von Football-Data.co.uk."""
    date: datetime
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_shots: int
    away_shots: int
    home_shots_on_target: int
    away_shots_on_target: int
    home_corners: int
    away_corners: int
    # Berechnete xG-Approximation
    home_xg: float
    away_xg: float


class FootballDataFetcher:
    """
    Holt Spielstatistiken von Football-Data.co.uk.

    Die CSV-Dateien sind kostenlos und ohne API-Key verfuegbar.
    """

    BASE_URL = "https://www.football-data.co.uk/mmz4281"

    # Mapping: OpenLigaDB Name -> Football-Data Name
    TEAM_MAPPING = {
        "FC Bayern München": "Bayern Munich",
        "Borussia Dortmund": "Dortmund",
        "RB Leipzig": "RB Leipzig",
        "Bayer 04 Leverkusen": "Leverkusen",
        "Eintracht Frankfurt": "Ein Frankfurt",
        "VfL Wolfsburg": "Wolfsburg",
        "Borussia Mönchengladbach": "M'gladbach",
        "SC Freiburg": "Freiburg",
        "TSG 1899 Hoffenheim": "Hoffenheim",
        "1. FSV Mainz 05": "Mainz",
        "FC Augsburg": "Augsburg",
        "VfB Stuttgart": "Stuttgart",
        "SV Werder Bremen": "Werder Bremen",
        "1. FC Union Berlin": "Union Berlin",
        "1. FC Köln": "FC Koln",
        "VfL Bochum 1848": "Bochum",
        "1. FC Heidenheim 1846": "Heidenheim",
        "SV Darmstadt 98": "Darmstadt",
        "FC St. Pauli": "St Pauli",
        "Holstein Kiel": "Holstein Kiel",
    }

    # Reverse Mapping
    REVERSE_MAPPING = {v: k for k, v in TEAM_MAPPING.items()}

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self._cache = {}

    def get_season_matches(self, season: str = "2024") -> list[FootballDataMatch]:
        """
        Holt alle Spiele einer Saison.

        Args:
            season: Saison als Jahr (2024 = Saison 24/25)

        Returns:
            Liste von FootballDataMatch
        """
        # Cache pruefen
        if season in self._cache:
            return self._cache[season]

        # Saison-Code erstellen (2024 -> 2425)
        season_int = int(season)
        season_code = f"{season_int % 100:02d}{(season_int + 1) % 100:02d}"

        url = f"{self.BASE_URL}/{season_code}/D1.csv"

        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Fehler beim Abruf von Football-Data: {e}")
            return []

        matches = self._parse_csv(response.text)
        self._cache[season] = matches

        return matches

    def _parse_csv(self, csv_text: str) -> list[FootballDataMatch]:
        """Parst die CSV-Daten."""
        matches = []

        # BOM entfernen falls vorhanden
        if csv_text.startswith('\ufeff'):
            csv_text = csv_text[1:]

        reader = csv.DictReader(StringIO(csv_text))

        for row in reader:
            try:
                # Datum parsen
                date_str = row.get("Date", "")
                try:
                    match_date = datetime.strptime(date_str, "%d/%m/%Y")
                except ValueError:
                    try:
                        match_date = datetime.strptime(date_str, "%d/%m/%y")
                    except ValueError:
                        match_date = datetime.now()

                # Statistiken extrahieren
                home_goals = int(row.get("FTHG", 0) or 0)
                away_goals = int(row.get("FTAG", 0) or 0)
                home_shots = int(row.get("HS", 0) or 0)
                away_shots = int(row.get("AS", 0) or 0)
                home_sot = int(row.get("HST", 0) or 0)
                away_sot = int(row.get("AST", 0) or 0)
                home_corners = int(row.get("HC", 0) or 0)
                away_corners = int(row.get("AC", 0) or 0)

                # xG-Approximation berechnen
                home_xg = self._calculate_xg(home_shots, home_sot, home_corners)
                away_xg = self._calculate_xg(away_shots, away_sot, away_corners)

                matches.append(FootballDataMatch(
                    date=match_date,
                    home_team=row.get("HomeTeam", "Unknown"),
                    away_team=row.get("AwayTeam", "Unknown"),
                    home_goals=home_goals,
                    away_goals=away_goals,
                    home_shots=home_shots,
                    away_shots=away_shots,
                    home_shots_on_target=home_sot,
                    away_shots_on_target=away_sot,
                    home_corners=home_corners,
                    away_corners=away_corners,
                    home_xg=round(home_xg, 2),
                    away_xg=round(away_xg, 2),
                ))

            except (ValueError, KeyError) as e:
                continue

        return matches

    def _calculate_xg(
        self,
        shots: int,
        shots_on_target: int,
        corners: int
    ) -> float:
        """
        Berechnet eine xG-Approximation aus Schussstatistiken.

        Formel basiert auf durchschnittlichen Konversionsraten:
        - Schuss allgemein: ~10% Torchance
        - Schuss aufs Tor: ~30% Torchance
        - Ecke: ~3% Torchance

        Wir gewichten Schuesse aufs Tor hoeher, da sie qualitativ
        bessere Chancen repraesentieren.
        """
        # Gewichtete xG-Berechnung
        # Schuesse aufs Tor sind qualitativ besser
        xg_from_sot = shots_on_target * 0.33  # 33% Konversionsrate

        # Restliche Schuesse (nicht aufs Tor)
        shots_off_target = max(0, shots - shots_on_target)
        xg_from_shots = shots_off_target * 0.03  # 3% fuer Schuesse daneben

        # Ecken als kleiner Bonus
        xg_from_corners = corners * 0.025  # 2.5% pro Ecke

        total_xg = xg_from_sot + xg_from_shots + xg_from_corners

        return total_xg

    def map_to_openliga_name(self, fd_name: str) -> str:
        """Mapped Football-Data Name auf OpenLigaDB Name."""
        return self.REVERSE_MAPPING.get(fd_name, fd_name)

    def map_from_openliga_name(self, openliga_name: str) -> str:
        """Mapped OpenLigaDB Name auf Football-Data Name."""
        return self.TEAM_MAPPING.get(openliga_name, openliga_name)

    def get_xg_for_match(
        self,
        home_team: str,
        away_team: str,
        matches: Optional[list[FootballDataMatch]] = None,
        season: str = "2024"
    ) -> Optional[tuple[float, float]]:
        """
        Findet xG-Daten fuer ein bestimmtes Spiel.

        Args:
            home_team: Heimteam (OpenLigaDB-Name)
            away_team: Auswaertsteam (OpenLigaDB-Name)
            matches: Optionale Liste von Spielen
            season: Saison falls matches nicht angegeben

        Returns:
            Tuple (home_xg, away_xg) oder None
        """
        if matches is None:
            matches = self.get_season_matches(season)

        home_fd = self.map_from_openliga_name(home_team)
        away_fd = self.map_from_openliga_name(away_team)

        for match in matches:
            if match.home_team == home_fd and match.away_team == away_fd:
                return (match.home_xg, match.away_xg)

        return None

    def get_team_stats(
        self,
        team_name: str,
        season: str = "2024",
        last_n: int = 5
    ) -> Optional[dict]:
        """
        Berechnet Durchschnittsstatistiken fuer ein Team.

        Args:
            team_name: Teamname (OpenLigaDB-Format)
            season: Saison
            last_n: Anzahl der letzten Spiele

        Returns:
            Dict mit Durchschnittswerten oder None
        """
        matches = self.get_season_matches(season)
        fd_name = self.map_from_openliga_name(team_name)

        # Spiele des Teams finden
        team_matches = []
        for match in matches:
            if match.home_team == fd_name:
                team_matches.append({
                    "date": match.date,
                    "is_home": True,
                    "goals": match.home_goals,
                    "goals_against": match.away_goals,
                    "xg": match.home_xg,
                    "xga": match.away_xg,
                    "shots": match.home_shots,
                    "sot": match.home_shots_on_target,
                })
            elif match.away_team == fd_name:
                team_matches.append({
                    "date": match.date,
                    "is_home": False,
                    "goals": match.away_goals,
                    "goals_against": match.home_goals,
                    "xg": match.away_xg,
                    "xga": match.home_xg,
                    "shots": match.away_shots,
                    "sot": match.away_shots_on_target,
                })

        if not team_matches:
            return None

        # Nach Datum sortieren und letzte N nehmen
        team_matches.sort(key=lambda x: x["date"], reverse=True)
        recent = team_matches[:last_n]

        if not recent:
            return None

        # Durchschnitte berechnen
        return {
            "matches_analyzed": len(recent),
            "avg_goals": sum(m["goals"] for m in recent) / len(recent),
            "avg_goals_against": sum(m["goals_against"] for m in recent) / len(recent),
            "avg_xg": sum(m["xg"] for m in recent) / len(recent),
            "avg_xga": sum(m["xga"] for m in recent) / len(recent),
            "avg_shots": sum(m["shots"] for m in recent) / len(recent),
            "avg_sot": sum(m["sot"] for m in recent) / len(recent),
        }


# Direkter Test
if __name__ == "__main__":
    fetcher = FootballDataFetcher()

    print("=== Football-Data.co.uk Test ===\n")

    matches = fetcher.get_season_matches("2024")
    print(f"Spiele geladen: {len(matches)}\n")

    # Letzte 5 Spiele
    print("--- Letzte 5 Spiele mit xG ---")
    for match in matches[-5:]:
        print(
            f"  {match.home_team} {match.home_goals}:{match.away_goals} {match.away_team} "
            f"(xG: {match.home_xg:.2f} - {match.away_xg:.2f})"
        )

    print()

    # Team-Stats testen
    print("--- Bayern Stats (letzte 5 Spiele) ---")
    stats = fetcher.get_team_stats("FC Bayern München")
    if stats:
        print(f"  Avg Goals: {stats['avg_goals']:.2f}")
        print(f"  Avg xG: {stats['avg_xg']:.2f}")
        print(f"  Avg Goals Against: {stats['avg_goals_against']:.2f}")
        print(f"  Avg xGA: {stats['avg_xga']:.2f}")
