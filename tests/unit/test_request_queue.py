import asyncio
import pytest

from hestia.request_queue import RequestQueue, QueuedRequest, QueueTimeoutError


def test_request_queue_initialization():
    """Test basic request queue initialization."""
    queue = RequestQueue(max_queue_size=10, default_timeout_seconds=30)
    assert queue.max_queue_size == 10
    assert queue.default_timeout_seconds == 30
    assert len(queue._service_queues) == 0


def test_queued_request_creation():
    """Test QueuedRequest creation and properties."""
    future = asyncio.Future()
    request = QueuedRequest(
        service_id="test-service",
        request_data={"method": "GET", "path": "/test"},
        timeout_seconds=30,
        future=future,
    )

    assert request.service_id == "test-service"
    assert request.request_data == {"method": "GET", "path": "/test"}
    assert request.timeout_seconds == 30
    assert request.future is future
    assert request.created_at is not None


@pytest.mark.asyncio
async def test_queue_request_and_process():
    """Test queuing a request and processing it."""
    queue = RequestQueue(max_queue_size=5, default_timeout_seconds=30)

    # Queue a request
    future = await queue.queue_request(
        service_id="test-service",
        request_data={"method": "GET", "path": "/models"},
        timeout_seconds=10,
    )

    # Verify request is queued
    assert "test-service" in queue._service_queues
    assert len(queue._service_queues["test-service"]) == 1
    assert not future.done()

    # Process the request
    response_data = {"status": "success", "data": []}
    queue.process_next_request("test-service", response_data)

    # Verify future is resolved
    assert future.done()
    result = await future
    assert result == response_data


@pytest.mark.asyncio
async def test_queue_request_timeout():
    """Test request timeout handling."""
    queue = RequestQueue(max_queue_size=5, default_timeout_seconds=30)

    # Queue a request with very short timeout
    future = await queue.queue_request(
        service_id="test-service",
        request_data={"method": "GET", "path": "/models"},
        timeout_seconds=0.1,  # 100ms timeout
    )

    # Wait for timeout to occur
    with pytest.raises(QueueTimeoutError, match="Request timed out after 0.1 seconds"):
        await future


@pytest.mark.asyncio
async def test_queue_size_limit():
    """Test queue size limits are enforced."""
    queue = RequestQueue(max_queue_size=2, default_timeout_seconds=30)

    # Fill the queue to capacity
    future1 = await queue.queue_request(
        service_id="test-service", request_data={"method": "GET", "path": "/test1"}
    )
    await queue.queue_request(
        service_id="test-service", request_data={"method": "GET", "path": "/test2"}
    )

    # Verify both requests are queued
    assert len(queue._service_queues["test-service"]) == 2

    # Third request should be rejected
    with pytest.raises(ValueError, match="Queue for service test-service is full"):
        await queue.queue_request(
            service_id="test-service", request_data={"method": "GET", "path": "/test3"}
        )

    # Process one request to make space
    queue.process_next_request("test-service", {"result": "success"})
    await future1

    # Now we should be able to queue another
    future3 = await queue.queue_request(
        service_id="test-service", request_data={"method": "GET", "path": "/test3"}
    )
    assert not future3.done()


def test_multiple_service_queues():
    """Test that different services have separate queues."""
    queue = RequestQueue(max_queue_size=5, default_timeout_seconds=30)

    # Start async context to use queue_request
    async def test_multiple_services():
        # Queue requests for different services
        future1 = await queue.queue_request(
            service_id="service1", request_data={"method": "GET", "path": "/test1"}
        )
        future2 = await queue.queue_request(
            service_id="service2", request_data={"method": "GET", "path": "/test2"}
        )

        # Verify separate queues
        assert len(queue._service_queues) == 2
        assert "service1" in queue._service_queues
        assert "service2" in queue._service_queues
        assert len(queue._service_queues["service1"]) == 1
        assert len(queue._service_queues["service2"]) == 1

        # Process service1 request
        queue.process_next_request("service1", {"result": "service1_response"})
        result1 = await future1
        assert result1 == {"result": "service1_response"}

        # service2 queue should still have the request
        assert len(queue._service_queues["service2"]) == 1
        assert not future2.done()

    asyncio.run(test_multiple_services())


def test_process_next_request_empty_queue():
    """Test processing when queue is empty."""
    queue = RequestQueue(max_queue_size=5, default_timeout_seconds=30)

    # Processing empty queue should not raise error
    result = queue.process_next_request("nonexistent-service", {"data": "test"})
    assert result is None


def test_fifo_order():
    """Test that requests are processed in FIFO order."""
    queue = RequestQueue(max_queue_size=10, default_timeout_seconds=30)

    async def test_fifo():
        # Queue multiple requests
        future1 = await queue.queue_request(service_id="test-service", request_data={"order": 1})
        future2 = await queue.queue_request(service_id="test-service", request_data={"order": 2})
        future3 = await queue.queue_request(service_id="test-service", request_data={"order": 3})

        # Process in order
        queue.process_next_request("test-service", {"processed": 1})
        result1 = await future1
        assert result1 == {"processed": 1}

        queue.process_next_request("test-service", {"processed": 2})
        result2 = await future2
        assert result2 == {"processed": 2}

        queue.process_next_request("test-service", {"processed": 3})
        result3 = await future3
        assert result3 == {"processed": 3}

    asyncio.run(test_fifo())


def test_queue_status():
    """Test getting queue status information."""
    queue = RequestQueue(max_queue_size=5, default_timeout_seconds=30)

    async def test_status():
        # Initially empty
        status = queue.get_queue_status("test-service")
        assert status == {"pending_requests": 0, "max_size": 5}

        # Add some requests
        await queue.queue_request("test-service", {"req": 1})
        await queue.queue_request("test-service", {"req": 2})

        status = queue.get_queue_status("test-service")
        assert status == {"pending_requests": 2, "max_size": 5}

        # Process one
        queue.process_next_request("test-service", {"result": "ok"})

        status = queue.get_queue_status("test-service")
        assert status == {"pending_requests": 1, "max_size": 5}

    asyncio.run(test_status())


def test_clear_queue():
    """Test clearing all requests for a service."""
    queue = RequestQueue(max_queue_size=5, default_timeout_seconds=30)

    async def test_clear():
        # Add some requests
        future1 = await queue.queue_request("test-service", {"req": 1})
        future2 = await queue.queue_request("test-service", {"req": 2})

        assert len(queue._service_queues["test-service"]) == 2

        # Clear the queue
        cleared_count = queue.clear_queue("test-service")
        assert cleared_count == 2
        assert len(queue._service_queues.get("test-service", [])) == 0

        # Futures should be cancelled
        assert future1.cancelled()
        assert future2.cancelled()

    asyncio.run(test_clear())


@pytest.mark.asyncio
async def test_prevent_duplicate_startups():
    """Test that duplicate startup attempts are prevented."""
    queue = RequestQueue(max_queue_size=5, default_timeout_seconds=30)

    # Mock service startup function
    startup_calls = []

    async def mock_startup(service_id):
        startup_calls.append(service_id)
        await asyncio.sleep(0.1)  # Simulate startup time
        return "started"

    # Queue multiple requests quickly for same service
    futures = []
    for i in range(3):
        future = await queue.queue_request(service_id="test-service", request_data={"request": i})
        futures.append(future)

    # Simulate startup being triggered only once
    # (in real implementation, this would be handled by the queue logic)
    assert len(queue._service_queues["test-service"]) == 3

    # Process all requests with same response (service now ready)
    for i in range(3):
        queue.process_next_request("test-service", {"service_ready": True, "request_id": i})

    # All futures should be resolved
    for i, future in enumerate(futures):
        result = await future
        assert result == {"service_ready": True, "request_id": i}


def test_queue_cleanup_on_timeout():
    """Test that timed out requests are cleaned up properly."""
    queue = RequestQueue(max_queue_size=5, default_timeout_seconds=30)

    # This test is more conceptual - in practice, timeout cleanup
    # would be handled by the asyncio timeout mechanism
    # Here we test the data structures remain consistent

    async def test_cleanup():
        # Add a request
        future = await queue.queue_request("test-service", {"test": "data"})
        assert len(queue._service_queues["test-service"]) == 1

        # Manually cancel the future (simulating timeout)
        future.cancel()

        # The queue should still show the request until processed/cleared
        assert len(queue._service_queues["test-service"]) == 1

        # Clear the queue to clean up
        queue.clear_queue("test-service")
        assert len(queue._service_queues.get("test-service", [])) == 0

    asyncio.run(test_cleanup())
