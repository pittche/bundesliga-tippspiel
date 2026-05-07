"""
News Fetcher - Bundesliga-News aus RSS-Feeds.

Nutzt oeffentliche RSS-Feeds von Sport-Nachrichtenportalen.
Keine API-Keys noetig, keine Registrierung.

Verwendet xml.etree statt feedparser fuer weniger Dependencies.
"""

import requests
from xml.etree import ElementTree
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import re


@dataclass
class RawNewsItem:
    """Rohe News-Meldung aus RSS-Feed."""
    title: str
    description: str
    published: datetime
    source: str
    link: str
    team: Optional[str] = None


class NewsFetcher:
    """
    Holt News aus oeffentlichen RSS-Feeds.

    Quellen:
    - Kicker Bundesliga
    - Transfermarkt News
    """

    RSS_FEEDS = {
        "kicker": "https://newsfeed.kicker.de/news/bundesliga",
        "transfermarkt": "https://www.transfermarkt.de/rss/news",
    }

    # Team-Aliase fuer Erkennung in News-Texten
    TEAM_ALIASES = {
        # Bayern
        "bayern": "FC Bayern München",
        "fcb": "FC Bayern München",
        "münchen": "FC Bayern München",
        "munich": "FC Bayern München",

        # Dortmund
        "dortmund": "Borussia Dortmund",
        "bvb": "Borussia Dortmund",
        "borussia dortmund": "Borussia Dortmund",

        # Leipzig
        "leipzig": "RB Leipzig",
        "rbl": "RB Leipzig",
        "rasenball": "RB Leipzig",

        # Leverkusen
        "leverkusen": "Bayer 04 Leverkusen",
        "bayer": "Bayer 04 Leverkusen",
        "werkself": "Bayer 04 Leverkusen",
        "b04": "Bayer 04 Leverkusen",

        # Frankfurt
        "frankfurt": "Eintracht Frankfurt",
        "eintracht": "Eintracht Frankfurt",
        "sge": "Eintracht Frankfurt",

        # Wolfsburg
        "wolfsburg": "VfL Wolfsburg",
        "wölfe": "VfL Wolfsburg",

        # Gladbach
        "gladbach": "Borussia Mönchengladbach",
        "mönchengladbach": "Borussia Mönchengladbach",
        "bmg": "Borussia Mönchengladbach",
        "fohlen": "Borussia Mönchengladbach",

        # Freiburg
        "freiburg": "SC Freiburg",
        "scf": "SC Freiburg",

        # Hoffenheim
        "hoffenheim": "TSG 1899 Hoffenheim",
        "tsg": "TSG 1899 Hoffenheim",

        # Mainz
        "mainz": "1. FSV Mainz 05",
        "m05": "1. FSV Mainz 05",

        # Augsburg
        "augsburg": "FC Augsburg",
        "fca": "FC Augsburg",

        # Stuttgart
        "stuttgart": "VfB Stuttgart",
        "vfb": "VfB Stuttgart",

        # Bremen
        "bremen": "SV Werder Bremen",
        "werder": "SV Werder Bremen",
        "svw": "SV Werder Bremen",

        # Union
        "union": "1. FC Union Berlin",
        "union berlin": "1. FC Union Berlin",
        "köpenick": "1. FC Union Berlin",

        # Köln
        "köln": "1. FC Köln",
        "fc köln": "1. FC Köln",
        "geißböcke": "1. FC Köln",

        # Bochum
        "bochum": "VfL Bochum 1848",

        # Heidenheim
        "heidenheim": "1. FC Heidenheim 1846",
        "fch": "1. FC Heidenheim 1846",

        # St. Pauli
        "pauli": "FC St. Pauli",
        "st. pauli": "FC St. Pauli",
        "st pauli": "FC St. Pauli",
        "millerntor": "FC St. Pauli",

        # Kiel
        "kiel": "Holstein Kiel",
        "holstein": "Holstein Kiel",
        "störche": "Holstein Kiel",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def fetch_all(self, max_age_hours: int = 72) -> list[RawNewsItem]:
        """
        Holt News aus allen konfigurierten RSS-Feeds.

        Args:
            max_age_hours: Maximales Alter der News in Stunden

        Returns:
            Liste von RawNewsItem, nach Datum sortiert
        """
        all_news = []
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        for source, url in self.RSS_FEEDS.items():
            try:
                news_items = self._fetch_feed(source, url, cutoff)
                all_news.extend(news_items)
            except Exception as e:
                print(f"Fehler beim Abruf von {source}: {e}")
                continue

        # Nach Datum sortieren (neueste zuerst)
        all_news.sort(key=lambda x: x.published, reverse=True)

        return all_news

    def fetch_source(
        self,
        source: str,
        max_age_hours: int = 72
    ) -> list[RawNewsItem]:
        """
        Holt News aus einer bestimmten Quelle.

        Args:
            source: Name der Quelle (kicker, transfermarkt)
            max_age_hours: Maximales Alter

        Returns:
            Liste von RawNewsItem
        """
        url = self.RSS_FEEDS.get(source)
        if not url:
            print(f"Unbekannte Quelle: {source}")
            return []

        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        return self._fetch_feed(source, url, cutoff)

    def _fetch_feed(
        self,
        source: str,
        url: str,
        cutoff: datetime
    ) -> list[RawNewsItem]:
        """Laedt und parst einen einzelnen RSS-Feed."""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"HTTP-Fehler bei {source}: {e}")
            return []

        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as e:
            print(f"XML-Parsing-Fehler bei {source}: {e}")
            return []

        news_items = []

        # RSS 2.0: channel/item
        items = root.findall(".//item")

        for item in items[:30]:  # Max 30 Eintraege pro Feed
            # Titel
            title_elem = item.find("title")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

            # Beschreibung
            desc_elem = item.find("description")
            description = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
            description = self._strip_html(description)

            # Link
            link_elem = item.find("link")
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""

            # Datum
            pub_elem = item.find("pubDate")
            published = self._parse_date(pub_elem.text if pub_elem is not None else None)

            if published and published < cutoff:
                continue

            if published is None:
                published = datetime.now()

            # Team erkennen
            full_text = f"{title} {description}".lower()
            team = self._extract_team(full_text)

            news_items.append(RawNewsItem(
                title=title,
                description=description[:500],
                published=published,
                source=source,
                link=link,
                team=team
            ))

        return news_items

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parst das Datum aus einem RSS-Feed."""
        if not date_str:
            return None

        # Verschiedene Formate versuchen
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",      # RFC 822
            "%a, %d %b %Y %H:%M:%S %Z",      # Mit Timezone-Name
            "%Y-%m-%dT%H:%M:%S%z",           # ISO 8601
            "%Y-%m-%d %H:%M:%S",             # Einfach
            "%d %b %Y %H:%M:%S %z",          # Ohne Wochentag
        ]

        # Timezone-Offset entfernen falls noetig (fuer einfaches Parsing)
        date_str_clean = re.sub(r'\s+\+\d{4}$', '', date_str)
        date_str_clean = re.sub(r'\s+GMT$', '', date_str_clean)
        date_str_clean = re.sub(r'\s+UTC$', '', date_str_clean)

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                pass

        # Fallback ohne Timezone
        for fmt in ["%a, %d %b %Y %H:%M:%S", "%d %b %Y %H:%M:%S"]:
            try:
                return datetime.strptime(date_str_clean, fmt)
            except ValueError:
                pass

        return None

    def _extract_team(self, text: str) -> Optional[str]:
        """Extrahiert den Teamnamen aus einem Text."""
        text_lower = text.lower()

        # Nach Aliassen suchen (laengere zuerst fuer bessere Matches)
        sorted_aliases = sorted(
            self.TEAM_ALIASES.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )

        for alias, team_name in sorted_aliases:
            if alias in text_lower:
                return team_name

        return None

    def _strip_html(self, text: str) -> str:
        """Entfernt HTML-Tags aus Text."""
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()

    def get_team_news(
        self,
        team_name: str,
        all_news: Optional[list[RawNewsItem]] = None,
        max_items: int = 10
    ) -> list[RawNewsItem]:
        """
        Filtert News fuer ein bestimmtes Team.

        Args:
            team_name: Name des Teams
            all_news: Optionale Liste von bereits geladenen News
            max_items: Maximale Anzahl zurueckzugebender Items

        Returns:
            Gefilterte Liste von RawNewsItem
        """
        if all_news is None:
            all_news = self.fetch_all()

        team_news = [n for n in all_news if n.team == team_name]
        return team_news[:max_items]


# Direkter Test
if __name__ == "__main__":
    fetcher = NewsFetcher()

    print("=== Bundesliga News (letzte 72h) ===\n")

    news = fetcher.fetch_all(max_age_hours=72)
    print(f"Gefunden: {len(news)} Nachrichten\n")

    # Nach Quelle gruppieren
    by_source = {}
    for item in news:
        by_source.setdefault(item.source, []).append(item)

    for source, items in by_source.items():
        print(f"--- {source.upper()} ({len(items)} Artikel) ---")
        for item in items[:3]:
            team_tag = f"[{item.team}]" if item.team else "[Allgemein]"
            print(f"  {team_tag} {item.title[:60]}...")
        print()

    # Team-Filter testen
    print("=== News fuer Bayern ===")
    bayern_news = fetcher.get_team_news("FC Bayern München", news)
    for item in bayern_news[:5]:
        print(f"  - {item.title[:70]}...")
