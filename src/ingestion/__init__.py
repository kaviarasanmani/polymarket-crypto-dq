"""Ingestion package for Polymarket prediction market data."""
from .downloader import DatasetManager
from .schema_discovery import SchemaDiscovery, ColumnProfile

__all__ = ["DatasetManager", "SchemaDiscovery", "ColumnProfile"]
