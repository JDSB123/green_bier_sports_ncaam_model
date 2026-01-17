"""
Metrics collection for monitoring and observability.

Provides simple metrics that can be exported to Prometheus or other systems.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class Counter:
    """Simple counter metric."""
    value: int = 0
    _lock: Lock = field(default_factory=Lock)

    def inc(self, amount: int = 1) -> None:
        """Increment counter."""
        with self._lock:
            self.value += amount

    def get(self) -> int:
        """Get current value."""
        with self._lock:
            return self.value

    def reset(self) -> None:
        """Reset counter."""
        with self._lock:
            self.value = 0


@dataclass
class Histogram:
    """
    Simple histogram metric with rolling window.

    Tracks total observations separately from the rolling window to ensure
    accurate count/sum reporting even when values are truncated.
    """
    values: list[float] = field(default_factory=list)
    _total_count: int = 0  # Total observations (including discarded)
    _total_sum: float = 0.0  # Running sum of all observations
    _lock: Lock = field(default_factory=Lock)
    _max_window_size: int = 1000  # Maximum values to keep in memory

    def observe(self, value: float) -> None:
        """
        Record a value.

        Maintains a rolling window of recent values while tracking
        total count and sum across all observations.
        """
        with self._lock:
            self._total_count += 1
            self._total_sum += value

            self.values.append(value)
            # Keep only last N values to prevent memory issues
            # But we still track total_count and total_sum accurately
            if len(self.values) > self._max_window_size:
                # Remove oldest value from window (but count/sum already includes it)
                self.values = self.values[-self._max_window_size:]

    def get_stats(self) -> dict[str, float]:
        """
        Get statistics.

        Returns:
        - count: Total observations (including discarded from rolling window)
        - sum: Sum of all observations (including discarded)
        - min/max/avg: Based on current rolling window (last N values)
        - p50/p95/p99: Percentiles based on current rolling window, using consistent calculation
        """
        with self._lock:
            if not self.values:
                return {
                    "count": self._total_count,
                    "sum": self._total_sum,
                    "min": 0.0,
                    "max": 0.0,
                    "avg": 0.0,
                    "p50": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                }

            sorted_vals = sorted(self.values)
            window_size = len(self.values)

            # Use consistent percentile calculation: (n-1) * percentile
            # This matches standard statistical definitions
            def percentile_index(n: int, p: float) -> int:
                """Calculate percentile index using (n-1) * p formula."""
                if n == 0:
                    return 0
                if n == 1:
                    return 0
                return min(int((n - 1) * p), n - 1)

            return {
                "count": self._total_count,  # Total observations (not just window)
                "sum": self._total_sum,  # Sum of all observations (not just window)
                "min": min(self.values),  # Min from current window
                "max": max(self.values),  # Max from current window
                "avg": sum(self.values) / window_size if window_size > 0 else 0.0,  # Avg of current window
                "p50": sorted_vals[percentile_index(window_size, 0.50)] if window_size > 0 else 0.0,
                "p95": sorted_vals[percentile_index(window_size, 0.95)] if window_size > 0 else 0.0,
                "p99": sorted_vals[percentile_index(window_size, 0.99)] if window_size > 0 else 0.0,
            }

    def reset(self) -> None:
        """Reset histogram (clears both window and totals)."""
        with self._lock:
            self.values.clear()
            self._total_count = 0
            self._total_sum = 0.0


class MetricsCollector:
    """Central metrics collector."""

    def __init__(self):
        self._counters: dict[str, Counter] = defaultdict(Counter)
        self._histograms: dict[str, Histogram] = defaultdict(Histogram)
        self._lock = Lock()

    def counter(self, name: str) -> Counter:
        """Get or create a counter."""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter()
            return self._counters[name]

    def histogram(self, name: str) -> Histogram:
        """Get or create a histogram."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram()
            return self._histograms[name]

    def get_all_metrics(self) -> dict:
        """Get all metrics in a format suitable for export."""
        with self._lock:
            counters = {
                name: counter.get()
                for name, counter in self._counters.items()
            }
            histograms = {
                name: histogram.get_stats()
                for name, histogram in self._histograms.items()
            }
            return {
                "counters": counters,
                "histograms": histograms,
            }

    def reset_all(self) -> None:
        """Reset all metrics."""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()
            for histogram in self._histograms.values():
                histogram.reset()


# Global metrics collector instance
metrics = MetricsCollector()


# Convenience functions
def increment_counter(name: str, amount: int = 1) -> None:
    """Increment a counter metric."""
    metrics.counter(name).inc(amount)


def observe_histogram(name: str, value: float) -> None:
    """Record a histogram value."""
    metrics.histogram(name).observe(value)


class Timer:
    """Context manager for timing operations."""

    def __init__(self, histogram_name: str):
        self.histogram_name = histogram_name
        self.start_time: float | None = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            observe_histogram(self.histogram_name, duration)
