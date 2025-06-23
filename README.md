# Hestia 🔥

_The heart of your homelab._

Hestia is a personal server manager designed to be the simple, central hearth for all your self-hosted services. It provides a clean interface to discover, monitor, and manage your applications.

The self-hosted services can be anything, Docker containers, FastAPI apps, or just any simple command that can host a web server at a port.

Hestia aims to be the central hub where you can keep easily add services, Track of all your services, monitor their health, and manage them easily.

This project is currently in its early stages. The immediate goal is to create a stable, dockerized FastAPI application that can serve as the foundation for future features.

## Core Philosophy

In the world of self-hosting, every service is an adventurer. Hestia is the Goddess of the Hearth, providing the central home—the _Familia_—where these adventurers are managed, monitored, and supported.

- **Services** are **Adventurers**.
- **The Dashboard** is **The Hearth**.
- **Monitoring** is the **Falna** update.

## Current Features

- **Dockerized FastAPI Backend:** A solid foundation built for performance and scalability.
- **Simple API Stub:** A basic API endpoint (`/`) to confirm the server is running.

## Getting Started

This project is containerized with Docker, so you only need Docker and Docker Compose installed to get started.

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/mNandhu/hestia.git
    cd hestia
    ```

2.  **Build and run the container:**

    ```bash
    docker-compose up --build
    ```

3.  **Verify it's running:**
    Open your web browser and navigate to `http://localhost:6173/ping`. You should see a welcome message from the Hestia API:
    ```json
    {
      "message": "Welcome to the Hearth. Hestia is watching over you."
    }
    ```

## Roadmap

This is just the beginning. The plan is to build Hestia into a fully-featured server manager.

- [ ] **Docker Integration:** Automatically detect and list other running Docker containers.
- [ ] **The Hearth Dashboard:** A simple web interface to view all managed "Adventurers" (services).
- [ ] **Health Monitoring (Falna):** Basic health checks to see if services are active or have fallen.
- [ ] **Service Controls:** Simple actions like start, stop, and restart from the UI.
- [ ] **Configuration Management:** A way to view the "Skills and Equipment" (environment variables and volumes) of each service.

## Technology Stack

- **Backend:** FastAPI
- **Containerization:** Docker & Docker Compose
- **Language:** Python 3.12+

---

Feel free to start building, adventurer!
