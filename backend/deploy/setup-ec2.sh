#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  Varalokam — EC2 Setup Script
#  Run this on a fresh Ubuntu 22.04+ EC2 instance
# ═══════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════"
echo "  🎨 Varalokam EC2 Setup"
echo "═══════════════════════════════════════════════════════"

# ── 1. System Update ─────────────────────────────────────
echo "[1/8] Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# ── 2. Install Python 3.12 ──────────────────────────────
echo "[2/8] Installing Python 3.12..."
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -y
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip

# ── 3. Install Redis ────────────────────────────────────
echo "[3/8] Installing Redis..."
sudo apt-get install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Verify Redis
redis-cli ping

# ── 4. Install Nginx ────────────────────────────────────
echo "[4/8] Installing Nginx..."
sudo apt-get install -y nginx
sudo systemctl enable nginx

# ── 5. Install Certbot (SSL) ────────────────────────────
echo "[5/8] Installing Certbot..."
sudo apt-get install -y certbot python3-certbot-nginx

# ── 6. Clone and Setup Application ──────────────────────
echo "[6/8] Setting up application..."
APP_DIR="/opt/varalokam"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# If you're using git:
# git clone https://github.com/YOUR_USERNAME/varalokam.git $APP_DIR/backend

# Create virtual environment
cd $APP_DIR/backend
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Copy .env
cp .env.example .env
echo "⚠️  Edit $APP_DIR/backend/.env with your actual values!"

# ── 7. Create Systemd Service ───────────────────────────
echo "[7/8] Creating systemd service..."
sudo tee /etc/systemd/system/varalokam.service > /dev/null << 'EOF'
[Unit]
Description=Varalokam Game Server
After=network.target redis-server.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/varalokam/backend
Environment=PATH=/opt/varalokam/backend/venv/bin:/usr/bin
ExecStart=/opt/varalokam/backend/venv/bin/python -m src.main
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable varalokam
sudo systemctl start varalokam

# ── 8. Configure Nginx ──────────────────────────────────
echo "[8/8] Configuring Nginx..."
sudo cp deploy/nginx.conf /etc/nginx/sites-available/varalokam
sudo ln -sf /etc/nginx/sites-available/varalokam /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Setup Complete!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo "  1. Edit /opt/varalokam/backend/.env"
echo "  2. Set up SSL: sudo certbot --nginx -d yourdomain.com"
echo "  3. Check status: sudo systemctl status varalokam"
echo "  4. View logs: sudo journalctl -u varalokam -f"
echo ""
echo "  Security Group rules needed:"
echo "  - SSH (22) from your IP"
echo "  - HTTP (80) from anywhere"
echo "  - HTTPS (443) from anywhere"
echo ""
