#!/bin/bash

sudo apt update
sudo apt install -y git docker.io docker-compose tmux
wget -qO- https://astral.sh/uv/install.sh | sh
sudo usermod -aG docker $USER

if [ ! -f .env ]; then
    echo "TZ=UTC" > .env
fi

. ~/.bashrc

tmux new-session -d -s httpserver
tmux send-keys -t httpserver 'cd www' C-m
tmux send-keys -t httpserver 'uv run python -m http.server 7999' C-m

(cd docker && docker-compose up -d)

tmux new-session -s dev
