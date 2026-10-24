"""Convenient CONTROLLED fixture only; never label this IBM evaluation."""
from pathlib import Path
from src.pipeline import FinancialCrimeDetectionPipeline

if __name__ == "__main__":
    file = Path(__file__).parent / "data" / "controlled_test_fixture.csv"
    result = FinancialCrimeDetectionPipeline(enable_cycle_detector=True).run_from_csv(str(file))
    print("TEAM-CREATED CONTROLLED DEMONSTRATION (NOT AN OFFICIAL IBM BENCHMARK)")
    print(result.public_summary())
    for alert in result.alerts:
        print(alert.alert_id, alert.detector, alert.transaction_ids, alert.reason)
