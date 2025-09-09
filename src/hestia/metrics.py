"""
Metrics Collection System for Hestia Gateway

Provides basic metrics collection (counters, timers, gauges) for monitoring
service performance, request patterns, and system health.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class MetricValue:
    """Base class for metric values."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CounterValue(MetricValue):
    """Counter metric value."""

    count: int = 0


@dataclass
class GaugeValue(MetricValue):
    """Gauge metric value."""

    value: float = 0.0


@dataclass
class TimerValue(MetricValue):
    """Timer metric value with statistics."""

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        """Average duration in milliseconds."""
        return self.total_ms / self.count if self.count > 0 else 0.0


@dataclass
class HistogramValue(MetricValue):
    """Histogram metric value with percentiles."""

    values: List[float] = field(default_factory=list)
    max_samples: int = 1000  # Keep last N samples for percentile calculation

    def add_value(self, value: float):
        """Add a value to the histogram."""
        self.values.append(value)
        # Keep only recent samples to prevent memory growth
        if len(self.values) > self.max_samples:
            self.values.pop(0)

    def get_percentile(self, percentile: float) -> float:
        """Get percentile value (0-100)."""
        if not self.values:
            return 0.0

        sorted_values = sorted(self.values)
        index = (percentile / 100.0) * (len(sorted_values) - 1)

        if index == int(index):
            # Exact index
            return sorted_values[int(index)]
        else:
            # Interpolate between two values
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(sorted_values) - 1)
            weight = index - lower_index
            return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight

    @property
    def p50(self) -> float:
        """50th percentile (median)."""
        return self.get_percentile(50)

    @property
    def p95(self) -> float:
        """95th percentile."""
        return self.get_percentile(95)

    @property
    def p99(self) -> float:
        """99th percentile."""
        return self.get_percentile(99)


class MetricsCollector:
    """Thread-safe metrics collector."""

    def __init__(self):
        """Initialize metrics collector."""
        self._lock = threading.RLock()
        self._counters: Dict[str, CounterValue] = {}
        self._gauges: Dict[str, GaugeValue] = {}
        self._timers: Dict[str, TimerValue] = {}
        self._histograms: Dict[str, HistogramValue] = {}

        # Service-specific metrics
        self._service_counters: Dict[str, Dict[str, CounterValue]] = defaultdict(dict)
        self._service_timers: Dict[str, Dict[str, TimerValue]] = defaultdict(dict)
        self._service_gauges: Dict[str, Dict[str, GaugeValue]] = defaultdict(dict)

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        service_id: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Increment a counter metric."""
        with self._lock:
            key = self._build_key(name, labels)

            if service_id:
                # Service-specific counter
                if key not in self._service_counters[service_id]:
                    self._service_counters[service_id][key] = CounterValue()
                self._service_counters[service_id][key].count += value
                self._service_counters[service_id][key].timestamp = datetime.now(timezone.utc)
            else:
                # Global counter
                if key not in self._counters:
                    self._counters[key] = CounterValue()
                self._counters[key].count += value
                self._counters[key].timestamp = datetime.now(timezone.utc)

    def set_gauge(
        self,
        name: str,
        value: float,
        service_id: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Set a gauge metric value."""
        with self._lock:
            key = self._build_key(name, labels)

            if service_id:
                # Service-specific gauge
                self._service_gauges[service_id][key] = GaugeValue(value=value)
            else:
                # Global gauge
                self._gauges[key] = GaugeValue(value=value)

    def record_timer(
        self,
        name: str,
        duration_ms: float,
        service_id: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Record a timer metric."""
        with self._lock:
            key = self._build_key(name, labels)

            if service_id:
                # Service-specific timer
                if key not in self._service_timers[service_id]:
                    self._service_timers[service_id][key] = TimerValue()

                timer = self._service_timers[service_id][key]
                timer.count += 1
                timer.total_ms += duration_ms
                timer.min_ms = min(timer.min_ms, duration_ms)
                timer.max_ms = max(timer.max_ms, duration_ms)
                timer.timestamp = datetime.now(timezone.utc)
            else:
                # Global timer
                if key not in self._timers:
                    self._timers[key] = TimerValue()

                timer = self._timers[key]
                timer.count += 1
                timer.total_ms += duration_ms
                timer.min_ms = min(timer.min_ms, duration_ms)
                timer.max_ms = max(timer.max_ms, duration_ms)
                timer.timestamp = datetime.now(timezone.utc)

    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram metric."""
        with self._lock:
            key = self._build_key(name, labels)

            if key not in self._histograms:
                self._histograms[key] = HistogramValue()

            self._histograms[key].add_value(value)
            self._histograms[key].timestamp = datetime.now(timezone.utc)

    def get_counter(
        self, name: str, service_id: Optional[str] = None, labels: Optional[Dict[str, str]] = None
    ) -> Optional[CounterValue]:
        """Get counter metric value."""
        with self._lock:
            key = self._build_key(name, labels)

            if service_id:
                return self._service_counters.get(service_id, {}).get(key)
            else:
                return self._counters.get(key)

    def get_gauge(
        self, name: str, service_id: Optional[str] = None, labels: Optional[Dict[str, str]] = None
    ) -> Optional[GaugeValue]:
        """Get gauge metric value."""
        with self._lock:
            key = self._build_key(name, labels)

            if service_id:
                return self._service_gauges.get(service_id, {}).get(key)
            else:
                return self._gauges.get(key)

    def get_timer(
        self, name: str, service_id: Optional[str] = None, labels: Optional[Dict[str, str]] = None
    ) -> Optional[TimerValue]:
        """Get timer metric value."""
        with self._lock:
            key = self._build_key(name, labels)

            if service_id:
                return self._service_timers.get(service_id, {}).get(key)
            else:
                return self._timers.get(key)

    def get_histogram(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Optional[HistogramValue]:
        """Get histogram metric value."""
        with self._lock:
            key = self._build_key(name, labels)
            return self._histograms.get(key)

    def get_all_metrics(self) -> Dict[str, Dict]:
        """Get all metrics as a dictionary."""
        with self._lock:
            return {
                "counters": {
                    k: {"count": v.count, "timestamp": v.timestamp.isoformat()}
                    for k, v in self._counters.items()
                },
                "gauges": {
                    k: {"value": v.value, "timestamp": v.timestamp.isoformat()}
                    for k, v in self._gauges.items()
                },
                "timers": {
                    k: {
                        "count": v.count,
                        "total_ms": v.total_ms,
                        "avg_ms": v.avg_ms,
                        "min_ms": v.min_ms if v.min_ms != float("inf") else 0,
                        "max_ms": v.max_ms,
                        "timestamp": v.timestamp.isoformat(),
                    }
                    for k, v in self._timers.items()
                },
                "histograms": {
                    k: {
                        "count": len(v.values),
                        "p50": v.p50,
                        "p95": v.p95,
                        "p99": v.p99,
                        "timestamp": v.timestamp.isoformat(),
                    }
                    for k, v in self._histograms.items()
                },
                "services": {
                    service_id: {
                        "counters": {
                            k: {"count": v.count, "timestamp": v.timestamp.isoformat()}
                            for k, v in counters.items()
                        },
                        "timers": {
                            k: {
                                "count": v.count,
                                "total_ms": v.total_ms,
                                "avg_ms": v.avg_ms,
                                "min_ms": v.min_ms if v.min_ms != float("inf") else 0,
                                "max_ms": v.max_ms,
                                "timestamp": v.timestamp.isoformat(),
                            }
                            for k, v in timers.items()
                        },
                        "gauges": {
                            k: {"value": v.value, "timestamp": v.timestamp.isoformat()}
                            for k, v in gauges.items()
                        },
                    }
                    for service_id in self._service_counters.keys()
                    | self._service_timers.keys()
                    | self._service_gauges.keys()
                    for counters in [self._service_counters.get(service_id, {})]
                    for timers in [self._service_timers.get(service_id, {})]
                    for gauges in [self._service_gauges.get(service_id, {})]
                },
            }

    def get_service_metrics(self, service_id: str) -> Dict[str, Dict]:
        """Get metrics for a specific service."""
        with self._lock:
            counters = self._service_counters.get(service_id, {})
            timers = self._service_timers.get(service_id, {})
            gauges = self._service_gauges.get(service_id, {})

            return {
                "counters": {
                    k: {"count": v.count, "timestamp": v.timestamp.isoformat()}
                    for k, v in counters.items()
                },
                "timers": {
                    k: {
                        "count": v.count,
                        "total_ms": v.total_ms,
                        "avg_ms": v.avg_ms,
                        "min_ms": v.min_ms if v.min_ms != float("inf") else 0,
                        "max_ms": v.max_ms,
                        "timestamp": v.timestamp.isoformat(),
                    }
                    for k, v in timers.items()
                },
                "gauges": {
                    k: {"value": v.value, "timestamp": v.timestamp.isoformat()}
                    for k, v in gauges.items()
                },
            }

    def reset_metrics(self, service_id: Optional[str] = None):
        """Reset metrics (useful for testing)."""
        with self._lock:
            if service_id:
                # Reset service-specific metrics
                self._service_counters.pop(service_id, None)
                self._service_timers.pop(service_id, None)
                self._service_gauges.pop(service_id, None)
            else:
                # Reset all metrics
                self._counters.clear()
                self._gauges.clear()
                self._timers.clear()
                self._histograms.clear()
                self._service_counters.clear()
                self._service_timers.clear()
                self._service_gauges.clear()

    def _build_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Build metric key with labels."""
        if not labels:
            return name

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"


class Timer:
    """Context manager for timing operations."""

    def __init__(
        self,
        metrics: MetricsCollector,
        name: str,
        service_id: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        self.metrics = metrics
        self.name = name
        self.service_id = service_id
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.metrics.record_timer(self.name, duration_ms, self.service_id, self.labels)


# Global metrics collector instance
metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return metrics


# Common metric names
class MetricNames:
    """Common metric names for consistency."""

    # Request metrics
    REQUESTS_TOTAL = "requests_total"
    REQUEST_DURATION = "request_duration_ms"
    RESPONSE_SIZE = "response_size_bytes"

    # Service metrics
    SERVICE_STARTS = "service_starts_total"
    SERVICE_STOPS = "service_stops_total"
    SERVICE_ERRORS = "service_errors_total"
    SERVICE_STARTUP_DURATION = "service_startup_duration_ms"
    SERVICE_STATE_CHANGES = "service_state_changes_total"

    # Queue metrics
    QUEUE_SIZE = "queue_size"
    QUEUE_WAIT_TIME = "queue_wait_time_ms"
    QUEUE_TIMEOUTS = "queue_timeouts_total"

    # Proxy metrics
    PROXY_REQUESTS = "proxy_requests_total"
    PROXY_DURATION = "proxy_duration_ms"
    PROXY_ERRORS = "proxy_errors_total"

    # Health check metrics
    HEALTH_CHECKS = "health_checks_total"
    HEALTH_CHECK_DURATION = "health_check_duration_ms"
    HEALTH_CHECK_FAILURES = "health_check_failures_total"

    # Gateway metrics
    ACTIVE_CONNECTIONS = "active_connections"
    MEMORY_USAGE = "memory_usage_bytes"
    CPU_USAGE = "cpu_usage_percent"


# Example usage and testing
if __name__ == "__main__":
    # Test metrics collection
    collector = MetricsCollector()

    # Test counters
    collector.increment_counter(
        MetricNames.REQUESTS_TOTAL, labels={"method": "GET", "status": "200"}
    )
    collector.increment_counter(
        MetricNames.REQUESTS_TOTAL, labels={"method": "POST", "status": "201"}
    )
    collector.increment_counter(MetricNames.SERVICE_STARTS, service_id="ollama")

    # Test timers
    collector.record_timer(MetricNames.REQUEST_DURATION, 125.5, labels={"method": "GET"})
    collector.record_timer(MetricNames.REQUEST_DURATION, 89.2, labels={"method": "GET"})
    collector.record_timer(MetricNames.SERVICE_STARTUP_DURATION, 1250.0, service_id="ollama")

    # Test gauges
    collector.set_gauge(MetricNames.QUEUE_SIZE, 3, service_id="ollama")
    collector.set_gauge(MetricNames.ACTIVE_CONNECTIONS, 15)

    # Test histograms
    collector.record_histogram("response_time_histogram", 125.5, labels={"method": "GET"})
    collector.record_histogram("response_time_histogram", 89.2, labels={"method": "GET"})
    collector.record_histogram("response_time_histogram", 234.1, labels={"method": "GET"})

    # Test timer context manager
    with Timer(collector, MetricNames.REQUEST_DURATION, labels={"method": "POST"}):
        time.sleep(0.01)  # Simulate work

    # Get all metrics
    all_metrics = collector.get_all_metrics()
    print("All metrics:")
    import json

    print(json.dumps(all_metrics, indent=2))

    # Get service-specific metrics
    service_metrics = collector.get_service_metrics("ollama")
    print("\nOllama service metrics:")
    print(json.dumps(service_metrics, indent=2))

    print("\nMetrics collection test completed!")
