# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2025-07-11

### Added

- Comprehensive pytest test suite with 51 tests covering all major components
- Test fixtures and configuration in `tests/conftest.py`
- Unit tests for configuration loading and validation (`tests/test_config.py`)
- Unit tests for strategy execution engine (`tests/test_strategies.py`)
- Unit tests for database functionality (`tests/test_db.py`)
- API endpoint tests with mocking (`tests/test_app.py`)
- Integration tests for end-to-end workflows (`tests/test_integration.py`)
- pytest configuration file with proper markers and settings
- Test dependencies: pytest, httpx, pytest-asyncio

### Fixed

- **Type errors in `db.py`**:
  - Updated deprecated `datetime.utcnow()` to `datetime.now(timezone.utc)`
  - Fixed SQLAlchemy model attribute access with proper type handling
  - Updated to use modern `sqlalchemy.orm.declarative_base`
- **Type errors in `app.py`**:
  - Fixed SQLAlchemy attribute access issues using `getattr()`
  - Resolved conditional operand type conflicts with SQLAlchemy columns
- **Type errors in `schemas.py`**:
  - Restructured Pydantic models to avoid inheritance conflicts
  - Removed problematic base class with conflicting field types
  - Created union type for response models
- **Strategy execution error handling**:
  - Improved FileNotFoundError handling in `execute_strategy()`
  - Added proper try-catch blocks for module loading

### Changed

- Simplified Pydantic response models by removing inheritance
- Enhanced error handling in strategy execution module
- Updated SQLAlchemy imports to use modern declarative_base

## [0.1.0] - Phase 1 Implementation

### Added

- Core FastAPI application with gateway endpoint (`src/hestia/app.py`)
- Configuration system with Pydantic models (`src/hestia/config.py`)
- SQLite database with SQLAlchemy ORM (`src/hestia/db.py`)
- Dynamic strategy execution engine (`src/hestia/strategies.py`)
- Pydantic response schemas (`src/hestia/schemas.py`)
- Mock routing strategy for testing (`strategies/mock_router.py`)
- YAML configuration file (`hestia_config.yml`)
- Project dependencies and packaging (`pyproject.toml`)

### Features Implemented

- Service discovery and configuration loading
- Database state management for services
- Dynamic Python module loading for routing strategies
- RESTful API with decision-making logic (Phase 1 - no actual proxying)
- Support for multiple HTTP methods (GET, POST, PUT, DELETE, PATCH, OPTIONS)
- Context assembly for strategy execution
- Error handling for missing services and strategy failures

## Project Architecture

### Phase 1 Completion Status ✅

All Phase 1 requirements from the phased plan have been successfully implemented:

1. **✅ Configuration System** - Complete with Pydantic models and YAML loading
2. **✅ State Database** - SQLite with SQLAlchemy ORM and service state tracking
3. **✅ Strategy Executor** - Dynamic module loading with proper error handling
4. **✅ Core Gateway Logic** - Decision-making endpoint with JSON responses
5. **✅ Test Coverage** - Comprehensive test suite with 35+ passing tests

### Next Steps (Phase 2)

- Implement actual HTTP proxying to backend services
- Add cold start orchestration with external task runners
- Implement janitor background tasks for service lifecycle management
- Add health checking and service monitoring
- Enhance error handling and logging
