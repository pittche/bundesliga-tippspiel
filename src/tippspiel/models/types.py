"""
Datentypen für das Tippspiel.
Verwendet dataclasses für einfache, typisierte Datenstrukturen.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Team:
    """Ein Bundesliga-Team."""
    id: int
    name: str
    short_name: str
    openliga_id: int
    understat_name: str
    elo_rating: float = 1500.0


@dataclass
class Match:
    """Ein Bundesliga-Spiel."""
    id: Optional[int]
    season: str
    matchday: int
    home_team_id: int
    away_team_id: int
    match_date: datetime
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None
    home_xg: Optional[float] = None
    away_xg: Optional[float] = None
    finished: bool = False

    @property
    def result(self) -> Optional[str]:
        """Gibt das Ergebnis als String zurück (z.B. '2:1')."""
        if self.home_goals is None or self.away_goals is None:
            return None
        return f"{self.home_goals}:{self.away_goals}"

    @property
    def winner(self) -> Optional[str]:
        """Gibt 'home', 'away' oder 'draw' zurück."""
        if not self.finished or self.home_goals is None:
            return None
        if self.home_goals > self.away_goals:
            return "home"
        elif self.home_goals < self.away_goals:
            return "away"
        return "draw"


@dataclass
class TeamForm:
    """Aktuelle Form eines Teams."""
    team_id: int
    calculated_at: datetime
    elo_rating: float
    xg_avg: Optional[float] = None      # Durchschnitt xG letzte 5 Spiele
    xga_avg: Optional[float] = None     # Durchschnitt xGA letzte 5 Spiele
    xg_trend: float = 0.0               # Steigung der xG-Kurve
    goals_avg: Optional[float] = None
    luck_factor: float = 0.0            # Tore - xG (positiv = Glück)
    sentiment_score: float = 0.0        # -1 bis +1


@dataclass
class NewsItem:
    """Eine News-Meldung."""
    id: Optional[int]
    published_at: datetime
    source: str
    title: str
    description: str
    team_id: Optional[int] = None
    sentiment_score: float = 0.0
    keywords_found: list[str] = field(default_factory=list)
    link: str = ""


@dataclass
class Prediction:
    """Eine Spielprognose."""
    match_id: int
    calculated_at: datetime
    home_team: str
    away_team: str
    prob_home: float
    prob_draw: float
    prob_away: float
    recommendation: str
    confidence: str  # 'high', 'medium', 'low'
    factors: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"{self.home_team} vs {self.away_team}: "
            f"H {self.prob_home:.0%} | D {self.prob_draw:.0%} | A {self.prob_away:.0%} "
            f"=> {self.recommendation} ({self.confidence})"
        )


@dataclass
class SentimentResult:
    """Ergebnis einer Sentiment-Analyse."""
    score: float              # -1 bis +1
    keywords_found: list[str]
    confidence: str           # 'high', 'medium', 'low'
