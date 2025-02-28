#!/bin/bash
[ $EUID -eq 0 ] && echo "Don't run as root/sudo" && exit 1

# Environment and password setup
[ ! -f .env ] && echo "TZ=UTC" > .env
. .env
[ -z "$PASSWORD" ] && read -sp "Enter password for network share: " PASSWORD && \
    echo && echo "PASSWORD=$PASSWORD" >> .env

# System setup
sudo apt update && sudo apt install -y git docker.io docker-compose tmux samba samba-common-bin jq
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
DEPS="--with uvicorn --with jinja2 --with python-multipart --with requests --with python-dotenv"
tmux new-session -d -s fastapi "uv run $DEPS uvicorn app:app --reload --host 0.0.0.0 --port 7999"

(cd docker && docker-compose up -d)

