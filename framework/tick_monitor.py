"""
==============================================================================
Tick File Process Monitor
==============================================================================

This module implements monitoring for Tick File ETL processes.

Tick file processes are 9 parallel processes (Tick1-Tick9) that process
market tick data files daily. This monitor tracks:
- Success/failure rates
- Execution frequency (should run daily on weekdays)
- Data volume (inserted records, file sizes)
- Pre/post processing completion
- Message patterns (ERROR, WARNING counts)

Developer Notes:
- Inherits from BaseProcessMonitor
- Designed for 9 parallel independent processes
- Uses pandas for data analysis
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


class TickFileMonitor(BaseProcessMonitor):
    """
    Monitor for Tick File ETL processes.

    This class monitors 9 parallel tick file processes, checking for:
    - Process failures
    - Missing executions
    - Data volume anomalies
    - File size deviations
    - Pre/post processing completeness

    Configuration is loaded from monitor_config.yaml under 'processes.tick_files'
    """

    def __init__(self, config: Dict[str, Any], db_connection: Any,
                 logger: Optional[logging.Logger] = None):
        """Initialize Tick File Monitor."""
        super().__init__(config, db_connection, logger)

        # Extract tick-specific configuration
        self.volume_thresholds = config.get('volume_thresholds', {})
        self.file_size_thresholds = config.get('file_size_thresholds', {})
        self.frequency_thresholds = config.get('frequency_thresholds', {})
        self.success_thresholds = config.get('success_thresholds', {})
        self.message_thresholds = config.get('message_thresholds', {})
        self.preprocessing_checks = config.get('preprocessing_checks', {})

        self.logger.info(
            f"Initialized TickFileMonitor for {len(self.process_ids)} processes"
        )

    def get_process_data(self, lookback_days: int) -> pd.DataFrame:
        """
        Retrieve tick file process data from database.

        Args:
            lookback_days: Number of days of history to retrieve

        Returns:
            DataFrame with process log data

        Developer Notes:
        - Queries the PROCESS_LOG_TICKS table
        - Filters for configured process IDs
        - Returns all columns needed for analysis
        - For production: Replace with actual cx_Oracle query
        """
        self.logger.debug(f"Fetching data for last {lookback_days} days")

        # For demonstration, we'll use the Excel file as a mock data source
        # In production, this would be a database query like:
        #
        # query = f"""
        #     SELECT *
        #     FROM {self.table_name}
        #     WHERE PROCESS_DATE >= SYSDATE - {lookback_days}
        #       AND PROCESS_ID IN ({','.join(map(str, self.process_ids))})
        #     ORDER BY PROCESS_DATE DESC, START_TIME DESC
        # """
        # df = pd.read_sql(query, self.db_connection)

        try:
            # Mock: Read from Excel file (replace with DB query in production)
            df = pd.read_excel(
                self.db_connection,  # Using file path as mock connection
                sheet_name='Process_Log_TICKS_2023'
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
        Check the success/failure rate of tick file processes.

        Analyzes:
        - Overall success rate across all processes
        - Per-process success rates
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

        # Evaluate against thresholds
        warning_threshold = self.success_thresholds.get('warning_rate', 95.0)
        critical_threshold = self.success_thresholds.get('critical_rate', 90.0)

        status, alert_level, message = ThresholdEvaluator.evaluate_percentage(
            success_rate,
            warning_threshold,
            critical_threshold,
            higher_is_better=True
        )

        # Check for consecutive failures
        consecutive_failures = self._check_consecutive_failures(df)
        max_consecutive = self.message_thresholds.get('consecutive_failures_critical', 3)

        if consecutive_failures >= max_consecutive:
            status = HealthStatus.CRITICAL
            alert_level = AlertLevel.CRITICAL
            message = f"CRITICAL: {consecutive_failures} consecutive failures detected"

        # Calculate score (success rate maps directly to score)
        score = success_rate

        # Per-process breakdown
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

        details = {
            'overall_success_rate': round(success_rate, 2),
            'total_executions': total_executions,
            'completed': completed,
            'failed': failed,
            'consecutive_failures': consecutive_failures,
            'process_breakdown': process_breakdown,
            'problem_processes': problem_processes
        }

        return MonitorResult(
            check_type=CheckType.SUCCESS_RATE,
            check_name="Success Rate Check",
            status=status,
            score=score,
            alert_level=alert_level,
            message=f"Success rate: {success_rate:.1f}% " +
                   (f"- {len(problem_processes)} processes below threshold"
                    if problem_processes else ""),
            details=details
        )

    def check_execution_frequency(self) -> MonitorResult:
        """
        Check if tick file processes are executing at expected frequency.

        Analyzes:
        - Runs per day (should be ~1.0 for daily processes)
        - Coverage percentage (% of expected days with runs)
        - Missing runs (consecutive days without execution)
        - Weekend/holiday execution patterns

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
        max_runs_per_day = self.frequency_thresholds.get('max_runs_per_day', 1.5)
        max_days_without = self.frequency_thresholds.get('max_days_without_run', 2)

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

        # Calculate score based on coverage and frequency
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
        Check for data volume anomalies in inserted records.

        Analyzes:
        - Inserted records per run (mean, median, std dev)
        - Recent volume compared to baseline
        - Significant drops or spikes
        - Zero record runs

        Returns:
            MonitorResult with data volume assessment
        """
        self.logger.debug("Checking data volume")

        df = self._get_cached_data(
            lookback_days=self.config.get('monitoring', {}).get('lookback_days', 90)
        )

        if df.empty:
            return MonitorResult(
                check_type=CheckType.VOLUME_ANOMALY,
                check_name="Data Volume Check",
                status=HealthStatus.UNKNOWN,
                score=50.0,
                alert_level=AlertLevel.INFO,
                message="No data available for volume analysis"
            )

        # Extract volume data
        metric_name = self.volume_thresholds.get('metric_name', 'Inserted records')
        stat_column = self.volume_thresholds.get('stat_column', 'STAT_VALUE_1')

        # Filter for rows with the volume metric
        volume_data = df[df['STAT_VALUE_NAME_1'] == metric_name][stat_column].dropna()

        if len(volume_data) < 10:
            return MonitorResult(
                check_type=CheckType.VOLUME_ANOMALY,
                check_name="Data Volume Check",
                status=HealthStatus.UNKNOWN,
                score=50.0,
                alert_level=AlertLevel.INFO,
                message=f"Insufficient volume data: {len(volume_data)} samples"
            )

        # Calculate baseline statistics
        baseline_median = volume_data.median()
        baseline_mean = volume_data.mean()
        baseline_stddev = volume_data.std()

        # Get recent data (last 2 days)
        recent_days = self.config.get('monitoring', {}).get('recent_days', 2)
        recent_cutoff = datetime.now() - timedelta(days=recent_days)
        recent_df = df[df['PROCESS_DATE'] >= recent_cutoff]
        recent_volume = recent_df[recent_df['STAT_VALUE_NAME_1'] == metric_name][stat_column].dropna()

        if len(recent_volume) == 0:
            status = HealthStatus.UNKNOWN
            alert_level = AlertLevel.WARNING
            score = 50.0
            message = "No recent volume data available"
            recent_avg = 0
        else:
            recent_avg = recent_volume.mean()

            # Evaluate against thresholds
            warning_stddev_mult = self.volume_thresholds.get('warning_stddev_multiplier', 2.0)
            critical_stddev_mult = self.volume_thresholds.get('critical_stddev_multiplier', 3.0)

            status, alert_level, deviation_msg = ThresholdEvaluator.evaluate_deviation(
                recent_avg,
                baseline_median,
                baseline_stddev,
                warning_stddev_mult,
                critical_stddev_mult
            )

            # Also check percentage thresholds
            pct_change = ((recent_avg - baseline_median) / baseline_median * 100) \
                        if baseline_median > 0 else 0

            warning_decrease = self.volume_thresholds.get('warning_decrease_pct', 50.0)
            critical_decrease = self.volume_thresholds.get('critical_decrease_pct', 80.0)
            warning_increase = self.volume_thresholds.get('warning_increase_pct', 200.0)

            if pct_change < -critical_decrease:
                status = HealthStatus.CRITICAL
                alert_level = AlertLevel.CRITICAL
                message = f"CRITICAL volume drop: {abs(pct_change):.1f}% below baseline"
            elif pct_change < -warning_decrease:
                status = HealthStatus.FAIR if status == HealthStatus.EXCELLENT else status
                alert_level = AlertLevel.WARNING
                message = f"Volume drop: {abs(pct_change):.1f}% below baseline"
            elif pct_change > warning_increase:
                status = HealthStatus.FAIR if status == HealthStatus.EXCELLENT else status
                alert_level = AlertLevel.WARNING
                message = f"Volume spike: {pct_change:.1f}% above baseline"
            else:
                message = f"Volume normal: {pct_change:+.1f}% from baseline"

            # Score based on how close to baseline (100 = at baseline)
            if baseline_stddev > 0:
                deviation_score = max(0, 100 - (abs(recent_avg - baseline_median) / baseline_stddev * 10))
            else:
                deviation_score = 100
            score = deviation_score

        details = {
            'baseline_median': int(baseline_median),
            'baseline_mean': int(baseline_mean),
            'baseline_stddev': int(baseline_stddev),
            'recent_average': int(recent_avg),
            'percent_change': round(pct_change if recent_avg > 0 else 0, 2),
            'min_volume': int(volume_data.min()),
            'max_volume': int(volume_data.max()),
            'sample_size': len(volume_data)
        }

        return MonitorResult(
            check_type=CheckType.VOLUME_ANOMALY,
            check_name="Data Volume Check",
            status=status,
            score=score,
            alert_level=alert_level,
            message=message,
            details=details
        )

    def check_message_patterns(self) -> Optional[MonitorResult]:
        """
        Check message type patterns for anomalies.

        Analyzes:
        - ERROR message count
        - WARNING message count
        - Message type distribution
        - Unusual patterns

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

        # Evaluate against thresholds
        max_error_pct = self.message_thresholds.get('max_error_percentage', 1.0)
        max_warning_pct = self.message_thresholds.get('max_warning_percentage', 5.0)

        issues = []
        if error_pct > max_error_pct:
            issues.append(f"{error_count} ERROR messages ({error_pct:.1f}%)")
        if warning_pct > max_warning_pct:
            issues.append(f"{warning_count} WARNING messages ({warning_pct:.1f}%)")

        if issues:
            status = HealthStatus.FAIR
            alert_level = AlertLevel.WARNING
            score = max(50, 100 - (error_pct * 10 + warning_pct * 2))
            message = "High error/warning rate: " + ", ".join(issues)
        else:
            status = HealthStatus.EXCELLENT
            alert_level = AlertLevel.INFO
            score = 100.0
            message = f"Message patterns normal: {error_count} errors, {warning_count} warnings"

        # Message type distribution
        msg_distribution = df['MESSAGE_TYPE'].value_counts().to_dict()

        details = {
            'total_messages': total_messages,
            'error_count': error_count,
            'warning_count': warning_count,
            'error_percentage': round(error_pct, 2),
            'warning_percentage': round(warning_pct, 2),
            'message_distribution': msg_distribution
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

    def _check_consecutive_failures(self, df: pd.DataFrame) -> int:
        """
        Check for consecutive failures in recent runs.

        Args:
            df: Process data DataFrame

        Returns:
            Number of consecutive failures
        """
        # Sort by date descending
        df_sorted = df.sort_values('PROCESS_DATE', ascending=False)

        # Group by execution ID and check status
        recent_executions = df_sorted.groupby('EXECUTION_ID')['STATUS'].first().head(10)

        consecutive = 0
        for status in recent_executions:
            if status == 'FAILED':
                consecutive += 1
            else:
                break

        return consecutive
