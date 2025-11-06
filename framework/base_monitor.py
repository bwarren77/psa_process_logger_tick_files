"""
==============================================================================
Base Monitor Framework
==============================================================================

This module provides the abstract base classes and core functionality for the
ETL Process Health Monitoring Framework.

The framework is designed with extensibility in mind:
- New process types can be added by inheriting from BaseProcessMonitor
- Custom health checks can be added by implementing check methods
- Threshold configurations are externalized to YAML

Architecture:
- BaseProcessMonitor: Abstract base class for all process monitors
- MonitorResult: Data class for storing check results
- HealthScore: Calculated health metrics
- ThresholdEvaluator: Evaluates metrics against thresholds

Author: ETL Monitoring Framework
Version: 1.0.0
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging

# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class HealthStatus(Enum):
    """
    Health status categories for processes and checks.

    EXCELLENT: Operating optimally (95-100)
    GOOD: Operating normally (85-94)
    FAIR: Minor issues detected (70-84)
    POOR: Significant issues detected (50-69)
    CRITICAL: Severe issues, immediate attention required (0-49)
    UNKNOWN: Insufficient data to determine status
    """
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class AlertLevel(Enum):
    """
    Alert severity levels for monitoring events.

    INFO: Informational message, no action required
    WARNING: Potential issue, review recommended
    CRITICAL: Serious issue, immediate action required
    """
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class CheckType(Enum):
    """
    Types of monitoring checks performed.

    Used for categorizing and filtering check results.
    """
    FAILURE_DETECTION = "FAILURE_DETECTION"
    FREQUENCY_MONITORING = "FREQUENCY_MONITORING"
    VOLUME_ANOMALY = "VOLUME_ANOMALY"
    DURATION_MONITORING = "DURATION_MONITORING"
    DEPENDENCY_CHECK = "DEPENDENCY_CHECK"
    MESSAGE_ANALYSIS = "MESSAGE_ANALYSIS"
    SUCCESS_RATE = "SUCCESS_RATE"
    PREPROCESSING = "PREPROCESSING"


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class MonitorResult:
    """
    Represents the result of a single monitoring check.

    This class encapsulates all information about a monitoring check,
    including its status, score, and any issues detected.

    Attributes:
        check_type: Type of check performed
        check_name: Human-readable name of the check
        status: Health status determined by the check
        score: Numeric score (0-100)
        alert_level: Severity of any issues found
        message: Detailed message about the check result
        details: Additional structured data about the check
        timestamp: When the check was performed
        process_id: ID of the process being checked (optional)
        process_name: Name of the process being checked (optional)
    """
    check_type: CheckType
    check_name: str
    status: HealthStatus
    score: float
    alert_level: AlertLevel
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    process_id: Optional[int] = None
    process_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'check_type': self.check_type.value,
            'check_name': self.check_name,
            'status': self.status.value,
            'score': round(self.score, 2),
            'alert_level': self.alert_level.value,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'process_id': self.process_id,
            'process_name': self.process_name
        }


@dataclass
class HealthScore:
    """
    Represents the overall health score for a process or process group.

    Aggregates multiple check results into a single health assessment.

    Attributes:
        process_name: Name of the process or process group
        overall_score: Overall health score (0-100)
        overall_status: Overall health status
        component_scores: Individual check scores
        checks: List of all check results
        timestamp: When the health score was calculated
        trend: Score trend (positive/negative/stable)
        alerts: List of active alerts
    """
    process_name: str
    overall_score: float
    overall_status: HealthStatus
    component_scores: Dict[str, float]
    checks: List[MonitorResult]
    timestamp: datetime = field(default_factory=datetime.now)
    trend: Optional[str] = None
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'process_name': self.process_name,
            'overall_score': round(self.overall_score, 2),
            'overall_status': self.overall_status.value,
            'component_scores': {k: round(v, 2) for k, v in self.component_scores.items()},
            'checks': [check.to_dict() for check in self.checks],
            'timestamp': self.timestamp.isoformat(),
            'trend': self.trend,
            'alerts': self.alerts
        }


# ==============================================================================
# THRESHOLD EVALUATOR
# ==============================================================================

class ThresholdEvaluator:
    """
    Evaluates metrics against configured thresholds.

    This class provides utility methods for comparing actual values against
    expected thresholds and determining appropriate health status and alerts.

    Developer Notes:
    - All threshold comparisons should go through this class for consistency
    - Methods are static to allow easy testing and reuse
    - Returns tuples of (status, alert_level, message) for easy consumption
    """

    @staticmethod
    def evaluate_percentage(
        actual: float,
        warning_threshold: float,
        critical_threshold: float,
        higher_is_better: bool = True
    ) -> Tuple[HealthStatus, AlertLevel, str]:
        """
        Evaluate a percentage metric against thresholds.

        Args:
            actual: Actual percentage value
            warning_threshold: Threshold for WARNING alert
            critical_threshold: Threshold for CRITICAL alert
            higher_is_better: True if higher values are better (e.g., success rate)
                            False if lower values are better (e.g., error rate)

        Returns:
            Tuple of (HealthStatus, AlertLevel, description message)
        """
        if higher_is_better:
            if actual >= warning_threshold:
                return HealthStatus.EXCELLENT, AlertLevel.INFO, f"At {actual:.1f}%"
            elif actual >= critical_threshold:
                return HealthStatus.FAIR, AlertLevel.WARNING, \
                       f"Below warning threshold: {actual:.1f}% < {warning_threshold:.1f}%"
            else:
                return HealthStatus.CRITICAL, AlertLevel.CRITICAL, \
                       f"Below critical threshold: {actual:.1f}% < {critical_threshold:.1f}%"
        else:
            if actual <= critical_threshold:
                return HealthStatus.EXCELLENT, AlertLevel.INFO, f"At {actual:.1f}%"
            elif actual <= warning_threshold:
                return HealthStatus.FAIR, AlertLevel.WARNING, \
                       f"Above warning threshold: {actual:.1f}% > {warning_threshold:.1f}%"
            else:
                return HealthStatus.CRITICAL, AlertLevel.CRITICAL, \
                       f"Above critical threshold: {actual:.1f}% > {critical_threshold:.1f}%"

    @staticmethod
    def evaluate_deviation(
        actual: float,
        baseline: float,
        std_dev: float,
        warning_multiplier: float = 2.0,
        critical_multiplier: float = 3.0
    ) -> Tuple[HealthStatus, AlertLevel, str]:
        """
        Evaluate a metric based on standard deviation from baseline.

        Args:
            actual: Actual value
            baseline: Expected baseline value (e.g., median)
            std_dev: Standard deviation
            warning_multiplier: Number of std devs for WARNING
            critical_multiplier: Number of std devs for CRITICAL

        Returns:
            Tuple of (HealthStatus, AlertLevel, description message)
        """
        if std_dev == 0:
            return HealthStatus.UNKNOWN, AlertLevel.INFO, "Insufficient variance to evaluate"

        deviation = abs(actual - baseline) / std_dev

        if deviation < warning_multiplier:
            return HealthStatus.EXCELLENT, AlertLevel.INFO, \
                   f"Within normal range ({deviation:.1f} std devs)"
        elif deviation < critical_multiplier:
            return HealthStatus.FAIR, AlertLevel.WARNING, \
                   f"Outside normal range ({deviation:.1f} std devs from baseline)"
        else:
            return HealthStatus.CRITICAL, AlertLevel.CRITICAL, \
                   f"Significant deviation ({deviation:.1f} std devs from baseline)"

    @staticmethod
    def evaluate_count(
        actual: int,
        max_allowed: int,
        zero_is_good: bool = True
    ) -> Tuple[HealthStatus, AlertLevel, str]:
        """
        Evaluate a count metric (e.g., failure count, error count).

        Args:
            actual: Actual count
            max_allowed: Maximum allowed count
            zero_is_good: True if zero is the ideal value

        Returns:
            Tuple of (HealthStatus, AlertLevel, description message)
        """
        if zero_is_good and actual == 0:
            return HealthStatus.EXCELLENT, AlertLevel.INFO, "No issues detected"
        elif actual <= max_allowed:
            return HealthStatus.GOOD, AlertLevel.INFO, f"{actual} detected (within limit)"
        elif actual <= max_allowed * 2:
            return HealthStatus.FAIR, AlertLevel.WARNING, \
                   f"{actual} detected (above limit of {max_allowed})"
        else:
            return HealthStatus.CRITICAL, AlertLevel.CRITICAL, \
                   f"{actual} detected (significantly above limit of {max_allowed})"


# ==============================================================================
# BASE PROCESS MONITOR
# ==============================================================================

class BaseProcessMonitor(ABC):
    """
    Abstract base class for all process monitors.

    This class defines the interface that all specific process monitors must
    implement. It provides common functionality for data retrieval, threshold
    evaluation, and health scoring.

    To create a new process monitor:
    1. Inherit from this class
    2. Implement all @abstractmethod methods
    3. Override any optional methods as needed
    4. Add configuration to monitor_config.yaml

    Developer Notes:
    - All database queries should be performed in get_process_data()
    - Individual checks should be implemented as separate methods
    - Each check should return a MonitorResult object
    - The calculate_health_score() method aggregates all checks

    Example:
        class MyProcessMonitor(BaseProcessMonitor):
            def get_process_data(self, lookback_days):
                # Query database for process data
                return data

            def check_failure_rate(self):
                # Implement failure rate check
                return MonitorResult(...)
    """

    def __init__(
        self,
        config: Dict[str, Any],
        db_connection: Any,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the process monitor.

        Args:
            config: Configuration dictionary for this process group
            db_connection: Database connection object
            logger: Logger instance (optional)
        """
        self.config = config
        self.db_connection = db_connection
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Extract common configuration
        self.process_name = config.get('description', 'Unknown Process')
        self.table_name = config.get('table_name', '')
        self.process_ids = config.get('process_ids', [])
        self.process_names = config.get('process_names', [])
        self.enabled = config.get('enabled', True)

        # Cache for historical data
        self._data_cache: Optional[Any] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=10)

        self.logger.info(f"Initialized {self.__class__.__name__} for {self.process_name}")

    @abstractmethod
    def get_process_data(self, lookback_days: int) -> Any:
        """
        Retrieve process data from the database.

        This method should query the database and return data needed for
        all monitoring checks. The data format is implementation-specific.

        Args:
            lookback_days: Number of days to look back for historical data

        Returns:
            Process data (format depends on implementation)

        Developer Notes:
        - Use pandas DataFrame for structured data
        - Include all fields needed for monitoring checks
        - Consider caching to reduce database load
        - Handle connection errors gracefully
        """
        pass

    @abstractmethod
    def check_failure_rate(self) -> MonitorResult:
        """
        Check the failure rate of the process.

        Returns:
            MonitorResult with failure rate assessment
        """
        pass

    @abstractmethod
    def check_execution_frequency(self) -> MonitorResult:
        """
        Check if the process is executing at the expected frequency.

        Returns:
            MonitorResult with frequency assessment
        """
        pass

    @abstractmethod
    def check_data_volume(self) -> MonitorResult:
        """
        Check for data volume anomalies.

        Returns:
            MonitorResult with data volume assessment
        """
        pass

    def check_execution_duration(self) -> Optional[MonitorResult]:
        """
        Check for execution duration anomalies.

        This is optional as some processes may not track duration.

        Returns:
            MonitorResult with duration assessment, or None if not applicable
        """
        return None

    def check_message_patterns(self) -> Optional[MonitorResult]:
        """
        Check message patterns for anomalies (ERROR, WARNING counts).

        Returns:
            MonitorResult with message analysis, or None if not applicable
        """
        return None

    def calculate_health_score(self) -> HealthScore:
        """
        Calculate overall health score by aggregating all checks.

        This method:
        1. Runs all enabled checks
        2. Applies configured weights to each check
        3. Calculates weighted average score
        4. Determines overall status
        5. Identifies alerts

        Returns:
            HealthScore object with overall assessment

        Developer Notes:
        - Check methods should not raise exceptions (catch internally)
        - Disabled checks are skipped automatically
        - Weights are normalized if they don't sum to 1.0
        - Unknown checks receive a neutral score (50)
        """
        self.logger.info(f"Calculating health score for {self.process_name}")

        checks: List[MonitorResult] = []
        component_scores: Dict[str, float] = {}

        # Get health weights from configuration
        weights = self.config.get('health_weights', {})

        # Run failure rate check
        try:
            result = self.check_failure_rate()
            checks.append(result)
            component_scores['success_rate'] = result.score
        except Exception as e:
            self.logger.error(f"Error in failure rate check: {e}", exc_info=True)

        # Run frequency check
        try:
            result = self.check_execution_frequency()
            checks.append(result)
            component_scores['frequency'] = result.score
        except Exception as e:
            self.logger.error(f"Error in frequency check: {e}", exc_info=True)

        # Run data volume check
        try:
            result = self.check_data_volume()
            checks.append(result)
            component_scores['volume_consistency'] = result.score
        except Exception as e:
            self.logger.error(f"Error in data volume check: {e}", exc_info=True)

        # Optional checks
        optional_checks = [
            ('check_execution_duration', 'duration'),
            ('check_message_patterns', 'message_quality')
        ]

        for method_name, component_name in optional_checks:
            if hasattr(self, method_name):
                try:
                    result = getattr(self, method_name)()
                    if result:
                        checks.append(result)
                        component_scores[component_name] = result.score
                except Exception as e:
                    self.logger.error(f"Error in {method_name}: {e}", exc_info=True)

        # Calculate weighted average
        overall_score = self._calculate_weighted_score(component_scores, weights)
        overall_status = self._score_to_status(overall_score)

        # Collect alerts
        alerts = [
            check.message for check in checks
            if check.alert_level in [AlertLevel.WARNING, AlertLevel.CRITICAL]
        ]

        health_score = HealthScore(
            process_name=self.process_name,
            overall_score=overall_score,
            overall_status=overall_status,
            component_scores=component_scores,
            checks=checks,
            alerts=alerts
        )

        self.logger.info(
            f"Health score for {self.process_name}: {overall_score:.1f} ({overall_status.value})"
        )

        return health_score

    def _calculate_weighted_score(
        self,
        component_scores: Dict[str, float],
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate weighted average of component scores.

        Args:
            component_scores: Dictionary of component names to scores
            weights: Dictionary of component names to weights

        Returns:
            Weighted average score
        """
        if not component_scores:
            return 50.0  # Neutral score if no data

        # Normalize weights
        total_weight = sum(weights.get(k, 0) for k in component_scores.keys())
        if total_weight == 0:
            # Equal weights if not configured
            total_weight = len(component_scores)
            normalized_weights = {k: 1.0 / total_weight for k in component_scores.keys()}
        else:
            normalized_weights = {
                k: weights.get(k, 0) / total_weight
                for k in component_scores.keys()
            }

        # Calculate weighted sum
        weighted_sum = sum(
            score * normalized_weights.get(component, 0)
            for component, score in component_scores.items()
        )

        return weighted_sum

    def _score_to_status(self, score: float) -> HealthStatus:
        """
        Convert numeric score to health status.

        Args:
            score: Numeric health score (0-100)

        Returns:
            Corresponding HealthStatus
        """
        if score >= 95:
            return HealthStatus.EXCELLENT
        elif score >= 85:
            return HealthStatus.GOOD
        elif score >= 70:
            return HealthStatus.FAIR
        elif score >= 50:
            return HealthStatus.POOR
        else:
            return HealthStatus.CRITICAL

    def _get_cached_data(self, lookback_days: int) -> Any:
        """
        Get data from cache or fetch from database.

        Args:
            lookback_days: Number of days to look back

        Returns:
            Cached or freshly fetched data
        """
        now = datetime.now()

        if (self._data_cache is not None and
            self._cache_timestamp is not None and
            now - self._cache_timestamp < self._cache_duration):
            self.logger.debug("Using cached data")
            return self._data_cache

        self.logger.debug("Fetching fresh data from database")
        self._data_cache = self.get_process_data(lookback_days)
        self._cache_timestamp = now

        return self._data_cache
