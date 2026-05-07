"""
Hauptanwendung - Orchestriert alle Komponenten.

Diese Klasse ist der zentrale Einstiegspunkt für das Tippspiel.
Sie koordiniert Daten-Updates, Berechnungen und Prognosen.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def safe_print(text: str) -> str:
    """Ersetzt Umlaute fuer sichere Konsolen-Ausgabe auf Windows."""
    if sys.platform == "win32":
        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
            'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
            'ß': 'ss', 'é': 'e', 'è': 'e',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
    return text

from .models.database import Database
from .models.types import Match, NewsItem
from .fetchers.openligadb import OpenLigaDBFetcher
from .fetchers.footballdata import FootballDataFetcher
from .fetchers.news import NewsFetcher
from .analysis.elo import EloCalculator
from .analysis.form import FormAnalyzer, MatchPerformance
from .analysis.sentiment import KeywordSentiment
from .predictor import Predictor, TeamData, PredictionResult


class TippspielApp:
    """
    Hauptklasse für das Bundesliga-Tippspiel.

    Nutzung:
        app = TippspielApp()
        app.update_all()  # Daten aktualisieren
        predictions = app.get_predictions()  # Prognosen abrufen
    """

    def __init__(self, db_path: str = "tippspiel.db", season: str = "2024"):
        """
        Args:
            db_path: Pfad zur SQLite-Datenbank
            season: Aktuelle Saison (Jahr)
        """
        self.db = Database(db_path)
        self.season = season

        # Fetcher
        self.openliga = OpenLigaDBFetcher()
        self.footballdata = FootballDataFetcher()
        self.news_fetcher = NewsFetcher()

        # Analyzer
        self.elo = EloCalculator()
        self.form = FormAnalyzer(window_size=5)
        self.sentiment = KeywordSentiment()

        # Predictor
        self.predictor = Predictor(self.elo, self.form, self.sentiment)

        # Cache
        self._footballdata_cache = None
        self._news_cache = None

    def initialize(self):
        """
        Initialisiert die Datenbank mit Teams.
        Sollte beim ersten Start aufgerufen werden.
        """
        print("Initialisiere Datenbank...")
        self.db.init_teams()

        print("Lade Teams von OpenLigaDB...")
        teams = self.openliga.get_teams(season=int(self.season))
        for team in teams:
            self.db.upsert_team(team["name"], team["id"])

        print(f"[OK] {len(teams)} Teams initialisiert")

    def update_all(self, verbose: bool = True):
        """
        Aktualisiert alle Daten.

        1. Ergebnisse von OpenLigaDB
        2. xG-Daten von Understat
        3. News von RSS-Feeds
        4. Elo-Ratings neu berechnen
        """
        if verbose:
            print(f"\n{'='*50}")
            print(f"Daten-Update gestartet: {datetime.now():%Y-%m-%d %H:%M}")
            print(f"{'='*50}\n")

        # 1. Ergebnisse
        self._update_matches(verbose)

        # 2. xG-Daten
        self._update_xg_data(verbose)

        # 3. Elo-Ratings
        self._recalculate_elo(verbose)

        # 4. News
        self._update_news(verbose)

        if verbose:
            print(f"\n[OK] Update abgeschlossen: {datetime.now():%H:%M}")

    def _update_matches(self, verbose: bool = True):
        """Aktualisiert Spielergebnisse von OpenLigaDB."""
        if verbose:
            print("[STAT] Lade Spielergebnisse...")

        matches = self.openliga.get_season_matches(season=int(self.season))

        count_new = 0
        count_updated = 0

        for ol_match in matches:
            # Team-IDs aus DB holen
            home_team = self.db.get_team_by_name(ol_match.home_team)
            away_team = self.db.get_team_by_name(ol_match.away_team)

            if not home_team or not away_team:
                # Team noch nicht in DB - anlegen
                home_id = self.db.upsert_team(ol_match.home_team, ol_match.home_team_id)
                away_id = self.db.upsert_team(ol_match.away_team, ol_match.away_team_id)
            else:
                home_id = home_team.id
                away_id = away_team.id

            # Match erstellen/updaten
            match = Match(
                id=None,
                season=self.season,
                matchday=ol_match.matchday,
                home_team_id=home_id,
                away_team_id=away_id,
                match_date=ol_match.match_date,
                home_goals=ol_match.home_goals,
                away_goals=ol_match.away_goals,
                finished=ol_match.finished
            )

            self.db.upsert_match(match)

            if ol_match.finished:
                count_updated += 1
            else:
                count_new += 1

        if verbose:
            print(f"  [OK] {count_updated} beendete, {count_new} anstehende Spiele")

    def _update_xg_data(self, verbose: bool = True):
        """Laedt xG-Daten von Football-Data.co.uk und merged sie."""
        if verbose:
            print("[XG] Lade Statistiken von Football-Data.co.uk...")

        try:
            fd_matches = self.footballdata.get_season_matches(self.season)
            self._footballdata_cache = fd_matches

            if verbose:
                print(f"  {len(fd_matches)} Spiele von Football-Data geladen")

            # Mit DB-Matches mergen
            db_matches = self.db.get_matches_by_season(self.season)
            merged = 0

            for db_match in db_matches:
                if not db_match.finished:
                    continue

                home_team = self.db.get_team_by_id(db_match.home_team_id)
                away_team = self.db.get_team_by_id(db_match.away_team_id)

                if not home_team or not away_team:
                    continue

                # xG suchen
                xg_data = self.footballdata.get_xg_for_match(
                    home_team.name,
                    away_team.name,
                    fd_matches
                )

                if xg_data:
                    db_match.home_xg = xg_data[0]
                    db_match.away_xg = xg_data[1]
                    self.db.upsert_match(db_match)
                    merged += 1

            if verbose:
                print(f"  [OK] {merged} Spiele mit xG-Daten angereichert")

        except Exception as e:
            if verbose:
                print(f"  [!] Fehler bei xG-Abruf: {e}")

    def _recalculate_elo(self, verbose: bool = True):
        """Berechnet Elo-Ratings für alle Teams neu."""
        if verbose:
            print("[ELO] Berechne Elo-Ratings...")

        # Alle Teams auf Start-Elo setzen
        teams = self.db.get_all_teams()
        elo_ratings = {t.id: 1500.0 for t in teams}

        # Alle beendeten Spiele chronologisch durchgehen
        matches = self.db.get_finished_matches(self.season)
        matches.sort(key=lambda m: m.match_date)

        for match in matches:
            if match.home_goals is None or match.away_goals is None:
                continue

            home_elo = elo_ratings.get(match.home_team_id, 1500)
            away_elo = elo_ratings.get(match.away_team_id, 1500)

            result = self.elo.update_ratings(
                home_elo, away_elo,
                match.home_goals, match.away_goals
            )

            elo_ratings[match.home_team_id] = result.new_home_elo
            elo_ratings[match.away_team_id] = result.new_away_elo

        # In DB speichern
        for team_id, elo in elo_ratings.items():
            self.db.update_team_elo(team_id, elo)

        if verbose:
            # Top 5 zeigen
            sorted_elo = sorted(elo_ratings.items(), key=lambda x: x[1], reverse=True)
            print("  Top 5 Elo-Ratings:")
            for team_id, elo in sorted_elo[:5]:
                team = self.db.get_team_by_id(team_id)
                if team:
                    print(f"    {team.short_name or team.name}: {elo:.0f}")

    def _update_news(self, verbose: bool = True):
        """Lädt aktuelle News aus RSS-Feeds."""
        if verbose:
            print("[NEWS] Lade News...")

        news_items = self.news_fetcher.fetch_all(max_age_hours=72)
        self._news_cache = news_items

        saved = 0
        for item in news_items:
            # Team-ID finden
            team_id = None
            if item.team:
                team = self.db.get_team_by_name(item.team)
                if team:
                    team_id = team.id

            # Sentiment analysieren
            result = self.sentiment.analyze(f"{item.title} {item.description}")

            news = NewsItem(
                id=None,
                published_at=item.published,
                source=item.source,
                title=item.title,
                description=item.description,
                team_id=team_id,
                sentiment_score=result.score,
                keywords_found=result.keywords_found,
                link=item.link
            )

            if self.db.save_news(news):
                saved += 1

        if verbose:
            print(f"  [OK] {len(news_items)} News geladen, {saved} neue gespeichert")

    def get_predictions(
        self,
        matchday: Optional[int] = None
    ) -> list[PredictionResult]:
        """
        Generiert Prognosen für anstehende Spiele.

        Args:
            matchday: Optionaler Spieltag (sonst nächste Spiele)

        Returns:
            Liste von PredictionResult
        """
        # Anstehende Spiele holen
        if matchday:
            matches = [
                m for m in self.db.get_matches_by_season(self.season)
                if m.matchday == matchday and not m.finished
            ]
        else:
            matches = self.db.get_upcoming_matches(limit=9)

        predictions = []

        for match in matches:
            home_data = self._build_team_data(match.home_team_id)
            away_data = self._build_team_data(match.away_team_id)

            if home_data and away_data:
                pred = self.predictor.predict(home_data, away_data)
                predictions.append(pred)

        return predictions

    def _build_team_data(self, team_id: int) -> Optional[TeamData]:
        """Baut TeamData-Objekt für Prognose."""
        team = self.db.get_team_by_id(team_id)
        if not team:
            return None

        # Letzte Spiele für Form
        recent_matches = self.db.get_team_matches(team_id, limit=5)
        performances = []

        for match in recent_matches:
            if match.home_xg is None or match.away_xg is None:
                continue

            is_home = match.home_team_id == team_id

            performances.append(MatchPerformance(
                xg=match.home_xg if is_home else match.away_xg,
                xga=match.away_xg if is_home else match.home_xg,
                goals=match.home_goals if is_home else match.away_goals,
                goals_against=match.away_goals if is_home else match.home_goals,
                is_home=is_home
            ))

        # Form analysieren
        form_result = self.form.analyze(performances) if performances else None

        # News für Sentiment
        news_items = self.db.get_team_news(team_id, limit=10)
        if news_items:
            sentiment_data = self.sentiment.analyze_for_team([
                {"title": n.title, "description": n.description}
                for n in news_items
            ])
            sentiment_score = sentiment_data["score"]
        else:
            sentiment_score = 0.0

        return TeamData(
            name=team.name,
            short_name=team.short_name,
            elo_rating=team.elo_rating,
            form=form_result,
            sentiment_score=sentiment_score,
            recent_matches=performances,
            news_items=[{"title": n.title, "description": n.description} for n in news_items]
        )

    def print_predictions(self, predictions: list[PredictionResult]):
        """Gibt Prognosen formatiert aus."""
        print(f"\n{'='*60}")
        print(f"  BUNDESLIGA PROGNOSEN - {datetime.now():%d.%m.%Y}")
        print(f"{'='*60}\n")

        for pred in predictions:
            home_short = safe_print(pred.home_team[:15])
            away_short = safe_print(pred.away_team[:15])

            print(f"  {home_short:15} vs {away_short:15}")
            print(f"  {'-'*40}")
            print(f"  Tendenz:   {pred.prob_home:.0%}  |  {pred.prob_draw:.0%}  |  {pred.prob_away:.0%}  => {pred.tip}")
            print(f"  TIPP:      {pred.score}  (Konfidenz: {pred.score.confidence})")
            print()
            print(f"  {safe_print(pred.explanation)}")
            print(f"\n{'-'*60}\n")

    def get_table(self) -> list[dict]:
        """Gibt die aktuelle Tabelle zurück."""
        return self.db.get_table(self.season)

    def print_table(self):
        """Gibt die Tabelle formatiert aus."""
        table = self.get_table()

        print(f"\n{'='*60}")
        print(f"  BUNDESLIGA TABELLE - Saison {self.season}")
        print(f"{'='*60}\n")

        print(f"  {'Pl':>2}  {'Team':<20}  {'Sp':>2}  {'S':>2}  {'U':>2}  {'N':>2}  {'Diff':>4}  {'Pkt':>3}  {'Elo':>4}")
        print(f"  {'-'*56}")

        for entry in table[:18]:
            diff = entry['goal_diff']
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            team_name = safe_print(entry['team_name'][:20])

            print(
                f"  {entry['position']:>2}  {team_name:<20}  "
                f"{entry['played']:>2}  {entry['won']:>2}  {entry['drawn']:>2}  {entry['lost']:>2}  "
                f"{diff_str:>4}  {entry['points']:>3}  {entry['elo']:>4.0f}"
            )


# CLI-Einstiegspunkt
def main():
    """CLI für das Tippspiel."""
    import sys

    app = TippspielApp()

    if len(sys.argv) < 2:
        print("Nutzung: python -m tippspiel.app <command>")
        print()
        print("Commands:")
        print("  init      - Datenbank initialisieren")
        print("  update    - Daten aktualisieren")
        print("  predict   - Prognosen anzeigen")
        print("  table     - Tabelle anzeigen")
        print("  all       - Alles: Update + Prognosen + Tabelle")
        return

    command = sys.argv[1].lower()

    if command == "init":
        app.initialize()

    elif command == "update":
        app.update_all()

    elif command == "predict":
        predictions = app.get_predictions()
        if predictions:
            app.print_predictions(predictions)
        else:
            print("Keine anstehenden Spiele gefunden.")

    elif command == "table":
        app.print_table()

    elif command == "all":
        app.initialize()
        app.update_all()
        predictions = app.get_predictions()
        if predictions:
            app.print_predictions(predictions)
        app.print_table()

    else:
        print(f"Unbekannter Befehl: {command}")


if __name__ == "__main__":
    main()
