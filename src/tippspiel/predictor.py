"""
Prognose-Engine - Kombiniert alle Faktoren zu einer Vorhersage.

Gewichtung:
- 50% Elo-Rating (langfristige Stärke)
- 30% xG-Form (aktuelle Leistung)
- 15% Sentiment (Soft Factors)
- 5%  Heimvorteil-Bonus

Das Modell ist bewusst einfach gehalten und transparent.
Keine Black-Box, alle Faktoren sind nachvollziehbar.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .analysis.elo import EloCalculator, MatchProbabilities
from .analysis.form import FormAnalyzer, FormResult, MatchPerformance
from .analysis.sentiment import KeywordSentiment


@dataclass
class TeamData:
    """Alle Daten fuer ein Team."""
    name: str
    short_name: str
    elo_rating: float
    form: Optional[FormResult]
    sentiment_score: float
    recent_matches: list[MatchPerformance]
    news_items: list[dict]


@dataclass
class ScorePrediction:
    """Konkreter Ergebnis-Tipp."""
    home_goals: int
    away_goals: int
    confidence: str  # 'high', 'medium', 'low'

    def __str__(self) -> str:
        return f"{self.home_goals}:{self.away_goals}"


@dataclass
class PredictionResult:
    """Komplettes Prognose-Ergebnis."""
    home_team: str
    away_team: str
    prob_home: float
    prob_draw: float
    prob_away: float
    recommendation: str
    confidence: str
    tip: str                    # "1", "X", "2"
    score: ScorePrediction      # Konkreter Ergebnis-Tipp
    factors: dict
    explanation: str


class Predictor:
    """
    Kombiniert Elo, Form und Sentiment zu einer Prognose.

    Gewichtung kann angepasst werden.
    """

    # Standard-Gewichtung
    WEIGHT_ELO = 0.50       # 50% Elo
    WEIGHT_FORM = 0.30      # 30% xG-Form
    WEIGHT_SENTIMENT = 0.15  # 15% Sentiment
    WEIGHT_HOME = 0.05      # 5% Extra-Heimbonus

    def __init__(
        self,
        elo_calculator: Optional[EloCalculator] = None,
        form_analyzer: Optional[FormAnalyzer] = None,
        sentiment_analyzer: Optional[KeywordSentiment] = None
    ):
        self.elo = elo_calculator or EloCalculator()
        self.form = form_analyzer or FormAnalyzer()
        self.sentiment = sentiment_analyzer or KeywordSentiment()

    def predict(
        self,
        home_team: TeamData,
        away_team: TeamData
    ) -> PredictionResult:
        """
        Erstellt eine Prognose fuer ein Spiel.

        Args:
            home_team: TeamData fuer Heimmannschaft
            away_team: TeamData fuer Auswärtsmannschaft

        Returns:
            PredictionResult mit allen Details
        """
        # 1. Elo-basierte Basiswahrscheinlichkeiten
        elo_probs = self.elo.predict_match(
            home_team.elo_rating,
            away_team.elo_rating
        )

        # 2. Form-Adjustierung
        form_adjustment = self._calculate_form_adjustment(
            home_team.form,
            away_team.form
        )

        # 3. Sentiment-Adjustierung
        sentiment_adjustment = self._calculate_sentiment_adjustment(
            home_team.sentiment_score,
            away_team.sentiment_score
        )

        # 4. Kombinierte Wahrscheinlichkeiten
        final_probs = self._combine_probabilities(
            elo_probs,
            form_adjustment,
            sentiment_adjustment
        )

        # 5. Empfehlung und Tipp generieren
        recommendation, tip, confidence = self._generate_recommendation(
            final_probs,
            home_team.name,
            away_team.name
        )

        # 6. Konkreten Ergebnis-Tipp generieren
        score = self._predict_score(
            elo_probs.elo_diff,
            final_probs,
            home_team.form,
            away_team.form
        )

        # 7. Erklaerung erstellen
        explanation = self._generate_explanation(
            home_team,
            away_team,
            elo_probs,
            form_adjustment,
            sentiment_adjustment,
            final_probs
        )

        return PredictionResult(
            home_team=home_team.name,
            away_team=away_team.name,
            prob_home=final_probs["home"],
            prob_draw=final_probs["draw"],
            prob_away=final_probs["away"],
            recommendation=recommendation,
            confidence=confidence,
            tip=tip,
            score=score,
            factors={
                "elo_diff": elo_probs.elo_diff,
                "elo_probs": {
                    "home": elo_probs.home_win,
                    "draw": elo_probs.draw,
                    "away": elo_probs.away_win
                },
                "form_adjustment": form_adjustment,
                "sentiment_adjustment": sentiment_adjustment,
                "home_elo": home_team.elo_rating,
                "away_elo": away_team.elo_rating,
                "home_sentiment": home_team.sentiment_score,
                "away_sentiment": away_team.sentiment_score,
            },
            explanation=explanation
        )

    def _calculate_form_adjustment(
        self,
        home_form: Optional[FormResult],
        away_form: Optional[FormResult]
    ) -> float:
        """
        Berechnet Form-Adjustierung.

        Returns:
            Wert zwischen -0.15 und +0.15
            Positiv = Vorteil Heimteam
        """
        if not home_form or not away_form:
            return 0.0

        if not home_form.xg_avg or not away_form.xg_avg:
            return 0.0

        # Form-Differenz
        form_diff = home_form.overall_form - away_form.overall_form

        # xG-Matchup: Heim-Offense vs Auswärts-Defense und umgekehrt
        home_attack_edge = home_form.xg_avg - away_form.xga_avg
        away_attack_edge = away_form.xg_avg - home_form.xga_avg
        xg_edge = home_attack_edge - away_attack_edge

        # Trend-Bonus
        trend_diff = home_form.xg_trend - away_form.xg_trend

        # Gewichtete Kombination
        adjustment = (form_diff * 0.4 + xg_edge * 0.08 + trend_diff * 0.3)

        # Auf -0.15 bis +0.15 begrenzen
        return max(-0.15, min(0.15, adjustment))

    def _calculate_sentiment_adjustment(
        self,
        home_sentiment: float,
        away_sentiment: float
    ) -> float:
        """
        Berechnet Sentiment-Adjustierung.

        Returns:
            Wert zwischen -0.08 und +0.08
            Positiv = Vorteil Heimteam (bessere Stimmung)
        """
        sentiment_diff = home_sentiment - away_sentiment

        # Skalieren: Max ±0.08 bei extremem Unterschied
        adjustment = sentiment_diff * 0.04

        return max(-0.08, min(0.08, adjustment))

    def _combine_probabilities(
        self,
        elo_probs: MatchProbabilities,
        form_adj: float,
        sentiment_adj: float
    ) -> dict:
        """
        Kombiniert alle Faktoren zu finalen Wahrscheinlichkeiten.
        """
        # Basis von Elo
        base_home = elo_probs.home_win
        base_draw = elo_probs.draw
        base_away = elo_probs.away_win

        # Adjustierungen anwenden
        total_adj = form_adj * self.WEIGHT_FORM + sentiment_adj * self.WEIGHT_SENTIMENT

        # Extra Heimbonus
        home_bonus = 0.02 * self.WEIGHT_HOME

        # Anpassen
        adjusted_home = base_home + total_adj + home_bonus
        adjusted_away = base_away - total_adj

        # Sicherstellen dass alles positiv ist
        adjusted_home = max(0.05, adjusted_home)
        adjusted_away = max(0.05, adjusted_away)
        adjusted_draw = max(0.10, base_draw)

        # Normalisieren auf 100%
        total = adjusted_home + adjusted_draw + adjusted_away
        return {
            "home": round(adjusted_home / total, 3),
            "draw": round(adjusted_draw / total, 3),
            "away": round(adjusted_away / total, 3)
        }

    def _predict_score(
        self,
        elo_diff: float,
        probs: dict,
        home_form: Optional[FormResult],
        away_form: Optional[FormResult]
    ) -> ScorePrediction:
        """
        Generiert einen konkreten Ergebnis-Tipp.

        PUNKTESYSTEM-OPTIMIERT:
        - 3 Punkte: Exaktes Ergebnis
        - 2 Punkte: Richtige Tendenz + richtige Tordifferenz
        - 1 Punkt: Richtige Tendenz, falsche Tordifferenz
        - 0 Punkte: Falsche Tendenz
        - REMIS: NUR 3 Punkte bei exakt richtig, sonst 0!

        Strategie:
        - Remis nur tippen wenn P(draw) > 35% (hohes Risiko!)
        - Haeufige Ergebnisse bevorzugen (2:1, 1:0, 2:0)
        - Bei klarem Favorit: Tordifferenz +1 oder +2

        Returns:
            ScorePrediction mit home_goals, away_goals, confidence
        """
        # Haeufigste Bundesliga-Ergebnisse (fuer Erwartungswert-Optimierung)
        # 1:1 (12%), 2:1 (11%), 1:0 (10%), 2:0 (8%), 0:0 (7%), 3:1 (6%)

        # xG-Daten verwenden falls vorhanden
        if home_form and home_form.xg_avg and away_form and away_form.xga_avg:
            expected_home = (home_form.xg_avg + away_form.xga_avg) / 2
            expected_away = (away_form.xg_avg + home_form.xga_avg) / 2
            score_confidence = "medium"
        else:
            # Elo-basierte Schaetzung
            goal_advantage = elo_diff / 400
            expected_home = 1.55 + (goal_advantage * 0.5)
            expected_away = 1.35 - (goal_advantage * 0.5)
            score_confidence = "low"

        # Auf vernuenftige Werte begrenzen
        expected_home = max(0.3, min(4.0, expected_home))
        expected_away = max(0.3, min(4.0, expected_away))

        # STRATEGISCHE ENTSCHEIDUNG basierend auf Punktesystem

        # REMIS: Nur tippen wenn sehr wahrscheinlich (>35%)
        # Grund: Bei Remis gibt es nur 3 oder 0 Punkte!
        if probs["draw"] > 0.35:
            # Remis tippen - waehle haeufigstes Remis-Ergebnis
            avg_goals = round((expected_home + expected_away) / 2)
            avg_goals = max(0, min(2, avg_goals))  # 0:0, 1:1, 2:2

            # 1:1 ist das haeufigste Remis
            if avg_goals == 0 and expected_home + expected_away > 1.5:
                avg_goals = 1

            return ScorePrediction(
                home_goals=avg_goals,
                away_goals=avg_goals,
                confidence="medium" if probs["draw"] > 0.40 else "low"
            )

        # SIEG: Optimiere fuer Tendenz + Tordifferenz (2 Punkte)
        if probs["home"] > probs["away"]:
            # Heimsieg
            home_goals, away_goals = self._optimal_win_score(
                expected_home, expected_away, is_home_win=True, win_prob=probs["home"]
            )
        else:
            # Auswaertssieg
            home_goals, away_goals = self._optimal_win_score(
                expected_home, expected_away, is_home_win=False, win_prob=probs["away"]
            )

        # Konfidenz
        max_prob = max(probs["home"], probs["away"])
        if max_prob >= 0.55:
            score_confidence = "high"
        elif max_prob >= 0.42:
            score_confidence = "medium"
        else:
            score_confidence = "low"

        return ScorePrediction(
            home_goals=home_goals,
            away_goals=away_goals,
            confidence=score_confidence
        )

    def _optimal_win_score(
        self,
        exp_home: float,
        exp_away: float,
        is_home_win: bool,
        win_prob: float
    ) -> tuple[int, int]:
        """
        Berechnet optimales Ergebnis fuer einen Sieg.

        Strategie:
        - Bei klarem Favorit (>55%): +2 Tore Differenz (3:1, 2:0)
        - Bei leichtem Favorit: +1 Tor Differenz (2:1, 1:0)
        - Haeufige Ergebnisse bevorzugen
        """
        # Haeufigste Siege nach Tordifferenz:
        # +1: 2:1 (11%), 1:0 (10%), 3:2 (5%)
        # +2: 2:0 (8%), 3:1 (6%)
        # +3: 3:0 (4%), 4:1 (2%)

        if is_home_win:
            # Heimsieg
            if win_prob >= 0.60:
                # Klarer Favorit: 2 Tore Differenz
                # Waehle zwischen 2:0, 3:1
                if exp_home >= 2.5:
                    return (3, 1)
                else:
                    return (2, 0)
            elif win_prob >= 0.45:
                # Leichter Favorit: 1 Tor Differenz
                # Waehle zwischen 2:1, 1:0
                if exp_home >= 1.8:
                    return (2, 1)
                else:
                    return (1, 0)
            else:
                # Knapper Favorit: 2:1 ist sicherer als 1:0
                return (2, 1)
        else:
            # Auswaertssieg
            if win_prob >= 0.55:
                # Klarer Favorit: 2 Tore Differenz
                if exp_away >= 2.3:
                    return (1, 3)
                else:
                    return (0, 2)
            elif win_prob >= 0.42:
                # Leichter Favorit
                if exp_away >= 1.6:
                    return (1, 2)
                else:
                    return (0, 1)
            else:
                # Knapper Favorit
                return (1, 2)

    def _generate_recommendation(
        self,
        probs: dict,
        home_name: str,
        away_name: str
    ) -> tuple[str, str, str]:
        """
        Generiert Empfehlung, Tipp und Konfidenz.

        PUNKTESYSTEM-OPTIMIERT:
        - Remis nur bei >35% (sonst zu riskant: 0 oder 3 Punkte)
        - Bei unsicheren Spielen lieber Sieg tippen (1 Punkt sicher)

        Returns:
            (recommendation, tip, confidence)
        """
        home = probs["home"]
        draw = probs["draw"]
        away = probs["away"]

        # REMIS: Nur empfehlen wenn wirklich wahrscheinlich
        # Grund: Bei Remis gibt es NUR 3 Punkte (exakt) oder 0!
        if draw > 0.35:
            recommendation = "Remis wahrscheinlich (Risiko-Tipp!)"
            tip = "X"
            confidence = "medium" if draw > 0.40 else "low"
            return recommendation, tip, confidence

        # Bei draw <= 35%: Immer Sieg tippen (sicherer fuer Punkte)

        # Konfidenz basierend auf Klarheit
        if home > away:
            diff = home - away
            if home >= 0.55:
                recommendation = f"Klarer Heimsieg {home_name}"
                tip = "1"
                confidence = "high"
            elif home >= 0.42:
                recommendation = f"Tendenz {home_name}"
                tip = "1"
                confidence = "medium"
            else:
                recommendation = f"Leichte Tendenz {home_name}"
                tip = "1"
                confidence = "low"
        else:
            if away >= 0.50:
                recommendation = f"Klarer Auswaertssieg {away_name}"
                tip = "2"
                confidence = "high"
            elif away >= 0.38:
                recommendation = f"Tendenz {away_name}"
                tip = "2"
                confidence = "medium"
            else:
                recommendation = f"Leichte Tendenz {away_name}"
                tip = "2"
                confidence = "low"

        return recommendation, tip, confidence

    def _generate_explanation(
        self,
        home: TeamData,
        away: TeamData,
        elo_probs: MatchProbabilities,
        form_adj: float,
        sentiment_adj: float,
        final_probs: dict
    ) -> str:
        """Generiert eine menschenlesbare Erklaerung."""
        lines = []

        # Elo-Analyse
        if elo_probs.elo_diff > 100:
            lines.append(f"[STAT] {home.short_name or home.name} ist statistisch klar staerker (Elo +{elo_probs.elo_diff:.0f})")
        elif elo_probs.elo_diff > 50:
            lines.append(f"[STAT] {home.short_name or home.name} hat leichten Elo-Vorteil (+{elo_probs.elo_diff:.0f})")
        elif elo_probs.elo_diff < -100:
            lines.append(f"[STAT] {away.short_name or away.name} ist statistisch klar staerker (Elo {elo_probs.elo_diff:.0f})")
        elif elo_probs.elo_diff < -50:
            lines.append(f"[STAT] {away.short_name or away.name} hat leichten Elo-Vorteil ({elo_probs.elo_diff:.0f})")
        else:
            lines.append("[STAT] Teams auf Augenhoehe (Elo ausgeglichen)")

        # Form-Analyse
        if form_adj > 0.05:
            lines.append(f"[XG] {home.short_name or home.name} in besserer Form")
        elif form_adj < -0.05:
            lines.append(f"[XG] {away.short_name or away.name} in besserer Form")

        # Sentiment-Analyse
        if sentiment_adj > 0.03:
            lines.append(f"[NEWS] Positive Nachrichten fuer {home.short_name or home.name}")
        elif sentiment_adj < -0.03:
            lines.append(f"[NEWS] Positive Nachrichten fuer {away.short_name or away.name}")

        if home.sentiment_score < -0.3:
            lines.append(f"[!] Unruhe bei {home.short_name or home.name}")
        if away.sentiment_score < -0.3:
            lines.append(f"[!] Unruhe bei {away.short_name or away.name}")

        # Remis-Warnung (wichtig fuer Punktesystem!)
        if final_probs['draw'] > 0.30:
            if final_probs['draw'] <= 0.35:
                lines.append("[TIPP] Remis moeglich, aber Sieg sicherer (1 Pkt garantiert)")
            else:
                lines.append("[TIPP] Remis-Tipp riskant: nur 3 Pkt bei exakt, sonst 0!")

        # Fazit
        lines.append(
            f"=> {final_probs['home']:.0%} / {final_probs['draw']:.0%} / {final_probs['away']:.0%}"
        )

        return "\n".join(lines)

    def quick_predict(
        self,
        home_elo: float,
        away_elo: float,
        home_sentiment: float = 0,
        away_sentiment: float = 0
    ) -> dict:
        """
        Schnelle Prognose nur mit Elo und optional Sentiment.
        Gut fuer Tests ohne vollständige TeamData.
        """
        elo_probs = self.elo.predict_match(home_elo, away_elo)

        sentiment_adj = self._calculate_sentiment_adjustment(
            home_sentiment, away_sentiment
        )

        final_probs = self._combine_probabilities(
            elo_probs, 0, sentiment_adj
        )

        return {
            "home": final_probs["home"],
            "draw": final_probs["draw"],
            "away": final_probs["away"],
            "elo_diff": elo_probs.elo_diff
        }


# Direkter Test
if __name__ == "__main__":
    predictor = Predictor()

    print("=== Prognose-Engine Test ===\n")

    # Schnelle Prognose
    print("--- Schnelle Elo-Prognose ---")
    result = predictor.quick_predict(
        home_elo=1700,  # Bayern
        away_elo=1450,  # Augsburg
        home_sentiment=0.2,
        away_sentiment=-0.1
    )
    print(f"Bayern vs Augsburg:")
    print(f"  Heim: {result['home']:.0%}")
    print(f"  Remis: {result['draw']:.0%}")
    print(f"  Auswärts: {result['away']:.0%}")

    # Ausgeglichenes Spiel
    print("\n--- Ausgeglichenes Spiel ---")
    result2 = predictor.quick_predict(
        home_elo=1550,
        away_elo=1580,
        home_sentiment=0,
        away_sentiment=0
    )
    print(f"Team A (1550) vs Team B (1580):")
    print(f"  Heim: {result2['home']:.0%}")
    print(f"  Remis: {result2['draw']:.0%}")
    print(f"  Auswärts: {result2['away']:.0%}")

    # Mit Krise
    print("\n--- Spiel mit Krise ---")
    result3 = predictor.quick_predict(
        home_elo=1600,
        away_elo=1500,
        home_sentiment=-0.6,  # Krise!
        away_sentiment=0.3    # Gute Stimmung
    )
    print(f"Heim (Krise) vs Auswärts (gut drauf):")
    print(f"  Heim: {result3['home']:.0%}")
    print(f"  Remis: {result3['draw']:.0%}")
    print(f"  Auswärts: {result3['away']:.0%}")
