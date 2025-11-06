# ETL Process Health Monitoring Framework

A comprehensive, extensible real-time monitoring framework for ETL processes with Power BI dashboard integration.

## Overview

This framework provides continuous monitoring of ETL processes, performing automated health checks, calculating health scores, detecting anomalies, and generating XML output for Power BI dashboards. It's designed to run as a long-lived service with configurable thresholds and extensible architecture.

## Key Features

- **Real-time Monitoring**: Continuous monitoring with configurable check intervals (default: 5 minutes)
- **Configurable Thresholds**: All parameters externalized to YAML configuration
- **Extensible Architecture**: Easy to add new process types and custom checks
- **Power BI Integration**: XML output optimized for Power BI dashboards
- **Health Scoring**: Weighted scoring system with aggregate and detailed views
- **Automated Checks**:
  - Success/failure rate monitoring
  - Execution frequency analysis
  - Data volume anomaly detection
  - Sequential dependency tracking (for pipeline processes)
  - Message pattern analysis (ERROR/WARNING counts)
- **Production-Ready**: Long-running daemon with error recovery and logging
- **Historical Archival**: Automatic archiving for trend analysis

## Quick Start

```bash
# 1. Clone/download the repository
cd psa_process_logger_tick_files

# 2. Run setup
chmod +x setup.sh
./setup.sh

# 3. Activate virtual environment
source venv/bin/activate

# 4. Test the framework
python test_framework.py

# 5. Start the service
python framework/monitor_service.py
```

## Project Structure

```
psa_process_logger_tick_files/
├── framework/                          # Core framework code
│   ├── __init__.py                    # Package initialization
│   ├── base_monitor.py                # Abstract base classes
│   ├── tick_monitor.py                # Tick file process monitor
│   ├── mq_monitor.py                  # MQ summary process monitor
│   ├── output_generator.py            # XML/JSON output generation
│   └── monitor_service.py             # Main service coordinator
├── monitor_config.yaml                 # Configuration file ⚙️
├── requirements.txt                    # Python dependencies
├── setup.sh                           # Installation script
├── test_framework.py                  # Test script
├── README.md                          # This file
├── FRAMEWORK_DOCUMENTATION.md          # Complete documentation 📚
├── PROCESS_LOG_ANALYSIS_SUMMARY.md    # Initial data analysis
└── Process_Log_2023_RPT_Tick_MQ_Summary.xlsx  # Sample data

Generated at runtime:
├── logs/                              # Log files
├── output/                            # XML/JSON outputs for Power BI
└── output/archive/                    # Historical outputs
```

## Configuration

All monitoring parameters are configured in `monitor_config.yaml`:

```yaml
monitoring:
  check_interval: 300      # Check every 5 minutes
  lookback_days: 90        # 90 days of historical data

processes:
  tick_files:              # Tick file processes
    enabled: true
    frequency_thresholds:
      min_runs_per_day: 0.9
      max_days_without_run: 2
    success_thresholds:
      warning_rate: 95.0
      critical_rate: 90.0

  mq_summary:              # MQ summary pipeline
    enabled: true
    dependencies:
      enabled: true        # Check pipeline order
```

See `FRAMEWORK_DOCUMENTATION.md` for complete configuration reference.

## Monitored Processes

### Tick File Processes (9 parallel processes)
- Tick1-Tick9 File processes
- Daily execution (weekdays)
- ~5 million records per run
- Success rate: 98-99%

### MQ Summary Processes (4 sequential processes)
- MQ Load FCT_BID_ASK → FCT_TRADE → Summary → Summary Part 2
- Pipeline with dependencies
- Data operations: Inserts, Updates, Deletes
- Success rate: 99-100%

## Output Files

The framework generates three output files every check interval:

1. **process_health.xml** - Aggregate view for Power BI (primary)
2. **process_health_detailed.xml** - Detailed view with all checks
3. **process_health.json** - JSON format for debugging

### Power BI Integration

Import XML into Power BI:

1. Power BI Desktop → Get Data → XML
2. Load `output/process_health.xml`
3. Transform data (set column types)
4. Create visualizations:
   - Gauge: Overall Health Score
   - Table: Process Groups by Status
   - Bar Chart: Component Scores
   - Table: Active Alerts

See `FRAMEWORK_DOCUMENTATION.md` → Power BI Integration for detailed instructions.

## Extending the Framework

The framework is designed for easy extension:

### Adding a New Process Type

1. Create a new monitor class inheriting from `BaseProcessMonitor`
2. Add configuration to `monitor_config.yaml`
3. Register in `monitor_service.py`

Example:

```python
from framework.base_monitor import BaseProcessMonitor, MonitorResult

class MyProcessMonitor(BaseProcessMonitor):
    def get_process_data(self, lookback_days):
        # Query your database table
        pass

    def check_failure_rate(self):
        # Implement check
        return MonitorResult(...)

    def check_execution_frequency(self):
        # Implement check
        return MonitorResult(...)

    def check_data_volume(self):
        # Implement check
        return MonitorResult(...)
```

See `FRAMEWORK_DOCUMENTATION.md` → Extending the Framework for complete guide.

## Health Scoring

Each process group receives a health score (0-100) calculated from weighted components:

```
Overall Score = Σ (Component Score × Component Weight)
```

**Status Categories**:
- 95-100: EXCELLENT (Green)
- 85-94: GOOD (Light Green)
- 70-84: FAIR (Yellow)
- 50-69: POOR (Orange)
- 0-49: CRITICAL (Red)

**Example Weights** (configurable):
- Success Rate: 30%
- Execution Frequency: 20%
- Data Volume Consistency: 20%
- Duration: 10%
- Message Quality: 10%
- Pre/Post Processing: 10%

## Monitoring Checks

The framework performs these automated checks:

1. **Failure Detection**: Success/failure rates, consecutive failures
2. **Frequency Monitoring**: Runs per day, missing executions
3. **Volume Anomaly Detection**: Data volume vs baseline (statistical)
4. **Dependency Checking**: Sequential pipeline integrity (MQ processes)
5. **Message Analysis**: ERROR/WARNING message patterns
6. **Duration Monitoring**: Execution time analysis (optional)

## Running as a Service

### Systemd (Linux)

```bash
# Install as system service
sudo cp process-monitor.service.sample /etc/systemd/system/process-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable process-monitor
sudo systemctl start process-monitor

# Check status
sudo systemctl status process-monitor

# View logs
sudo journalctl -u process-monitor -f
```

### Manual Start

```bash
# Foreground
python framework/monitor_service.py

# Background (nohup)
nohup python framework/monitor_service.py > monitor.out 2>&1 &

# Background (screen)
screen -S monitor
python framework/monitor_service.py
# Ctrl+A, D to detach
```

## Logs

Logs are written to:
- `logs/process_monitor.log` - All logs (INFO level)
- `logs/process_monitor_errors.log` - Errors only

```bash
# View live logs
tail -f logs/process_monitor.log

# View errors only
tail -f logs/process_monitor_errors.log

# Search for specific process
grep "Tick1 File" logs/process_monitor.log
```

## Troubleshooting

### No data / Empty results
- Check database connection
- Verify table names and process IDs in config
- Increase `lookback_days` value

### All scores show 50.0
- Insufficient historical data (< 10 samples)
- Lower `min_sample_size` threshold
- Check database queries returning data

### Output files not generated
- Check permissions on output directory
- Review logs for errors
- Ensure OutputGenerator initialized

### Power BI import errors
- Validate XML: `xmllint --noout output/process_health.xml`
- Check for special characters in data
- Ensure file isn't locked

See `FRAMEWORK_DOCUMENTATION.md` → Troubleshooting for complete guide.

## Requirements

- Python 3.8 or higher
- Oracle Database access (for production)
- Dependencies: pandas, numpy, pyyaml, openpyxl, requests

See `requirements.txt` for complete list.

## Documentation

- **README.md** (this file): Quick start and overview
- **FRAMEWORK_DOCUMENTATION.md**: Complete documentation
  - Architecture
  - Configuration reference
  - Extending the framework
  - Power BI integration
  - API reference
  - Troubleshooting
  - Best practices
- **PROCESS_LOG_ANALYSIS_SUMMARY.md**: Initial data analysis
  - Process inventory
  - Historical patterns
  - Monitoring recommendations

## Configuration Tuning

### Threshold Adjustment Guidelines

**Success Rate** (adjust based on process maturity):
- Mature processes: 98%+ warning threshold
- New processes: 85%+ warning threshold

**Frequency** (adjust based on schedule):
- Daily: `min_runs_per_day: 0.9, max_runs_per_day: 1.5`
- Hourly: `min_runs_per_day: 20, max_runs_per_day: 26`
- Weekly: `min_runs_per_day: 0.1, max_runs_per_day: 0.2`

**Volume** (adjust based on business requirements):
- Critical processes: Tighter thresholds (30% deviation)
- Variable processes: Looser thresholds (70% deviation)

**Health Weights** (adjust based on priorities):
- Mission-critical: Increase `success_rate` weight to 0.50
- Real-time: Increase `duration` weight to 0.25
- High-volume: Increase `volume_consistency` to 0.30

## Architecture Highlights

### Extensibility

The framework uses:
- **Abstract Base Classes**: Easy to inherit and extend
- **Dependency Injection**: Monitors receive config and DB connection
- **Strategy Pattern**: Different monitor types for different processes
- **Factory Pattern**: MonitorService creates appropriate monitors
- **Data Classes**: Clean data structures for results

### Production Features

- **Error Recovery**: Graceful handling of database failures
- **Retry Logic**: Automatic retry of failed operations
- **Log Rotation**: Automatic log file rotation (100MB, 5 backups)
- **Archive Cleanup**: Automatic cleanup of old archives (30 days)
- **Caching**: Optional caching to reduce database load
- **Parallel Processing**: Optional parallel execution of monitors
- **Graceful Shutdown**: Handles SIGTERM/SIGINT signals

## Example Output

### Console Output

```
================================================================================
Process Health Monitoring Service Initialized
================================================================================
Configuration: ./monitor_config.yaml
Monitors initialized: 2
Check interval: 300s

Starting monitoring cycle #1
Monitor tick_files completed in 2.35s - Score: 96.8 (EXCELLENT)
Monitor mq_summary completed in 1.82s - Score: 99.2 (EXCELLENT)
Output generation completed in 0.45s
  - aggregate_xml: ./output/process_health.xml
  - detailed_xml: ./output/process_health_detailed.xml
  - json: ./output/process_health.json
Monitoring cycle #1 completed in 4.62s
```

### XML Output (Sample)

```xml
<ProcessHealthMonitor>
  <GeneratedAt>2025-01-15T10:30:00</GeneratedAt>
  <OverallHealth>
    <Score>98.0</Score>
    <Status>EXCELLENT</Status>
  </OverallHealth>
  <ProcessGroups>
    <ProcessGroup>
      <Name>Tick file ETL processes</Name>
      <Score>96.8</Score>
      <Status>EXCELLENT</Status>
      <Trend>STABLE</Trend>
      <AlertCount>0</AlertCount>
    </ProcessGroup>
  </ProcessGroups>
</ProcessHealthMonitor>
```

## Development

### Testing

```bash
# Run test cycle
python test_framework.py

# Run with debug logging
# Edit monitor_config.yaml: logging.level: "DEBUG"
python framework/monitor_service.py

# Validate configuration
python -c "import yaml; yaml.safe_load(open('monitor_config.yaml'))"

# Check XML validity
xmllint --noout output/process_health.xml
```

### Code Structure

- **base_monitor.py**: Core abstractions (400+ lines)
- **tick_monitor.py**: Tick process implementation (450+ lines)
- **mq_monitor.py**: MQ process implementation (500+ lines)
- **output_generator.py**: XML/JSON generation (450+ lines)
- **monitor_service.py**: Main coordinator (350+ lines)

Total: ~2200 lines of well-documented Python code

## Version History

**1.0.0** (2025)
- Initial release
- Support for Tick File and MQ Summary processes
- Real-time monitoring with configurable thresholds
- Power BI XML output
- Health scoring system
- Production-ready daemon

## License

Internal use for ETL monitoring purposes.

## Author

ETL Monitoring Framework Team

---

**For complete documentation, see `FRAMEWORK_DOCUMENTATION.md`**

**For data analysis and monitoring insights, see `PROCESS_LOG_ANALYSIS_SUMMARY.md`**
