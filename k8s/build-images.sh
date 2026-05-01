#!/usr/bin/env bash
# Build every image used by the k8s manifests with docker's default builder so
# Docker Desktop's Kubernetes can use them directly (imagePullPolicy: IfNotPresent).
set -euo pipefail
cd "$(dirname "$0")/.."

docker build -f services/user-api/Dockerfile       -t yelp/user-api:local       ./backend
docker build -f services/owner-api/Dockerfile      -t yelp/owner-api:local      ./backend
docker build -f services/restaurant-api/Dockerfile -t yelp/restaurant-api:local ./backend
docker build -f services/review-api/Dockerfile     -t yelp/review-api:local     ./backend
docker build -f workers/review-worker/Dockerfile    -t yelp/review-worker:local    ./backend
docker build -f workers/restaurant-worker/Dockerfile -t yelp/restaurant-worker:local ./backend
docker build -f workers/user-worker/Dockerfile      -t yelp/user-worker:local      ./backend
docker build -f frontend/Dockerfile                -t yelp/frontend:local       ./frontend

echo "Done. Apply manifests with: kubectl apply -f k8s/"
