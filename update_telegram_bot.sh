#!/bin/bash

# Pull the latest image for telegram_bot
echo "Pulling the latest image for telegram_bot..."
docker pull ghcr.io/fsoclldrug/giveaway_bot:master

# Check if the image pull was successful
if [ $? -ne 0 ]; then
    echo "Error pulling the Docker image"
    exit 1
fi

# Check if the image was updated
if [ "$(docker images -q ghcr.io/fsoclldrug/giveaway_bot:master)" != "$(docker ps -q -f ancestor=ghcr.io/fsoclldrug/giveaway_bot:master)" ]; then
    echo "New version found. Restarting telegram_bot container."

    # Stop and remove the old container
    docker-compose stop telegram_bot
    docker-compose rm -f telegram_bot

    # Start the new container
    docker-compose up -d telegram_bot

    # Remove unused Docker images
    echo "Removing old Docker images..."
    docker image prune -f
else
    echo "No new version found."
fi
