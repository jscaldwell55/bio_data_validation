# scripts/setup/init_dvc.py
"""Initialize DVC for data versioning"""
import subprocess
import os
from pathlib import Path

def setup_dvc():
    """Setup DVC tracking for datasets and models"""
    
    # Initialize DVC if not already done
    if not Path(".dvc").exists():
        subprocess.run(["dvc", "init"], check=True)
        print("✅ DVC initialized")
    
    # Track data directories
    data_dirs = [
        "data/raw",
        "data/processed",
        "data/validation_results",
        "config/validation_rules.yml",
        "config/policy_config.yml"
    ]
    
    for dir_path in data_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        dvc_file = f"{dir_path}.dvc"
        
        if not Path(dvc_file).exists():
            subprocess.run(["dvc", "add", dir_path], check=True)
            print(f"✅ Tracking {dir_path}")
    
    # Setup remote storage
    remote_url = os.getenv("DVC_REMOTE_URL", "s3://bio-validation-data/dvc-storage")
    subprocess.run(["dvc", "remote", "add", "-d", "storage", remote_url], check=True)
    
    print(f"✅ DVC setup complete")
    print(f"📦 Remote storage: {remote_url}")

if __name__ == "__main__":
    setup_dvc()