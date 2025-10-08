# scripts/metrics/push_to_mlflow.py
"""
Push validation metrics to MLflow.
"""
import argparse
import json
from pathlib import Path
import mlflow
import os


def push_metrics(metrics_file: Path, experiment_name: str):
    """
    Push metrics to MLflow.
    
    Args:
        metrics_file: Path to metrics JSON file
        experiment_name: MLflow experiment name
    """
    # Load metrics
    with open(metrics_file, 'r') as f:
        metrics = json.load(f)
    
    # Set MLflow tracking URI
    tracking_uri = os.getenv('MLFLOW_TRACKING_URI', 'http://localhost:5000')
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    
    # Start MLflow run
    with mlflow.start_run(run_name="data_quality_metrics"):
        # Log metrics
        mlflow.log_metric("total_datasets", metrics['total_datasets'])
        mlflow.log_metric("success_rate", metrics['success_rate'])
        mlflow.log_metric("avg_execution_time", metrics['avg_execution_time'])
        mlflow.log_metric("max_execution_time", metrics['max_execution_time'])
        mlflow.log_metric("records_processed", metrics['records_processed'])
        
        # Log decision counts
        for decision, count in metrics['decisions'].items():
            mlflow.log_metric(f"decision_{decision.lower()}", count)
        
        # Log issue counts
        for severity, count in metrics['issue_counts'].items():
            mlflow.log_metric(f"issues_{severity}", count)
        
        # Log stage metrics
        for stage_name, stage_metrics in metrics['stages'].items():
            mlflow.log_metric(f"{stage_name}_executed", stage_metrics['executed'])
            mlflow.log_metric(f"{stage_name}_passed", stage_metrics['passed'])
        
        # Log parameters
        mlflow.log_param("experiment_name", experiment_name)
        mlflow.log_param("timestamp", metrics.get('timestamp', 'N/A'))
        
        # Log metrics file as artifact
        mlflow.log_artifact(str(metrics_file))
        
        print(f"✓ Metrics pushed to MLflow experiment: {experiment_name}")
        print(f"  Run ID: {mlflow.active_run().info.run_id}")


def main():
    parser = argparse.ArgumentParser(description='Push metrics to MLflow')
    parser.add_argument('--metrics-file', type=str, required=True,
                        help='Path to metrics JSON file')
    parser.add_argument('--experiment-name', type=str, 
                        default='data-quality-pipeline',
                        help='MLflow experiment name')
    
    args = parser.parse_args()
    
    metrics_file = Path(args.metrics_file)
    
    if not metrics_file.exists():
        print(f"ERROR: Metrics file not found: {metrics_file}")
        return
    
    push_metrics(metrics_file, args.experiment_name)


if __name__ == "__main__":
    main()