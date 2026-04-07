# Deployment Guide

## Server Requirements

- Ubuntu 22.04+ / Debian 12+
- Docker 24+ and Docker Compose v2
- 4GB RAM minimum, 8GB recommended
- 40GB SSD
- Static IP (87.228.29.55)

## Initial Setup

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2. Clone Repository

```bash
cd /opt
git clone https://github.com/your-org/rossi-siteguard-monitor.git siteguard
cd siteguard
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env  # Fill in all values
```

Key values to set:
- `SECRET_KEY` - generate with: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `LICENSE_SECRET_KEY` - generate another unique key
- `POSTGRES_PASSWORD` - strong database password
- `TELEGRAM_BOT_TOKEN` - from @BotFather
- `SMTP_*` - your email server settings

### 4. Start Services

```bash
cd siteguard-backend
docker compose up -d
```

### 5. Verify Deployment

```bash
# Check all services are running
docker compose ps

# Check API health
curl http://localhost/api/health

# Check logs
docker compose logs -f api
```

## SSL Setup (Let's Encrypt)

```bash
# Install certbot
apt install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d siteguard.app -d www.siteguard.app

# Uncomment HTTPS section in nginx.conf
# Update docker-compose.yml to mount certificates
```

## Monitoring

### Check service status
```bash
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 monitor
```

### Database backup
```bash
docker compose exec postgres pg_dump -U siteguard siteguard > backup_$(date +%Y%m%d).sql
```

### Restart services
```bash
docker compose restart api
docker compose restart monitor
```

## Updates

```bash
cd /opt/siteguard
git pull origin main
cd siteguard-backend
docker compose build
docker compose up -d --remove-orphans
docker system prune -f
```

## Automated Deployment

Push a version tag to trigger CI/CD:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The GitHub Actions workflow will:
1. Build Docker image
2. Push to registry
3. SSH to server and update
4. Build desktop and mobile apps
5. Create GitHub Release
6. Notify team via Telegram

## Troubleshooting

### API not responding
```bash
docker compose logs api
docker compose restart api
```

### Database connection issues
```bash
docker compose logs postgres
docker compose exec postgres pg_isready
```

### Redis issues
```bash
docker compose exec redis redis-cli ping
```

### Disk space
```bash
docker system prune -a  # Remove unused images
docker volume prune     # Remove unused volumes
```
