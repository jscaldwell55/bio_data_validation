# Rule Versioning in Validation Reports

**Status**: ✅ IMPLEMENTED  
**Priority**: HIGH  
**Impact**: Enables full reproducibility and audit trails

---

## Overview

Every validation report now includes complete ruleset version information, enabling:
- **Full reproducibility** - Know exactly which rules validated the data
- **Change tracking** - Audit when rules were updated
- **Integrity verification** - Hash ensures rules weren't modified
- **Compliance** - Meet regulatory requirements (21 CFR Part 11, GxP)

---

## What's Tracked

### Ruleset Metadata in Every Report

```json
{
  "validation_id": "47d087eb-958e-4056",
  "dataset_id": "experiment_001",
  "final_decision": "accepted",
  
  "ruleset_metadata": {
    "version": "1.2.0",
    "last_updated": "2025-10-17",
    "source": "config/validation_rules.yml",
    "hash": "a3f9c8d1e2b4f5a6",
    "latest_changes": [
      "Added gene symbol caching support",
      "Added Ensembl fallback provider",
      "Added variant annotation validation rules"
    ]
  },
  
  "api_configuration": {
    "ncbi_api_key_configured": true,
    "ncbi_rate_limit": "10 req/sec",
    "cache_enabled": true,
    "ensembl_fallback_enabled": true
  }
}
```

---

## Version Format

### Semantic Versioning

We use [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes to validation logic
- **MINOR**: New validation rules added (backward compatible)
- **PATCH**: Bug fixes, threshold adjustments

**Examples:**
- `1.0.0` → `2.0.0`: Changed GC content threshold from 40-70% to 30-80% (breaking)
- `1.0.0` → `1.1.0`: Added new duplicate detection rule (additive)
- `1.0.0` → `1.0.1`: Fixed typo in error message (non-functional)

---

## Configuration File Format

### validation_rules.yml Structure

```yaml
# Version metadata at top
version: "1.2.0"
last_updated: "2025-10-17"
changelog:
  - version: "1.2.0"
    date: "2025-10-17"
    changes:
      - "Added gene symbol caching support"
      - "Added Ensembl fallback provider"
  - version: "1.1.0"
    date: "2025-10-09"
    changes:
      - "Added custom rule support"
      - "Enhanced bias detection"

# Validation rules
rules:
  consistency:
    required_columns: [...]
  duplicates:
    check_duplicate_rows: true
  ...
```

---

## Hash Computation

### What's Hashed

The SHA256 hash is computed from the **entire** `validation_rules.yml` file:
- All rule definitions
- All thresholds and parameters
- Comments and formatting (ensures exact match)

```python
import hashlib

content = Path("config/validation_rules.yml").read_text()
full_hash = hashlib.sha256(content.encode()).hexdigest()
short_hash = full_hash[:16]  # First 16 characters for reports
```

### Why Hash?

- **Integrity**: Detect if rules file was modified
- **Reproducibility**: Different hash = different rules
- **Audit trail**: Prove which exact ruleset was used

---

## Use Cases

### 1. Reproducibility

**Problem**: "Can I reproduce results from 6 months ago?"

**Solution**: Check the `ruleset_metadata.hash` in the old report:

```bash
# Find old report
cat validation_output/validation_20250417_*.json | jq '.ruleset_metadata'

# Output:
{
  "version": "1.0.0",
  "hash": "e8a7b3c2d4f1a6b9"
}

# Check if current rules match
python -c "
import hashlib
from pathlib import Path
content = Path('config/validation_rules.yml').read_text()
current_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
print(f'Current: {current_hash}')
print(f'Old:     e8a7b3c2d4f1a6b9')
print('Match!' if current_hash == 'e8a7b3c2d4f1a6b9' else 'Rules changed!')
"
```

### 2. Regulatory Compliance

**Requirement**: 21 CFR Part 11 requires audit trails

**Solution**: Every report includes:
- Ruleset version used
- Date rules were last updated
- Cryptographic hash for integrity
- Complete change history

```json
{
  "validation_id": "...",
  "ruleset_metadata": {
    "version": "1.2.0",
    "last_updated": "2025-10-17",
    "hash": "a3f9c8d1e2b4f5a6"
  }
}
```

### 3. Change Impact Analysis

**Problem**: "Which validations were affected by rule changes?"

**Solution**: Query reports by hash/version:

```bash
# Find all reports using old ruleset
grep -r "\"version\": \"1.0.0\"" validation_output/ | wc -l

# Find reports that need re-validation
for report in validation_output/validation_*.json; do
  version=$(jq -r '.ruleset_metadata.version' "$report")
  if [ "$version" != "1.2.0" ]; then
    echo "Needs re-validation: $report"
  fi
done
```

---

## Updating Rules

### Step 1: Increment Version

```yaml
# Before
version: "1.1.0"
last_updated: "2025-10-09"

# After
version: "1.2.0"
last_updated: "2025-10-17"
```

### Step 2: Add Changelog Entry

```yaml
changelog:
  - version: "1.2.0"  # New entry at top
    date: "2025-10-17"
    changes:
      - "Added caching support"
      - "New variant validation rules"
  - version: "1.1.0"
    date: "2025-10-09"
    changes:
      - "Previous changes"
```

### Step 3: Update Rules

```yaml
rules:
  consistency:
    value_ranges:
      gc_content:
        min: 0.4
        max: 0.7  # Changed from 0.6
```

### Step 4: Verify

```bash
# Test new rules
python scripts/test_rule_versioning.py

# Check version is loaded
curl http://localhost:8000/api/v1/validate/... | jq '.ruleset_metadata'
```

---

## API Integration

### Accessing Version Info

```python
from src.agents.orchestrator import ValidationOrchestrator

orchestrator = ValidationOrchestrator()

# Version info available immediately
print(orchestrator.ruleset_metadata)
# {
#   'version': '1.2.0',
#   'last_updated': '2025-10-17',
#   'hash': 'a3f9c8d1e2b4f5a6',
#   'source': 'config/validation_rules.yml'
# }
```

### In Validation Reports

```python
report = await orchestrator.validate_dataset(df, metadata)

print(report["ruleset_metadata"]["version"])  # "1.2.0"
print(report["ruleset_metadata"]["hash"])     # "a3f9c8d1e2b4f5a6"
```

---

## Best Practices

### 1. Version Every Change

Even minor threshold adjustments should increment the version:

```yaml
# Bad: Changed threshold without version bump
rules:
  consistency:
    value_ranges:
      gc_content: {min: 0.4, max: 0.7}  # Was 0.6

# Good: Version bumped
version: "1.0.1"  # Was 1.0.0
changelog:
  - version: "1.0.1"
    changes: ["Relaxed GC content max from 0.6 to 0.7"]
```

### 2. Descriptive Changelog

```yaml
# Bad
changes: ["Updated rules"]

# Good
changes:
  - "Increased GC content max from 60% to 70%"
  - "Added NCBI gene symbol validation"
  - "Fixed: Duplicate detection false positives"
```

### 3. Archive Old Rulesets

```bash
# Before updating rules
cp config/validation_rules.yml \
   config/archive/validation_rules_v1.1.0.yml

# Update to v1.2.0
vim config/validation_rules.yml
```

### 4. Document Breaking Changes

```yaml
changelog:
  - version: "2.0.0"
    date: "2025-11-01"
    changes:
      - "BREAKING: Changed PAM validation logic"
      - "BREAKING: Removed support for hg19 reference"
      - "Migration guide: See docs/migration_v2.md"
```

---

## Troubleshooting

### Version Shows "unknown"

**Problem**: Report shows `"version": "unknown"`

**Cause**: validation_rules.yml missing version field

**Fix**:
```yaml
# Add to top of validation_rules.yml
version: "1.0.0"
last_updated: "2025-10-17"
```

### Hash is None

**Problem**: Report shows `"hash": null`

**Cause**: Rules file not found or not readable

**Fix**:
```bash
# Check file exists
ls -lh config/validation_rules.yml

# Check permissions
chmod 644 config/validation_rules.yml
```

### Hashes Don't Match

**Problem**: Same rules file, different hashes

**Cause**: File was modified (even whitespace changes hash)

**Solution**:
```bash
# See what changed
git diff config/validation_rules.yml

# Or use version control
git log config/validation_rules.yml
```

---

## Testing

Run the test suite:

```bash
python scripts/test_rule_versioning.py
```

**Expected output:**
```
✅ Rule Versioning: PASSED
✅ Reproducibility Tracking: PASSED

🎉 ALL TESTS PASSED!

📋 Benefits:
  - Full reproducibility tracking
  - Ruleset changes auditable
  - Reports include version context
  - Hash enables integrity verification
```

---

## References

- Semantic Versioning: https://semver.org/
- 21 CFR Part 11: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/part-11-electronic-records-electronic-signatures-scope-and-application
- SHA256: https://en.wikipedia.org/wiki/SHA-2

---

**Last Updated**: 2025-10-17  
**Version**: 1.0.0  
**Status**: ✅ Production Ready