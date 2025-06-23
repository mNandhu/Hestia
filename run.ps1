# Build the Docker image for Hestia FastAPI app

docker build -t hestia-app .

# Run the container, mapping port 6173 on host to port 80 in container

docker run --rm -p 6173:80 hestia-app
