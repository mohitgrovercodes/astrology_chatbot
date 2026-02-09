# 🚀 NakshatraAI - Deployment Guide

**Version:** 1.0.0  
**Last Updated:** February 9, 2026  
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Local Development](#local-development)
5. [Production Deployment](#production-deployment)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 4GB
- Disk: 10GB free space
- OS: Linux, macOS, or Windows with WSL2

**Recommended (Production):**
- CPU: 4+ cores
- RAM: 8GB+
- Disk: 20GB+ SSD
- OS: Ubuntu 20.04+ or similar

### Software Dependencies

**Required:**
- Docker 20.10+ and Docker Compose 2.0+
- OR Python 3.11+ with pip

**Optional:**
- Redis 7.0+ (for session management)
- MongoDB 5.0+ (for user profiles)
- Nginx (for reverse proxy)

### API Keys

**Required:**
- OpenAI API key (or Google Cloud credentials)

**Optional:**
- MongoDB connection string
- Redis password (for production)

---

## Environment Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd astro_chatbot
```

### 2. Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit configuration
nano .env  # or vim, code, etc.
```

### 3. Essential Environment Variables

**Minimum Configuration:**
```env
# LLM Provider
OPENAI_API_KEY=sk-your-openai-key-here
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# Authentication
INTERNAL_SERVICE_SECRET=generate-a-strong-random-secret-here
VALID_API_KEYS=your-api-key-1,your-api-key-2

# Database (optional - can use dummy)
USE_DUMMY_USER_DB=true
```

**Full Production Configuration:**
```env
# API Configuration
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Security
INTERNAL_SERVICE_SECRET=<64-char-random-string>
VALID_API_KEYS=<comma-separated-keys>

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<strong-password>
SESSION_EXPIRY_HOURS=24

# Database
MONGODB_URI=mongodb://username:password@host:27017/nakshatraai
USE_DUMMY_USER_DB=false

# LLM
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# CORS
ALLOWED_ORIGINS=https://yourdomain.com

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
```

### 4. Generate Secrets

```bash
# Generate strong secrets
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Docker Deployment

### Quick Start

```bash
# 1. Build and start services
docker-compose up -d

# 2. Verify deployment
docker-compose ps

# 3. Check logs
docker-compose logs -f api

# 4. Test health endpoint
curl http://localhost:8000/api/v1/health
```

### Service Architecture

```yaml
services:
  api:          # FastAPI application (port 8000)
  redis:        # Session storage (port 6379)
```

### Docker Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart specific service
docker-compose restart api

# View logs
docker-compose logs -f api
docker-compose logs -f redis

# Execute command in container
docker-compose exec api bash

# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d
```

### Volume Management

```bash
# View volumes
docker volume ls

# Backup data
docker run --rm -v astro_chatbot_data:/data -v $(pwd):/backup \
  ubuntu tar czf /backup/data-backup.tar.gz /data

# Restore data
docker run --rm -v astro_chatbot_data:/data -v $(pwd):/backup \
  ubuntu tar xzf /backup/data-backup.tar.gz -C /
```

---

## Local Development

### Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Redis (separate terminal)
redis-server

# 4. Start API server
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Development Workflow

```bash
# Run tests
pytest tests/

# Format code
black src/
ruff check src/

# Type checking
mypy src/

# Start with auto-reload
uvicorn src.api.main:app --reload
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] Environment variables configured
- [ ] Secrets generated and secured
- [ ] Database connection tested
- [ ] Redis connection tested
- [ ] SSL certificates obtained
- [ ] Domain DNS configured
- [ ] Firewall rules configured
- [ ] Monitoring tools ready

### Option 1: Docker Compose (Recommended)

**1. Production Configuration**

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  api:
    build: .
    container_name: nakshatraai-api-prod
    restart: always
    ports:
      - "8000:8000"
    env_file:
      - .env.production
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    networks:
      - nakshatraai-network
    depends_on:
      - redis
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G

  redis:
    image: redis:7-alpine
    container_name: nakshatraai-redis-prod
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - nakshatraai-network

  nginx:
    image: nginx:alpine
    container_name: nakshatraai-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    networks:
      - nakshatraai-network
    depends_on:
      - api

volumes:
  redis-data:

networks:
  nakshatraai-network:
    driver: bridge
```

**2. Nginx Configuration**

Create `nginx.conf`:

```nginx
upstream api {
    server api:8000;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**3. Deploy**

```bash
# Deploy to production
docker-compose -f docker-compose.prod.yml up -d

# Verify
curl https://yourdomain.com/api/v1/health
```

### Option 2: Systemd Service (Linux)

**1. Create Service File**

`/etc/systemd/system/nakshatraai.service`:

```ini
[Unit]
Description=NakshatraAI API Service
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/nakshatraai
Environment="PATH=/opt/nakshatraai/venv/bin"
ExecStart=/opt/nakshatraai/venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**2. Enable and Start**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable nakshatraai

# Start service
sudo systemctl start nakshatraai

# Check status
sudo systemctl status nakshatraai

# View logs
sudo journalctl -u nakshatraai -f
```

---

## Monitoring & Maintenance

### Health Checks

**Endpoint:** `GET /api/v1/health`

```bash
# Manual check
curl http://localhost:8000/api/v1/health

# Automated monitoring (cron)
*/5 * * * * curl -f http://localhost:8000/api/v1/health || systemctl restart nakshatraai
```

### Logging

**Log Locations:**
- Docker: `docker-compose logs -f api`
- Systemd: `journalctl -u nakshatraai -f`
- File: `logs/api.log`

**Log Rotation:**

Create `/etc/logrotate.d/nakshatraai`:

```
/opt/nakshatraai/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload nakshatraai
    endscript
}
```

### Backup Strategy

**Daily Backups:**

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR="/backups/nakshatraai"

# Backup Redis data
docker-compose exec -T redis redis-cli SAVE
docker cp nakshatraai-redis:/data/dump.rdb $BACKUP_DIR/redis-$DATE.rdb

# Backup vector database
tar czf $BACKUP_DIR/vectordb-$DATE.tar.gz data/vectordb/

# Backup logs
tar czf $BACKUP_DIR/logs-$DATE.tar.gz logs/

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "*.rdb" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

**Cron Schedule:**

```cron
0 2 * * * /opt/nakshatraai/backup.sh
```

### Performance Monitoring

**Metrics to Track:**
- Response times (p50, p95, p99)
- Request rate
- Error rate
- Redis memory usage
- CPU and memory usage

**Tools:**
- Prometheus + Grafana (recommended)
- Docker stats: `docker stats nakshatraai-api`
- System monitoring: `htop`, `iotop`

---

## Troubleshooting

### Common Issues

#### 1. Container Won't Start

```bash
# Check logs
docker-compose logs api

# Common causes:
# - Missing environment variables
# - Port already in use
# - Invalid configuration

# Solution:
docker-compose down
docker-compose up -d
```

#### 2. Redis Connection Failed

```bash
# Check Redis status
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping

# Restart Redis
docker-compose restart redis
```

#### 3. High Memory Usage

```bash
# Check memory usage
docker stats nakshatraai-api

# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL

# Restart with memory limit
docker-compose up -d --force-recreate
```

#### 4. Slow Response Times

**Diagnosis:**
```bash
# Check logs for slow queries
docker-compose logs api | grep "processing_time"

# Monitor Redis
docker-compose exec redis redis-cli --latency

# Check system resources
docker stats
```

**Solutions:**
- Increase worker count
- Add response caching
- Optimize database queries
- Scale horizontally

### Emergency Procedures

**Complete System Reset:**

```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: deletes data)
docker volume rm astro_chatbot_redis-data

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d
```

**Rollback Deployment:**

```bash
# Stop current version
docker-compose down

# Checkout previous version
git checkout <previous-commit>

# Rebuild and deploy
docker-compose build
docker-compose up -d
```

---

## Security Best Practices

### 1. Environment Variables

- ✅ Never commit `.env` to git
- ✅ Use strong, random secrets (min 32 chars)
- ✅ Rotate secrets regularly
- ✅ Use different secrets for dev/staging/prod

### 2. Network Security

```bash
# Firewall rules (ufw example)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 8000/tcp   # Block direct API access
sudo ufw enable
```

### 3. SSL/TLS

```bash
# Generate Let's Encrypt certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo certbot renew --dry-run
```

### 4. Access Control

- Use API keys for all requests
- Implement IP whitelisting for admin endpoints
- Enable rate limiting
- Monitor for suspicious activity

---

## Scaling Strategies

### Horizontal Scaling

**Load Balancer Configuration:**

```nginx
upstream api_cluster {
    least_conn;
    server api1:8000;
    server api2:8000;
    server api3:8000;
}
```

### Vertical Scaling

**Increase Resources:**

```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
```

### Database Scaling

**Redis Cluster:**
- Use Redis Cluster for high availability
- Implement read replicas
- Enable persistence

**MongoDB Sharding:**
- Shard by user_id
- Use replica sets
- Enable connection pooling

---

## Support & Resources

**Documentation:**
- API Reference: `docs/API_REFERENCE.md`
- Handoff Document: `docs/handoff_feb09_2026.md`
- Project Status: `docs/project_status_master.md`

**Logs:**
- Application: `logs/api.log`
- Docker: `docker-compose logs`
- System: `/var/log/syslog`

**Health Check:**
- Endpoint: `http://localhost:8000/api/v1/health`
- Docs: `http://localhost:8000/api/docs`

---

**Deployment Status:** ✅ Ready for Production

**Next Steps:**
1. Deploy to staging environment
2. Run integration tests
3. Monitor for 48 hours
4. Deploy to production
