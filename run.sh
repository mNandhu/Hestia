#!/usr/bin/env bash

docker build -t hestia-app .
docker run --rm -p 6173:80 hestia-app
