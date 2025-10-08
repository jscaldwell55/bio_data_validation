"""
Pytest configuration and shared fixtures
This file is automatically loaded by pytest
"""
import pytest
import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Set test environment
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'DEBUG'


# ===== PYTEST CONFIGURATION =====

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "api: mark test as API test requiring external services"
    )


# ===== SHARED FIXTURES =====

@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory"""
    return Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def example_data_dir():
    """Path to example data directory"""
    return Path(__file__).parent.parent / "data" / "examples"


@pytest.fixture
def valid_guide_rna_df():
    """Standard valid guide RNA dataset for testing"""
    return pd.DataFrame({
        'guide_id': [f'gRNA_{i:03d}' for i in range(20)],
        'sequence': ['ATCGATCGATCGATCGATCG'] * 20,
        'pam_sequence': ['AGG'] * 20,
        'target_gene': ['BRCA1'] * 10 + ['TP53'] * 10,
        'organism': ['human'] * 20,
        'nuclease_type': ['SpCas9'] * 20,
        'gc_content': [0.5] * 20,
        'efficiency_score': [0.85] * 20,
        'start_position': list(range(1000000, 1000020)),
        'end_position': list(range(1000020, 1000040)),
        'chromosome': ['chr17'] * 20,
        'strand': ['+'] * 20
    })


@pytest.fixture
def invalid_guide_rna_df():
    """Invalid guide RNA dataset for testing error detection"""
    return pd.DataFrame({
        'guide_id': ['gRNA_001', 'gRNA_001', 'gRNA_003'],  # Duplicate
        'sequence': ['ATCG', 'INVALID123', ''],  # Too short, invalid chars, empty
        'pam_sequence': ['AAA', 'TGG', 'XYZ'],  # Invalid PAM
        'target_gene': ['', 'UNKNOWN_GENE', 'BRCA1'],  # Missing, unknown
        'organism': ['human', 'human', 'human'],
        'nuclease_type': ['SpCas9', 'SpCas9', 'SpCas9'],
        'gc_content': [1.5, -0.1, 0.5],  # Out of range
        'efficiency_score': [1.2, 0.85, -0.5]  # Out of range
    })


@pytest.fixture
def large_dataset():
    """Large dataset for performance testing (10,000 records)"""
    n_records = 10000
    return pd.DataFrame({
        'guide_id': [f'gRNA_{i:05d}' for i in range(n_records)],
        'sequence': ['ATCGATCGATCGATCGATCG'] * n_records,
        'pam_sequence': np.random.choice(['AGG', 'TGG', 'CGG'], n_records),
        'target_gene': np.random.choice(['BRCA1', 'TP53', 'EGFR', 'KRAS'], n_records),
        'organism': ['human'] * n_records,
        'nuclease_type': ['SpCas9'] * n_records,
        'gc_content': np.random.uniform(0.3, 0.7, n_records),
        'efficiency_score': np.random.uniform(0.6, 1.0, n_records),
        'start_position': np.arange(1000000, 1000000 + n_records),
        'end_position': np.arange(1000020, 1000020 + n_records)
    })


@pytest.fixture
def metadata_factory():
    """Factory for creating test metadata"""
    def create_metadata(
        dataset_id="test_dataset",
        format_type="guide_rna",
        record_count=20,
        organism="human",
        **kwargs
    ):
        from src.schemas.base_schemas import DatasetMetadata, FormatType
        
        return DatasetMetadata(
            dataset_id=dataset_id,
            format_type=FormatType(format_type),
            record_count=record_count,
            organism=organism,
            submission_date=kwargs.get('submission_date', datetime.now()),
            **{k: v for k, v in kwargs.items() if k != 'submission_date'}
        )
    
    return create_metadata


@pytest.fixture
def mock_ncbi_response():
    """Mock NCBI API response for testing"""
    return {
        'BRCA1': {
            'gene_id': '672',
            'symbol': 'BRCA1',
            'description': 'BRCA1 DNA repair associated',
            'organism': 'Homo sapiens'
        },
        'TP53': {
            'gene_id': '7157',
            'symbol': 'TP53',
            'description': 'tumor protein p53',
            'organism': 'Homo sapiens'
        },
        'EGFR': {
            'gene_id': '1956',
            'symbol': 'EGFR',
            'description': 'epidermal growth factor receptor',
            'organism': 'Homo sapiens'
        }
    }


@pytest.fixture
def mock_ensembl_response():
    """Mock Ensembl API response for testing"""
    return {
        'BRCA1': {
            'id': 'ENSG00000012048',
            'display_name': 'BRCA1',
            'biotype': 'protein_coding',
            'strand': 1,
            'start': 43044295,
            'end': 43125483,
            'seq_region_name': '17'
        }
    }


# ===== HELPER FUNCTIONS =====

@pytest.fixture
def assert_validation_result():
    """Helper to assert ValidationResult structure"""
    def _assert(result):
        from src.schemas.base_schemas import ValidationResult
        
        assert isinstance(result, ValidationResult)
        assert hasattr(result, 'validator_name')
        assert hasattr(result, 'passed')
        assert hasattr(result, 'severity')
        assert hasattr(result, 'issues')
        assert hasattr(result, 'execution_time_ms')
        assert hasattr(result, 'records_processed')
        
        assert isinstance(result.passed, bool)
        assert isinstance(result.issues, list)
        assert result.execution_time_ms >= 0
        assert result.records_processed >= 0
        
        return True
    
    return _assert


@pytest.fixture
def count_issues_by_severity():
    """Helper to count issues by severity"""
    def _count(issues, severity=None):
        if severity is None:
            return len(issues)
        
        return len([i for i in issues if i.severity.value == severity or i.severity == severity])
    
    return _count


# ===== CLEANUP =====

@pytest.fixture(autouse=True)
def cleanup_test_artifacts(tmp_path):
    """Automatically cleanup test artifacts after each test"""
    yield
    
    # Clean up any test files
    if tmp_path.exists():
        import shutil
        try:
            shutil.rmtree(tmp_path)
        except Exception:
            pass


# ===== ASYNC SUPPORT =====

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ===== SKIP CONDITIONS =====

def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers"""
    
    # Skip API tests if SKIP_API_TESTS environment variable is set
    if os.getenv('SKIP_API_TESTS', 'false').lower() == 'true':
        skip_api = pytest.mark.skip(reason="API tests disabled via SKIP_API_TESTS")
        for item in items:
            if "api" in item.keywords:
                item.add_marker(skip_api)
    
    # Skip slow tests if running quick tests
    if os.getenv('QUICK_TESTS', 'false').lower() == 'true':
        skip_slow = pytest.mark.skip(reason="Slow tests disabled via QUICK_TESTS")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)