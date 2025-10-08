# Validation Report

**Generated:** 2025-10-08 06:50:51

## Summary

- **Dataset ID:** CRISPR_SCREEN_2024_Q4
- **Decision:** REJECTED
- **Rationale:** Conditional accept: 3 error(s), 6 warning(s) require attention
- **Records:** 10
- **Execution Time:** 0.41s
- **Short-circuited:** False

## Issue Summary

- **ERROR:** 3
- **WARNING:** 6

## Stages

### SCHEMA

- **Status:** ✗ FAIL
- **Issues:** 1
- **Execution Time:** 2.8ms

#### Issues

1. **[ERROR]** Value error, Invalid PAM for SpCas9: AAA

### RULES

- **Status:** ✓ PASS
- **Issues:** 1
- **Execution Time:** 2.4ms

#### Issues

1. **[WARNING]** Found 4 duplicate sequences
   - Rule: `DUP_003`, Field: `sequence`

### BIO_RULES

- **Status:** ✗ FAIL
- **Issues:** 6
- **Execution Time:** 3.5ms

#### Issues

1. **[ERROR]** 1 guides are critically short (<15bp) - likely unusable
   - Rule: `BIO_001A`, Field: `sequence`
2. **[WARNING]** 1 guides have suboptimal length (optimal: 19-20bp)
   - Rule: `BIO_001B`, Field: `sequence`
3. **[ERROR]** 1 invalid PAM sequences for SpCas9
   - Rule: `BIO_002`, Field: `pam_sequence`
4. **[WARNING]** 1 guides have suboptimal GC content (optimal: 40-70%)
   - Rule: `BIO_003`, Field: `sequence`
5. **[WARNING]** 1 guides contain poly-T stretch (TTTT), may cause transcription termination
   - Rule: `BIO_004`, Field: `sequence`
6. **[WARNING]** 1 guides contain homopolymer runs (5+ identical bases)
   - Rule: `BIO_005`, Field: `sequence`

### BIO_LOOKUPS

- **Status:** ✓ PASS
- **Issues:** 1
- **Execution Time:** 300.5ms

#### Issues

1. **[WARNING]** 1 ambiguous gene symbols (multiple matches)
   - Rule: `LOOKUP_002`, Field: `target_gene`

### HUMAN_REVIEW

- **Status:** ✗ FAIL
- **Issues:** 0
- **Execution Time:** 101.6ms

