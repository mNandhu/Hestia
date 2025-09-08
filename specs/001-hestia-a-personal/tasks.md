# Tasks: Hestia - Personal On-Demand Service Gateway

1. Create repo src structure (models/, services/, cli/, lib/)
2. Initialize pyproject.toml with Python 3.12 and dependencies (FastAPI, Uvicorn, Pydantic, SQLAlchemy, httpx)
3. Add dev dependencies: pytest, pytest-asyncio, respx, black, ruff
4. Add docker-compose.yml with hestia and semaphore services
5. Add Dockerfile (multi-stage) for hestia image
6. Define named volumes for SQLite and semaphore data
7. Bind-mount strategies/ and hestia_config.yml in compose for dev
8. Implement config loader for hestia_config.yml (Pydantic model)
9. Implement SQLite models (Service, Machine, RoutingRule, Activity, AuthKey) with SQLAlchemy
10. Implement persistence layer and migrations bootstrap (if needed)
11. Implement strategy plugin loader (importlib from strategies/)
12. Implement health/readiness checker (health endpoint or warm-up delay)
13. Implement startup policy (retry → fallback → error) with configuration
14. Implement request queue for cold services (FIFO, bounded, timeouts)
15. Implement gateway endpoint (POST /v1/requests) with transparent proxying via httpx
16. Implement service status endpoint (GET /v1/services/{id}/status)
17. Implement proactive start endpoint (POST /v1/services/{id}/start)
18. Add optional API key middleware; add dashboard auth (username/password) stub
19. Add structured logging with levels and event types per FR-013
20. Integrate with Semaphore API over internal network (http://semaphore:3000)
21. Add unit tests for config loader, models, strategy loader
22. Add integration tests for gateway→strategy→db flow (pytest-asyncio)
23. Add mocks for Semaphore (respx) and service health endpoints
24. Add CI (GitHub Actions) for lint (ruff) and format (black) on push to main
25. Add CI job to run pytest on Python 3.12
26. Write quickstart.md content and verify endpoints with curl examples
27. Document contracts in contracts/openapi.yaml and keep in sync
28. Create example strategies/ placeholder and sample hestia_config.yml
29. Add versioning (0.1.0) and CHANGELOG skeleton
30. Review and update docs; ensure spec alignment

[P] Parallelizable: 2,3,4,6,21,24,25,29
