"""
==============================================================================
Daily Failure Escalation Generator Module
==============================================================================

This module generates real-time daily failure escalation XML datasets for
executive dashboards. It provides:

- Real-time tracking of process failures throughout the day
- Automatic daily reset at a configurable time (default: 5 AM)
- Stale data detection and warning indicators
- Expected process execution windows and next refresh times
- Executive-level visibility into process health

The escalation dataset resets daily to provide a fresh view of the current
day's operations, while maintaining historical context when needed.

Key Features:
- Daily reset mechanism at configured time
- Stale data warnings when viewing data beyond reset time
- Expected refresh time calculations per process
- Real-time failure tracking
- Process execution status indicators

Developer Notes:
- XML schema optimized for Power BI dashboard consumption
- Atomic file updates prevent partial reads
- Timezone-aware for accurate timing

Author: ETL Monitoring Framework
Version: 1.0.0
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import json
from zoneinfo import ZoneInfo


class DailyEscalationGenerator:
    """
    Generates daily failure escalation XML for executive dashboards.

    This class creates a specialized XML dataset that:
    - Resets daily at a configured time (default 5 AM)
    - Tracks real-time failures throughout the day
    - Provides stale data warnings
    - Shows expected refresh times for each process
    - Highlights processes that should have run but haven't
    """

    def __init__(self, config: Dict[str, Any], processes_config: Dict[str, Any],
                 logger: Optional[logging.Logger] = None):
        """
        Initialize Daily Escalation Generator.

        Args:
            config: Output configuration from YAML
            processes_config: Process definitions from YAML
            logger: Logger instance (optional)
        """
        self.config = config
        self.processes_config = processes_config
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Extract escalation-specific configuration
        escalation_config = config.get('daily_escalation', {})

        # Reset time configuration
        reset_time_str = escalation_config.get('reset_time', '05:00')
        self.reset_hour, self.reset_minute = map(int, reset_time_str.split(':'))
        self.reset_time = datetime_time(self.reset_hour, self.reset_minute)

        # File paths
        self.escalation_xml_path = Path(
            escalation_config.get('xml_path', './output/daily_failure_escalation.xml')
        )
        self.escalation_state_path = Path(
            escalation_config.get('state_path', './output/escalation_state.json')
        )

        # Timezone for process schedules
        self.timezone = ZoneInfo(escalation_config.get('timezone', 'America/New_York'))

        # Stale data warning threshold (minutes after expected completion)
        self.stale_warning_minutes = escalation_config.get('stale_warning_minutes', 60)

        # Ensure directories exist
        self._ensure_directories()

        # Load or initialize state
        self.state = self._load_state()

        self.logger.info(f"Initialized DailyEscalationGenerator (Reset time: {reset_time_str})")

    def _ensure_directories(self):
        """Create output directories if they don't exist."""
        self.escalation_xml_path.parent.mkdir(parents=True, exist_ok=True)
        self.escalation_state_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> Dict[str, Any]:
        """
        Load escalation state from disk.

        Returns:
            State dictionary
        """
        if self.escalation_state_path.exists():
            try:
                with open(self.escalation_state_path, 'r') as f:
                    state = json.load(f)
                    self.logger.debug("Loaded escalation state from disk")
                    return state
            except Exception as e:
                self.logger.warning(f"Failed to load state, using empty state: {e}")

        return {
            'last_reset': None,
            'current_day_failures': [],
            'process_executions': {}
        }

    def _save_state(self):
        """Save escalation state to disk."""
        try:
            tmp_file = self.escalation_state_path.with_suffix('.tmp')
            with open(tmp_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
            tmp_file.replace(self.escalation_state_path)
            self.logger.debug("Saved escalation state to disk")
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")

    def _should_reset(self, current_time: datetime) -> bool:
        """
        Determine if daily reset should occur.

        Args:
            current_time: Current datetime

        Returns:
            True if reset should occur
        """
        # If never reset, should reset
        if not self.state.get('last_reset'):
            return True

        last_reset = datetime.fromisoformat(self.state['last_reset'])

        # Check if we've crossed the reset time boundary
        current_date = current_time.date()
        last_reset_date = last_reset.date()

        # If it's a new day and we're past the reset time
        if current_date > last_reset_date:
            current_time_only = current_time.time()
            if current_time_only >= self.reset_time:
                return True

        return False

    def _reset_daily_data(self, current_time: datetime):
        """
        Reset daily failure tracking data.

        Args:
            current_time: Current datetime
        """
        self.logger.info(f"Resetting daily escalation data at {current_time.isoformat()}")

        self.state = {
            'last_reset': current_time.isoformat(),
            'current_day_failures': [],
            'process_executions': {}
        }

        self._save_state()

    def _get_process_execution_window(self, process_config: Dict[str, Any]) -> Tuple[datetime_time, datetime_time]:
        """
        Get expected execution window for a process.

        Args:
            process_config: Process configuration

        Returns:
            Tuple of (start_time, end_time)
        """
        schedule = process_config.get('schedule', {})
        time_window = schedule.get('expected_time_window', {})

        start_str = time_window.get('start', '00:00')
        end_str = time_window.get('end', '23:59')

        start_hour, start_minute = map(int, start_str.split(':'))
        end_hour, end_minute = map(int, end_str.split(':'))

        return (
            datetime_time(start_hour, start_minute),
            datetime_time(end_hour, end_minute)
        )

    def _is_process_expected_today(self, process_config: Dict[str, Any], current_time: datetime) -> bool:
        """
        Determine if process is expected to run today.

        Args:
            process_config: Process configuration
            current_time: Current datetime

        Returns:
            True if process should run today
        """
        schedule = process_config.get('schedule', {})
        expected_days = schedule.get('expected_days', [])

        if not expected_days:
            return True  # If no restriction, assume daily

        current_day = current_time.strftime('%A').lower()
        return current_day in [day.lower() for day in expected_days]

    def _calculate_next_expected_run(self, process_config: Dict[str, Any],
                                     current_time: datetime) -> Optional[datetime]:
        """
        Calculate next expected run time for a process.

        Args:
            process_config: Process configuration
            current_time: Current datetime

        Returns:
            Next expected run datetime or None
        """
        schedule = process_config.get('schedule', {})
        expected_days = schedule.get('expected_days', [])
        start_time, end_time = self._get_process_execution_window(process_config)

        # If process is expected today and we're before the window
        if self._is_process_expected_today(process_config, current_time):
            current_time_only = current_time.time()
            if current_time_only < start_time:
                # Expected later today
                return datetime.combine(current_time.date(), start_time, tzinfo=self.timezone)
            elif current_time_only <= end_time:
                # Should be running now or very soon
                return current_time.replace(tzinfo=self.timezone)

        # Find next expected day
        if not expected_days:
            # Daily process - tomorrow
            tomorrow = current_time + timedelta(days=1)
            return datetime.combine(tomorrow.date(), start_time, tzinfo=self.timezone)

        # Find next matching weekday
        expected_weekdays = []
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }

        for day in expected_days:
            if day.lower() in day_map:
                expected_weekdays.append(day_map[day.lower()])

        if not expected_weekdays:
            return None

        current_weekday = current_time.weekday()

        # Find next occurrence
        for days_ahead in range(1, 8):
            future_date = current_time + timedelta(days=days_ahead)
            if future_date.weekday() in expected_weekdays:
                return datetime.combine(future_date.date(), start_time, tzinfo=self.timezone)

        return None

    def _get_process_status(self, process_name: str, process_config: Dict[str, Any],
                           health_scores: List['HealthScore'], current_time: datetime) -> Dict[str, Any]:
        """
        Get comprehensive status for a process.

        Args:
            process_name: Name of process
            process_config: Process configuration
            health_scores: List of current health scores
            current_time: Current datetime

        Returns:
            Dictionary with process status information
        """
        # Find matching health score
        health_score = None
        for hs in health_scores:
            if hs.process_name == process_config.get('description', ''):
                health_score = hs
                break

        # Determine if process is expected today
        expected_today = self._is_process_expected_today(process_config, current_time)

        # Get execution window
        start_time, end_time = self._get_process_execution_window(process_config)

        # Calculate next expected run
        next_run = self._calculate_next_expected_run(process_config, current_time)

        # Determine current status
        current_time_only = current_time.time()

        status = {
            'process_name': process_config.get('description', process_name),
            'process_group': process_name,
            'expected_today': expected_today,
            'execution_window_start': start_time.strftime('%H:%M'),
            'execution_window_end': end_time.strftime('%H:%M'),
            'next_expected_run': next_run.isoformat() if next_run else None,
            'current_status': 'PENDING',
            'has_failures': False,
            'failure_count': 0,
            'health_score': 0.0,
            'last_check_time': None,
            'is_overdue': False,
            'minutes_overdue': 0
        }

        if health_score:
            status['health_score'] = health_score.overall_score
            status['last_check_time'] = health_score.timestamp.isoformat()

            # Check for failures in health score
            failed_checks = [c for c in health_score.checks if c.status.value in ['CRITICAL', 'FAILED']]
            status['has_failures'] = len(failed_checks) > 0
            status['failure_count'] = len(failed_checks)

            # Determine status
            if health_score.overall_status.value in ['EXCELLENT', 'GOOD']:
                status['current_status'] = 'COMPLETED'
            elif health_score.overall_status.value in ['POOR', 'CRITICAL']:
                status['current_status'] = 'FAILED'
            else:
                status['current_status'] = 'RUNNING'

        # Check if overdue
        if expected_today and current_time_only > end_time:
            if status['current_status'] not in ['COMPLETED', 'RUNNING']:
                status['is_overdue'] = True
                end_datetime = datetime.combine(current_time.date(), end_time, tzinfo=self.timezone)
                minutes_diff = (current_time - end_datetime).total_seconds() / 60
                status['minutes_overdue'] = int(minutes_diff)

        return status

    def _is_data_stale(self, current_time: datetime) -> Tuple[bool, str]:
        """
        Determine if data is stale (from previous day's run).

        Args:
            current_time: Current datetime

        Returns:
            Tuple of (is_stale, reason_message)
        """
        # Check if we're past reset time but no reset has occurred
        if not self.state.get('last_reset'):
            return (False, "")

        last_reset = datetime.fromisoformat(self.state['last_reset'])
        current_time_only = current_time.time()

        # If we're past reset time and last reset was yesterday or earlier
        if current_time_only >= self.reset_time:
            if current_time.date() > last_reset.date():
                hours_stale = (current_time - last_reset).total_seconds() / 3600
                return (True,
                       f"Data from previous day (last updated {hours_stale:.1f} hours ago). "
                       f"Next refresh expected after {self.reset_time.strftime('%I:%M %p')}.")

        return (False, "")

    def generate_daily_escalation_xml(self, health_scores: List['HealthScore']) -> Path:
        """
        Generate daily failure escalation XML.

        Args:
            health_scores: List of HealthScore objects from monitors

        Returns:
            Path to generated XML file
        """
        current_time = datetime.now(self.timezone)

        # Check if daily reset should occur
        if self._should_reset(current_time):
            self._reset_daily_data(current_time)

        # Check for stale data
        is_stale, stale_message = self._is_data_stale(current_time)

        self.logger.debug("Generating daily failure escalation XML")

        # Create root element
        root = ET.Element('DailyFailureEscalation')

        # Add metadata
        ET.SubElement(root, 'GeneratedAt').text = current_time.isoformat()
        ET.SubElement(root, 'ResetTime').text = self.reset_time.strftime('%H:%M')
        ET.SubElement(root, 'LastResetAt').text = self.state.get('last_reset', 'Never')
        ET.SubElement(root, 'CurrentDate').text = current_time.strftime('%Y-%m-%d')
        ET.SubElement(root, 'CurrentTime').text = current_time.strftime('%H:%M:%S')
        ET.SubElement(root, 'Timezone').text = str(self.timezone)

        # Add stale data indicator
        data_status = ET.SubElement(root, 'DataStatus')
        ET.SubElement(data_status, 'IsStale').text = str(is_stale).lower()
        if is_stale:
            ET.SubElement(data_status, 'StaleDataWarning').text = stale_message
            ET.SubElement(data_status, 'AlertLevel').text = 'WARNING'
        else:
            ET.SubElement(data_status, 'Status').text = 'Current'
            ET.SubElement(data_status, 'AlertLevel').text = 'INFO'

        # Add executive summary
        summary = ET.SubElement(root, 'ExecutiveSummary')

        # Collect process statuses
        process_statuses = []
        for process_name, process_config in self.processes_config.items():
            if not process_config.get('enabled', True):
                continue

            status = self._get_process_status(
                process_name, process_config, health_scores, current_time
            )
            process_statuses.append(status)

        # Calculate summary metrics
        total_processes = len(process_statuses)
        completed = sum(1 for s in process_statuses if s['current_status'] == 'COMPLETED')
        failed = sum(1 for s in process_statuses if s['current_status'] == 'FAILED')
        running = sum(1 for s in process_statuses if s['current_status'] == 'RUNNING')
        pending = sum(1 for s in process_statuses if s['current_status'] == 'PENDING')
        overdue = sum(1 for s in process_statuses if s['is_overdue'])

        ET.SubElement(summary, 'TotalProcesses').text = str(total_processes)
        ET.SubElement(summary, 'CompletedSuccessfully').text = str(completed)
        ET.SubElement(summary, 'Failed').text = str(failed)
        ET.SubElement(summary, 'CurrentlyRunning').text = str(running)
        ET.SubElement(summary, 'PendingExecution').text = str(pending)
        ET.SubElement(summary, 'Overdue').text = str(overdue)

        # Overall status
        if failed > 0 or overdue > 0:
            overall_status = 'CRITICAL'
        elif running > 0:
            overall_status = 'ACTIVE'
        elif completed == total_processes:
            overall_status = 'ALL_COMPLETE'
        else:
            overall_status = 'NORMAL'

        ET.SubElement(summary, 'OverallStatus').text = overall_status

        # Add process details
        processes_elem = ET.SubElement(root, 'Processes')

        for status in process_statuses:
            process_elem = ET.SubElement(processes_elem, 'Process')

            ET.SubElement(process_elem, 'Name').text = status['process_name']
            ET.SubElement(process_elem, 'Group').text = status['process_group']
            ET.SubElement(process_elem, 'Status').text = status['current_status']
            ET.SubElement(process_elem, 'ExpectedToday').text = str(status['expected_today']).lower()

            # Execution window
            window_elem = ET.SubElement(process_elem, 'ExecutionWindow')
            ET.SubElement(window_elem, 'Start').text = status['execution_window_start']
            ET.SubElement(window_elem, 'End').text = status['execution_window_end']

            # Next expected run
            if status['next_expected_run']:
                next_run = datetime.fromisoformat(status['next_expected_run'])
                ET.SubElement(process_elem, 'NextExpectedRun').text = next_run.strftime('%Y-%m-%d %H:%M')
                ET.SubElement(process_elem, 'NextExpectedRunISO').text = status['next_expected_run']
            else:
                ET.SubElement(process_elem, 'NextExpectedRun').text = 'Unknown'

            # Health and failure info
            ET.SubElement(process_elem, 'HealthScore').text = f"{status['health_score']:.2f}"
            ET.SubElement(process_elem, 'HasFailures').text = str(status['has_failures']).lower()
            ET.SubElement(process_elem, 'FailureCount').text = str(status['failure_count'])

            # Overdue status
            if status['is_overdue']:
                overdue_elem = ET.SubElement(process_elem, 'OverdueStatus')
                ET.SubElement(overdue_elem, 'IsOverdue').text = 'true'
                ET.SubElement(overdue_elem, 'MinutesOverdue').text = str(status['minutes_overdue'])
                ET.SubElement(overdue_elem, 'Alert').text = (
                    f"Process is {status['minutes_overdue']} minutes overdue. "
                    f"Expected completion by {status['execution_window_end']}."
                )

            # Last check time
            if status['last_check_time']:
                ET.SubElement(process_elem, 'LastCheckTime').text = status['last_check_time']

        # Add failures section for executive visibility
        failures_elem = ET.SubElement(root, 'ActiveFailures')
        failure_count = 0

        for status in process_statuses:
            if status['has_failures'] or status['current_status'] == 'FAILED':
                failure_elem = ET.SubElement(failures_elem, 'Failure')
                ET.SubElement(failure_elem, 'ProcessName').text = status['process_name']
                ET.SubElement(failure_elem, 'Status').text = status['current_status']
                ET.SubElement(failure_elem, 'FailureCount').text = str(status['failure_count'])
                ET.SubElement(failure_elem, 'HealthScore').text = f"{status['health_score']:.2f}"

                if status['is_overdue']:
                    ET.SubElement(failure_elem, 'AdditionalConcern').text = (
                        f"Process is also {status['minutes_overdue']} minutes overdue"
                    )

                failure_count += 1

        ET.SubElement(failures_elem, 'TotalActiveFailures').text = str(failure_count)

        # Add refresh schedule
        refresh_elem = ET.SubElement(root, 'RefreshSchedule')
        ET.SubElement(refresh_elem, 'DailyResetTime').text = self.reset_time.strftime('%I:%M %p')
        ET.SubElement(refresh_elem, 'NextResetDate').text = self._get_next_reset_date(current_time).strftime('%Y-%m-%d')
        ET.SubElement(refresh_elem, 'NextResetDateTime').text = self._get_next_reset_datetime(current_time).isoformat()

        # Write to file (atomically)
        xml_str = self._prettify_xml(root)
        tmp_file = self.escalation_xml_path.with_suffix('.tmp')

        with open(tmp_file, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        tmp_file.replace(self.escalation_xml_path)

        self.logger.info(
            f"Generated daily escalation XML: {self.escalation_xml_path} "
            f"(Stale: {is_stale}, Failures: {failure_count})"
        )

        return self.escalation_xml_path

    def _get_next_reset_date(self, current_time: datetime) -> datetime:
        """Get the date of the next reset."""
        current_time_only = current_time.time()

        if current_time_only < self.reset_time:
            # Reset is today
            return current_time.date()
        else:
            # Reset is tomorrow
            return (current_time + timedelta(days=1)).date()

    def _get_next_reset_datetime(self, current_time: datetime) -> datetime:
        """Get the full datetime of the next reset."""
        next_reset_date = self._get_next_reset_date(current_time)
        return datetime.combine(next_reset_date, self.reset_time, tzinfo=self.timezone)

    def _prettify_xml(self, elem: ET.Element) -> str:
        """
        Return a pretty-printed XML string.

        Args:
            elem: XML Element

        Returns:
            Formatted XML string
        """
        rough_string = ET.tostring(elem, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
