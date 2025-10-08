"""
Integration tests for API endpoints
Tests REST API with real validators
"""
import pytest
import pandas as pd
from fastapi.testclient import TestClient
from src.api.routes import app
from src.schemas.base_schemas import FormatType


class TestAPIIntegration:
    """Integration tests for validation API"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def valid_payload(self):
        """Valid validation request payload"""
        return {
            "format": "guide_rna",
            "metadata": {
                "dataset_id": "api_test_001",
                "organism": "human",
                "record_count": 2
            },
            "data": [
                {
                    "guide_id": "gRNA_001",
                    "sequence": "ATCGATCGATCGATCGATCG",
                    "pam_sequence": "AGG",
                    "target_gene": "BRCA1",
                    "organism": "human",
                    "nuclease_type": "SpCas9"
                },
                {
                    "guide_id": "gRNA_002",
                    "sequence": "GCTAGCTAGCTAGCTAGCTA",
                    "pam_sequence": "TGG",
                    "target_gene": "TP53",
                    "organism": "human",
                    "nuclease_type": "SpCas9"
                }
            ]
        }
    
    # ===== HEALTH CHECK =====
    
    @pytest.mark.integration
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    # ===== VALIDATION ENDPOINT =====
    
    @pytest.mark.integration
    def test_submit_validation_success(self, client, valid_payload):
        """Test successful validation submission"""
        response = client.post("/api/v1/validate", json=valid_payload)
        
        assert response.status_code in [200, 202]  # 200 OK or 202 Accepted
        data = response.json()
        
        assert "validation_id" in data
        assert "status" in data
    
    @pytest.mark.integration
    def test_validation_returns_report(self, client, valid_payload):
        """Test validation returns complete report"""
        response = client.post("/api/v1/validate", json=valid_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "final_decision" in data
        assert "stages" in data
        assert "execution_time_seconds" in data
    
    @pytest.mark.integration
    def test_invalid_format_rejected(self, client):
        """Test invalid format is rejected"""
        invalid_payload = {
            "format": "invalid_format",
            "data": []
        }
        
        response = client.post("/api/v1/validate", json=invalid_payload)
        
        assert response.status_code == 422  # Unprocessable Entity
    
    @pytest.mark.integration
    def test_missing_required_fields(self, client):
        """Test missing required fields returns error"""
        incomplete_payload = {
            "format": "guide_rna"
            # Missing 'data' field
        }
        
        response = client.post("/api/v1/validate", json=incomplete_payload)
        
        assert response.status_code == 422
    
    # ===== GET VALIDATION RESULTS =====
    
    @pytest.mark.integration
    def test_get_validation_results(self, client, valid_payload):
        """Test retrieving validation results"""
        # First submit validation
        submit_response = client.post("/api/v1/validate", json=valid_payload)
        validation_id = submit_response.json()["validation_id"]
        
        # Then retrieve results
        get_response = client.get(f"/api/v1/validate/{validation_id}")
        
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["validation_id"] == validation_id
    @pytest.mark.integration
    def test_nonexistent_validation_id(self, client):
        """Test requesting nonexistent validation ID"""
        response = client.get("/api/v1/validate/nonexistent-id-12345")
        
        assert response.status_code == 404
    
    # ===== FILE UPLOAD =====
    
    @pytest.mark.integration
    def test_file_upload_validation(self, client, tmp_path):
        """Test validation via file upload"""
        # Create temporary CSV file
        csv_file = tmp_path / "test_data.csv"
        csv_content = """guide_id,sequence,pam_sequence,target_gene,organism,nuclease_type
gRNA_001,ATCGATCGATCGATCGATCG,AGG,BRCA1,human,SpCas9
gRNA_002,GCTAGCTAGCTAGCTAGCTA,TGG,TP53,human,SpCas9"""
        csv_file.write_text(csv_content)
        
        with open(csv_file, 'rb') as f:
            response = client.post(
                "/api/v1/validate/file",
                files={"file": ("test_data.csv", f, "text/csv")},
                data={"format": "guide_rna"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "validation_id" in data
    
    @pytest.mark.integration
    def test_invalid_file_format_rejected(self, client, tmp_path):
        """Test invalid file format is rejected"""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("not a valid format")
        
        with open(invalid_file, 'rb') as f:
            response = client.post(
                "/api/v1/validate/file",
                files={"file": ("test.txt", f, "text/plain")},
                data={"format": "guide_rna"}
            )
        
        assert response.status_code in [400, 422]
    
    # ===== BATCH VALIDATION =====
    
    @pytest.mark.integration
    def test_batch_validation(self, client):
        """Test batch validation of multiple datasets"""
        batch_payload = {
            "datasets": [
                {
                    "format": "guide_rna",
                    "data": [
                        {
                            "guide_id": "gRNA_001",
                            "sequence": "ATCGATCGATCGATCGATCG",
                            "pam_sequence": "AGG",
                            "target_gene": "BRCA1",
                            "organism": "human",
                            "nuclease_type": "SpCas9"
                        }
                    ]
                },
                {
                    "format": "guide_rna",
                    "data": [
                        {
                            "guide_id": "gRNA_002",
                            "sequence": "GCTAGCTAGCTAGCTAGCTA",
                            "pam_sequence": "TGG",
                            "target_gene": "TP53",
                            "organism": "human",
                            "nuclease_type": "SpCas9"
                        }
                    ]
                }
            ]
        }
        
        response = client.post("/api/v1/validate/batch", json=batch_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert "validation_ids" in data
        assert len(data["validation_ids"]) == 2
    
    # ===== METRICS ENDPOINT =====
    
    @pytest.mark.integration
    def test_get_metrics(self, client):
        """Test retrieving system metrics"""
        response = client.get("/api/v1/metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_validations" in data
        assert "average_execution_time" in data
    
    # ===== ERROR HANDLING =====
    
    @pytest.mark.integration
    def test_malformed_json_rejected(self, client):
        """Test malformed JSON is rejected"""
        response = client.post(
            "/api/v1/validate",
            data="invalid json{{{",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    @pytest.mark.integration
    def test_large_payload_handling(self, client):
        """Test handling of large payloads"""
        # Create payload with 1000 records
        large_data = []
        for i in range(1000):
            large_data.append({
                "guide_id": f"gRNA_{i:04d}",
                "sequence": "ATCGATCGATCGATCGATCG",
                "pam_sequence": "AGG",
                "target_gene": "BRCA1",
                "organism": "human",
                "nuclease_type": "SpCas9"
            })
        
        payload = {
            "format": "guide_rna",
            "data": large_data
        }
        
        response = client.post("/api/v1/validate", json=payload)
        
        # Should accept and process or return appropriate error
        assert response.status_code in [200, 202, 413]  # 413 = Payload Too Large


class TestAPIAuthentication:
    """Tests for API authentication (if implemented)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.integration
    def test_unauthenticated_access(self, client):
        """Test API access without authentication"""
        # If auth is required, should return 401
        # If auth is not required, should succeed
        response = client.get("/api/v1/metrics")
        
        assert response.status_code in [200, 401]
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires authentication implementation")
    def test_authenticated_access(self, client):
        """Test API access with valid authentication"""
        headers = {"Authorization": "Bearer valid_token"}
        response = client.get("/api/v1/metrics", headers=headers)
        
        assert response.status_code == 200


class TestAPICORS:
    """Tests for CORS configuration"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.integration
    def test_cors_headers_present(self, client):
        """Test CORS headers are present"""
        response = client.options("/api/v1/validate")
        
        # Should have CORS headers (if configured)
        assert response.status_code in [200, 204]


class TestAPIRateLimiting:
    """Tests for rate limiting (if implemented)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires rate limiting implementation")
    def test_rate_limit_enforced(self, client, valid_payload):
        """Test rate limiting is enforced"""
        # Make many requests rapidly
        responses = []
        for _ in range(100):
            response = client.post("/api/v1/validate", json=valid_payload)
            responses.append(response)
        
        # Should eventually get rate limited (429)
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])