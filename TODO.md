# TODO

## Immediate Tasks

- [ ] **App Configuration** Migrate from `.env` to `.ini` based configuration.

  - [ ] **Database Configuration** Make the database URL configurable via `.ini` file.

- [ ] **Add Logging** Implement structured logging for better traceability.
  - [ ] **Log Format** Use JSON format for logs to facilitate parsing and analysis.
  - [ ] Replace all print statements with logger calls.

## RoadMap

- [ ] **Docker Integration:** Automatically detect and list other running Docker containers.
- [ ] **The Hearth Dashboard:** A simple web interface to view all managed "Adventurers" (services).
- [ ] **Health Monitoring (Falna):** Basic health checks to see if services are active or have fallen.
- [ ] **Service Controls:** Simple actions like start, stop, and restart from the UI.
- [ ] **Configuration Management:** A way to view the "Skills and Equipment" (environment variables and volumes) of each service.
