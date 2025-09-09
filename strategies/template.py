"""
Strategy Template

Use this template as a starting point for creating your own custom strategies.
Copy this file and modify it to implement your specific logic.
"""

from typing import Dict, Any


class TemplateStrategy:
    """
    Template strategy showing the basic structure and common patterns.

    Replace this with your own strategy description explaining:
    - What problem this strategy solves
    - When to use this strategy
    - How it integrates with Hestia
    - Configuration options available
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """
        Initialize the strategy with optional configuration.

        Args:
            config: Configuration dictionary for this strategy
        """
        # Required strategy metadata
        self.name = "template_strategy"  # Change this to your strategy name
        self.description = "Template strategy for custom implementations"  # Your description
        self.version = "1.0.0"  # Your version

        # Strategy configuration
        self.config = config or {}

        # Initialize your strategy state here
        self._initialize_strategy()

    def _initialize_strategy(self):
        """
        Initialize strategy-specific state and configuration.

        This method is called during __init__ and can be used to:
        - Validate configuration
        - Set up internal state
        - Initialize external connections
        - Register event handlers
        """
        # Example: validate required configuration
        required_keys = ["example_setting"]
        for key in required_keys:
            if key not in self.config:
                print(f"Warning: Missing required configuration key: {key}")

        # Example: initialize strategy state
        self.example_state = {}

        print(f"Initialized {self.name} strategy with config: {self.config}")

    def process_request(self, service_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request using your custom strategy logic.

        Args:
            service_id: The service this request is for
            request_data: Request information including method, path, headers, etc.

        Returns:
            Dictionary with processing results and any modifications

        Example:
            result = {
                "action": "allow",  # or "deny", "modify", "route", etc.
                "modifications": {"headers": {"X-Strategy": "template"}},
                "metadata": {"strategy_version": self.version}
            }
        """
        # Your strategy logic goes here

        # Example: log the request
        print(
            f"Processing request for {service_id}: {request_data.get('method', 'UNKNOWN')} {request_data.get('path', '/')}"
        )

        # Example: add custom header
        modifications = {
            "headers": {"X-Strategy-Processed": self.name, "X-Strategy-Version": self.version}
        }

        # Example: return processing result
        return {
            "action": "allow",
            "modifications": modifications,
            "metadata": {
                "strategy": self.name,
                "processing_time_ms": 1,  # In real implementation, measure actual time
            },
        }

    def handle_response(self, service_id: str, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a response from a service using your custom strategy logic.

        Args:
            service_id: The service that generated this response
            response_data: Response information including status, headers, body, etc.

        Returns:
            Dictionary with processing results and any modifications
        """
        # Your response processing logic goes here

        # Example: log the response
        print(f"Processing response from {service_id}: {response_data.get('status', 'UNKNOWN')}")

        # Example: add custom response header
        modifications = {"headers": {"X-Strategy-Response-Processed": self.name}}

        return {
            "action": "allow",
            "modifications": modifications,
            "metadata": {"strategy": self.name},
        }

    def handle_error(
        self, service_id: str, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle errors that occur during request processing.

        Args:
            service_id: The service where the error occurred
            error: The exception that was raised
            context: Additional context about the error

        Returns:
            Dictionary with error handling results
        """
        # Your error handling logic goes here

        # Example: log the error
        print(f"Handling error for {service_id}: {str(error)}")

        # Example: return error handling result
        return {
            "action": "retry",  # or "fail", "fallback", etc.
            "retry_delay_ms": 1000,
            "max_retries": 3,
            "metadata": {"strategy": self.name, "error_type": type(error).__name__},
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Return metrics and statistics about this strategy's performance.

        Returns:
            Dictionary with metrics data
        """
        # Your metrics collection logic goes here

        return {
            "strategy": self.name,
            "requests_processed": 0,  # Track actual count
            "responses_processed": 0,  # Track actual count
            "errors_handled": 0,  # Track actual count
            "average_processing_time_ms": 0.0,  # Calculate actual average
            "configuration": self.config,
        }

    def update_configuration(self, new_config: Dict[str, Any]) -> bool:
        """
        Update the strategy configuration at runtime.

        Args:
            new_config: New configuration to apply

        Returns:
            True if configuration was updated successfully, False otherwise
        """
        try:
            # Validate new configuration
            # Your validation logic goes here

            # Apply new configuration
            self.config.update(new_config)

            # Re-initialize if needed
            self._initialize_strategy()

            print(f"Updated configuration for {self.name}: {new_config}")
            return True

        except Exception as e:
            print(f"Failed to update configuration for {self.name}: {str(e)}")
            return False

    def get_strategy_info(self) -> Dict[str, Any]:
        """
        Return comprehensive information about this strategy.

        This method is used by Hestia for strategy discovery, documentation,
        and administrative interfaces.

        Returns:
            Dictionary with strategy information
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "type": "template",  # Change this to your strategy type
            "features": [
                "request_processing",
                "response_processing",
                "error_handling",
                "metrics_collection",
                "runtime_configuration",
            ],
            "configuration_schema": {
                "example_setting": {
                    "type": "string",
                    "description": "Example configuration setting",
                    "required": True,
                    "default": "default_value",
                }
            },
            "supported_events": ["request", "response", "error", "service_start", "service_stop"],
            "author": "Your Name",
            "license": "MIT",
            "documentation_url": "https://github.com/yourusername/your-strategy",
        }


# Register the strategy with Hestia
def register_strategy(registry):
    """
    This function is called by Hestia's strategy loader.
    Register your strategy with the provided registry.

    You can also perform any global initialization here.
    """
    # Example: load configuration from environment or file
    config = {"example_setting": "example_value"}

    def create_template_strategy():
        return TemplateStrategy(config)

    registry.register("template_strategy", create_template_strategy)


# Example usage and testing
if __name__ == "__main__":
    # This code runs when the file is executed directly
    # Use it for testing your strategy implementation

    print("Testing Template Strategy...")

    # Create strategy instance directly for testing
    strategy = TemplateStrategy({"example_setting": "example_value"})

    # Test strategy methods
    print("\nStrategy Info:")
    info = strategy.get_strategy_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    print("\nTesting request processing:")
    request_data = {"method": "GET", "path": "/api/test", "headers": {"User-Agent": "Test"}}
    result = strategy.process_request("test-service", request_data)
    print(f"  Result: {result}")

    print("\nTesting response processing:")
    response_data = {
        "status": 200,
        "headers": {"Content-Type": "application/json"},
        "body": {"result": "success"},
    }
    result = strategy.handle_response("test-service", response_data)
    print(f"  Result: {result}")

    print("\nTesting error handling:")
    test_error = Exception("Test error")
    result = strategy.handle_error("test-service", test_error, {})
    print(f"  Result: {result}")

    print("\nStrategy metrics:")
    metrics = strategy.get_metrics()
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    print("\nTemplate strategy test completed!")


# Additional Notes for Strategy Developers:
#
# 1. Strategy Lifecycle:
#    - __init__: Strategy initialization
#    - register_strategy: Strategy registration with Hestia
#    - Various methods: Called during request/response processing
#    - Cleanup: Implement __del__ if needed for resource cleanup
#
# 2. Configuration Best Practices:
#    - Provide sensible defaults for all configuration options
#    - Validate configuration in __init__ or _initialize_strategy
#    - Support runtime configuration updates when possible
#    - Document all configuration options in get_strategy_info
#
# 3. Error Handling:
#    - Always handle exceptions gracefully
#    - Provide meaningful error messages
#    - Implement proper logging
#    - Consider retry and fallback mechanisms
#
# 4. Performance Considerations:
#    - Minimize processing time in request/response methods
#    - Use async/await for I/O operations when possible
#    - Implement caching for expensive operations
#    - Profile your strategy under load
#
# 5. Testing:
#    - Write comprehensive unit tests
#    - Test with various input scenarios
#    - Test error conditions and edge cases
#    - Integration test with Hestia
#
# 6. Documentation:
#    - Provide clear docstrings for all methods
#    - Include usage examples
#    - Document configuration options
#    - Explain integration points with Hestia
