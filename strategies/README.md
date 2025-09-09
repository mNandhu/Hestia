# Hestia Strategies

This directory contains custom strategy implementations for extending Hestia's capabilities. Strategies allow you to implement custom logic for load balancing, health checking, routing, and other gateway operations.

## Overview

Hestia's strategy system uses a plugin-based architecture where strategies are automatically discovered and loaded from this directory. Each strategy is a Python module that implements specific interfaces and provides a `register_strategy()` function.

## Available Strategies

### 1. Load Balancer Strategy (`load_balancer.py`)

Implements round-robin load balancing with health tracking across multiple service instances.

**Features:**
- Round-robin request distribution
- Automatic health tracking and failover
- Regional preference routing
- Weight-based distribution
- Circuit breaker pattern

**Usage:**
```python
from strategies.load_balancer import LoadBalancerStrategy

lb = LoadBalancerStrategy()
lb.register_service_instances("ollama", [
    {"url": "http://ollama-1:11434", "weight": 1, "region": "us-east"},
    {"url": "http://ollama-2:11434", "weight": 2, "region": "us-west"}
])

# Get next instance for request
instance_url = lb.get_next_instance("ollama", {"user_region": "us-east"})
```

### 2. Health Checker Strategy (`health_checker.py`)

Advanced health monitoring with multiple check types and automated recovery actions.

**Features:**
- HTTP endpoint health checks
- Metrics validation
- Circuit breaker pattern
- Automated notifications
- Health history tracking
- Recovery action triggers

**Usage:**
```python
from strategies.health_checker import HealthCheckerStrategy

hc = HealthCheckerStrategy()
health_config = {
    "endpoints": [
        {"url": "http://service:8080/health", "type": "http"}
    ],
    "validation": {"response_time_ms": 1000},
    "recovery": {"notification_webhook": "http://alerts:8080/webhook"}
}

hc.register_service("ollama", health_config)
result = await hc.check_service_health("ollama")
```

### 3. Custom Routing Strategy (`custom_routing.py`)

Flexible routing with rule-based logic and A/B testing capabilities.

**Features:**
- Rule-based routing conditions
- A/B testing support
- User-based routing
- Geographic routing
- Model-aware routing
- Complex condition evaluation

**Usage:**
```python
from strategies.custom_routing import CustomRoutingStrategy

router = CustomRoutingStrategy()
rules = [
    {
        "name": "premium_users",
        "condition": {"user_tier": "premium"},
        "target": "http://premium-ollama:11434"
    }
]

router.register_routing_rules("ollama", rules)
result = router.route_request("ollama", {"user_tier": "premium"})
```

## Creating Custom Strategies

### 1. Strategy Structure

Create a new Python file in this directory with the following structure:

```python
"""
Strategy Description

Brief description of what this strategy does and when to use it.
"""

class MyCustomStrategy:
    def __init__(self):
        self.name = "my_custom_strategy"
        self.description = "Description of the strategy"
        self.version = "1.0.0"
    
    def my_strategy_method(self, *args, **kwargs):
        """Implement your custom logic here."""
        pass
    
    def get_strategy_info(self):
        """Return information about this strategy."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "type": "my_strategy_type",
            "features": ["feature1", "feature2"]
        }

# Required: Register function for Hestia's strategy loader
def register_strategy():
    """
    This function is called by Hestia's strategy loader.
    Return an instance of your strategy class.
    """
    return MyCustomStrategy()
```

### 2. Strategy Types

Common strategy types and their purposes:

- **`load_balancer`**: Distribute requests across multiple instances
- **`health_checker`**: Monitor service health and trigger actions
- **`routing`**: Custom routing logic based on request attributes
- **`auth`**: Authentication and authorization logic
- **`rate_limiter`**: Rate limiting and throttling
- **`cache`**: Caching strategies and cache invalidation
- **`metrics`**: Custom metrics collection and analysis
- **`circuit_breaker`**: Circuit breaker implementations

### 3. Best Practices

#### Configuration
- Use type hints for better IDE support and documentation
- Provide comprehensive docstrings for all methods
- Include configuration validation in `__init__`
- Support both programmatic and file-based configuration

#### Error Handling
- Always provide fallback behavior for failures
- Log errors appropriately with context
- Use circuit breaker patterns for external dependencies
- Implement proper timeout handling

#### Performance
- Minimize blocking operations in request paths
- Use async/await for I/O operations when possible
- Implement caching for expensive operations
- Consider memory usage for long-running processes

#### Testing
- Write unit tests for your strategy logic
- Include integration tests with Hestia
- Test error conditions and edge cases
- Validate configuration and input parameters

### 4. Integration with Hestia

#### Strategy Discovery
Hestia automatically discovers strategies by:
1. Scanning all `.py` files in the `strategies/` directory
2. Looking for a `register_strategy()` function in each module
3. Calling the function to get a strategy instance
4. Registering the strategy in the global strategy registry

#### Using Strategies
Strategies can be used in several ways:

1. **Direct Integration**: Called directly by Hestia's core logic
2. **Event Handlers**: Triggered by specific events (startup, request, error)
3. **Middleware**: Applied to all requests automatically
4. **Manual Invocation**: Called explicitly by other components

#### Configuration Integration
Strategies can be configured via:
- `hestia_config.yml` file
- Environment variables
- Database settings
- Runtime API calls

## Example Configurations

### Load Balancer with Health Checking
```yaml
# hestia_config.yml
services:
  ollama:
    instances:
      - url: "http://ollama-1:11434"
        weight: 1
        region: "us-east"
      - url: "http://ollama-2:11434" 
        weight: 2
        region: "us-west"
    
    strategies:
      load_balancer:
        algorithm: "round_robin"
        health_check_interval: 30
      
      health_checker:
        endpoints:
          - url: "http://ollama-1:11434/health"
            type: "http"
        failure_threshold: 3
```

### A/B Testing Setup
```yaml
services:
  ollama:
    strategies:
      custom_routing:
        ab_tests:
          - name: "new_model_test"
            variants:
              - name: "control"
                target: "http://ollama-v1:11434"
                traffic: 80
              - name: "treatment"
                target: "http://ollama-v2:11434"
                traffic: 20
            start_time: "2025-01-01T00:00:00Z"
            end_time: "2025-01-31T23:59:59Z"
```

## Development Tips

### 1. Debugging Strategies
- Use Hestia's logging system for debug output
- Test strategies independently before integration
- Use the `/v1/strategies` API endpoint to inspect loaded strategies
- Enable verbose logging during development

### 2. Strategy Dependencies
- Keep external dependencies minimal
- Use async libraries for I/O operations
- Handle missing dependencies gracefully
- Document all required packages

### 3. Performance Considerations
- Profile strategy code under load
- Use connection pooling for external services
- Implement proper caching strategies
- Consider memory usage patterns

### 4. Security Considerations
- Validate all input parameters
- Use secure communication for external calls
- Implement proper authentication for strategy APIs
- Avoid logging sensitive information

## Contributing

When contributing new strategies:

1. Follow the established code style and patterns
2. Include comprehensive documentation and examples
3. Write tests for all functionality
4. Update this README with your new strategy
5. Consider backward compatibility
6. Submit a pull request with clear description

## Troubleshooting

### Strategy Not Loading
- Check that the file has a `register_strategy()` function
- Verify there are no syntax errors in the Python code
- Check Hestia's logs for import errors
- Ensure all dependencies are installed

### Strategy Errors
- Check the strategy's implementation of required methods
- Verify configuration format and values
- Test the strategy independently
- Check for resource constraints (memory, network)

### Performance Issues
- Profile the strategy code to identify bottlenecks
- Check for blocking operations in async contexts
- Verify proper connection management
- Monitor memory usage patterns

For more information, see the [Hestia Documentation](https://github.com/mNandhu/Hestia-SSD).