"""
Unit tests for metrics collection to verify bug fixes.
"""

import pytest
from app.metrics import Histogram, Counter, MetricsCollector, increment_counter, observe_histogram


def test_histogram_truncation_preserves_total_count():
    """Test Bug 1 fix: Total count and sum should reflect all observations, not just window."""
    hist = Histogram()
    
    # Add 2000 observations
    for i in range(2000):
        hist.observe(float(i))
    
    stats = hist.get_stats()
    
    # Should report total count (2000), not window size (1000)
    assert stats["count"] == 2000, f"Expected count=2000, got {stats['count']}"
    
    # Sum should be sum of all 2000 values, not just last 1000
    expected_sum = sum(range(2000))
    assert stats["sum"] == expected_sum, f"Expected sum={expected_sum}, got {stats['sum']}"
    
    # Window should only have 1000 values
    assert len(hist.values) == 1000


def test_histogram_percentile_consistency():
    """Test Bug 2 fix: Percentiles should use consistent calculation method."""
    hist = Histogram()
    
    # Add 100 observations (0.0 to 99.0)
    for i in range(100):
        hist.observe(float(i))
    
    stats = hist.get_stats()
    
    # All percentiles should use (n-1) * p formula
    # For 100 values:
    # p50: (100-1) * 0.50 = 49.5 -> index 49 -> value 49.0
    # p95: (100-1) * 0.95 = 94.05 -> index 94 -> value 94.0
    # p99: (100-1) * 0.99 = 98.01 -> index 98 -> value 98.0
    
    # Verify percentiles are calculated consistently
    assert stats["p50"] == 49.0, f"Expected p50=49.0, got {stats['p50']}"
    assert stats["p95"] == 94.0, f"Expected p95=94.0, got {stats['p95']}"
    assert stats["p99"] == 98.0, f"Expected p99=98.0, got {stats['p99']}"


def test_histogram_percentile_edge_cases():
    """Test percentile calculation with edge cases."""
    hist = Histogram()
    
    # Single value
    hist.observe(42.0)
    stats = hist.get_stats()
    assert stats["p50"] == 42.0
    assert stats["p95"] == 42.0
    assert stats["p99"] == 42.0
    
    # Two values
    hist.reset()
    hist.observe(10.0)
    hist.observe(20.0)
    stats = hist.get_stats()
    # (2-1) * 0.5 = 0.5 -> index 0 -> value 10.0
    assert stats["p50"] == 10.0
    
    # Empty histogram
    hist.reset()
    stats = hist.get_stats()
    assert stats["count"] == 0
    assert stats["sum"] == 0.0
    assert stats["p50"] == 0.0
    assert stats["p95"] == 0.0
    assert stats["p99"] == 0.0


def test_histogram_rolling_window():
    """Test that rolling window works correctly while preserving totals."""
    hist = Histogram()
    
    # Add exactly max_window_size + 10 values
    for i in range(1010):
        hist.observe(float(i))
    
    stats = hist.get_stats()
    
    # Total count should be 1010
    assert stats["count"] == 1010
    
    # Total sum should be sum of all 1010 values
    expected_sum = sum(range(1010))
    assert stats["sum"] == expected_sum
    
    # Window should only have 1000 values (last 1000)
    assert len(hist.values) == 1000
    
    # Window should contain values 10-1009
    assert min(hist.values) == 10.0
    assert max(hist.values) == 1009.0


def test_counter_basic():
    """Test counter functionality."""
    counter = Counter()
    
    assert counter.get() == 0
    counter.inc()
    assert counter.get() == 1
    counter.inc(5)
    assert counter.get() == 6
    counter.reset()
    assert counter.get() == 0


def test_metrics_collector():
    """Test metrics collector."""
    collector = MetricsCollector()
    
    # Test counters
    collector.counter("test_counter").inc(10)
    assert collector.counter("test_counter").get() == 10
    
    # Test histograms
    collector.histogram("test_hist").observe(1.5)
    collector.histogram("test_hist").observe(2.5)
    stats = collector.histogram("test_hist").get_stats()
    assert stats["count"] == 2
    assert stats["sum"] == 4.0
    
    # Test get_all_metrics
    all_metrics = collector.get_all_metrics()
    assert "test_counter" in all_metrics["counters"]
    assert all_metrics["counters"]["test_counter"] == 10
    assert "test_hist" in all_metrics["histograms"]
    assert all_metrics["histograms"]["test_hist"]["count"] == 2

