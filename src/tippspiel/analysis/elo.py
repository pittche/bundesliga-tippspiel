"""
Elo-Rating System für Bundesliga.

Das Elo-System ist ein bewährtes Ratingsystem zur Bewertung der
relativen Stärke von Teams. Ursprünglich für Schach entwickelt,
funktioniert es hervorragend für Fußball.

Vorteile:
- Einfach und transparent
- Keine externe Datenquelle nötig
- Selbst-kalibrierend über Zeit
- Berücksichtigt Heimvorteil
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EloResult:
    """Ergebnis einer Elo-Berechnung."""
    new_home_elo: float
    new_away_elo: float
    home_change: float
    away_change: float
    expected_home: float
    expected_away: float


@dataclass
class MatchProbabilities:
    """Wahrscheinlichkeiten für ein Spiel."""
    home_win: float
    draw: float
    away_win: float
    elo_diff: float


class EloCalculator:
    """
    Elo-Rating Calculator für Bundesliga.

    Standard-Einstellungen basieren auf empirischen Werten
    für die Bundesliga.
    """

    # Standard-Parameter
    DEFAULT_K = 32          # Änderungsgeschwindigkeit
    DEFAULT_HOME_ADV = 65   # Heimvorteil in Elo-Punkten
    INITIAL_ELO = 1500      # Startwert für neue Teams

    def __init__(
        self,
        k_factor: float = DEFAULT_K,
        home_advantage: float = DEFAULT_HOME_ADV
    ):
        """
        Args:
            k_factor: Wie schnell sich Ratings ändern (höher = schneller)
            home_advantage: Elo-Punkte Bonus für Heimteam
        """
        self.k_factor = k_factor
        self.home_advantage = home_advantage

    def expected_score(self, elo_a: float, elo_b: float) -> float:
        """
        Berechnet den erwarteten Score für Team A gegen Team B.

        Formel: E_A = 1 / (1 + 10^((R_B - R_A) / 400))

        Args:
            elo_a: Elo-Rating von Team A
            elo_b: Elo-Rating von Team B

        Returns:
            Erwarteter Score zwischen 0 und 1
        """
        return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

    def update_ratings(
        self,
        home_elo: float,
        away_elo: float,
        home_goals: int,
        away_goals: int,
        k_factor: Optional[float] = None
    ) -> EloResult:
        """
        Aktualisiert Elo-Ratings nach einem Spiel.

        Args:
            home_elo: Aktuelles Elo des Heimteams
            away_elo: Aktuelles Elo des Auswärtsteams
            home_goals: Tore Heimteam
            away_goals: Tore Auswärtsteam
            k_factor: Optionaler K-Faktor (überschreibt Standard)

        Returns:
            EloResult mit neuen Ratings und Änderungen
        """
        k = k_factor or self.k_factor

        # Heimvorteil einrechnen für Erwartungsberechnung
        adjusted_home = home_elo + self.home_advantage

        # Erwartete Scores berechnen
        exp_home = self.expected_score(adjusted_home, away_elo)
        exp_away = 1 - exp_home

        # Tatsächliches Ergebnis in Score umwandeln
        # Sieg = 1, Remis = 0.5, Niederlage = 0
        if home_goals > away_goals:
            actual_home, actual_away = 1.0, 0.0
        elif home_goals < away_goals:
            actual_home, actual_away = 0.0, 1.0
        else:
            actual_home, actual_away = 0.5, 0.5

        # Elo-Änderungen berechnen
        home_change = k * (actual_home - exp_home)
        away_change = k * (actual_away - exp_away)

        # Neue Ratings
        new_home = home_elo + home_change
        new_away = away_elo + away_change

        return EloResult(
            new_home_elo=round(new_home, 1),
            new_away_elo=round(new_away, 1),
            home_change=round(home_change, 1),
            away_change=round(away_change, 1),
            expected_home=round(exp_home, 3),
            expected_away=round(exp_away, 3)
        )

    def predict_match(
        self,
        home_elo: float,
        away_elo: float
    ) -> MatchProbabilities:
        """
        Berechnet Wahrscheinlichkeiten für Heim/Remis/Auswärts.

        Die Umrechnung von Elo-Erwartung zu H/D/A basiert auf
        empirischen Bundesliga-Daten.

        Args:
            home_elo: Elo-Rating Heimteam
            away_elo: Elo-Rating Auswärtsteam

        Returns:
            MatchProbabilities mit Wahrscheinlichkeiten
        """
        # Heimvorteil einrechnen
        adjusted_home = home_elo + self.home_advantage
        elo_diff = adjusted_home - away_elo

        # Basis-Erwartung
        exp_home = self.expected_score(adjusted_home, away_elo)

        # Remis-Wahrscheinlichkeit
        # Empirisch: Mehr Remis bei kleiner Elo-Differenz
        # Bundesliga-Durchschnitt: ~25% Remis
        draw_prob = self._calculate_draw_probability(elo_diff)

        # Verbleibende Wahrscheinlichkeit auf Sieg/Niederlage verteilen
        remaining = 1 - draw_prob

        # Elo-Erwartung auf Siege umrechnen
        # Bei 50% Erwartung: 37.5% Heim, 25% Remis, 37.5% Auswärts
        home_win = exp_home * remaining
        away_win = (1 - exp_home) * remaining

        return MatchProbabilities(
            home_win=round(home_win, 3),
            draw=round(draw_prob, 3),
            away_win=round(away_win, 3),
            elo_diff=round(elo_diff, 1)
        )

    def _calculate_draw_probability(self, elo_diff: float) -> float:
        """
        Berechnet die Remis-Wahrscheinlichkeit basierend auf Elo-Differenz.

        Empirische Beobachtung:
        - Große Differenz (>200): ~15-20% Remis
        - Kleine Differenz (<50): ~28-32% Remis
        - Mittel: ~25%
        """
        # Basis-Remis-Quote
        base_draw = 0.25

        # Anpassung basierend auf Differenz
        # Je größer die Differenz, desto weniger Remis
        adjustment = abs(elo_diff) / 1500  # Normalisieren
        draw_prob = base_draw - (adjustment * 0.12)

        # Grenzen setzen
        return max(0.15, min(0.32, draw_prob))

    def calculate_k_with_crisis(
        self,
        base_k: float,
        crisis_score: float
    ) -> float:
        """
        Berechnet einen dynamischen K-Faktor basierend auf Krisen-Score.

        Idee: In Krisenzeiten (hoher Sentiment-Negativwert) sind
        Ergebnisse weniger vorhersagbar. Ein höherer K-Faktor
        lässt das System schneller reagieren.

        Args:
            base_k: Basis K-Faktor
            crisis_score: Krisen-Score von 0 (stabil) bis 1 (Krise)

        Returns:
            Angepasster K-Faktor
        """
        # K kann um bis zu 50% steigen bei voller Krise
        multiplier = 1 + (crisis_score * 0.5)
        return base_k * multiplier

    def get_win_probability_for_display(
        self,
        probs: MatchProbabilities
    ) -> dict:
        """
        Formatiert Wahrscheinlichkeiten für Anzeige.

        Returns:
            Dict mit formatierten Prozentwerten
        """
        return {
            "home": f"{probs.home_win:.0%}",
            "draw": f"{probs.draw:.0%}",
            "away": f"{probs.away_win:.0%}",
            "favorite": (
                "Heim" if probs.home_win > probs.away_win + 0.1
                else "Auswärts" if probs.away_win > probs.home_win + 0.1
                else "Offen"
            )
        }


# Direkter Test
if __name__ == "__main__":
    calc = EloCalculator()

    print("=== Elo-Rating Test ===\n")

    # Beispiel: Bayern (stark) vs Augsburg (schwach)
    bayern_elo = 1750
    augsburg_elo = 1400

    probs = calc.predict_match(bayern_elo, augsburg_elo)
    print(f"Bayern ({bayern_elo}) vs Augsburg ({augsburg_elo})")
    print(f"  Elo-Diff: {probs.elo_diff:.0f}")
    print(f"  Heim: {probs.home_win:.1%}")
    print(f"  Remis: {probs.draw:.1%}")
    print(f"  Auswärts: {probs.away_win:.1%}")

    # Beispiel: Ausgeglichenes Spiel
    print("\nDortmund (1600) vs Leipzig (1580)")
    probs2 = calc.predict_match(1600, 1580)
    print(f"  Elo-Diff: {probs2.elo_diff:.0f}")
    print(f"  Heim: {probs2.home_win:.1%}")
    print(f"  Remis: {probs2.draw:.1%}")
    print(f"  Auswärts: {probs2.away_win:.1%}")

    # Rating-Update nach Spiel
    print("\n=== Rating-Update Test ===")
    print("Bayern 2:1 Augsburg")
    result = calc.update_ratings(bayern_elo, augsburg_elo, 2, 1)
    print(f"  Bayern: {bayern_elo} => {result.new_home_elo} ({result.home_change:+.1f})")
    print(f"  Augsburg: {augsburg_elo} => {result.new_away_elo} ({result.away_change:+.1f})")

    print("\nÜberraschung: Augsburg 3:0 Bayern")
    result2 = calc.update_ratings(bayern_elo, augsburg_elo, 0, 3)
    print(f"  Bayern: {bayern_elo} => {result2.new_home_elo} ({result2.home_change:+.1f})")
    print(f"  Augsburg: {augsburg_elo} => {result2.new_away_elo} ({result2.away_change:+.1f})")
