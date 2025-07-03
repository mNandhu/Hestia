#!/usr/bin/env bash

docker build -t hestia-app .

# Check if .env file exists and handle accordingly
if [ -f .env ]; then
    echo "Found .env file, mounting it to the container..."
    docker run --rm -p 7777:80 --env-file .env -v "$(pwd)/.env:/app/.env" hestia-app
else
    docker run --rm -p 7777:80 hestia-app
fi 
