"""
==============================================================================
ETL Process Health Monitoring Framework
==============================================================================

This package provides a comprehensive, extensible framework for monitoring
ETL processes and generating health reports for Power BI dashboards.

Key Components:
- BaseProcessMonitor: Abstract base class for all monitors
- TickFileMonitor: Monitor for tick file processes
- MQSummaryMonitor: Monitor for MQ summary processes
- OutputGenerator: Generates XML/JSON output for Power BI
- MonitorService: Main service coordinator

Quick Start:
    from framework.monitor_service import MonitorService

    service = MonitorService('monitor_config.yaml')
    service.start()

Author: ETL Monitoring Framework
Version: 1.0.0
"""

__version__ = '1.0.0'
__author__ = 'ETL Monitoring Framework'

from framework.base_monitor import (
    BaseProcessMonitor,
    MonitorResult,
    HealthScore,
    HealthStatus,
    AlertLevel,
    CheckType,
    ThresholdEvaluator
)

from framework.tick_monitor import TickFileMonitor
from framework.mq_monitor import MQSummaryMonitor
from framework.output_generator import OutputGenerator, PowerBISchemaHelper
from framework.monitor_service import MonitorService

__all__ = [
    'BaseProcessMonitor',
    'MonitorResult',
    'HealthScore',
    'HealthStatus',
    'AlertLevel',
    'CheckType',
    'ThresholdEvaluator',
    'TickFileMonitor',
    'MQSummaryMonitor',
    'OutputGenerator',
    'PowerBISchemaHelper',
    'MonitorService'
]
