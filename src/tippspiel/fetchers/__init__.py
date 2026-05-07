"""Daten-Fetcher für verschiedene Quellen."""

from .openligadb import OpenLigaDBFetcher
from .footballdata import FootballDataFetcher
from .news import NewsFetcher

# Legacy-Alias fuer Kompatibilitaet
UnderstatFetcher = FootballDataFetcher

__all__ = ["OpenLigaDBFetcher", "FootballDataFetcher", "NewsFetcher", "UnderstatFetcher"]
