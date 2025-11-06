"""
==============================================================================
MQ Summary Process Monitor
==============================================================================

This module implements monitoring for Market Quote Summary ETL processes.

MQ Summary processes are 4 sequential processes that form a pipeline:
1. MQ Load FCT_BID_ASK
2. MQ Load FCT_TRADE
3. MQ Load Summary
4. MQ Load Summary Part 2

This monitor tracks:
- Success/failure rates
- Sequential execution dependencies
- Data operations (inserts, updates, deletes)
- Execution order and timing gaps
- Message patterns

Developer Notes:
- Inherits from BaseProcessMonitor
- Designed for sequential pipeline processes
- Adds dependency checking unique to sequential workflows
- All thresholds are configurable via YAML

Author: ETL Monitoring Framework
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

from framework.base_monitor import (
    BaseProcessMonitor,
    MonitorResult,
    HealthStatus,
    AlertLevel,
    CheckType,
    ThresholdEvaluator
)


class MQSummaryMonitor(BaseProcessMonitor):
    """
    Monitor for MQ Summary ETL processes.

    This class monitors 4 sequential MQ processes, checking for:
    - Process failures
    - Pipeline execution order
    - Time gaps between sequential processes
    - Data operation volumes (inserts/updates/deletes)
    - Delete-to-insert ratios

    Configuration is loaded from monitor_config.yaml under 'processes.mq_summary'
    """

    def __init__(self, config: Dict[str, Any], db_connection: Any,
                 logger: Optional[logging.Logger] = None):
        """Initialize MQ Summary Monitor."""
        super().__init__(config, db_connection, logger)

        # Extract MQ-specific configuration
        self.dependencies = config.get('dependencies', {})
        self.operation_thresholds = config.get('operation_thresholds', {})
        self.frequency_thresholds = config.get('frequency_thresholds', {})
        self.success_thresholds = config.get('success_thresholds', {})
        self.message_thresholds = config.get('message_thresholds', {})

        self.logger.info(
            f"Initialized MQSummaryMonitor for {len(self.process_ids)} processes"
        )

    def get_process_data(self, lookback_days: int) -> pd.DataFrame:
        """
        Retrieve MQ Summary process data from database.

        Args:
            lookback_days: Number of days of history to retrieve

        Returns:
            DataFrame with process log data

        Developer Notes:
        - Queries the PROCESS_LOG_MQ_SUMMARY table
        - Filters for configured process IDs
        - Returns all columns needed for analysis
        - For production: Replace with actual cx_Oracle query
        """
        self.logger.debug(f"Fetching data for last {lookback_days} days")

        # For demonstration, we'll use the Excel file as a mock data source
        # In production, this would be a database query

        try:
            # Mock: Read from Excel file (replace with DB query in production)
            df = pd.read_excel(
                self.db_connection,  # Using file path as mock connection
                sheet_name='Process_Log_MQ_Summary_2023'
            )

            # Filter for lookback period
            cutoff_date = datetime.now() - timedelta(days=lookback_days)
            df = df[df['PROCESS_DATE'] >= cutoff_date]

            # Filter for configured process IDs
            if self.process_ids:
                df = df[df['PROCESS_ID'].isin(self.process_ids)]

            self.logger.info(f"Retrieved {len(df)} records")
            return df

        except Exception as e:
            self.logger.error(f"Error retrieving data: {e}", exc_info=True)
            return pd.DataFrame()

    def check_failure_rate(self) -> MonitorResult:
        """
        Check the success/failure rate of MQ Summary processes.

        Analyzes:
        - Overall success rate across all processes
        - Per-process success rates (especially critical for pipeline)
        - Recent failures (last 2 days)
        - Consecutive failure patterns

        Returns:
            MonitorResult with success rate assessment
        """
        self.logger.debug("Checking failure rate")

        df = self._get_cached_data(
            lookback_days=self.config.get('monitoring', {}).get('lookback_days', 90)
        )

        if df.empty:
            return MonitorResult(
                check_type=CheckType.SUCCESS_RATE,
                check_name="Success Rate Check",
                status=HealthStatus.UNKNOWN,
                score=50.0,
                alert_level=AlertLevel.INFO,
                message="No data available for success rate analysis"
            )

        # Calculate overall success rate
        total_executions = len(df[df['STATUS'].notna()])
        if total_executions < self.success_thresholds.get('min_sample_size', 10):
            return MonitorResult(
                check_type=CheckType.SUCCESS_RATE,
                check_name="Success Rate Check",
                status=HealthStatus.UNKNOWN,
                score=50.0,
                alert_level=AlertLevel.INFO,
                message=f"Insufficient data: {total_executions} executions"
            )

        completed = len(df[df['STATUS'] == 'COMPLETED'])
        failed = len(df[df['STATUS'] == 'FAILED'])
        success_rate = (completed / total_executions * 100) if total_executions > 0 else 0

        # Evaluate against thresholds (stricter for MQ processes)
        warning_threshold = self.success_thresholds.get('warning_rate', 98.0)
        critical_threshold = self.success_thresholds.get('critical_rate', 95.0)

        status, alert_level, message = ThresholdEvaluator.evaluate_percentage(
            success_rate,
            warning_threshold,
            critical_threshold,
            higher_is_better=True
        )

        # Check for consecutive failures
        consecutive_failures = self._check_consecutive_failures(df)
        max_consecutive = self.message_thresholds.get('consecutive_failures_critical', 2)

        if consecutive_failures >= max_consecutive:
            status = HealthStatus.CRITICAL
            alert_level = AlertLevel.CRITICAL
            message = f"CRITICAL: {consecutive_failures} consecutive failures detected"

        # Calculate score (success rate maps directly to score)
        score = success_rate

        # Per-process breakdown (critical for pipeline)
        process_breakdown = df.groupby('PROCESS_NAME')['STATUS'].apply(
            lambda x: {
                'total': len(x),
                'completed': (x == 'COMPLETED').sum(),
                'failed': (x == 'FAILED').sum(),
                'rate': (x == 'COMPLETED').sum() / len(x) * 100 if len(x) > 0 else 0
            }
        ).to_dict()

        # Identify processes with issues
        problem_processes = [
            name for name, stats in process_breakdown.items()
            if stats['rate'] < warning_threshold
        ]

        # Check if early pipeline processes are failing (more critical)
        pipeline_order = self.dependencies.get('pipeline_order', [])
        early_failures = []
        for process_id in pipeline_order[:2]:  # First 2 processes are most critical
            process_name = self._get_process_name(process_id)
            if process_name in problem_processes:
                early_failures.append(process_name)

        if early_failures:
            alert_level = AlertLevel.CRITICAL
            status = HealthStatus.CRITICAL

        details = {
            'overall_success_rate': round(success_rate, 2),
            'total_executions': total_executions,
            'completed': completed,
            'failed': failed,
            'consecutive_failures': consecutive_failures,
            'process_breakdown': process_breakdown,
            'problem_processes': problem_processes,
            'early_pipeline_failures': early_failures
        }

        return MonitorResult(
            check_type=CheckType.SUCCESS_RATE,
            check_name="Success Rate Check",
            status=status,
            score=score,
            alert_level=alert_level,
            message=f"Success rate: {success_rate:.1f}% " +
                   (f"- Pipeline issues: {', '.join(early_failures)}"
                    if early_failures else ""),
            details=details
        )

    def check_execution_frequency(self) -> MonitorResult:
        """
        Check if MQ Summary processes are executing at expected frequency.

        Analyzes:
        - Runs per day (should be ~1.0-2.0 for daily processes, allowing reruns)
        - Coverage percentage (% of expected days with runs)
        - Missing runs (consecutive days without execution)

        Returns:
            MonitorResult with frequency assessment
        """
        self.logger.debug("Checking execution frequency")

        df = self._get_cached_data(
            lookback_days=self.config.get('monitoring', {}).get('lookback_days', 90)
        )

        if df.empty:
            return MonitorResult(
                check_type=CheckType.FREQUENCY_MONITORING,
                check_name="Execution Frequency Check",
                status=HealthStatus.UNKNOWN,
                score=50.0,
                alert_level=AlertLevel.INFO,
                message="No data available for frequency analysis"
            )

        # Calculate frequency metrics
        date_range_days = (df['PROCESS_DATE'].max() - df['PROCESS_DATE'].min()).days + 1
        unique_dates = df['PROCESS_DATE'].nunique()
        unique_executions = df['EXECUTION_ID'].nunique()

        coverage_pct = (unique_dates / date_range_days * 100) if date_range_days > 0 else 0
        runs_per_active_day = (unique_executions / unique_dates) if unique_dates > 0 else 0

        # Check for missing runs (recent)
        recent_days = self.config.get('monitoring', {}).get('recent_days', 2)
        recent_cutoff = datetime.now() - timedelta(days=recent_days)
        recent_data = df[df['PROCESS_DATE'] >= recent_cutoff]
        has_recent_runs = len(recent_data) > 0

        # Evaluate against thresholds
        min_coverage = self.frequency_thresholds.get('min_coverage_percentage', 65.0)
        min_runs_per_day = self.frequency_thresholds.get('min_runs_per_day', 0.9)
        max_runs_per_day = self.frequency_thresholds.get('max_runs_per_day', 2.0)

        # Determine status
        issues = []

        if not has_recent_runs:
            status = HealthStatus.CRITICAL
            alert_level = AlertLevel.CRITICAL
            issues.append(f"No executions in last {recent_days} days")
        elif coverage_pct < min_coverage:
            status = HealthStatus.FAIR
            alert_level = AlertLevel.WARNING
            issues.append(f"Low coverage: {coverage_pct:.1f}% < {min_coverage}%")
        elif runs_per_active_day < min_runs_per_day or runs_per_active_day > max_runs_per_day:
            status = HealthStatus.FAIR
            alert_level = AlertLevel.WARNING
            issues.append(f"Unusual frequency: {runs_per_active_day:.2f} runs/day")
        else:
            status = HealthStatus.EXCELLENT
            alert_level = AlertLevel.INFO
            issues.append("Executing at expected frequency")

        # Calculate score
        coverage_score = min(100, coverage_pct / min_coverage * 100)
        frequency_score = 100 if (min_runs_per_day <= runs_per_active_day <= max_runs_per_day) else 70
        score = (coverage_score * 0.6 + frequency_score * 0.4)

        details = {
            'coverage_percentage': round(coverage_pct, 2),
            'runs_per_day': round(runs_per_active_day, 2),
            'unique_dates': unique_dates,
            'unique_executions': unique_executions,
            'date_range_days': date_range_days,
            'has_recent_runs': has_recent_runs,
            'expected_min_coverage': min_coverage
        }

        message = " | ".join(issues)

        return MonitorResult(
            check_type=CheckType.FREQUENCY_MONITORING,
            check_name="Execution Frequency Check",
            status=status,
            score=score,
            alert_level=alert_level,
            message=message,
            details=details
        )

    def check_data_volume(self) -> MonitorResult:
        """
        Check for data operation volume anomalies.

        Analyzes:
        - Rows inserted, updated, deleted
        - Delete-to-insert ratios (high deletes may indicate issues)
        - Recent volumes compared to baseline

        Returns:
            MonitorResult with data operation assessment
        """
        self.logger.debug("Checking data volumes")

        df = self._get_cached_data(
            lookback_days=self.config.get('monitoring', {}).get('lookback_days', 90)
        )

        if df.empty:
            return MonitorResult(
                check_type=CheckType.VOLUME_ANOMALY,
                check_name="Data Operation Check",
                status=HealthStatus.UNKNOWN,
                score=50.0,
                alert_level=AlertLevel.INFO,
                message="No data available for volume analysis"
            )

        # Analyze each operation type
        operations = ['Rows Inserted', 'Rows Updated', 'Rows Deleted']
        operation_stats = {}
        issues = []

        for operation in operations:
            # Extract data for this operation
            op_data = df[df['STAT_VALUE_NAME_1'] == operation]['STAT_VALUE_1']

            # Convert to numeric (handle mixed types)
            op_data_numeric = pd.to_numeric(op_data, errors='coerce').dropna()

            if len(op_data_numeric) > 5:
                baseline_median = op_data_numeric.median()
                baseline_mean = op_data_numeric.mean()

                # Get recent data
                recent_cutoff = datetime.now() - timedelta(days=2)
                recent_df = df[df['PROCESS_DATE'] >= recent_cutoff]
                recent_op = recent_df[recent_df['STAT_VALUE_NAME_1'] == operation]['STAT_VALUE_1']
                recent_op_numeric = pd.to_numeric(recent_op, errors='coerce').dropna()

                recent_avg = recent_op_numeric.mean() if len(recent_op_numeric) > 0 else 0

                operation_stats[operation] = {
                    'baseline_median': int(baseline_median),
                    'baseline_mean': int(baseline_mean),
                    'recent_average': int(recent_avg),
                    'percent_change': ((recent_avg - baseline_median) / baseline_median * 100)
                                     if baseline_median > 0 else 0
                }

        # Check delete-to-insert ratio
        inserts_recent = operation_stats.get('Rows Inserted', {}).get('recent_average', 0)
        deletes_recent = operation_stats.get('Rows Deleted', {}).get('recent_average', 0)

        if inserts_recent > 0:
            delete_insert_ratio = deletes_recent / inserts_recent
            warning_ratio = self.operation_thresholds.get('delete_insert_ratio', {}).get('warning_ratio', 2.0)
            critical_ratio = self.operation_thresholds.get('delete_insert_ratio', {}).get('critical_ratio', 5.0)

            if delete_insert_ratio > critical_ratio:
                status = HealthStatus.CRITICAL
                alert_level = AlertLevel.CRITICAL
                issues.append(f"Critical: Deletes {delete_insert_ratio:.1f}x inserts")
            elif delete_insert_ratio > warning_ratio:
                status = HealthStatus.FAIR
                alert_level = AlertLevel.WARNING
                issues.append(f"Warning: Deletes {delete_insert_ratio:.1f}x inserts")
            else:
                status = HealthStatus.EXCELLENT
                alert_level = AlertLevel.INFO
                issues.append(f"Delete/insert ratio normal ({delete_insert_ratio:.1f})")
        else:
            status = HealthStatus.UNKNOWN
            alert_level = AlertLevel.WARNING
            issues.append("No recent insert data")
            delete_insert_ratio = 0

        # Check for significant drops in inserts
        inserts_pct_change = operation_stats.get('Rows Inserted', {}).get('percent_change', 0)
        if inserts_pct_change < -50:
            status = HealthStatus.FAIR
            alert_level = AlertLevel.WARNING
            issues.append(f"Insert volume down {abs(inserts_pct_change):.0f}%")

        # Calculate score
        if status == HealthStatus.EXCELLENT:
            score = 100.0
        elif status == HealthStatus.FAIR:
            score = 70.0
        elif status == HealthStatus.CRITICAL:
            score = 30.0
        else:
            score = 50.0

        details = {
            'operation_stats': operation_stats,
            'delete_insert_ratio': round(delete_insert_ratio, 2)
        }

        message = " | ".join(issues) if issues else "Data operations normal"

        return MonitorResult(
            check_type=CheckType.VOLUME_ANOMALY,
            check_name="Data Operation Check",
            status=status,
            score=score,
            alert_level=alert_level,
            message=message,
            details=details
        )

    def check_dependency_integrity(self) -> Optional[MonitorResult]:
        """
        Check sequential pipeline execution integrity.

        Analyzes:
        - Whether processes execute in correct order
        - Time gaps between sequential processes
        - Missing processes in pipeline
        - Orphaned downstream processes (upstream failed)

        Returns:
            MonitorResult with dependency assessment
        """
        if not self.dependencies.get('enabled', False):
            return None

        self.logger.debug("Checking pipeline dependencies")

        df = self._get_cached_data(
            lookback_days=self.config.get('monitoring', {}).get('lookback_days', 90)
        )

        if df.empty:
            return None

        pipeline_order = self.dependencies.get('pipeline_order', [])
        max_gap_minutes = self.dependencies.get('max_time_gap_minutes', 60)

        # Group by execution date and check order
        issues = []
        pipeline_violations = 0

        # Get recent executions
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_df = df[df['PROCESS_DATE'] >= recent_cutoff]

        # Group by process date
        for process_date, date_group in recent_df.groupby('PROCESS_DATE'):
            # Get unique processes that ran
            processes_run = date_group['PROCESS_ID'].unique()

            # Check if all pipeline processes ran
            missing_processes = [pid for pid in pipeline_order if pid not in processes_run]

            if missing_processes:
                missing_names = [self._get_process_name(pid) for pid in missing_processes]
                issues.append(f"{process_date.date()}: Missing {', '.join(missing_names)}")
                pipeline_violations += 1

            # Check execution order (by start time)
            if len(processes_run) > 1:
                process_times = date_group.groupby('PROCESS_ID')['START_TIME'].min().sort_values()
                actual_order = process_times.index.tolist()

                # Check if actual order matches expected order
                expected_subset = [pid for pid in pipeline_order if pid in actual_order]
                if actual_order != expected_subset:
                    issues.append(f"{process_date.date()}: Out of order execution")
                    pipeline_violations += 1

        # Determine status
        if pipeline_violations == 0:
            status = HealthStatus.EXCELLENT
            alert_level = AlertLevel.INFO
            score = 100.0
            message = "Pipeline executing in correct order"
        elif pipeline_violations <= 2:
            status = HealthStatus.FAIR
            alert_level = AlertLevel.WARNING
            score = 70.0
            message = f"{pipeline_violations} pipeline violations in last 7 days"
        else:
            status = HealthStatus.CRITICAL
            alert_level = AlertLevel.CRITICAL
            score = 30.0
            message = f"{pipeline_violations} pipeline violations - investigate dependencies"

        details = {
            'pipeline_order': [self._get_process_name(pid) for pid in pipeline_order],
            'violations': pipeline_violations,
            'issues': issues[:10]  # Limit to 10 most recent
        }

        return MonitorResult(
            check_type=CheckType.DEPENDENCY_CHECK,
            check_name="Pipeline Dependency Check",
            status=status,
            score=score,
            alert_level=alert_level,
            message=message,
            details=details
        )

    def check_message_patterns(self) -> Optional[MonitorResult]:
        """
        Check message type patterns for anomalies.

        Returns:
            MonitorResult with message analysis
        """
        self.logger.debug("Checking message patterns")

        df = self._get_cached_data(
            lookback_days=self.config.get('monitoring', {}).get('lookback_days', 90)
        )

        if df.empty or 'MESSAGE_TYPE' not in df.columns:
            return None

        # Count message types
        total_messages = len(df)
        error_count = len(df[df['MESSAGE_TYPE'] == 'ERROR'])
        warning_count = len(df[df['MESSAGE_TYPE'] == 'WARNING'])

        error_pct = (error_count / total_messages * 100) if total_messages > 0 else 0
        warning_pct = (warning_count / total_messages * 100) if total_messages > 0 else 0

        # Evaluate against thresholds (stricter for MQ)
        max_error_pct = self.message_thresholds.get('max_error_percentage', 0.5)
        max_warning_pct = self.message_thresholds.get('max_warning_percentage', 3.0)

        issues = []
        if error_pct > max_error_pct:
            issues.append(f"{error_count} ERROR messages ({error_pct:.1f}%)")
        if warning_pct > max_warning_pct:
            issues.append(f"{warning_count} WARNING messages ({warning_pct:.1f}%)")

        if issues:
            status = HealthStatus.FAIR
            alert_level = AlertLevel.WARNING
            score = max(50, 100 - (error_pct * 20 + warning_pct * 3))
            message = "High error/warning rate: " + ", ".join(issues)
        else:
            status = HealthStatus.EXCELLENT
            alert_level = AlertLevel.INFO
            score = 100.0
            message = f"Message patterns normal: {error_count} errors, {warning_count} warnings"

        details = {
            'total_messages': total_messages,
            'error_count': error_count,
            'warning_count': warning_count,
            'error_percentage': round(error_pct, 2),
            'warning_percentage': round(warning_pct, 2),
            'message_distribution': df['MESSAGE_TYPE'].value_counts().to_dict()
        }

        return MonitorResult(
            check_type=CheckType.MESSAGE_ANALYSIS,
            check_name="Message Pattern Check",
            status=status,
            score=score,
            alert_level=alert_level,
            message=message,
            details=details
        )

    def calculate_health_score(self) -> 'HealthScore':
        """
        Calculate overall health score including dependency checks.

        Overrides base class to add dependency checking specific to MQ processes.
        """
        from framework.base_monitor import HealthScore

        # Get base health score
        health_score = super().calculate_health_score()

        # Add dependency check if enabled
        if self.dependencies.get('enabled', False):
            try:
                dep_result = self.check_dependency_integrity()
                if dep_result:
                    health_score.checks.append(dep_result)
                    health_score.component_scores['dependency_integrity'] = dep_result.score

                    # Recalculate overall score with dependency
                    weights = self.config.get('health_weights', {})
                    overall_score = self._calculate_weighted_score(
                        health_score.component_scores,
                        weights
                    )
                    health_score.overall_score = overall_score
                    health_score.overall_status = self._score_to_status(overall_score)

                    if dep_result.alert_level in [AlertLevel.WARNING, AlertLevel.CRITICAL]:
                        health_score.alerts.append(dep_result.message)
            except Exception as e:
                self.logger.error(f"Error in dependency check: {e}", exc_info=True)

        return health_score

    def _check_consecutive_failures(self, df: pd.DataFrame) -> int:
        """Check for consecutive failures in recent runs."""
        df_sorted = df.sort_values('PROCESS_DATE', ascending=False)
        recent_executions = df_sorted.groupby('EXECUTION_ID')['STATUS'].first().head(10)

        consecutive = 0
        for status in recent_executions:
            if status == 'FAILED':
                consecutive += 1
            else:
                break

        return consecutive

    def _get_process_name(self, process_id: int) -> str:
        """Get process name from process ID."""
        if process_id in self.process_ids:
            idx = self.process_ids.index(process_id)
            if idx < len(self.process_names):
                return self.process_names[idx]
        return f"Process {process_id}"
