# Unspend Platform Infrastructure Documentation

## Overview
This document provides comprehensive infrastructure and deployment information for the Unspend invoice reconciliation platform.

## Architecture

### Components
- **Frontend**: Static HTML/CSS/JS served via Firebase Hosting
- **Backend**: Python Flask API with async processing capabilities
- **Database**: SQLite with connection pooling (upgradeable to PostgreSQL)
- **Cache**: Multi-layer caching system (in-memory + persistent)
- **Batch Processor**: Async job queue for high-volume processing

## Deployment

### Environments

#### Production
- URL: https://unspend-91424.web.app
- Branch: `main`
- Config: `environments/production.env`

#### Staging
- URL: https://unspend-91424--staging-web.app
- Branch: `infra/deployment-management`
- Config: `environments/staging.env`

### Deployment Methods

#### 1. Firebase Hosting (Recommended for Frontend)
```bash
# Quick deploy
npm run deploy

# Enhanced deploy with tests
./deploy_enhanced.sh production true
```

#### 2. Docker Deployment (Full Stack)
```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### 3. Manual Deployment
```bash
# Install dependencies
pip install -r requirements.txt
npm install

# Run tests
./run_tests.sh

# Start backend
python backend/app.py

# Deploy frontend
firebase deploy --only hosting
```

## CI/CD Pipeline

### GitHub Actions Workflow
Located at `.github/workflows/ci-cd.yml`

#### Pipeline Stages:
1. **Test Backend**: Python linting, formatting, unit tests
2. **Test Frontend**: HTML validation, JavaScript linting
3. **Security Scan**: Trivy, Bandit, Safety checks
4. **Build & Deploy**: Conditional deployment based on branch

### Triggering Deployments:
- **Production**: Push to `main` branch
- **Staging**: Create pull request to `main`
- **Manual**: Use workflow dispatch in GitHub Actions

## Testing

### Running Tests
```bash
# Run all tests
./run_tests.sh

# Backend tests only
pytest backend/tests/ -v

# With coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

### Test Categories:
- Unit tests (backend/tests/)
- Integration tests (API endpoints)
- Security scans (Bandit, Safety)
- Performance tests (response times, file sizes)

## Monitoring

### Metrics Endpoints:
- `/api/health` - System health check
- `/api/metrics` - Comprehensive metrics
- `/api/metrics/llm` - LLM performance metrics
- `/api/batch/stats` - Batch processor statistics

### Prometheus Integration:
```bash
# Start Prometheus
prometheus --config.file=monitoring/prometheus.yml
```

### Available Metrics:
- Request rate and latency
- Error rates by endpoint
- Cache hit rates
- LLM token usage and costs
- Batch processing queue depth

## Configuration

### Environment Variables

#### Required:
- `OPENAI_API_KEY` - OpenAI API key for LLM operations
- `FIREBASE_PROJECT_ID` - Firebase project identifier

#### Optional:
- `MAX_WORKERS` - Batch processor workers (default: 4)
- `CACHE_TTL` - Cache time-to-live in seconds (default: 3600)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `ENABLE_METRICS` - Enable metrics collection (default: true)

### Firebase Configuration:
- `firebase.json` - Hosting configuration
- `.firebaserc` - Project settings

## Security

### Rate Limiting:
- Strict: 10 req/min (sensitive operations)
- Standard: 30 req/min (normal operations)
- Relaxed: 60 req/min (read operations)

### Authentication:
- API key validation for admin endpoints
- CORS configuration for frontend access

### Data Protection:
- File upload validation
- SQL injection prevention
- XSS protection

## Backup & Recovery

### Automated Backups:
```bash
# Created automatically during deployment
backups/YYYYMMDD_HHMMSS/
```

### Manual Backup:
```bash
# Database
cp backend/unspend.db backups/unspend_$(date +%Y%m%d).db

# Full backup
tar -czf backup_$(date +%Y%m%d).tar.gz backend/ frontend/ *.json
```

## Troubleshooting

### Common Issues:

#### 1. Firebase deployment fails
```bash
# Check authentication
npx firebase-tools login

# Verify project
npx firebase-tools projects:list
```

#### 2. Backend won't start
```bash
# Check Python version
python --version  # Should be 3.9+

# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

#### 3. Tests failing
```bash
# Run specific test
pytest backend/tests/test_api.py::TestHealthEndpoint -v

# Check test environment
python -m pytest --version
```

## Performance Optimization

### Caching Strategy:
1. In-memory cache (immediate)
2. Persistent cache (Redis-like)
3. Database cache (long-term)

### Batch Processing:
- Concurrent workers: 4 (configurable)
- Max queue size: 20 jobs
- Priority levels: URGENT, HIGH, NORMAL, LOW

### API Optimization:
- Connection pooling for LLM calls
- Async request handling
- Response compression

## Maintenance

### Regular Tasks:
1. **Daily**: Check health endpoints
2. **Weekly**: Review metrics and logs
3. **Monthly**: Update dependencies, run security scans
4. **Quarterly**: Performance review and optimization

### Cache Maintenance:
```bash
# Clear all caches
curl -X POST http://localhost:5000/api/admin/cache/clear

# Reset metrics
curl -X POST http://localhost:5000/api/admin/metrics/reset
```

## Support

### Logs Location:
- Application logs: `logs/app.log`
- Deployment logs: `deployment.log`
- Error logs: Check Docker/systemd logs

### Debug Mode:
```bash
# Enable debug logging
export FLASK_DEBUG=True
export LOG_LEVEL=DEBUG
python backend/app.py
```

---

**Last Updated**: 2025-08-16
**Maintained by**: Infrastructure Instance
**Version**: 2.0.0