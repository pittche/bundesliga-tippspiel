"""
Form-Analyse basierend auf xG-Daten.

Analysiert die aktuelle Form eines Teams anhand der Expected Goals
der letzten Spiele. xG ist ein besserer Prädiktor für zukünftige
Leistung als tatsächliche Tore.

Key Insight: Ein Team das viel xG generiert aber wenig Tore schießt,
wird statistisch bald mehr Tore erzielen (Mean Reversion).
"""

import statistics
from dataclasses import dataclass
from typing import Optional


@dataclass
class MatchPerformance:
    """Leistungsdaten eines Teams in einem Spiel."""
    xg: float           # Expected Goals
    xga: float          # Expected Goals Against
    goals: int          # Tatsächliche Tore
    goals_against: int  # Gegentore
    is_home: bool       # Heimspiel?


@dataclass
class FormResult:
    """Ergebnis der Form-Analyse."""
    xg_avg: Optional[float]        # Durchschnitt xG
    xga_avg: Optional[float]       # Durchschnitt xGA
    goals_avg: Optional[float]     # Durchschnitt Tore
    xg_trend: float                # Trend (positiv = aufwärts)
    luck_factor: float             # Tore - xG (positiv = Glück)
    defensive_strength: float      # Negative xGA = gute Defensive
    offensive_strength: float      # Hohe xG = gute Offensive
    overall_form: float            # Gesamtbewertung -1 bis +1
    matches_analyzed: int          # Anzahl analysierter Spiele


class FormAnalyzer:
    """
    Analysiert die Form eines Teams basierend auf xG-Daten.

    Die Analyse berücksichtigt:
    - Offensive Stärke (xG generiert)
    - Defensive Stärke (xGA zugelassen)
    - Trend (verbessert/verschlechtert sich das Team?)
    - Luck Factor (über-/unterperformt das Team seine xG?)
    """

    def __init__(self, window_size: int = 5):
        """
        Args:
            window_size: Anzahl der letzten Spiele für die Analyse
        """
        self.window_size = window_size

    def analyze(self, matches: list[MatchPerformance]) -> FormResult:
        """
        Analysiert die Form basierend auf den letzten Spielen.

        Args:
            matches: Liste von MatchPerformance (chronologisch, älteste zuerst)

        Returns:
            FormResult mit allen Metriken
        """
        if not matches:
            return self._empty_result()

        # Auf die letzten N Spiele beschränken
        recent = matches[-self.window_size:]

        if len(recent) < 2:
            return self._empty_result(matches_analyzed=len(recent))

        # Grundwerte extrahieren
        xg_values = [m.xg for m in recent]
        xga_values = [m.xga for m in recent]
        goals_values = [m.goals for m in recent]

        # Durchschnitte berechnen
        xg_avg = statistics.mean(xg_values)
        xga_avg = statistics.mean(xga_values)
        goals_avg = statistics.mean(goals_values)

        # Trend berechnen (lineare Regression)
        xg_trend = self._calculate_trend(xg_values)

        # Luck Factor: Tore - xG
        # Positiv = Team erzielt mehr Tore als erwartet (Glück)
        # Negativ = Team erzielt weniger Tore als erwartet (Pech)
        luck_factor = goals_avg - xg_avg

        # Offensive/Defensive Stärke (relativ zum Liga-Durchschnitt ~1.3 xG)
        league_avg_xg = 1.3
        offensive_strength = (xg_avg - league_avg_xg) / league_avg_xg
        defensive_strength = (league_avg_xg - xga_avg) / league_avg_xg

        # Gesamtform berechnen (-1 bis +1)
        overall_form = self._calculate_overall_form(
            xg_avg, xga_avg, xg_trend, luck_factor
        )

        return FormResult(
            xg_avg=round(xg_avg, 2),
            xga_avg=round(xga_avg, 2),
            goals_avg=round(goals_avg, 2),
            xg_trend=round(xg_trend, 3),
            luck_factor=round(luck_factor, 2),
            defensive_strength=round(defensive_strength, 2),
            offensive_strength=round(offensive_strength, 2),
            overall_form=round(overall_form, 2),
            matches_analyzed=len(recent)
        )

    def _calculate_trend(self, values: list[float]) -> float:
        """
        Berechnet den Trend als Steigung einer linearen Regression.

        Positiver Wert = Aufwärtstrend
        Negativer Wert = Abwärtstrend
        """
        n = len(values)
        if n < 2:
            return 0.0

        # Einfache lineare Regression
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)

        numerator = sum(
            (i - x_mean) * (y - y_mean)
            for i, y in enumerate(values)
        )
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _calculate_overall_form(
        self,
        xg_avg: float,
        xga_avg: float,
        xg_trend: float,
        luck_factor: float
    ) -> float:
        """
        Berechnet eine Gesamtbewertung der Form.

        Komponenten:
        - xG-Differenz (Offense - Defense)
        - Trend-Bonus
        - Luck-Korrektur (zu viel Glück = Regression erwartet)
        """
        # xG-Differenz normalisiert
        xg_diff = xg_avg - xga_avg
        base_form = max(-1, min(1, xg_diff / 2))

        # Trend-Bonus (max ±0.2)
        trend_bonus = max(-0.2, min(0.2, xg_trend * 2))

        # Luck-Korrektur
        # Viel Glück = erwarte Regression (leicht negativ)
        # Viel Pech = erwarte Verbesserung (leicht positiv)
        luck_correction = -luck_factor * 0.1
        luck_correction = max(-0.15, min(0.15, luck_correction))

        # Kombinieren
        overall = base_form + trend_bonus + luck_correction
        return max(-1, min(1, overall))

    def _empty_result(self, matches_analyzed: int = 0) -> FormResult:
        """Gibt ein leeres FormResult zurück."""
        return FormResult(
            xg_avg=None,
            xga_avg=None,
            goals_avg=None,
            xg_trend=0.0,
            luck_factor=0.0,
            defensive_strength=0.0,
            offensive_strength=0.0,
            overall_form=0.0,
            matches_analyzed=matches_analyzed
        )

    def compare_forms(
        self,
        home_form: FormResult,
        away_form: FormResult
    ) -> dict:
        """
        Vergleicht die Form zweier Teams.

        Returns:
            Dict mit Vergleichswerten und Empfehlung
        """
        if not home_form.xg_avg or not away_form.xg_avg:
            return {
                "advantage": "unknown",
                "confidence": "low",
                "details": "Nicht genug Daten"
            }

        # Form-Differenz
        form_diff = home_form.overall_form - away_form.overall_form

        # xG-Vorteil (Offense vs Defense)
        # Heimteam Offense vs Auswärts Defense
        home_attacking_edge = home_form.xg_avg - away_form.xga_avg
        # Auswärts Offense vs Heim Defense
        away_attacking_edge = away_form.xg_avg - home_form.xga_avg

        xg_edge = home_attacking_edge - away_attacking_edge

        # Trend-Vorteil
        trend_edge = home_form.xg_trend - away_form.xg_trend

        # Gesamtbewertung
        total_edge = (form_diff * 0.4) + (xg_edge * 0.4) + (trend_edge * 0.2)

        # Empfehlung
        if total_edge > 0.3:
            advantage = "home_strong"
            confidence = "high"
        elif total_edge > 0.1:
            advantage = "home_slight"
            confidence = "medium"
        elif total_edge < -0.3:
            advantage = "away_strong"
            confidence = "high"
        elif total_edge < -0.1:
            advantage = "away_slight"
            confidence = "medium"
        else:
            advantage = "even"
            confidence = "low"

        return {
            "advantage": advantage,
            "confidence": confidence,
            "form_edge": round(form_diff, 2),
            "xg_edge": round(xg_edge, 2),
            "trend_edge": round(trend_edge, 3),
            "total_edge": round(total_edge, 2)
        }

    def get_form_description(self, form: FormResult) -> str:
        """
        Gibt eine menschenlesbare Beschreibung der Form zurück.
        """
        if form.matches_analyzed < 2:
            return "Zu wenig Daten"

        descriptions = []

        # Offensive
        if form.offensive_strength > 0.2:
            descriptions.append("stark offensiv")
        elif form.offensive_strength < -0.2:
            descriptions.append("schwach offensiv")

        # Defensive
        if form.defensive_strength > 0.2:
            descriptions.append("stark defensiv")
        elif form.defensive_strength < -0.2:
            descriptions.append("schwach defensiv")

        # Trend
        if form.xg_trend > 0.1:
            descriptions.append("aufsteigend")
        elif form.xg_trend < -0.1:
            descriptions.append("absteigend")

        # Luck
        if form.luck_factor > 0.5:
            descriptions.append("Glückssträhne")
        elif form.luck_factor < -0.5:
            descriptions.append("Pechsträhne")

        if not descriptions:
            return "Durchschnittliche Form"

        return ", ".join(descriptions).capitalize()


# Direkter Test
if __name__ == "__main__":
    analyzer = FormAnalyzer(window_size=5)

    print("=== Form-Analyse Test ===\n")

    # Beispiel: Team in guter Form
    good_form = [
        MatchPerformance(xg=2.1, xga=0.8, goals=2, goals_against=1, is_home=True),
        MatchPerformance(xg=1.8, xga=1.2, goals=3, goals_against=1, is_home=False),
        MatchPerformance(xg=2.5, xga=0.9, goals=2, goals_against=0, is_home=True),
        MatchPerformance(xg=1.9, xga=1.1, goals=1, goals_against=1, is_home=False),
        MatchPerformance(xg=2.8, xga=0.7, goals=4, goals_against=1, is_home=True),
    ]

    result = analyzer.analyze(good_form)
    print("Team A (Gute Form):")
    print(f"  xG Ø: {result.xg_avg}")
    print(f"  xGA Ø: {result.xga_avg}")
    print(f"  Trend: {result.xg_trend:+.3f}")
    print(f"  Luck Factor: {result.luck_factor:+.2f}")
    print(f"  Gesamt: {result.overall_form:+.2f}")
    print(f"  Beschreibung: {analyzer.get_form_description(result)}")

    # Beispiel: Team in schlechter Form
    bad_form = [
        MatchPerformance(xg=1.0, xga=2.1, goals=0, goals_against=2, is_home=True),
        MatchPerformance(xg=0.8, xga=1.8, goals=1, goals_against=3, is_home=False),
        MatchPerformance(xg=0.9, xga=2.0, goals=1, goals_against=2, is_home=True),
        MatchPerformance(xg=0.7, xga=2.2, goals=0, goals_against=1, is_home=False),
        MatchPerformance(xg=0.6, xga=1.9, goals=0, goals_against=2, is_home=True),
    ]

    result2 = analyzer.analyze(bad_form)
    print("\nTeam B (Schlechte Form):")
    print(f"  xG Ø: {result2.xg_avg}")
    print(f"  xGA Ø: {result2.xga_avg}")
    print(f"  Trend: {result2.xg_trend:+.3f}")
    print(f"  Luck Factor: {result2.luck_factor:+.2f}")
    print(f"  Gesamt: {result2.overall_form:+.2f}")
    print(f"  Beschreibung: {analyzer.get_form_description(result2)}")

    # Vergleich
    print("\n=== Vergleich ===")
    comparison = analyzer.compare_forms(result, result2)
    print(f"Vorteil: {comparison['advantage']}")
    print(f"Konfidenz: {comparison['confidence']}")
    print(f"Form Edge: {comparison['form_edge']:+.2f}")
    print(f"xG Edge: {comparison['xg_edge']:+.2f}")
