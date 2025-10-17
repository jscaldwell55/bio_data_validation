#!/usr/bin/env python3
"""
Test script for cache and Ensembl fallback functionality.

Tests:
1. Cache hit/miss behavior
2. NCBI → Ensembl fallback
3. Cache statistics
4. Performance improvements

Usage:
    python scripts/test_cache_and_fallback.py
"""

import asyncio
import pandas as pd
import time
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validators.bio_lookups import BioLookupsValidator
from src.utils.cache_manager import get_cache_manager
from src.schemas.base_schemas import DatasetMetadata


async def test_cache_functionality():
    """Test 1: Cache hit/miss behavior"""
    print("\n" + "="*70)
    print("TEST 1: Cache Functionality")
    print("="*70)
    
    # Clear cache to start fresh
    cache = get_cache_manager(enable_cache=True)
    cache.clear_all()
    print("✓ Cache cleared")
    
    # Create test data
    test_genes = pd.DataFrame({
        'target_gene': ['BRCA1', 'TP53', 'EGFR', 'KRAS', 'MYC'],
        'organism': ['human'] * 5
    })
    
    validator = BioLookupsValidator(enable_cache=True)
    
    # First validation (cache misses)
    print("\n--- First Validation (Cache MISS expected) ---")
    start = time.time()
    result1 = await validator.validate(test_genes, validation_type='gene_symbols')
    time1 = time.time() - start
    
    print(f"Execution time: {time1:.2f}s")
    print(f"Cache hits: {result1.metadata['cache_hits']}")
    print(f"Cache misses: {result1.metadata['cache_misses']}")
    print(f"API calls: {result1.metadata['api_calls_made']}")
    
    # Second validation (cache hits)
    print("\n--- Second Validation (Cache HIT expected) ---")
    start = time.time()
    result2 = await validator.validate(test_genes, validation_type='gene_symbols')
    time2 = time.time() - start
    
    print(f"Execution time: {time2:.2f}s")
    print(f"Cache hits: {result2.metadata['cache_hits']}")
    print(f"Cache misses: {result2.metadata['cache_misses']}")
    print(f"API calls: {result2.metadata['api_calls_made']}")
    
    # Performance comparison
    speedup = (time1 / time2) if time2 > 0 else float('inf')
    print(f"\n✅ Speedup: {speedup:.1f}x faster with cache")
    print(f"✅ API call reduction: {result2.metadata['api_call_reduction']}")
    
    # Cache statistics
    stats = cache.get_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Hit rate: {stats['hit_rate']:.1%}")
    print(f"  Cached entries: {stats.get('cached_entries', 0)}")
    
    return time1, time2, stats


async def test_ensembl_fallback():
    """Test 2: Ensembl fallback when NCBI fails"""
    print("\n" + "="*70)
    print("TEST 2: Ensembl Fallback")
    print("="*70)
    
    # Test with genes that might be in Ensembl but not NCBI
    # (or simulate NCBI failure)
    test_genes = pd.DataFrame({
        'target_gene': ['BRCA1', 'TP53', 'FAKE_GENE_12345'],
        'organism': ['human'] * 3
    })
    
    validator = BioLookupsValidator(enable_cache=False)  # Disable cache for this test
    
    print("\n--- Testing with real genes and one fake gene ---")
    result = await validator.validate(test_genes, validation_type='gene_symbols')
    
    print(f"\nValidation Results:")
    print(f"  NCBI successes: {result.metadata['ncbi_successes']}")
    print(f"  Ensembl fallbacks: {result.metadata['ensembl_fallbacks']}")
    print(f"  Degraded mode: {result.metadata['degraded_mode']}")
    print(f"  Provider reliability: {result.metadata['provider_reliability']}")
    
    if result.metadata['ensembl_fallbacks'] > 0:
        print(f"\n✅ Ensembl fallback working! {result.metadata['ensembl_fallbacks']} genes validated via Ensembl")
    else:
        print("\n⚠️  All genes validated via NCBI (fallback not triggered)")
    
    # Print issues
    if result.issues:
        print(f"\n📋 Issues Found:")
        for issue in result.issues[:3]:
            print(f"  - [{issue.severity}] {issue.message}")
    
    return result


async def test_cache_statistics():
    """Test 3: Cache statistics and management"""
    print("\n" + "="*70)
    print("TEST 3: Cache Statistics")
    print("="*70)
    
    cache = get_cache_manager(enable_cache=True)
    
    # Get detailed statistics
    stats = cache.get_stats()
    
    print("\n📊 Detailed Cache Statistics:")
    print(f"  Cache enabled: {cache.enable_cache}")
    print(f"  Cache path: {cache.cache_path}")
    print(f"  TTL: {cache.ttl_hours} hours")
    print(f"\n  Performance:")
    print(f"    Total requests: {stats['total_requests']}")
    print(f"    Hits: {stats['hits']}")
    print(f"    Misses: {stats['misses']}")
    print(f"    Hit rate: {stats['hit_rate']:.1%}")
    print(f"\n  Storage:")
    print(f"    Cached entries: {stats.get('cached_entries', 0)}")
    print(f"    Cache size: {stats.get('cache_size_bytes', 0) / 1024:.1f} KB")
    print(f"    Writes: {stats['writes']}")
    print(f"    Evictions: {stats['evictions']}")
    print(f"    Errors: {stats['errors']}")
    
    if 'by_provider' in stats:
        print(f"\n  By Provider:")
        for provider, count in stats['by_provider'].items():
            print(f"    {provider}: {count} entries")
    
    return stats


async def test_performance_comparison():
    """Test 4: Performance comparison with/without cache"""
    print("\n" + "="*70)
    print("TEST 4: Performance Comparison")
    print("="*70)
    
    # Larger dataset for meaningful comparison
    large_genes = pd.DataFrame({
        'target_gene': [
            'BRCA1', 'BRCA2', 'TP53', 'EGFR', 'KRAS', 'MYC', 'PTEN', 'ALK',
            'BRAF', 'PIK3CA', 'RB1', 'APC', 'CDKN2A', 'ERBB2', 'FGFR1',
            'FGFR2', 'FGFR3', 'IDH1', 'IDH2', 'KIT'
        ],
        'organism': ['human'] * 20
    })
    
    # Test WITHOUT cache
    print("\n--- Test 1: WITHOUT Cache ---")
    validator_no_cache = BioLookupsValidator(enable_cache=False)
    start = time.time()
    result_no_cache = await validator_no_cache.validate(large_genes, validation_type='gene_symbols')
    time_no_cache = time.time() - start
    
    print(f"Execution time: {time_no_cache:.2f}s")
    print(f"API calls: {result_no_cache.metadata['api_calls_made']}")
    
    # Test WITH cache (second run to ensure hits)
    print("\n--- Test 2: WITH Cache (pre-warmed) ---")
    validator_cache = BioLookupsValidator(enable_cache=True)
    
    # First run to populate cache
    await validator_cache.validate(large_genes, validation_type='gene_symbols')
    
    # Second run to measure cache performance
    start = time.time()
    result_cache = await validator_cache.validate(large_genes, validation_type='gene_symbols')
    time_cache = time.time() - start
    
    print(f"Execution time: {time_cache:.2f}s")
    print(f"Cache hits: {result_cache.metadata['cache_hits']}")
    print(f"API calls: {result_cache.metadata['api_calls_made']}")
    
    # Comparison
    speedup = (time_no_cache / time_cache) if time_cache > 0 else float('inf')
    api_reduction = (1 - (result_cache.metadata['api_calls_made'] / result_no_cache.metadata['api_calls_made'])) * 100
    
    print(f"\n📈 Performance Improvement:")
    print(f"  Speedup: {speedup:.1f}x faster")
    print(f"  Time saved: {time_no_cache - time_cache:.2f}s ({(1 - time_cache/time_no_cache)*100:.0f}%)")
    print(f"  API calls reduced: {api_reduction:.0f}%")
    
    return {
        'speedup': speedup,
        'time_saved': time_no_cache - time_cache,
        'api_reduction': api_reduction
    }


async def main():
    """Run all tests"""
    print("\n" + "🧪 " * 35)
    print(" CACHE + ENSEMBL FALLBACK TEST SUITE")
    print("🧪 " * 35)
    
    try:
        # Test 1: Basic cache functionality
        time1, time2, cache_stats = await test_cache_functionality()
        
        # Test 2: Ensembl fallback
        fallback_result = await test_ensembl_fallback()
        
        # Test 3: Cache statistics
        detailed_stats = await test_cache_statistics()
        
        # Test 4: Performance comparison
        perf_results = await test_performance_comparison()
        
        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        
        print("\n✅ Cache Functionality:")
        print(f"  - Cache speedup: {time1/time2:.1f}x")
        print(f"  - Hit rate: {cache_stats['hit_rate']:.1%}")
        
        print("\n✅ Ensembl Fallback:")
        print(f"  - NCBI successes: {fallback_result.metadata['ncbi_successes']}")
        print(f"  - Ensembl fallbacks: {fallback_result.metadata['ensembl_fallbacks']}")
        print(f"  - Provider reliability: {fallback_result.metadata['provider_reliability']}")
        
        print("\n✅ Performance Gains:")
        print(f"  - Overall speedup: {perf_results['speedup']:.1f}x")
        print(f"  - Time saved: {perf_results['time_saved']:.2f}s")
        print(f"  - API call reduction: {perf_results['api_reduction']:.0f}%")
        
        print("\n" + "🎉 " * 35)
        print(" ALL TESTS COMPLETED SUCCESSFULLY!")
        print("🎉 " * 35)
        
        print("\n📋 Next Steps:")
        print("  1. Review cache statistics in validation reports")
        print("  2. Monitor Prometheus metrics for cache hit rate")
        print("  3. Test with larger datasets for production validation")
        print("  4. Configure cache TTL based on use case")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)