#!/bin/bash

sudo apt update
sudo apt install -y git docker.io docker-compose
sudo usermod -aG docker $USER

if [ ! -f .env ]; then
    echo "TZ=UTC" > .env
fi

cd docker && docker-compose up -d
