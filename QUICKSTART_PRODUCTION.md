# Quick Start: Production Deployment

**Time Required**: 15 minutes  
**Difficulty**: Intermediate

---

## **Prerequisites**

- Docker & Docker Compose installed
- 8GB+ RAM available
- 50GB+ disk space
- NCBI API key (get from: https://www.ncbi.nlm.nih.gov/account/)

---

## **5-Minute Production Deploy**

### **Step 1: Clone & Configure** (3 minutes)

```bash
# Clone repository
git clone <your-repo-url>
cd bio_data_validation

# Copy production config
cp .env.production .env

# Edit configuration
vim .env
# Required changes:
# 1. NCBI_API_KEY=your_actual_key
# 2. SECRET_KEY=random_string_here
# 3. GRAFANA_PASSWORD=your_password

# Generate secret keys
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env
python -c "import secrets; print('GRAFANA_SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env

# Create directories
mkdir -p validation_output logs backups
chmod 755 validation_output logs
chmod 600 .env
```

### **Step 2: Deploy** (2 minutes)

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to start (30 seconds)
sleep 30

# Check status
docker-compose -f docker-compose.prod.yml ps
```

**Expected output:**
```
NAME                      STATUS    PORTS
bio-validation-api        Up        0.0.0.0:8000->8000/tcp
bio-validation-prometheus Up        0.0.0.0:9090->9090/tcp
bio-validation-grafana    Up        0.0.0.0:3000->3000/tcp
```

### **Step 3: Verify** (1 minute)

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# Cache stats
curl http://localhost:8000/api/v1/cache/stats | jq '.cache_enabled'
# Expected: true

# Warm cache
curl -X POST http://localhost:8000/api/v1/cache/warm
```

### **Step 4: Test** (1 minute)

```bash
# Submit test validation
curl -X POST http://localhost:8000/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{
    "format": "guide_rna",
    "data": [{
      "guide_id": "test1",
      "sequence": "ATCGATCGATCGATCGATCG",
      "pam_sequence": "AGG",
      "target_gene": "BRCA1",
      "organism": "human",
      "nuclease_type": "SpCas9"
    }]
  }'

# You should get a validation_id in response
# Check the report was saved:
ls -lh validation_output/
```

---

## **Access Points**

| Service | URL | Credentials |
|---------|-----|-------------|
| **API** | http://localhost:8000 | None |
| **API Docs** | http://localhost:8000/docs | None |
| **Prometheus** | http://localhost:9090 | None |
| **Grafana** | http://localhost:3000 | admin / YOUR_PASSWORD |

---

## **First Validation**

### **Via curl:**

```bash
curl -X POST http://localhost:8000/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{
    "format": "guide_rna",
    "data": [{
      "guide_id": "g001",
      "sequence": "ATCGATCGATCGATCGATCG",
      "pam_sequence": "AGG",
      "target_gene": "BRCA1",
      "organism": "human",
      "nuclease_type": "SpCas9"
    }],
    "metadata": {
      "experiment_id": "pilot_001",
      "researcher": "Jane Doe"
    }
  }'
```

### **Via Python:**

```python
import requests

data = {
    "format": "guide_rna",
    "data": [{
        "guide_id": "g001",
        "sequence": "ATCGATCGATCGATCGATCG",
        "pam_sequence": "AGG",
        "target_gene": "BRCA1",
        "organism": "human",
        "nuclease_type": "SpCas9"
    }]
}

response = requests.post(
    "http://localhost:8000/api/v1/validate",
    json=data
)

print(response.json())
# Get validation_id from response

# Check status
validation_id = response.json()["validation_id"]
status = requests.get(f"http://localhost:8000/api/v1/validate/{validation_id}")
print(status.json())
```

---

## **Monitoring Setup**

### **Access Grafana:**

1. Open http://localhost:3000
2. Login with admin / YOUR_PASSWORD
3. Navigate to Dashboards → Bio Validation Overview
4. Set auto-refresh to 10 seconds

### **Key Metrics to Watch:**

- **Cache Hit Rate**: Should be >80% after warmup
- **API Success Rate**: Should be >99%
- **Validation Duration**: P95 should be <2 seconds
- **NCBI API Errors**: Should be near 0

---

## **Daily Operations**

### **Check System Health:**

```bash
# All services running?
docker-compose -f docker-compose.prod.yml ps

# Any errors in logs?
docker-compose -f docker-compose.prod.yml logs --tail 50 | grep ERROR

# Cache performance?
curl http://localhost:8000/api/v1/cache/stats | jq '.statistics.hit_rate'

# Disk space OK?
df -h .
```

### **Clear Expired Cache:**

```bash
# Daily at 2am via cron:
0 2 * * * curl -X POST http://localhost:8000/api/v1/cache/clear?expired_only=true
```

### **Backup Reports:**

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
tar -czf backups/validation_output_$DATE.tar.gz validation_output/
tar -czf backups/validation_cache_$DATE.tar.gz validation_cache.db

# Keep last 30 days
find backups/ -name "*.tar.gz" -mtime +30 -delete
```

---

## **Troubleshooting**

### **API Not Starting:**

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs api

# Common fixes:
# 1. Port 8000 in use
sudo lsof -i :8000

# 2. Missing .env
ls -la .env

# 3. Restart
docker-compose -f docker-compose.prod.yml restart api
```

### **Cache Not Working:**

```bash
# Check cache enabled
curl http://localhost:8000/api/v1/cache/stats | jq '.cache_enabled'

# Clear and rebuild
curl -X POST http://localhost:8000/api/v1/cache/clear
curl -X POST http://localhost:8000/api/v1/cache/warm
```

### **High Memory:**

```bash
# Check usage
docker stats

# Restart if needed
docker-compose -f docker-compose.prod.yml restart api
```

---

## **Stopping Services**

```bash
# Stop (keeps data)
docker-compose -f docker-compose.prod.yml stop

# Stop and remove containers (keeps volumes)
docker-compose -f docker-compose.prod.yml down

# Stop and remove everything including data
docker-compose -f docker-compose.prod.yml down -v
```

---

## **Updating**

```bash
# Pull latest code
git pull

# Rebuild
docker-compose -f docker-compose.prod.yml build --no-cache

# Restart
docker-compose -f docker-compose.prod.yml up -d

# Verify
curl http://localhost:8000/health
```

---

## **Getting Help**

- **API Documentation**: http://localhost:8000/docs
- **System Logs**: `docker-compose logs api`
- **Grafana Dashboards**: http://localhost:3000
- **Full Deployment Guide**: See PRODUCTION_DEPLOYMENT_CHECKLIST.md

---

## **Success Checklist** ✅

After deployment, verify:

- [ ] API health check returns 200
- [ ] Cache is enabled and working
- [ ] NCBI API key is configured (10 req/sec)
- [ ] Ensembl fallback is enabled
- [ ] Grafana dashboard loads
- [ ] Prometheus is scraping metrics
- [ ] Test validation completes successfully
- [ ] Reports are saved to validation_output/
- [ ] No errors in logs

---

**🎉 You're ready for production!**

Next steps:
1. Review full deployment checklist
2. Set up monitoring alerts
3. Train your team
4. Run pilot validations