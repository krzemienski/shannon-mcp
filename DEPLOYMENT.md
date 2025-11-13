# Shannon MCP Server - Production Deployment Guide

Complete guide for deploying Shannon MCP Server to production environments, including remote hosting, cloud platforms, and container deployments.

---

## Table of Contents

1. [Deployment Options Overview](#1-deployment-options-overview)
2. [Remote Server Deployment](#2-remote-server-deployment)
3. [Docker Deployment](#3-docker-deployment)
4. [Claude Desktop Integration](#4-claude-desktop-integration)
5. [Cloud Platform Deployments](#5-cloud-platform-deployments)
6. [Production Best Practices](#6-production-best-practices)
7. [Security](#7-security)
8. [CI/CD Pipeline](#8-cicd-pipeline)
9. [Monitoring and Observability](#9-monitoring-and-observability)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Deployment Options Overview

### Comparison Matrix

| Deployment Type | Complexity | Scalability | Cost | Best For |
|----------------|------------|-------------|------|----------|
| **Local** | Low | N/A | Free | Development, testing |
| **VPS/Cloud VM** | Medium | Medium | $5-50/mo | Small teams, production |
| **Docker** | Medium | High | Variable | CI/CD, reproducibility |
| **Kubernetes** | High | Very High | $50+/mo | Enterprise, multi-tenant |
| **Serverless** | Medium | Auto | Usage-based | Event-driven, cost optimization |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Claude Desktop Client                  │
│                  (Local or Remote)                       │
└───────────────────────┬─────────────────────────────────┘
                        │ MCP Protocol (stdio/SSE)
                        ▼
┌─────────────────────────────────────────────────────────┐
│               Shannon MCP Server                         │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐    │
│  │   Session    │ │    Agent     │ │  Checkpoint │    │
│  │   Manager    │ │   Manager    │ │   Manager   │    │
│  └──────────────┘ └──────────────┘ └─────────────┘    │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐    │
│  │   Binary     │ │   Analytics  │ │    Hooks    │    │
│  │   Manager    │ │    Engine    │ │  Framework  │    │
│  └──────────────┘ └──────────────┘ └─────────────┘    │
└───────────────────────┬─────────────────────────────────┘
                        │ Manages
                        ▼
┌─────────────────────────────────────────────────────────┐
│               Claude Code CLI Binary                     │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Remote Server Deployment

### 2.1 VPS/Cloud VM Setup

#### System Requirements

**Minimum Specifications:**
- CPU: 2 cores
- RAM: 2GB
- Disk: 20GB SSD
- Network: 100Mbps

**Recommended Specifications (Production):**
- CPU: 4 cores
- RAM: 4GB
- Disk: 50GB SSD (with monitoring)
- Network: 1Gbps
- OS: Ubuntu 22.04 LTS or higher

#### Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    git \
    build-essential \
    curl \
    wget \
    nginx \
    certbot \
    python3-certbot-nginx

# Create dedicated user
sudo useradd -m -s /bin/bash shannon
sudo usermod -aG sudo shannon

# Switch to shannon user
sudo su - shannon
```

#### Security Hardening

```bash
# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable

# Disable root login
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Install fail2ban for SSH protection
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Configure automatic security updates
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 2.2 Installation on Remote Server

```bash
# Clone repository
cd /home/shannon
git clone https://github.com/krzemienski/shannon-mcp.git
cd shannon-mcp

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Install dependencies
poetry install --no-dev

# Create configuration directory
mkdir -p ~/.shannon-mcp/{logs,storage,checkpoints,analytics}

# Create production configuration
cat > ~/.shannon-mcp/config.yaml << 'EOF'
# Shannon MCP Production Configuration

# Logging
logging:
  level: INFO
  format: json
  directory: /home/shannon/.shannon-mcp/logs
  max_size: 52428800  # 50MB
  backup_count: 10
  enable_sentry: true
  sentry_dsn: "${SENTRY_DSN}"

# Database
database:
  path: /home/shannon/.shannon-mcp/shannon.db
  pool_size: 10
  timeout: 60.0
  journal_mode: WAL
  synchronous: NORMAL

# Binary Manager
binary_manager:
  search_paths:
    - /usr/local/bin
    - /home/shannon/.local/bin
  nvm_check: true
  update_check_interval: 86400

# Session Manager
session_manager:
  max_concurrent_sessions: 20
  session_timeout: 7200  # 2 hours
  buffer_size: 2097152   # 2MB
  stream_chunk_size: 16384
  enable_metrics: true

# Agent System
agent_manager:
  enable_default_agents: true
  max_concurrent_tasks: 50
  task_timeout: 600
  collaboration_enabled: true
  performance_tracking: true

# Checkpoint System
checkpoint:
  storage_path: /home/shannon/.shannon-mcp/checkpoints
  compression_enabled: true
  compression_level: 6
  auto_checkpoint_interval: 600
  max_checkpoints: 500
  cleanup_age_days: 90

# Analytics
analytics:
  enabled: true
  metrics_path: /home/shannon/.shannon-mcp/analytics
  retention_days: 180
  export_formats: ["json", "csv"]
  aggregation_interval: 3600

# MCP Protocol
mcp:
  transport: stdio
  connection_timeout: 60
  request_timeout: 600
  max_message_size: 104857600  # 100MB
  enable_compression: true
EOF

# Set environment variables
cat >> ~/.bashrc << 'EOF'

# Shannon MCP Environment Variables
export SHANNON_CONFIG_PATH=/home/shannon/.shannon-mcp/config.yaml
export SHANNON_LOG_LEVEL=INFO
export SHANNON_DEBUG=false
export SENTRY_DSN="${SENTRY_DSN:-}"
EOF

source ~/.bashrc
```

### 2.3 Process Management with systemd

Create systemd service for automatic startup and management:

```bash
# Create systemd service file
sudo tee /etc/systemd/system/shannon-mcp.service << 'EOF'
[Unit]
Description=Shannon MCP Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=shannon
Group=shannon
WorkingDirectory=/home/shannon/shannon-mcp
Environment="PATH=/home/shannon/.local/bin:/usr/local/bin:/usr/bin"
Environment="SHANNON_CONFIG_PATH=/home/shannon/.shannon-mcp/config.yaml"
ExecStart=/home/shannon/shannon-mcp/.venv/bin/shannon-mcp

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Resource limits
LimitNOFILE=65535
LimitNPROC=4096

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/shannon/.shannon-mcp

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=shannon-mcp

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable shannon-mcp
sudo systemctl start shannon-mcp

# Check status
sudo systemctl status shannon-mcp

# View logs
sudo journalctl -u shannon-mcp -f
```

#### Systemd Service Management Commands

```bash
# Start service
sudo systemctl start shannon-mcp

# Stop service
sudo systemctl stop shannon-mcp

# Restart service
sudo systemctl restart shannon-mcp

# View status
sudo systemctl status shannon-mcp

# View logs (last 100 lines)
sudo journalctl -u shannon-mcp -n 100

# Follow logs in real-time
sudo journalctl -u shannon-mcp -f

# View logs from today
sudo journalctl -u shannon-mcp --since today

# Check if service is enabled
sudo systemctl is-enabled shannon-mcp

# Disable service
sudo systemctl disable shannon-mcp
```

### 2.4 Log Rotation

Configure log rotation to prevent disk space issues:

```bash
# Create logrotate configuration
sudo tee /etc/logrotate.d/shannon-mcp << 'EOF'
/home/shannon/.shannon-mcp/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 shannon shannon
    sharedscripts
    postrotate
        systemctl reload shannon-mcp > /dev/null 2>&1 || true
    endscript
}
EOF

# Test logrotate configuration
sudo logrotate -d /etc/logrotate.d/shannon-mcp

# Force log rotation (for testing)
sudo logrotate -f /etc/logrotate.d/shannon-mcp
```

### 2.5 Networking and Reverse Proxy

#### nginx Configuration (for SSE transport)

If using SSE transport instead of stdio:

```bash
# Create nginx configuration
sudo tee /etc/nginx/sites-available/shannon-mcp << 'EOF'
# Upstream to Shannon MCP Server
upstream shannon_mcp {
    server 127.0.0.1:8080;
    keepalive 64;
}

# Rate limiting
limit_req_zone $binary_remote_addr zone=shannon_limit:10m rate=10r/s;
limit_conn_zone $binary_remote_addr zone=shannon_conn:10m;

server {
    listen 80;
    server_name mcp.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name mcp.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/mcp.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/shannon-mcp-access.log;
    error_log /var/log/nginx/shannon-mcp-error.log;

    # Rate limiting
    limit_req zone=shannon_limit burst=20 nodelay;
    limit_conn shannon_conn 10;

    # Client body size limit
    client_max_body_size 100M;

    location / {
        proxy_pass http://shannon_mcp;
        proxy_http_version 1.1;

        # WebSocket/SSE support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;

        # Buffering
        proxy_buffering off;
        proxy_cache off;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://shannon_mcp/health;
        access_log off;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/shannon-mcp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Obtain SSL certificate
sudo certbot --nginx -d mcp.yourdomain.com

# Auto-renewal is configured by certbot
# Test renewal: sudo certbot renew --dry-run
```

---

## 3. Docker Deployment

### 3.1 Dockerfile

Create a production-ready multi-stage Dockerfile:

```dockerfile
# Filename: Dockerfile
# Multi-stage build for Shannon MCP Server

# Stage 1: Builder
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Stage 2: Runtime
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash shannon

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=shannon:shannon . .

# Create necessary directories
RUN mkdir -p /home/shannon/.shannon-mcp/{logs,storage,checkpoints,analytics} \
    && chown -R shannon:shannon /home/shannon/.shannon-mcp

# Switch to non-root user
USER shannon

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SHANNON_CONFIG_PATH=/home/shannon/.shannon-mcp/config.yaml \
    PATH="/home/shannon/.local/bin:$PATH"

# Expose port (if using SSE transport)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Entry point
ENTRYPOINT ["python", "-m", "shannon_mcp.server"]
```

### 3.2 docker-compose.yml

Complete Docker Compose setup with all services:

```yaml
# Filename: docker-compose.yml
version: '3.8'

services:
  shannon-mcp:
    build:
      context: .
      dockerfile: Dockerfile
      cache_from:
        - shannon-mcp:latest
    image: shannon-mcp:latest
    container_name: shannon-mcp
    restart: unless-stopped

    # Environment variables
    environment:
      - SHANNON_CONFIG_PATH=/config/config.yaml
      - SHANNON_LOG_LEVEL=${LOG_LEVEL:-INFO}
      - SHANNON_DEBUG=${DEBUG:-false}
      - SENTRY_DSN=${SENTRY_DSN:-}
      - PYTHONUNBUFFERED=1

    # Volumes
    volumes:
      - ./config.yaml:/config/config.yaml:ro
      - shannon-data:/home/shannon/.shannon-mcp
      - ./logs:/home/shannon/.shannon-mcp/logs
      - /var/run/docker.sock:/var/run/docker.sock:ro  # For container management (optional)

    # Networking
    ports:
      - "8080:8080"  # SSE transport (if enabled)

    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M

    # Logging
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

    # Health check
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

    # Dependencies (if using external services)
    # depends_on:
    #   - redis
    #   - postgres

  # Optional: Redis for caching
  redis:
    image: redis:7-alpine
    container_name: shannon-redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  # Optional: Prometheus for metrics
  prometheus:
    image: prom/prometheus:latest
    container_name: shannon-prometheus
    restart: unless-stopped
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'

  # Optional: Grafana for visualization
  grafana:
    image: grafana/grafana:latest
    container_name: shannon-grafana
    restart: unless-stopped
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./grafana/datasources:/etc/grafana/provisioning/datasources:ro
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

volumes:
  shannon-data:
    driver: local
  redis-data:
    driver: local
  prometheus-data:
    driver: local
  grafana-data:
    driver: local

networks:
  default:
    name: shannon-network
    driver: bridge
```

### 3.3 Docker Deployment Commands

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f shannon-mcp

# Stop services
docker-compose down

# Restart service
docker-compose restart shannon-mcp

# Execute command in container
docker-compose exec shannon-mcp bash

# View resource usage
docker stats shannon-mcp

# Clean up everything
docker-compose down -v  # Warning: Deletes volumes!
```

### 3.4 Environment Configuration

Create `.env` file for environment variables:

```bash
# Filename: .env
# Shannon MCP Docker Environment

# Application
LOG_LEVEL=INFO
DEBUG=false
SHANNON_VERSION=0.1.0

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project

# Grafana
GRAFANA_PASSWORD=secure_password_here

# Resource Limits
SHANNON_MAX_SESSIONS=50
SHANNON_MAX_MEMORY=2G

# Storage
SHANNON_RETENTION_DAYS=90
```

### 3.5 Container Registry

#### Build and Push to Docker Hub

```bash
# Login to Docker Hub
docker login

# Tag image
docker tag shannon-mcp:latest yourusername/shannon-mcp:latest
docker tag shannon-mcp:latest yourusername/shannon-mcp:0.1.0

# Push image
docker push yourusername/shannon-mcp:latest
docker push yourusername/shannon-mcp:0.1.0

# Pull image on another system
docker pull yourusername/shannon-mcp:latest
```

#### Build and Push to GitHub Container Registry

```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Tag image
docker tag shannon-mcp:latest ghcr.io/yourusername/shannon-mcp:latest
docker tag shannon-mcp:latest ghcr.io/yourusername/shannon-mcp:0.1.0

# Push image
docker push ghcr.io/yourusername/shannon-mcp:latest
docker push ghcr.io/yourusername/shannon-mcp:0.1.0
```

---

## 4. Claude Desktop Integration

### 4.1 Local Configuration

Configure Claude Desktop to use locally installed Shannon MCP:

#### Configuration File Location

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### Local stdio Configuration

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "/home/user/shannon-mcp/.venv/bin/shannon-mcp",
      "args": [],
      "env": {
        "SHANNON_CONFIG_PATH": "/home/user/.shannon-mcp/config.yaml",
        "SHANNON_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

#### Local with Poetry

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "poetry",
      "args": ["run", "shannon-mcp"],
      "cwd": "/home/user/shannon-mcp",
      "env": {
        "SHANNON_CONFIG_PATH": "/home/user/.shannon-mcp/config.yaml"
      }
    }
  }
}
```

### 4.2 Remote Configuration

Connect Claude Desktop to remote Shannon MCP server.

#### SSH Tunnel Method

Create SSH tunnel to remote server:

```bash
# Create SSH tunnel (run on local machine)
ssh -L 8080:localhost:8080 user@remote-server.com -N -f

# Or with autossh for automatic reconnection
autossh -M 0 -L 8080:localhost:8080 user@remote-server.com -N
```

Configure Claude Desktop to use tunneled connection:

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "ssh",
      "args": [
        "-T",
        "user@remote-server.com",
        "/home/shannon/shannon-mcp/.venv/bin/shannon-mcp"
      ],
      "env": {
        "SHANNON_CONFIG_PATH": "/home/shannon/.shannon-mcp/config.yaml"
      }
    }
  }
}
```

#### Secure Tunneling with systemd

Create systemd service for persistent SSH tunnel:

```bash
# Create systemd user service
mkdir -p ~/.config/systemd/user/

cat > ~/.config/systemd/user/shannon-tunnel.service << 'EOF'
[Unit]
Description=Shannon MCP SSH Tunnel
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/ssh -NT -L 8080:localhost:8080 shannon@remote-server.com
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

# Enable and start tunnel
systemctl --user enable shannon-tunnel
systemctl --user start shannon-tunnel
systemctl --user status shannon-tunnel
```

#### Authentication Setup

For passwordless SSH access:

```bash
# Generate SSH key (if not exists)
ssh-keygen -t ed25519 -C "shannon-mcp-tunnel"

# Copy public key to remote server
ssh-copy-id shannon@remote-server.com

# Test connection
ssh shannon@remote-server.com "echo 'Connection successful'"
```

---

## 5. Cloud Platform Deployments

### 5.1 AWS Deployment

#### EC2 Instance Setup

```bash
# Launch Ubuntu 22.04 instance
# Instance type: t3.medium (2 vCPU, 4GB RAM)
# Storage: 30GB gp3 SSD

# Connect to instance
ssh -i shannon-key.pem ubuntu@ec2-instance-ip

# Follow remote server deployment steps from Section 2
```

#### EC2 User Data Script

```bash
#!/bin/bash
# AWS EC2 User Data Script for Shannon MCP

# Update system
apt-get update && apt-get upgrade -y

# Install dependencies
apt-get install -y python3.11 python3.11-venv git curl

# Create shannon user
useradd -m -s /bin/bash shannon

# Switch to shannon user and install
sudo -u shannon bash << 'EOFSHANNON'
cd /home/shannon
git clone https://github.com/krzemienski/shannon-mcp.git
cd shannon-mcp

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="/home/shannon/.local/bin:$PATH"

# Install dependencies
poetry install --no-dev

# Create config
mkdir -p ~/.shannon-mcp
cat > ~/.shannon-mcp/config.yaml << 'EOFCONFIG'
logging:
  level: INFO
session_manager:
  max_concurrent_sessions: 20
EOFCONFIG
EOFSHANNON

# Create systemd service (same as Section 2.3)
# ... systemd configuration ...

# Start service
systemctl enable shannon-mcp
systemctl start shannon-mcp
```

#### ECS/Fargate Deployment

Create ECS task definition:

```json
{
  "family": "shannon-mcp",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "shannon-mcp",
      "image": "yourusername/shannon-mcp:latest",
      "essential": true,
      "environment": [
        {"name": "SHANNON_LOG_LEVEL", "value": "INFO"},
        {"name": "SHANNON_DEBUG", "value": "false"}
      ],
      "secrets": [
        {
          "name": "SENTRY_DSN",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:shannon/sentry-dsn"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/shannon-mcp",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "mountPoints": [
        {
          "sourceVolume": "shannon-data",
          "containerPath": "/home/shannon/.shannon-mcp"
        }
      ]
    }
  ],
  "volumes": [
    {
      "name": "shannon-data",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-12345678",
        "transitEncryption": "ENABLED"
      }
    }
  ]
}
```

Deploy to ECS:

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create ECS service
aws ecs create-service \
    --cluster shannon-cluster \
    --service-name shannon-mcp \
    --task-definition shannon-mcp \
    --desired-count 2 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-12345],assignPublicIp=ENABLED}"
```

#### Lambda for Serverless

Create Lambda handler:

```python
# lambda_handler.py
import json
import asyncio
from shannon_mcp.server import ShannonMCPServer

def lambda_handler(event, context):
    """AWS Lambda handler for Shannon MCP."""

    # Parse MCP request from event
    mcp_request = json.loads(event['body'])

    # Create server instance
    server = ShannonMCPServer()

    # Process request
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(server.process_request(mcp_request))

    return {
        'statusCode': 200,
        'body': json.dumps(result),
        'headers': {
            'Content-Type': 'application/json'
        }
    }
```

### 5.2 Google Cloud Platform

#### Compute Engine

```bash
# Create VM instance
gcloud compute instances create shannon-mcp \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --machine-type=e2-medium \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-ssd \
    --tags=http-server,https-server \
    --metadata-from-file startup-script=startup.sh

# SSH into instance
gcloud compute ssh shannon-mcp

# Follow remote server deployment steps
```

#### Cloud Run

Create Cloud Run service:

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT_ID/shannon-mcp

# Deploy to Cloud Run
gcloud run deploy shannon-mcp \
    --image gcr.io/PROJECT_ID/shannon-mcp \
    --platform managed \
    --region us-central1 \
    --memory 2Gi \
    --cpu 2 \
    --timeout 600 \
    --concurrency 80 \
    --max-instances 10 \
    --set-env-vars SHANNON_LOG_LEVEL=INFO \
    --set-secrets SENTRY_DSN=sentry-dsn:latest \
    --allow-unauthenticated
```

### 5.3 Azure

#### Virtual Machine

```bash
# Create VM
az vm create \
    --resource-group shannon-rg \
    --name shannon-mcp-vm \
    --image UbuntuLTS \
    --size Standard_B2s \
    --admin-username shannon \
    --generate-ssh-keys \
    --custom-data cloud-init.txt

# Open ports
az vm open-port --resource-group shannon-rg --name shannon-mcp-vm --port 80
az vm open-port --resource-group shannon-rg --name shannon-mcp-vm --port 443

# Connect
az vm ssh shannon-mcp-vm
```

#### Container Instances

```bash
# Create container instance
az container create \
    --resource-group shannon-rg \
    --name shannon-mcp \
    --image yourusername/shannon-mcp:latest \
    --dns-name-label shannon-mcp \
    --ports 8080 \
    --cpu 2 \
    --memory 4 \
    --environment-variables \
        SHANNON_LOG_LEVEL=INFO \
    --secure-environment-variables \
        SENTRY_DSN=$SENTRY_DSN \
    --restart-policy Always
```

---

## 6. Production Best Practices

### 6.1 Environment Variables and Secrets Management

#### Using AWS Secrets Manager

```python
# secrets_manager.py
import boto3
import json

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name='us-east-1'
    )

    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage in configuration
secrets = get_secret('shannon-mcp/production')
sentry_dsn = secrets['SENTRY_DSN']
api_key = secrets['API_KEY']
```

#### Using HashiCorp Vault

```bash
# Store secrets
vault kv put secret/shannon-mcp \
    sentry_dsn="https://..." \
    api_key="sk-..."

# Retrieve in application
export VAULT_ADDR='https://vault.company.com'
export VAULT_TOKEN='s.xxxxxxxxxxxx'

# Python retrieval
import hvac

client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
secrets = client.secrets.kv.v2.read_secret_version(path='shannon-mcp')
```

### 6.2 Database Backup Strategies

#### Automated SQLite Backups

```bash
#!/bin/bash
# backup-shannon.sh - Automated backup script

BACKUP_DIR="/backups/shannon-mcp"
DB_PATH="/home/shannon/.shannon-mcp/shannon.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create backup with timestamp
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/shannon_$TIMESTAMP.db'"

# Compress backup
gzip "$BACKUP_DIR/shannon_$TIMESTAMP.db"

# Upload to S3 (optional)
aws s3 cp "$BACKUP_DIR/shannon_$TIMESTAMP.db.gz" \
    s3://shannon-backups/databases/ \
    --storage-class STANDARD_IA

# Clean old backups
find "$BACKUP_DIR" -name "shannon_*.db.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: shannon_$TIMESTAMP.db.gz"
```

Schedule with cron:

```bash
# Add to crontab
crontab -e

# Backup every 6 hours
0 */6 * * * /home/shannon/scripts/backup-shannon.sh >> /var/log/shannon-backup.log 2>&1
```

### 6.3 Monitoring and Alerting

#### Prometheus Metrics Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'shannon-mcp'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

rule_files:
  - 'shannon_alerts.yml'
```

```yaml
# shannon_alerts.yml
groups:
  - name: shannon_alerts
    interval: 30s
    rules:
      - alert: HighSessionCount
        expr: shannon_active_sessions > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High session count"
          description: "Active sessions: {{ $value }}"

      - alert: HighErrorRate
        expr: rate(shannon_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate: {{ $value }}/s"

      - alert: ServiceDown
        expr: up{job="shannon-mcp"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Shannon MCP service is down"
```

### 6.4 Log Aggregation

#### ELK Stack Integration

```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /home/shannon/.shannon-mcp/logs/*.log
    fields:
      service: shannon-mcp
      environment: production
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["localhost:9200"]
  index: "shannon-mcp-%{+yyyy.MM.dd}"

setup.kibana:
  host: "localhost:5601"

logging.level: info
logging.to_files: true
```

### 6.5 Disaster Recovery

#### Disaster Recovery Plan

```bash
#!/bin/bash
# disaster-recovery.sh - Full system recovery script

# 1. Restore database from backup
aws s3 cp s3://shannon-backups/databases/shannon_latest.db.gz /tmp/
gunzip /tmp/shannon_latest.db.gz
cp /tmp/shannon_latest.db /home/shannon/.shannon-mcp/shannon.db

# 2. Restore configuration
aws s3 cp s3://shannon-backups/config/config.yaml /home/shannon/.shannon-mcp/

# 3. Restore checkpoints
aws s3 sync s3://shannon-backups/checkpoints/ /home/shannon/.shannon-mcp/checkpoints/

# 4. Verify data integrity
sqlite3 /home/shannon/.shannon-mcp/shannon.db "PRAGMA integrity_check;"

# 5. Restart service
systemctl restart shannon-mcp

# 6. Verify service health
sleep 10
systemctl status shannon-mcp

echo "Disaster recovery completed"
```

### 6.6 Scaling Strategies

#### Horizontal Scaling with Load Balancer

```nginx
# nginx load balancer configuration
upstream shannon_backend {
    least_conn;  # Use least connections algorithm

    server shannon-mcp-1:8080 max_fails=3 fail_timeout=30s;
    server shannon-mcp-2:8080 max_fails=3 fail_timeout=30s;
    server shannon-mcp-3:8080 max_fails=3 fail_timeout=30s;

    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name mcp.yourdomain.com;

    # SSL configuration...

    location / {
        proxy_pass http://shannon_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        # Session affinity (sticky sessions)
        ip_hash;
    }
}
```

---

## 7. Security

### 7.1 Authentication and Authorization

#### API Key Authentication

```python
# auth_middleware.py
from functools import wraps
from typing import Optional
import hmac
import hashlib

class APIKeyAuth:
    """API key authentication middleware."""

    def __init__(self, valid_keys: list):
        self.valid_keys = set(valid_keys)

    def verify_key(self, api_key: str) -> bool:
        """Verify API key using constant-time comparison."""
        for valid_key in self.valid_keys:
            if hmac.compare_digest(api_key, valid_key):
                return True
        return False

    def authenticate(self, request):
        """Authenticate request."""
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            raise AuthenticationError("Missing API key")

        if not self.verify_key(api_key):
            raise AuthenticationError("Invalid API key")

        return True
```

Configure in Claude Desktop:

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "X-API-Key: your-secret-api-key",
        "-H", "Content-Type: application/json",
        "https://mcp.yourdomain.com/mcp"
      ]
    }
  }
}
```

### 7.2 Network Security

#### iptables Configuration

```bash
# Firewall rules for Shannon MCP server

# Flush existing rules
sudo iptables -F

# Default policies
sudo iptables -P INPUT DROP
sudo iptables -P FORWARD DROP
sudo iptables -P OUTPUT ACCEPT

# Allow loopback
sudo iptables -A INPUT -i lo -j ACCEPT

# Allow established connections
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow SSH (from specific IPs only)
sudo iptables -A INPUT -p tcp --dport 22 -s 203.0.113.0/24 -j ACCEPT

# Allow HTTP/HTTPS
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Rate limiting for SSH
sudo iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --set
sudo iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --update --seconds 60 --hitcount 4 -j DROP

# Save rules
sudo iptables-save > /etc/iptables/rules.v4
```

### 7.3 Data Encryption

#### Encryption at Rest

```python
# encryption.py
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64
import os

class DataEncryption:
    """Handle data encryption at rest."""

    def __init__(self, master_key: str):
        """Initialize with master key."""
        self.fernet = self._derive_key(master_key)

    def _derive_key(self, password: str) -> Fernet:
        """Derive encryption key from password."""
        salt = os.getenv('SHANNON_ENCRYPTION_SALT', 'default-salt').encode()
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data."""
        return self.fernet.encrypt(data)

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt data."""
        return self.fernet.decrypt(encrypted_data)
```

### 7.4 Security Updates

#### Automated Security Patching

```bash
#!/bin/bash
# auto-update.sh - Automated security updates

# Update package lists
apt-get update

# Install security updates only
apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

# Check if restart required
if [ -f /var/run/reboot-required ]; then
    echo "Reboot required"
    # Notify admin
    echo "Security updates installed, reboot required" | mail -s "Shannon MCP Update" admin@example.com
fi

# Update Python dependencies
cd /home/shannon/shannon-mcp
poetry update --dry-run > /tmp/poetry-updates.txt
if [ -s /tmp/poetry-updates.txt ]; then
    poetry update
    systemctl restart shannon-mcp
fi
```

---

## 8. CI/CD Pipeline

### 8.1 GitHub Actions

Complete CI/CD workflow:

```yaml
# .github/workflows/deploy.yml
name: Deploy Shannon MCP

on:
  push:
    branches: [main, production]
    tags: ['v*']
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: poetry install

      - name: Run linting
        run: |
          poetry run black --check .
          poetry run flake8
          poetry run mypy src/

      - name: Run tests
        run: |
          poetry run pytest --cov=src --cov-report=xml --cov-report=term

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name != 'pull_request'

    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: staging

    steps:
      - name: Deploy to staging
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.STAGING_HOST }}
          username: ${{ secrets.STAGING_USER }}
          key: ${{ secrets.STAGING_SSH_KEY }}
          script: |
            cd /home/shannon/shannon-mcp
            docker-compose pull
            docker-compose up -d
            docker-compose exec -T shannon-mcp python -c "import sys; sys.exit(0)"

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    environment: production

    steps:
      - name: Deploy to production
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.PRODUCTION_HOST }}
          username: ${{ secrets.PRODUCTION_USER }}
          key: ${{ secrets.PRODUCTION_SSH_KEY }}
          script: |
            cd /home/shannon/shannon-mcp
            docker-compose pull
            docker-compose up -d --no-deps shannon-mcp

            # Health check
            sleep 10
            docker-compose exec -T shannon-mcp python -c "import sys; sys.exit(0)"

            # Run database migrations if needed
            # docker-compose exec -T shannon-mcp python migrate.py

      - name: Notify deployment
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Deployment to production completed'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
        if: always()
```

### 8.2 GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

variables:
  DOCKER_DRIVER: overlay2
  IMAGE_TAG: $CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG

test:
  stage: test
  image: python:3.11
  before_script:
    - pip install poetry
    - poetry install
  script:
    - poetry run black --check .
    - poetry run flake8
    - poetry run pytest --cov=src --cov-report=xml --cov-report=term
  coverage: '/TOTAL.*\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build -t $IMAGE_TAG .
    - docker push $IMAGE_TAG
  only:
    - main
    - tags

deploy:staging:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$STAGING_SSH_KEY" | tr -d '\r' | ssh-add -
  script:
    - ssh -o StrictHostKeyChecking=no $STAGING_USER@$STAGING_HOST "
        cd /home/shannon/shannon-mcp &&
        docker-compose pull &&
        docker-compose up -d
      "
  environment:
    name: staging
    url: https://staging-mcp.yourdomain.com
  only:
    - main

deploy:production:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$PRODUCTION_SSH_KEY" | tr -d '\r' | ssh-add -
  script:
    - ssh -o StrictHostKeyChecking=no $PRODUCTION_USER@$PRODUCTION_HOST "
        cd /home/shannon/shannon-mcp &&
        docker-compose pull &&
        docker-compose up -d --no-deps shannon-mcp
      "
  environment:
    name: production
    url: https://mcp.yourdomain.com
  when: manual
  only:
    - tags
```

---

## 9. Monitoring and Observability

### 9.1 Health Checks

Implement comprehensive health check endpoint:

```python
# health.py
from typing import Dict, Any
from datetime import datetime
import psutil
import aiosqlite

async def health_check() -> Dict[str, Any]:
    """Comprehensive health check."""

    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    # Check database
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("SELECT 1")
            health["checks"]["database"] = {"status": "ok"}
    except Exception as e:
        health["checks"]["database"] = {"status": "error", "error": str(e)}
        health["status"] = "unhealthy"

    # Check disk space
    disk = psutil.disk_usage('/')
    health["checks"]["disk"] = {
        "status": "ok" if disk.percent < 90 else "warning",
        "used_percent": disk.percent,
        "free_gb": disk.free / (1024**3)
    }

    # Check memory
    memory = psutil.virtual_memory()
    health["checks"]["memory"] = {
        "status": "ok" if memory.percent < 90 else "warning",
        "used_percent": memory.percent,
        "available_gb": memory.available / (1024**3)
    }

    # Check CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    health["checks"]["cpu"] = {
        "status": "ok" if cpu_percent < 90 else "warning",
        "usage_percent": cpu_percent
    }

    return health
```

### 9.2 Metrics Collection

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

# Create registry
registry = CollectorRegistry()

# Define metrics
requests_total = Counter(
    'shannon_requests_total',
    'Total number of requests',
    ['method', 'status'],
    registry=registry
)

request_duration = Histogram(
    'shannon_request_duration_seconds',
    'Request duration in seconds',
    ['method'],
    registry=registry
)

active_sessions = Gauge(
    'shannon_active_sessions',
    'Number of active sessions',
    registry=registry
)

errors_total = Counter(
    'shannon_errors_total',
    'Total number of errors',
    ['type'],
    registry=registry
)
```

### 9.3 Logging Best Practices

```python
# structured_logging.py
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)

logger = structlog.get_logger()

# Usage
logger.info(
    "session_created",
    session_id="sess_123",
    model="claude-3-sonnet",
    duration_ms=450
)
```

### 9.4 Alert Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'team-slack'
  routes:
    - match:
        severity: critical
      receiver: 'team-pagerduty'
      continue: true

receivers:
  - name: 'team-slack'
    slack_configs:
      - channel: '#shannon-mcp-alerts'
        title: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: 'team-pagerduty'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
```

---

## 10. Troubleshooting

### 10.1 Common Issues

#### Service Won't Start

```bash
# Check service status
sudo systemctl status shannon-mcp

# View recent logs
sudo journalctl -u shannon-mcp -n 100 --no-pager

# Check configuration
/home/shannon/shannon-mcp/.venv/bin/python -m shannon_mcp.server --check-config

# Verify binary
which shannon-mcp

# Check permissions
ls -la /home/shannon/.shannon-mcp/
```

#### High Memory Usage

```bash
# Check memory usage
docker stats shannon-mcp

# View top processes
top -p $(pgrep -f shannon-mcp)

# Check session count
sqlite3 ~/.shannon-mcp/shannon.db "SELECT COUNT(*) FROM sessions WHERE state='running';"

# Restart with higher limits
sudo systemctl edit shannon-mcp
# Add: [Service]
#      MemoryLimit=4G
sudo systemctl daemon-reload
sudo systemctl restart shannon-mcp
```

#### Database Locked Errors

```bash
# Check for stale processes
lsof ~/.shannon-mcp/shannon.db

# Kill stale processes
pkill -f shannon-mcp

# Check database integrity
sqlite3 ~/.shannon-mcp/shannon.db "PRAGMA integrity_check;"

# Restore from backup if corrupted
cp ~/.shannon-mcp/shannon.db ~/.shannon-mcp/shannon.db.corrupted
cp /backups/shannon-mcp/shannon_latest.db ~/.shannon-mcp/shannon.db
sudo systemctl start shannon-mcp
```

### 10.2 Performance Issues

#### Slow Response Times

```bash
# Enable debug logging
export SHANNON_LOG_LEVEL=DEBUG
systemctl restart shannon-mcp

# Profile application
poetry run python -m cProfile -o profile.stats -m shannon_mcp.server

# Analyze profile
poetry run python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative')
p.print_stats(20)
"

# Check database performance
sqlite3 ~/.shannon-mcp/shannon.db "ANALYZE;"
```

### 10.3 Deployment Rollback

```bash
#!/bin/bash
# rollback.sh - Quick rollback script

# Stop current version
docker-compose down

# Restore previous version
docker tag shannon-mcp:latest shannon-mcp:rollback
docker tag shannon-mcp:previous shannon-mcp:latest

# Start previous version
docker-compose up -d

# Verify health
sleep 10
curl -f http://localhost:8080/health || {
    echo "Rollback failed!"
    exit 1
}

echo "Rollback successful"
```

### 10.4 Debug Mode

Enable comprehensive debugging:

```yaml
# config.yaml (debug mode)
debug: true

logging:
  level: DEBUG
  format: console  # More readable in development

session_manager:
  enable_metrics: true
  enable_replay: true  # Record all sessions for replay

analytics:
  enabled: true
  aggregation_interval: 60  # More frequent updates
```

```bash
# Run in debug mode
SHANNON_DEBUG=true SHANNON_LOG_LEVEL=DEBUG shannon-mcp
```

---

## Appendix

### A. Configuration Examples

#### Production Configuration

```yaml
# ~/.shannon-mcp/config.production.yaml
app_name: shannon-mcp
version: 0.1.0
debug: false

database:
  path: /var/lib/shannon-mcp/shannon.db
  pool_size: 20
  timeout: 60.0
  journal_mode: WAL
  synchronous: NORMAL

logging:
  level: INFO
  format: json
  directory: /var/log/shannon-mcp
  max_size: 104857600  # 100MB
  backup_count: 10
  enable_sentry: true
  sentry_dsn: "${SENTRY_DSN}"

binary_manager:
  search_paths:
    - /usr/local/bin
    - /usr/bin
  nvm_check: true
  update_check_interval: 86400
  cache_timeout: 3600

session_manager:
  max_concurrent_sessions: 100
  session_timeout: 7200
  buffer_size: 4194304  # 4MB
  stream_chunk_size: 16384
  enable_metrics: true
  enable_replay: false

agent_manager:
  enable_default_agents: true
  max_concurrent_tasks: 100
  task_timeout: 600
  collaboration_enabled: true
  performance_tracking: true

checkpoint:
  storage_path: /var/lib/shannon-mcp/checkpoints
  compression_enabled: true
  compression_level: 6
  auto_checkpoint_interval: 600
  max_checkpoints: 1000
  cleanup_age_days: 90

analytics:
  enabled: true
  metrics_path: /var/lib/shannon-mcp/metrics
  retention_days: 365
  export_formats: ["json", "csv", "parquet"]
  aggregation_interval: 3600

mcp:
  transport: stdio
  connection_timeout: 60
  request_timeout: 600
  max_message_size: 104857600
  enable_compression: true
```

### B. Deployment Checklist

- [ ] Server provisioned with adequate resources
- [ ] Operating system updated and hardened
- [ ] Firewall configured
- [ ] SSL/TLS certificates obtained
- [ ] Application installed and configured
- [ ] Database initialized and backed up
- [ ] Systemd service created and enabled
- [ ] Log rotation configured
- [ ] Monitoring and alerts set up
- [ ] Backup strategy implemented
- [ ] Disaster recovery plan documented
- [ ] Security audit completed
- [ ] Performance testing completed
- [ ] Documentation updated
- [ ] Team trained on operations

### C. Support and Resources

- **Documentation**: https://github.com/krzemienski/shannon-mcp
- **Issues**: https://github.com/krzemienski/shannon-mcp/issues
- **Discussions**: https://github.com/krzemienski/shannon-mcp/discussions
- **Security**: security@shannon-mcp.com

---

**Shannon MCP Server** - Production-ready deployment for Claude Code automation

*Last updated: 2025-11-13*
