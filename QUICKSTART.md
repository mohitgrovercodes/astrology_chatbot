<!-- QUICKSTART.md -->
# Quick Start Guide - Running the API Server

## Prerequisites

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Redis Server

Redis is required for session management. Choose one option:

#### Option A: Using Docker (Recommended - Easiest)
```bash
# Pull and run Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Verify it's running
docker ps
```

#### Option B: Using Docker Compose (Runs everything together)
```bash
# This will start both the API and Redis
docker-compose up
```

#### Option C: Install Redis Locally on Windows
1. Download Redis for Windows from: https://github.com/microsoftarchive/redis/releases
2. Or use WSL2 and install via apt:
   ```bash
   sudo apt-get update
   sudo apt-get install redis-server
   sudo service redis-server start
   ```

#### Option D: Install Redis on Linux/Mac
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

### 3. Verify Redis is Running
```bash
# Test connection
redis-cli ping
# Should return: PONG
```

## Running the API Server

### Development Mode (with auto-reload)
```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Python directly
```bash
python src/api/main.py
```

## Verify the Server is Running

Once started, you should see:
```
======================================================================
NakshatraAI API Starting...
Version: 1.0.0
Docs: http://localhost:8000/api/docs
======================================================================
```

### Test Endpoints

1. **Health Check**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

2. **API Documentation**
   - Swagger UI: http://localhost:8000/api/docs
   - ReDoc: http://localhost:8000/api/redoc

3. **Test Backend Integration** (requires Redis)
   ```bash
   python tests/test_backend_integration.py
   ```

## Troubleshooting

### Redis Connection Error
If you see `redis.exceptions.ConnectionError`:
- Ensure Redis is running: `redis-cli ping`
- Check Redis host/port in `.env`:
  ```env
  REDIS_HOST=localhost
  REDIS_PORT=6379
  ```

### Port Already in Use
If port 8000 is busy:
```bash
uvicorn src.api.main:app --reload --port 8001
```

### Missing Environment Variables
Ensure your `.env` file has:
```env
OPENAI_API_KEY=your-key-here
INTERNAL_SERVICE_SECRET=super-secret-internal-key-123
REDIS_HOST=localhost
REDIS_PORT=6379
```

## Next Steps

- Review the [API Reference](docs/API_REFERENCE.md) for endpoint documentation
- Test the backend integration endpoint with the provided test script
- Configure your backend to use the `X-Internal-Service` header for authentication
