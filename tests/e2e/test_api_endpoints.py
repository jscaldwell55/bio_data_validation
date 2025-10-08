"""
End-to-end tests for API endpoints
Tests complete API workflows from client perspective
"""
import pytest
import time
from fastapi.testclient import TestClient
from src.api.routes import app


class TestAPIEndToEnd:
    """End-to-end API tests"""
    
    @pytest.fixture
    def client(self):
        """Create API test client"""
        return TestClient(app)
    
    # ===== COMPLETE API WORKFLOWS =====
    
    @pytest.mark.e2e
    def test_complete_validation_workflow_via_api(self, client):
        """Test complete validation workflow through API"""
        # Step 1: Submit validation request
        payload = {
            "format": "guide_rna",
            "metadata": {
                "dataset_id": "api_e2e_001",
                "organism": "human"
            },
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
        }
        
        submit_response = client.post("/api/v1/validate", json=payload)
        assert submit_response.status_code == 200
        
        validation_id = submit_response.json()["validation_id"]
        
        # Step 2: Poll for results (if async)
        max_attempts = 10
        for _ in range(max_attempts):
            status_response = client.get(f"/api/v1/validate/{validation_id}")
            if status_response.status_code == 200:
                data = status_response.json()
                if data.get("status") == "completed":
                    break
            time.sleep(0.5)
        
        # Step 3: Verify final results
        final_response = client.get(f"/api/v1/validate/{validation_id}")
        assert final_response.status_code == 200
        
        result = final_response.json()
        assert "final_decision" in result
        assert "stages" in result
    
    @pytest.mark.e2e
    def test_file_upload_to_results_workflow(self, client, tmp_path):
        """Test complete file upload workflow"""
        # Step 1: Create CSV file
        csv_file = tmp_path / "upload_test.csv"
        csv_content = """guide_id,sequence,pam_sequence,target_gene,organism,nuclease_type
gRNA_001,ATCGATCGATCGATCGATCG,AGG,BRCA1,human,SpCas9
gRNA_002,GCTAGCTAGCTAGCTAGCTA,TGG,TP53,human,SpCas9
gRNA_003,GATTACAGATTACAGATTAC,CGG,EGFR,human,SpCas9"""
        csv_file.write_text(csv_content)
        
        # Step 2: Upload file
        with open(csv_file, 'rb') as f:
            upload_response = client.post(
                "/api/v1/validate/file",
                files={"file": ("test.csv", f, "text/csv")},
                data={"format": "guide_rna"}
            )
        
        assert upload_response.status_code == 200
        validation_id = upload_response.json()["validation_id"]
        
        # Step 3: Get results
        results_response = client.get(f"/api/v1/validate/{validation_id}")
        assert results_response.status_code == 200
        
        # Step 4: Download report (if available)
        report_response = client.get(f"/api/v1/validate/{validation_id}/report")
        assert report_response.status_code in [200, 404]  # May not have report endpoint
    
    @pytest.mark.e2e
    def test_batch_validation_workflow(self, client):
        """Test batch validation workflow"""
        # Submit batch
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
        
        batch_response = client.post("/api/v1/validate/batch", json=batch_payload)
        assert batch_response.status_code == 200
        
        batch_data = batch_response.json()
        assert "batch_id" in batch_data
        assert "validation_ids" in batch_data
        assert len(batch_data["validation_ids"]) == 2
        
        # Check each validation
        for val_id in batch_data["validation_ids"]:
            result_response = client.get(f"/api/v1/validate/{val_id}")
            assert result_response.status_code == 200
    
    # ===== ERROR HANDLING WORKFLOWS =====
    
    @pytest.mark.e2e
    def test_invalid_data_error_workflow(self, client):
        """Test complete error handling workflow"""
        # Submit invalid data
        invalid_payload = {
            "format": "guide_rna",
            "data": [
                {
                    "guide_id": "gRNA_001",
                    "sequence": "INVALID123",  # Invalid
                    "pam_sequence": "XYZ",  # Invalid
                    "target_gene": "",  # Missing
                    "organism": "human",
                    "nuclease_type": "SpCas9"
                }
            ]
        }
        
        response = client.post("/api/v1/validate", json=invalid_payload)
        assert response.status_code == 200  # Accepts request
        
        data = response.json()
        
        # Should report validation failure
        if "final_decision" in data:
            assert data["final_decision"] == "REJECTED"
    
    # ===== CONCURRENT REQUEST HANDLING =====
    
    @pytest.mark.e2e
    def test_concurrent_validation_requests(self, client):
        """Test handling multiple concurrent requests"""
        import concurrent.futures
        
        def submit_validation(index):
            payload = {
                "format": "guide_rna",
                "metadata": {"dataset_id": f"concurrent_{index:03d}"},
                "data": [
                    {
                        "guide_id": f"gRNA_{index:03d}",
                        "sequence": "ATCGATCGATCGATCGATCG",
                        "pam_sequence": "AGG",
                        "target_gene": "BRCA1",
                        "organism": "human",
                        "nuclease_type": "SpCas9"
                    }
                ]
            }
            response = client.post("/api/v1/validate", json=payload)
            return response.status_code, response.json()
        
        # Submit 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(submit_validation, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        for status_code, data in results:
            assert status_code == 200
            assert "validation_id" in data
    
    # ===== METRICS AND MONITORING =====
    
    @pytest.mark.e2e
    def test_metrics_update_after_validation(self, client):
        """Test that metrics are updated after validations"""
        # Get initial metrics
        initial_response = client.get("/api/v1/metrics")
        initial_metrics = initial_response.json()
        initial_count = initial_metrics.get("total_validations", 0)
        
        # Submit validation
        payload = {
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
        }
        client.post("/api/v1/validate", json=payload)
        
        # Get updated metrics
        updated_response = client.get("/api/v1/metrics")
        updated_metrics = updated_response.json()
        updated_count = updated_metrics.get("total_validations", 0)
        
        # Count should increase
        assert updated_count > initial_count


class TestAPIPerformance:
    """API performance tests"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_api_response_time(self, client):
        """Test API response time for small dataset"""
        payload = {
            "format": "guide_rna",
            "data": [
                {
                    "guide_id": f"gRNA_{i:03d}",
                    "sequence": "ATCGATCGATCGATCGATCG",
                    "pam_sequence": "AGG",
                    "target_gene": "BRCA1",
                    "organism": "human",
                    "nuclease_type": "SpCas9"
                }
                for i in range(100)
            ]
        }
        
        start = time.time()
        response = client.post("/api/v1/validate", json=payload)
        duration = time.time() - start
        
        assert response.status_code == 200
        # Should respond quickly for 100 records
        assert duration < 10.0
    
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_large_payload_handling(self, client):
        """Test handling of large payloads"""
        # Create 1000 record payload
        large_payload = {
            "format": "guide_rna",
            "data": [
                {
                    "guide_id": f"gRNA_{i:04d}",
                    "sequence": "ATCGATCGATCGATCGATCG",
                    "pam_sequence": "AGG",
                    "target_gene": "BRCA1",
                    "organism": "human",
                    "nuclease_type": "SpCas9"
                }
                for i in range(1000)
            ]
        }
        
        response = client.post("/api/v1/validate", json=large_payload)
        
        # Should either accept or return appropriate error
        assert response.status_code in [200, 202, 413]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])