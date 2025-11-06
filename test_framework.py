#!/usr/bin/env python3
"""
Test script for ETL Process Health Monitoring Framework

This script performs a single monitoring cycle to test the framework.
Use this to verify the framework is working correctly before deploying.

Usage:
    python test_framework.py
"""

import sys
import logging
from pathlib import Path

# Add framework to path
sys.path.insert(0, str(Path(__file__).parent))

from framework.monitor_service import MonitorService


def test_single_cycle():
    """Run a single monitoring cycle for testing."""

    print("=" * 80)
    print("ETL Process Health Monitoring Framework - Test")
    print("=" * 80)
    print()

    # Check config file exists
    config_file = 'monitor_config.yaml'
    if not Path(config_file).exists():
        print(f"ERROR: Configuration file not found: {config_file}")
        return False

    print(f"✓ Configuration file found: {config_file}")
    print()

    try:
        # Initialize service
        print("Initializing service...")
        service = MonitorService(config_file)
        print(f"✓ Service initialized with {len(service.monitors)} monitors")
        print()

        # Run one monitoring cycle
        print("Running monitoring cycle...")
        health_scores = service._run_monitoring_cycle()

        if not health_scores:
            print("WARNING: No health scores generated")
            return False

        print(f"✓ Monitoring cycle completed")
        print()

        # Display results
        print("=" * 80)
        print("RESULTS")
        print("=" * 80)
        print()

        for health_score in health_scores:
            print(f"Process Group: {health_score.process_name}")
            print(f"  Overall Score: {health_score.overall_score:.2f}")
            print(f"  Status: {health_score.overall_status.value}")
            print(f"  Components:")
            for component, score in health_score.component_scores.items():
                print(f"    - {component}: {score:.2f}")

            if health_score.alerts:
                print(f"  Alerts ({len(health_score.alerts)}):")
                for alert in health_score.alerts:
                    print(f"    ⚠ {alert}")
            else:
                print("  ✓ No alerts")
            print()

        # Generate outputs
        print("Generating output files...")
        service._generate_outputs(health_scores)

        # Check output files
        output_files = [
            'output/process_health.xml',
            'output/process_health_detailed.xml',
            'output/process_health.json'
        ]

        print()
        print("Output files:")
        for file_path in output_files:
            if Path(file_path).exists():
                size = Path(file_path).stat().st_size
                print(f"  ✓ {file_path} ({size:,} bytes)")
            else:
                print(f"  ✗ {file_path} (not found)")

        print()
        print("=" * 80)
        print("TEST PASSED")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Review output files in ./output/")
        print("  2. Import process_health.xml into Power BI")
        print("  3. Start the service: python framework/monitor_service.py")
        print()

        return True

    except Exception as e:
        print()
        print("=" * 80)
        print("TEST FAILED")
        print("=" * 80)
        print()
        print(f"Error: {e}")
        print()
        print("Check logs/process_monitor.log for details")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_single_cycle()
    sys.exit(0 if success else 1)
