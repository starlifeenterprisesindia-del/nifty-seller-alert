"""Core infrastructure for the single-snapshot AI department pipeline."""

try:
    from .data_intelligence import DataDistributor, MarketDataSnapshot, SnapshotManager
except ImportError:  # direct-file/test execution fallback
    from data_intelligence import DataDistributor, MarketDataSnapshot, SnapshotManager

__all__ = ["MarketDataSnapshot", "SnapshotManager", "DataDistributor"]
