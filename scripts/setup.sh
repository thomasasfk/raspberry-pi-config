#!/bin/bash
[ $EUID -eq 0 ] && echo "Don't run as root/sudo" && exit 1

# Environment and password setup
[ ! -f .env ] && echo "TZ=UTC" > .env
. .env
[ -z "$PASSWORD" ] && read -sp "Enter password for network share: " PASSWORD && \
    echo && echo "PASSWORD=$PASSWORD" >> .env

# System setup
sudo apt update && sudo apt install -y git docker.io docker-compose tmux samba samba-common-bin
wget -qO- https://astral.sh/uv/install.sh | sh
sudo usermod -aG docker $USER && . ~/.bashrc

# Samba setup
if ! grep -q "^\[homes\]" /etc/samba/smb.conf; then
    sudo tee -a /etc/samba/smb.conf > /dev/null << EOL
[homes]
   writable = yes
   create mask = 0644
   directory mask = 0755
EOL
fi
echo -e "$PASSWORD\n$PASSWORD" | sudo smbpasswd -s -a $USER
sudo systemctl restart smbd nmbd

# Services startup
tmux has-session -t fastapi 2>/dev/null && tmux kill-session -t fastapi
tmux new-session -d -s fastapi "uv run --with uvicorn --with python-multipart uvicorn app:app --reload --host 0.0.0.0 --port 7999"

(cd docker && docker-compose up -d)

# (crontab -l 2>/dev/null | grep -v "gdrive-repo-sync.py"; echo "*/5 * * * * uv run ~/gdrive-repo-sync/gdrive-repo-sync.py") | crontab -

sudo apt install rclone
# rclone config (this will need done manually)

# tmux has-session -t dev 2>/dev/null && tmux attach -t dev || tmux new-session -s dev