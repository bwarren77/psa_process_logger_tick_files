"""
==============================================================================
Process Health Monitoring Service
==============================================================================

This is the main service module that coordinates all monitoring activities.

The service:
- Loads configuration from YAML
- Initializes all process monitors
- Runs monitoring checks on a schedule
- Generates output files for Power BI
- Handles logging and error recovery
- Runs continuously as a long-lived daemon

Developer Notes:
- Designed to run 24/7 with minimal supervision
- Handles database connection failures gracefully
- Automatically retries failed operations
- Logs all activities for troubleshooting
- Can be run as a systemd service or Windows service

Author: ETL Monitoring Framework
Version: 1.0.0
"""

import yaml
import logging
import logging.handlers
import time
import signal
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from framework.base_monitor import BaseProcessMonitor, HealthScore
from framework.tick_monitor import TickFileMonitor
from framework.mq_monitor import MQSummaryMonitor
from framework.output_generator import OutputGenerator


class MonitorService:
    """
    Main monitoring service coordinator.

    This class orchestrates the entire monitoring framework:
    - Loads configuration
    - Initializes monitors for each process group
    - Schedules monitoring checks
    - Aggregates results
    - Generates output files
    - Handles errors and retries

    The service runs continuously until stopped via signal (SIGTERM/SIGINT).
    """

    def __init__(self, config_path: str):
        """
        Initialize the monitoring service.

        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.monitors: Dict[str, BaseProcessMonitor] = {}
        self.output_generator: Optional[OutputGenerator] = None
        self.logger: Optional[logging.Logger] = None

        self.running = False
        self.check_count = 0
        self.last_check_time: Optional[datetime] = None

        # Load configuration
        self._load_config()

        # Setup logging
        self._setup_logging()

        # Setup signal handlers
        self._setup_signal_handlers()

        # Initialize components
        self._initialize_monitors()
        self._initialize_output_generator()

        self.logger.info("=" * 80)
        self.logger.info("Process Health Monitoring Service Initialized")
        self.logger.info("=" * 80)
        self.logger.info(f"Configuration: {config_path}")
        self.logger.info(f"Monitors initialized: {len(self.monitors)}")
        self.logger.info(f"Check interval: {self.config['monitoring']['check_interval']}s")

    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            print(f"FATAL: Failed to load configuration from {self.config_path}: {e}")
            sys.exit(1)

    def _setup_logging(self):
        """Setup logging configuration."""
        log_config = self.config.get('logging', {})

        # Create logs directory
        log_file = Path(log_config.get('file_path', './logs/process_monitor.log'))
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Configure root logger
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_format = log_config.get('format',
                                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Create formatters
        formatter = logging.Formatter(log_format)

        # File handler with rotation
        max_bytes = log_config.get('max_file_size_mb', 100) * 1024 * 1024
        backup_count = log_config.get('backup_count', 5)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Create service logger
        self.logger = logging.getLogger('MonitorService')

        # Error log file
        error_log_path = log_config.get('error_log_path', './logs/process_monitor_errors.log')
        error_log_file = Path(error_log_path)
        error_log_file.parent.mkdir(parents=True, exist_ok=True)

        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)

        self.logger.info("Logging configured")

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        signal_name = signal.Signals(signum).name
        self.logger.info(f"Received signal {signal_name}, shutting down gracefully...")
        self.running = False

    def _initialize_monitors(self):
        """Initialize all process monitors based on configuration."""
        processes_config = self.config.get('processes', {})

        # Database connection (mock for now - would be real cx_Oracle connection)
        db_connection = self._get_db_connection()

        for process_group_name, process_config in processes_config.items():
            if not process_config.get('enabled', True):
                self.logger.info(f"Skipping disabled process group: {process_group_name}")
                continue

            try:
                # Determine monitor class based on process group
                if process_group_name == 'tick_files':
                    monitor = TickFileMonitor(process_config, db_connection, self.logger)
                elif process_group_name == 'mq_summary':
                    monitor = MQSummaryMonitor(process_config, db_connection, self.logger)
                else:
                    self.logger.warning(
                        f"Unknown process group type: {process_group_name}, skipping"
                    )
                    continue

                self.monitors[process_group_name] = monitor
                self.logger.info(
                    f"Initialized monitor for: {process_config.get('description', process_group_name)}"
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to initialize monitor for {process_group_name}: {e}",
                    exc_info=True
                )

    def _get_db_connection(self) -> Any:
        """
        Get database connection.

        In production, this would establish a connection to Oracle database:

        import cx_Oracle
        db_config = self.config.get('database', {})
        connection = cx_Oracle.connect(
            user=db_config['username'],
            password=db_config['password'],
            dsn=f"{db_config['host']}:{db_config['port']}/{db_config['service_name']}"
        )

        For now, we'll use the Excel file path as a mock connection.
        """
        # Mock: Return Excel file path for testing
        return '/home/user/psa_process_logger_tick_files/Process_Log_2023_RPT_Tick_MQ_Summary.xlsx'

    def _initialize_output_generator(self):
        """Initialize output generator."""
        try:
            output_config = self.config.get('output', {})
            self.output_generator = OutputGenerator(output_config, self.logger)
            self.logger.info("Output generator initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize output generator: {e}", exc_info=True)
            raise

    def start(self):
        """
        Start the monitoring service.

        This method runs the main monitoring loop:
        1. Run all monitoring checks
        2. Generate output files
        3. Sleep until next check interval
        4. Repeat until stopped

        The service runs continuously until a SIGTERM or SIGINT signal is received.
        """
        self.logger.info("Starting monitoring service...")
        self.running = True

        check_interval = self.config['monitoring']['check_interval']

        while self.running:
            try:
                cycle_start = time.time()
                self.check_count += 1

                self.logger.info(f"Starting monitoring cycle #{self.check_count}")

                # Run monitoring checks
                health_scores = self._run_monitoring_cycle()

                # Generate outputs
                if health_scores:
                    self._generate_outputs(health_scores)

                # Update last check time
                self.last_check_time = datetime.now()

                cycle_duration = time.time() - cycle_start
                self.logger.info(
                    f"Monitoring cycle #{self.check_count} completed in {cycle_duration:.2f}s"
                )

                # Sleep until next check
                if self.running:
                    sleep_time = max(0, check_interval - cycle_duration)
                    if sleep_time > 0:
                        self.logger.debug(f"Sleeping for {sleep_time:.2f}s until next check")
                        time.sleep(sleep_time)

            except Exception as e:
                self.logger.error(f"Error in monitoring cycle: {e}", exc_info=True)

                # Sleep before retry
                self.logger.info("Retrying in 60 seconds...")
                time.sleep(60)

        self.logger.info("Monitoring service stopped")

    def _run_monitoring_cycle(self) -> List[HealthScore]:
        """
        Run one complete monitoring cycle.

        Executes all enabled monitors and collects health scores.

        Returns:
            List of HealthScore objects from all monitors

        Developer Notes:
        - Monitors can be run in parallel for better performance
        - Failures in individual monitors don't stop the cycle
        - Each monitor runs independently
        """
        health_scores: List[HealthScore] = []

        # Check if parallel processing is enabled
        parallel_enabled = self.config.get('advanced', {}).get('parallel_processing', {}).get('enabled', True)
        max_workers = self.config.get('advanced', {}).get('parallel_processing', {}).get('max_workers', 4)

        if parallel_enabled and len(self.monitors) > 1:
            # Run monitors in parallel
            self.logger.debug(f"Running {len(self.monitors)} monitors in parallel")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_monitor = {
                    executor.submit(self._run_single_monitor, name, monitor): name
                    for name, monitor in self.monitors.items()
                }

                for future in as_completed(future_to_monitor):
                    monitor_name = future_to_monitor[future]
                    try:
                        health_score = future.result()
                        if health_score:
                            health_scores.append(health_score)
                    except Exception as e:
                        self.logger.error(
                            f"Monitor {monitor_name} failed: {e}",
                            exc_info=True
                        )

        else:
            # Run monitors sequentially
            self.logger.debug(f"Running {len(self.monitors)} monitors sequentially")

            for monitor_name, monitor in self.monitors.items():
                try:
                    health_score = self._run_single_monitor(monitor_name, monitor)
                    if health_score:
                        health_scores.append(health_score)
                except Exception as e:
                    self.logger.error(
                        f"Monitor {monitor_name} failed: {e}",
                        exc_info=True
                    )

        return health_scores

    def _run_single_monitor(
        self,
        monitor_name: str,
        monitor: BaseProcessMonitor
    ) -> Optional[HealthScore]:
        """
        Run a single monitor and return its health score.

        Args:
            monitor_name: Name of the monitor
            monitor: Monitor instance

        Returns:
            HealthScore object or None if failed
        """
        try:
            self.logger.debug(f"Running monitor: {monitor_name}")
            start_time = time.time()

            health_score = monitor.calculate_health_score()

            duration = time.time() - start_time
            self.logger.info(
                f"Monitor {monitor_name} completed in {duration:.2f}s - "
                f"Score: {health_score.overall_score:.1f} ({health_score.overall_status.value})"
            )

            # Log any alerts
            if health_score.alerts:
                self.logger.warning(
                    f"Monitor {monitor_name} has {len(health_score.alerts)} alerts"
                )
                for alert in health_score.alerts:
                    self.logger.warning(f"  - {alert}")

            return health_score

        except Exception as e:
            self.logger.error(f"Error running monitor {monitor_name}: {e}", exc_info=True)
            return None

    def _generate_outputs(self, health_scores: List[HealthScore]):
        """
        Generate all output files.

        Args:
            health_scores: List of HealthScore objects
        """
        try:
            self.logger.debug("Generating output files")
            start_time = time.time()

            output_files = self.output_generator.generate_all_outputs(health_scores)

            duration = time.time() - start_time
            self.logger.info(f"Output generation completed in {duration:.2f}s")

            for format_name, file_path in output_files.items():
                self.logger.debug(f"  - {format_name}: {file_path}")

        except Exception as e:
            self.logger.error(f"Error generating outputs: {e}", exc_info=True)

    def get_status(self) -> Dict[str, Any]:
        """
        Get current service status.

        Returns:
            Dictionary with service status information
        """
        return {
            'running': self.running,
            'check_count': self.check_count,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'monitors': list(self.monitors.keys()),
            'config_file': self.config_path
        }


def main():
    """
    Main entry point for the monitoring service.

    Usage:
        python monitor_service.py [config_file]

    If config_file is not provided, defaults to ./monitor_config.yaml
    """
    # Get config file from command line or use default
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        config_file = './monitor_config.yaml'

    # Validate config file exists
    if not Path(config_file).exists():
        print(f"ERROR: Configuration file not found: {config_file}")
        print("\nUsage: python monitor_service.py [config_file]")
        sys.exit(1)

    # Create and start service
    try:
        service = MonitorService(config_file)
        service.start()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
