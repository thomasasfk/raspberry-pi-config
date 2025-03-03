#!/bin/bash
[ $EUID -eq 0 ] && echo "Don't run as root/sudo" && exit 1

# Environment and password setup
[ ! -f .env ] && echo "TZ=UTC" > .env
. .env
[ -z "$PASSWORD" ] && read -sp "Enter password for network share: " PASSWORD && \
    echo && echo "PASSWORD=$PASSWORD" >> .env

# Installations
for pkg in git docker.io docker-compose tmux samba samba-common-bin jq; do
    dpkg -l | grep -q "ii  $pkg" || sudo apt install -y $pkg
done

if ! command -v uv &> /dev/null; then
    wget -qO- https://astral.sh/uv/install.sh | sh
fi

if ! groups $USER | grep -q docker; then
    sudo usermod -aG docker $USER
    echo "Added $USER to docker group. You may need to log out and back in for this to take effect."
fi

# Samba setup
if ! grep -q "^\[homes\]" /etc/samba/smb.conf; then
    sudo tee -a /etc/samba/smb.conf > /dev/null << EOL
[homes]
   writable = yes
   create mask = 0644
   directory mask = 0755
EOL
fi
sudo systemctl restart smbd nmbd

# Service startup
DEPS="--with uvicorn --with jinja2 --with python-multipart --with requests --with python-dotenv"
tmux new-session -d -s fastapi "uv run $DEPS uvicorn app:app --reload --host 0.0.0.0 --port 7999"
(cd docker && docker-compose up -d)

# Setup startup services
FASTAPI_PATH="$(which uv) run $DEPS uvicorn app:app --reload --host 0.0.0.0 --port 7999"
CRON_CMD="@reboot tmux new-session -d -s fastapi \"$FASTAPI_PATH\""
DOCKER_CMD="@reboot cd $(pwd)/docker && $(which docker-compose) up -d"

# Generate new crontab with our entries, removing any old versions
CURRENT_CRONTAB=$(crontab -l 2>/dev/null || echo "")
NEW_CRONTAB=$(echo "$CURRENT_CRONTAB" | grep -v "tmux new-session -d -s fastapi" | grep -v "docker-compose up -d")
echo -e "$NEW_CRONTAB\n$CRON_CMD\n$DOCKER_CMD" | sort | uniq | crontab -