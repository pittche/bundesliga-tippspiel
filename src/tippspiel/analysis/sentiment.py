"""
Keyword-basierte Sentiment-Analyse für Bundesliga-News.

Einfacher aber effektiver Ansatz ohne Machine Learning.
Nutzt ein domänenspezifisches Lexikon für Fußball-Begriffe.

Vorteile gegenüber ML:
- Keine Trainingssdaten nötig
- Transparent und erklärbar
- Schnell und ressourcenschonend
- Einfach erweiterbar
"""

from dataclasses import dataclass, field


@dataclass
class SentimentResult:
    """Ergebnis einer Sentiment-Analyse."""
    score: float                   # -1 (sehr negativ) bis +1 (sehr positiv)
    keywords_found: list[str]      # Gefundene Keywords
    confidence: str                # 'high', 'medium', 'low'
    category: str                  # 'crisis', 'conflict', 'positive', 'neutral'


class KeywordSentiment:
    """
    Keyword-basierte Sentiment-Analyse für deutsche Fußball-News.

    Die Analyse funktioniert durch:
    1. Suche nach positiven/negativen Keywords
    2. Gewichtung der Keywords nach Stärke
    3. Aggregation zu einem Gesamtscore
    """

    # === NEGATIVE KEYWORDS ===

    # Trainer-Probleme (stark negativ)
    TRAINER_CRISIS = {
        "entlassung": -0.9,
        "entlassen": -0.9,
        "rauswurf": -0.9,
        "freigestellt": -0.85,
        "freistellung": -0.85,
        "beurlaubt": -0.85,
        "beurlaubung": -0.85,
        "ultimatum": -0.8,
        "trainerdiskussion": -0.7,
        "trainerfrage": -0.6,
        "wackelt": -0.6,
        "angezählt": -0.7,
        "schicksalsspiel": -0.5,
        "endspiel": -0.4,  # Kann auch positiv sein (Finale)
    }

    # Interne Konflikte
    INTERNAL_CONFLICT = {
        "streit": -0.7,
        "zoff": -0.6,
        "eklat": -0.8,
        "ärger": -0.5,
        "unzufrieden": -0.5,
        "unzufriedenheit": -0.5,
        "kritik": -0.4,
        "kritisiert": -0.4,
        "suspendiert": -0.7,
        "suspendierung": -0.7,
        "ausgebootet": -0.6,
        "degradiert": -0.5,
        "wechselwunsch": -0.4,
        "abgang": -0.3,
        "abwanderung": -0.4,
        "unruhe": -0.5,
        "kabine": -0.2,  # Oft negativ im Kontext
        "disharmonie": -0.6,
        "spaltung": -0.7,
    }

    # Leistungsprobleme
    PERFORMANCE_ISSUES = {
        "krise": -0.7,
        "kriselt": -0.6,
        "absturz": -0.7,
        "abstürzen": -0.6,
        "pleite": -0.6,
        "debakel": -0.8,
        "blamage": -0.7,
        "desaster": -0.8,
        "abstiegskampf": -0.6,
        "abstieg": -0.7,
        "abstiegsplatz": -0.6,
        "niederlagenserie": -0.7,
        "sieglos": -0.5,
        "formkrise": -0.6,
        "abwärtstrend": -0.5,
        "torlos": -0.3,
        "chancenlos": -0.5,
        "unterlegen": -0.4,
        "schwach": -0.3,
        "enttäuschend": -0.5,
        "enttäuschung": -0.5,
    }

    # Verletzungen
    INJURIES = {
        "verletzt": -0.4,
        "verletzung": -0.4,
        "ausfall": -0.5,
        "ausfällt": -0.5,
        "fehlt": -0.3,
        "langzeitverletzt": -0.7,
        "kreuzbandriss": -0.8,
        "muskelverletzung": -0.5,
        "angeschlagen": -0.3,
        "fraglich": -0.2,
    }

    # Skandale/Privates
    SCANDALS = {
        "skandal": -0.8,
        "ermittlung": -0.7,
        "ermittlungen": -0.7,
        "vorfall": -0.5,
        "anzeige": -0.6,
        "polizei": -0.5,
        "verhaftet": -0.9,
        "vorwurf": -0.5,
        "vorwürfe": -0.5,
        "affäre": -0.6,
    }

    # === POSITIVE KEYWORDS ===

    # Erfolge
    SUCCESS = {
        "sieg": 0.5,
        "siegt": 0.5,
        "gewonnen": 0.5,
        "gewinnt": 0.5,
        "triumph": 0.7,
        "triumphiert": 0.7,
        "souverän": 0.5,
        "überlegen": 0.4,
        "kantersieg": 0.7,
        "glanzsieg": 0.7,
        "siegesserie": 0.7,
        "ungeschlagen": 0.5,
        "meister": 0.6,
        "meisterschaft": 0.6,
        "pokalsieger": 0.7,
        "tabellenführer": 0.5,
        "spitzenreiter": 0.5,
    }

    # Positive Entwicklung
    POSITIVE_TREND = {
        "aufschwung": 0.6,
        "aufholjagd": 0.5,
        "comeback": 0.6,
        "wiedergutmachung": 0.5,
        "trendwende": 0.6,
        "befreiungsschlag": 0.7,
        "aufwärtstrend": 0.5,
        "formstark": 0.5,
        "hochform": 0.6,
        "bestform": 0.6,
        "erfolgreich": 0.5,
        "erfolg": 0.4,
    }

    # Teamgeist
    TEAM_SPIRIT = {
        "zusammenhalt": 0.5,
        "geschlossen": 0.4,
        "einheit": 0.5,
        "teamgeist": 0.5,
        "kampfgeist": 0.5,
        "motivation": 0.4,
        "motiviert": 0.4,
        "zuversicht": 0.4,
        "optimismus": 0.4,
        "harmonie": 0.5,
    }

    # Verstärkungen
    REINFORCEMENTS = {
        "verpflichtung": 0.4,
        "verpflichtet": 0.4,
        "neuzugang": 0.4,
        "verstärkung": 0.5,
        "transfer": 0.3,
        "vertragsverlängerung": 0.5,
        "verlängert": 0.4,
        "bekenntnis": 0.4,
    }

    # Rückkehr/Fitness
    RECOVERY = {
        "zurück": 0.3,
        "rückkehr": 0.4,
        "fit": 0.4,
        "einsatzbereit": 0.4,
        "genesen": 0.5,
        "wieder dabei": 0.4,
    }

    def __init__(self):
        """Initialisiert das kombinierte Lexikon."""
        self.negative_keywords = {}
        self.positive_keywords = {}

        # Negative zusammenfügen
        for lexicon in [
            self.TRAINER_CRISIS,
            self.INTERNAL_CONFLICT,
            self.PERFORMANCE_ISSUES,
            self.INJURIES,
            self.SCANDALS,
        ]:
            self.negative_keywords.update(lexicon)

        # Positive zusammenfügen
        for lexicon in [
            self.SUCCESS,
            self.POSITIVE_TREND,
            self.TEAM_SPIRIT,
            self.REINFORCEMENTS,
            self.RECOVERY,
        ]:
            self.positive_keywords.update(lexicon)

    def analyze(self, text: str) -> SentimentResult:
        """
        Analysiert einen Text und gibt einen Sentiment-Score zurück.

        Args:
            text: Der zu analysierende Text

        Returns:
            SentimentResult mit Score, Keywords und Kategorie
        """
        text_lower = text.lower()
        found_keywords = []
        scores = []

        # Negative Keywords suchen
        for keyword, weight in self.negative_keywords.items():
            if keyword in text_lower:
                found_keywords.append(f"-{keyword}")
                scores.append(weight)

        # Positive Keywords suchen
        for keyword, weight in self.positive_keywords.items():
            if keyword in text_lower:
                found_keywords.append(f"+{keyword}")
                scores.append(weight)

        # Score berechnen
        if scores:
            # Durchschnitt der gewichteten Scores
            raw_score = sum(scores) / len(scores)
            # Normalisieren auf -1 bis +1
            final_score = max(-1, min(1, raw_score))
        else:
            final_score = 0

        # Confidence basierend auf Anzahl gefundener Keywords
        if len(found_keywords) >= 4:
            confidence = "high"
        elif len(found_keywords) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        # Kategorie bestimmen
        category = self._determine_category(final_score, found_keywords)

        return SentimentResult(
            score=round(final_score, 2),
            keywords_found=found_keywords,
            confidence=confidence,
            category=category
        )

    def _determine_category(
        self,
        score: float,
        keywords: list[str]
    ) -> str:
        """Bestimmt die Kategorie basierend auf Score und Keywords."""
        if not keywords:
            return "neutral"

        # Nach spezifischen Kategorien suchen
        crisis_keywords = set(self.TRAINER_CRISIS.keys()) | set(self.SCANDALS.keys())
        conflict_keywords = set(self.INTERNAL_CONFLICT.keys())

        found_set = {k.lstrip("+-") for k in keywords}

        if found_set & crisis_keywords:
            return "crisis"
        elif found_set & conflict_keywords:
            return "conflict"
        elif score > 0.2:
            return "positive"
        elif score < -0.2:
            return "negative"
        else:
            return "neutral"

    def analyze_for_team(
        self,
        news_items: list[dict],
        max_age_weight: bool = True
    ) -> dict:
        """
        Aggregiert Sentiment aus mehreren News-Items für ein Team.

        Args:
            news_items: Liste von dicts mit 'title', 'description', 'published'
            max_age_weight: Neuere News stärker gewichten?

        Returns:
            Dict mit aggregiertem Score und Details
        """
        if not news_items:
            return {
                "score": 0,
                "category": "neutral",
                "confidence": "low",
                "num_articles": 0,
                "crisis_indicators": [],
            }

        scores = []
        all_keywords = []
        crisis_indicators = []

        for i, item in enumerate(news_items):
            text = f"{item.get('title', '')} {item.get('description', '')}"
            result = self.analyze(text)

            # Gewichtung: neuere News (höherer Index) wichtiger
            weight = 1 + (i / len(news_items)) if max_age_weight else 1

            scores.append((result.score, weight))
            all_keywords.extend(result.keywords_found)

            # Krisen-Indikatoren sammeln
            if result.category in ("crisis", "conflict"):
                crisis_indicators.append({
                    "title": item.get("title", "")[:50],
                    "score": result.score,
                    "keywords": result.keywords_found
                })

        # Gewichteter Durchschnitt
        if scores:
            weighted_sum = sum(s * w for s, w in scores)
            weight_total = sum(w for _, w in scores)
            avg_score = weighted_sum / weight_total
        else:
            avg_score = 0

        # Gesamtkategorie
        if crisis_indicators:
            category = "crisis"
        elif avg_score > 0.3:
            category = "positive"
        elif avg_score < -0.3:
            category = "negative"
        else:
            category = "neutral"

        # Confidence
        if len(news_items) >= 5 and len(all_keywords) >= 8:
            confidence = "high"
        elif len(news_items) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "score": round(avg_score, 2),
            "category": category,
            "confidence": confidence,
            "num_articles": len(news_items),
            "total_keywords": len(all_keywords),
            "crisis_indicators": crisis_indicators[:3],  # Max 3
        }

    def get_sentiment_label(self, score: float) -> str:
        """Gibt ein menschenlesbares Label für einen Score zurück."""
        if score >= 0.5:
            return "Sehr positiv"
        elif score >= 0.2:
            return "Positiv"
        elif score >= -0.2:
            return "Neutral"
        elif score >= -0.5:
            return "Negativ"
        else:
            return "Sehr negativ"

    def get_sentiment_emoji(self, score: float) -> str:
        """Gibt ein Symbol fuer den Score zurueck."""
        if score >= 0.5:
            return "[++]"
        elif score >= 0.2:
            return "[+]"
        elif score >= -0.2:
            return "[~]"
        elif score >= -0.5:
            return "[-]"
        else:
            return "[--]"


# Direkter Test
if __name__ == "__main__":
    sentiment = KeywordSentiment()

    print("=== Sentiment-Analyse Test ===\n")

    test_texts = [
        "Bayern-Trainer steht nach Debakel vor dem Aus - Ultimatum gestellt",
        "Leverkusen setzt Siegesserie fort: Souveräner Triumph gegen Leipzig",
        "Zoff in der Kabine: Spieler kritisiert Trainer nach Pleite",
        "Dortmund verpflichtet Neuzugang: Verstärkung für den Angriff",
        "Verletzungsschock: Stürmer fällt mit Kreuzbandriss lange aus",
        "Team zeigt Zusammenhalt nach schwieriger Phase - Aufschwung erwartet",
        "Bundesliga-Spieltag: Alle Ergebnisse im Überblick",  # Neutral
    ]

    for text in test_texts:
        result = sentiment.analyze(text)
        emoji = sentiment.get_sentiment_emoji(result.score)
        label = sentiment.get_sentiment_label(result.score)

        print(f"{emoji} [{result.score:+.2f}] {label}")
        print(f"   \"{text[:60]}...\"")
        print(f"   Keywords: {', '.join(result.keywords_found[:5])}")
        print(f"   Kategorie: {result.category}, Konfidenz: {result.confidence}")
        print()

    # Aggregierter Test
    print("=== Aggregierte Team-Analyse ===\n")
    team_news = [
        {"title": "Trainer wackelt nach Niederlage", "description": "Kritik wird lauter"},
        {"title": "Streit in der Kabine", "description": "Spieler unzufrieden"},
        {"title": "Auswärtssieg bringt Erleichterung", "description": "Team zeigt Reaktion"},
    ]

    team_result = sentiment.analyze_for_team(team_news)
    print(f"Team-Score: {team_result['score']:+.2f}")
    print(f"Kategorie: {team_result['category']}")
    print(f"Artikel analysiert: {team_result['num_articles']}")
    if team_result['crisis_indicators']:
        print("Krisen-Indikatoren:")
        for ind in team_result['crisis_indicators']:
            print(f"  - {ind['title']}")
