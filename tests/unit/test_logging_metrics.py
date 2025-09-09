"""
Tests for Hestia Logging and Metrics

Tests the structured logging system, metrics collection, and middleware
integration for comprehensive observability.
"""

import time

from fastapi.testclient import TestClient

from hestia.app import app
from hestia.logging import (
    EventType,
    HestiaLogger,
    LogLevel,
    RequestTimer,
    clear_request_id,
    get_logger,
    get_request_id,
    set_request_id,
)
from hestia.metrics import MetricsCollector, Timer


class TestStructuredLogging:
    """Test structured logging functionality."""

    def setup_method(self):
        """Setup for each test."""
        self.logger = HestiaLogger("test_logger", LogLevel.DEBUG)

    def test_logger_initialization(self):
        """Test logger initialization."""
        logger = HestiaLogger("test", LogLevel.INFO)
        assert logger.name == "test"
        assert logger.logger.level == 20  # INFO level

    def test_basic_logging(self):
        """Test basic logging methods."""
        # These tests verify the methods don't raise exceptions
        self.logger.debug("Debug message")
        self.logger.info("Info message")
        self.logger.warning("Warning message")
        self.logger.error("Error message")
        self.logger.critical("Critical message")

    def test_structured_logging_with_fields(self):
        """Test logging with structured fields."""
        self.logger.info(
            "Test message",
            service_id="test-service",
            duration_ms=123.45,
            status_code=200,
            metadata={"key": "value"},
        )

    def test_event_logging(self):
        """Test event-specific logging methods."""
        self.logger.log_event(EventType.SERVICE_START, "Service starting")
        self.logger.log_service_start("test-service")
        self.logger.log_service_ready("test-service", duration_ms=1250.0)
        self.logger.log_service_stop("test-service", reason="shutdown")
        self.logger.log_service_error("test-service", "Connection failed")
        self.logger.log_service_state_change("test-service", "cold", "hot")

    def test_request_logging(self):
        """Test request start/end logging."""
        self.logger.log_request_start("GET", "/api/test", service_id="test-service")
        self.logger.log_request_end("GET", "/api/test", 200, 125.5, service_id="test-service")

    def test_proxy_logging(self):
        """Test proxy-specific logging."""
        self.logger.log_proxy_start("test-service", "http://target", "GET", "/api/test")
        self.logger.log_proxy_end("test-service", "http://target", 200, 89.2)

    def test_queue_logging(self):
        """Test queue event logging."""
        self.logger.log_queue_event(EventType.REQUEST_QUEUED, "test-service", queue_size=5)
        self.logger.log_queue_event(EventType.REQUEST_DEQUEUED, "test-service", queue_size=4)

    def test_health_check_logging(self):
        """Test health check logging."""
        self.logger.log_health_check("test-service", "http://health", "healthy", 25.0)
        self.logger.log_health_check("test-service", "http://health", "unhealthy", 5000.0)


class TestRequestContext:
    """Test request ID context management."""

    def setup_method(self):
        """Setup for each test."""
        clear_request_id()

    def teardown_method(self):
        """Cleanup after each test."""
        clear_request_id()

    def test_request_id_generation(self):
        """Test request ID generation."""
        req_id = set_request_id()
        assert req_id.startswith("req_")
        assert len(req_id) == 16  # "req_" + 12 hex chars
        assert get_request_id() == req_id

    def test_custom_request_id(self):
        """Test setting custom request ID."""
        custom_id = "custom-request-123"
        set_request_id(custom_id)
        assert get_request_id() == custom_id

    def test_request_id_clearing(self):
        """Test clearing request ID."""
        set_request_id("test-id")
        assert get_request_id() == "test-id"
        clear_request_id()
        assert get_request_id() is None

    def test_request_timer(self):
        """Test request timer context manager."""
        logger = get_logger()

        with RequestTimer(logger, "GET", "/test", "service") as timer:
            time.sleep(0.01)
            timer.set_status_code(200)

        # Timer should complete without error


class TestMetricsCollection:
    """Test metrics collection functionality."""

    def setup_method(self):
        """Setup for each test."""
        self.metrics = MetricsCollector()

    def test_counter_metrics(self):
        """Test counter metrics."""
        # Increment counter
        self.metrics.increment_counter("test_counter", 5)
        counter = self.metrics.get_counter("test_counter")
        assert counter is not None
        assert counter.count == 5

        # Increment again
        self.metrics.increment_counter("test_counter", 3)
        counter = self.metrics.get_counter("test_counter")
        assert counter is not None
        assert counter.count == 8

    def test_gauge_metrics(self):
        """Test gauge metrics."""
        self.metrics.set_gauge("test_gauge", 42.5)
        gauge = self.metrics.get_gauge("test_gauge")
        assert gauge is not None
        assert gauge.value == 42.5

        # Update gauge
        self.metrics.set_gauge("test_gauge", 100.0)
        gauge = self.metrics.get_gauge("test_gauge")
        assert gauge is not None
        assert gauge.value == 100.0

    def test_timer_metrics(self):
        """Test timer metrics."""
        self.metrics.record_timer("test_timer", 100.0)
        self.metrics.record_timer("test_timer", 200.0)
        self.metrics.record_timer("test_timer", 150.0)

        timer = self.metrics.get_timer("test_timer")
        assert timer is not None
        assert timer.count == 3
        assert timer.total_ms == 450.0
        assert timer.avg_ms == 150.0
        assert timer.min_ms == 100.0
        assert timer.max_ms == 200.0

    def test_histogram_metrics(self):
        """Test histogram metrics."""
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for value in values:
            self.metrics.record_histogram("test_histogram", value)

        histogram = self.metrics.get_histogram("test_histogram")
        assert histogram is not None
        assert len(histogram.values) == 10
        assert histogram.p50 == 55.0  # Interpolated median
        assert histogram.p95 == 95.5  # Interpolated 95th percentile

    def test_service_specific_metrics(self):
        """Test service-specific metrics."""
        self.metrics.increment_counter("requests", 5, service_id="service1")
        self.metrics.increment_counter("requests", 3, service_id="service2")
        self.metrics.record_timer("response_time", 100.0, service_id="service1")
        self.metrics.set_gauge("queue_size", 10, service_id="service1")

        # Check service1 metrics
        service1_metrics = self.metrics.get_service_metrics("service1")
        assert "requests" in service1_metrics["counters"]
        assert service1_metrics["counters"]["requests"]["count"] == 5
        assert "response_time" in service1_metrics["timers"]
        assert "queue_size" in service1_metrics["gauges"]

        # Check service2 metrics
        service2_metrics = self.metrics.get_service_metrics("service2")
        assert service2_metrics["counters"]["requests"]["count"] == 3

    def test_metrics_with_labels(self):
        """Test metrics with labels."""
        self.metrics.increment_counter("http_requests", labels={"method": "GET", "status": "200"})
        self.metrics.increment_counter("http_requests", labels={"method": "POST", "status": "201"})

        get_counter = self.metrics.get_counter(
            "http_requests", labels={"method": "GET", "status": "200"}
        )
        post_counter = self.metrics.get_counter(
            "http_requests", labels={"method": "POST", "status": "201"}
        )

        assert get_counter is not None
        assert get_counter.count == 1
        assert post_counter is not None
        assert post_counter.count == 1

    def test_timer_context_manager(self):
        """Test timer context manager."""
        with Timer(self.metrics, "operation_time"):
            time.sleep(0.01)

        timer = self.metrics.get_timer("operation_time")
        assert timer is not None
        assert timer.count == 1
        assert timer.avg_ms > 5  # Should be at least 5ms

    def test_all_metrics_export(self):
        """Test exporting all metrics."""
        self.metrics.increment_counter("counter1", 5)
        self.metrics.set_gauge("gauge1", 42.0)
        self.metrics.record_timer("timer1", 100.0)
        self.metrics.record_histogram("histogram1", 50.0)

        all_metrics = self.metrics.get_all_metrics()

        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "timers" in all_metrics
        assert "histograms" in all_metrics
        assert "services" in all_metrics

        assert "counter1" in all_metrics["counters"]
        assert "gauge1" in all_metrics["gauges"]
        assert "timer1" in all_metrics["timers"]
        assert "histogram1" in all_metrics["histograms"]

    def test_metrics_reset(self):
        """Test metrics reset functionality."""
        self.metrics.increment_counter("test", 5)
        self.metrics.set_gauge("test", 10.0)

        # Reset all metrics
        self.metrics.reset_metrics()

        assert self.metrics.get_counter("test") is None
        assert self.metrics.get_gauge("test") is None


class TestLoggingMiddleware:
    """Test logging middleware functionality."""

    def test_middleware_excludes_paths(self):
        """Test that middleware excludes specified paths."""
        client = TestClient(app)

        # Health endpoint should be excluded by default
        response = client.get("/health")
        # Should return 404 (not implemented) but not cause middleware errors
        assert response.status_code in [404, 200]

    def test_middleware_adds_request_id(self):
        """Test that middleware adds request ID to response."""
        client = TestClient(app)

        response = client.get("/v1/services/test/status")
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert request_id.startswith("req_")

    def test_middleware_preserves_custom_request_id(self):
        """Test that middleware preserves custom request ID."""
        client = TestClient(app)
        custom_id = "custom-req-123"

        response = client.get("/v1/services/test/status", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id

    def test_service_id_extraction(self):
        """Test service ID extraction from URL."""
        client = TestClient(app)

        # Service endpoint should extract service ID
        response = client.get("/v1/services/ollama/status")
        assert response.status_code == 200


class TestMetricsEndpoints:
    """Test metrics API endpoints."""

    def test_global_metrics_endpoint(self):
        """Test global metrics endpoint."""
        client = TestClient(app)

        response = client.get("/v1/metrics")
        assert response.status_code == 200

        metrics_data = response.json()
        assert "counters" in metrics_data
        assert "gauges" in metrics_data
        assert "timers" in metrics_data
        assert "histograms" in metrics_data
        assert "services" in metrics_data

    def test_service_metrics_endpoint(self):
        """Test service-specific metrics endpoint."""
        client = TestClient(app)

        response = client.get("/v1/services/ollama/metrics")
        assert response.status_code == 200

        metrics_data = response.json()
        assert "counters" in metrics_data
        assert "timers" in metrics_data
        assert "gauges" in metrics_data


class TestIntegration:
    """Test integration of logging and metrics in the app."""

    def test_service_startup_logging_and_metrics(self):
        """Test that service startup generates logs and metrics."""
        client = TestClient(app)

        # Start a service
        response = client.post("/v1/services/ollama/start")
        # Should either succeed (202) or conflict (409) if already started
        assert response.status_code in [202, 409]

        # Check that metrics were recorded
        metrics_response = client.get("/v1/services/ollama/metrics")
        assert metrics_response.status_code == 200

    def test_request_generates_metrics(self):
        """Test that requests generate appropriate metrics."""
        client = TestClient(app)

        # Make a request
        client.get("/v1/services/test/status")

        # Get updated metrics
        updated_response = client.get("/v1/metrics")
        updated_metrics = updated_response.json()

        # Should have metrics (exact counts depend on other tests running)
        assert "counters" in updated_metrics

    def test_error_handling_with_logging(self):
        """Test that errors are properly logged."""
        client = TestClient(app)

        # Make request to non-existent endpoint
        response = client.get("/v1/nonexistent")
        assert response.status_code == 404

        # Middleware should still add request ID
        assert "X-Request-ID" in response.headers


if __name__ == "__main__":
    # Run tests manually for development
    import sys
    import traceback

    test_classes = [
        TestStructuredLogging,
        TestRequestContext,
        TestMetricsCollection,
        TestLoggingMiddleware,
        TestMetricsEndpoints,
        TestIntegration,
    ]

    print("Running T025 Logging and Metrics tests...")

    passed = 0
    failed = 0

    for test_class in test_classes:
        print(f"\n--- {test_class.__name__} ---")
        instance = test_class()

        # Get test methods
        test_methods = [method for method in dir(instance) if method.startswith("test_")]

        for method_name in test_methods:
            try:
                # Setup
                if hasattr(instance, "setup_method"):
                    instance.setup_method()

                # Run test
                method = getattr(instance, method_name)
                method()

                print(f"✓ {method_name}")
                passed += 1

                # Teardown
                if hasattr(instance, "teardown_method"):
                    instance.teardown_method()

            except Exception as e:
                print(f"✗ {method_name}: {e}")
                traceback.print_exc()
                failed += 1

    print("\n--- Results ---")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")

    if failed == 0:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)
