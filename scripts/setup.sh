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
# Ensure Samba services are enabled and restarted
sudo systemctl enable smbd nmbd
sudo systemctl restart smbd nmbd

# Create systemd service for FastAPI
FASTAPI_SERVICE="fastapi-app.service"
DEPS="--with uvicorn --with jinja2 --with python-multipart --with requests --with python-dotenv"
FASTAPI_PATH="$(which uv) run $DEPS uvicorn app:app --reload --host 0.0.0.0 --port 7999"
PROJECT_DIR="/home/$USER/raspberry-pi-config"

sudo tee /etc/systemd/system/$FASTAPI_SERVICE > /dev/null << EOL
[Unit]
Description=FastAPI Application
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$FASTAPI_PATH
Restart=always
RestartSec=5
Environment="PATH=$PATH"
EnvironmentFile=$PROJECT_DIR/.env

[Install]
WantedBy=multi-user.target
EOL

# Create systemd service for Docker Compose
DOCKER_COMPOSE_SERVICE="docker-compose-app.service"
DOCKER_DIR="/home/$USER/raspberry-pi-config/docker"

sudo tee /etc/systemd/system/$DOCKER_COMPOSE_SERVICE > /dev/null << EOL
[Unit]
Description=Docker Compose Application
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$DOCKER_DIR
ExecStart=$(which docker-compose) up
ExecStop=$(which docker-compose) down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

# Enable and start the services
sudo systemctl daemon-reload
sudo systemctl enable $FASTAPI_SERVICE
sudo systemctl enable $DOCKER_COMPOSE_SERVICE
sudo systemctl start $FASTAPI_SERVICE
sudo systemctl start $DOCKER_COMPOSE_SERVICE

echo "Services installed and started. Check status with:"
echo "  sudo systemctl status $FASTAPI_SERVICE"
echo "  sudo systemctl status $DOCKER_COMPOSE_SERVICE"
echo ""
echo "View logs with:"
echo "  sudo journalctl -u $FASTAPI_SERVICE -f"
echo "  sudo journalctl -u $DOCKER_COMPOSE_SERVICE -f"