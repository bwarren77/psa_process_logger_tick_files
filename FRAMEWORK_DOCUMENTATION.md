# ETL Process Health Monitoring Framework

## Complete Documentation

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Service](#running-the-service)
6. [Power BI Integration](#power-bi-integration)
7. [Extending the Framework](#extending-the-framework)
8. [Monitoring Checks](#monitoring-checks)
9. [Health Scoring System](#health-scoring-system)
10. [Troubleshooting](#troubleshooting)
11. [Best Practices](#best-practices)
12. [API Reference](#api-reference)

---

## Overview

### Purpose

The ETL Process Health Monitoring Framework is a comprehensive, extensible system designed to monitor ETL (Extract, Transform, Load) processes in real-time and provide health assessments through configurable thresholds and automated checks.

### Key Features

- **Real-time Monitoring**: Continuous monitoring of ETL processes with configurable check intervals
- **Configurable Thresholds**: All monitoring parameters can be adjusted via YAML configuration
- **Extensible Architecture**: Easy to add new process types and custom checks
- **Power BI Integration**: XML output format optimized for Power BI dashboards
- **Aggregate & Detailed Views**: Both high-level and detailed monitoring data available
- **Health Scoring**: Weighted health scores with status categorization
- **Alert System**: Configurable alerting for failures and anomalies
- **Archival**: Historical data retention for trend analysis
- **Production-Ready**: Designed as a long-running daemon with error recovery

### What It Monitors

The framework currently monitors two types of ETL processes:

1. **Tick File Processes** (9 parallel processes)
   - Success/failure rates
   - Execution frequency
   - Data volume (inserted records, file sizes)
   - Pre/post processing completion
   - Message patterns (errors, warnings)

2. **MQ Summary Processes** (4 sequential pipeline processes)
   - Success/failure rates
   - Pipeline execution order
   - Data operations (inserts, updates, deletes)
   - Sequential dependencies
   - Time gaps between processes

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     Monitor Service (Main)                       │
│  - Service Coordinator                                           │
│  - Scheduling & Orchestration                                    │
│  - Error Handling & Recovery                                     │
└────────────────────┬────────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
┌────────▼─────────┐    ┌───────▼─────────┐
│  Tick Monitor    │    │   MQ Monitor    │
│  (9 processes)   │    │  (4 processes)  │
└────────┬─────────┘    └───────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   Output Generator    │
         │  - XML (Power BI)     │
         │  - JSON (Debug)       │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   Output Files        │
         │  - Aggregate XML      │
         │  - Detailed XML       │
         │  - JSON               │
         │  - Archives           │
         └───────────────────────┘
```

### Class Hierarchy

```
BaseProcessMonitor (Abstract)
├── TickFileMonitor
└── MQSummaryMonitor

MonitorResult (Data Class)
HealthScore (Data Class)

ThresholdEvaluator (Static Utilities)

OutputGenerator
└── PowerBISchemaHelper

MonitorService (Main Coordinator)
```

### Data Flow

```
1. MonitorService starts
   ↓
2. Load configuration from YAML
   ↓
3. Initialize monitors (Tick, MQ)
   ↓
4. Every N seconds (check_interval):
   a. Each monitor:
      - Queries database for process data
      - Runs configured checks
      - Calculates component scores
      - Aggregates into overall health score
   b. OutputGenerator:
      - Collects all health scores
      - Generates XML files for Power BI
      - Generates JSON for debugging
      - Archives previous outputs
   ↓
5. Sleep until next check interval
   ↓
6. Repeat from step 4
```

### File Structure

```
psa_process_logger_tick_files/
├── framework/
│   ├── __init__.py              # Package initialization
│   ├── base_monitor.py          # Abstract base classes
│   ├── tick_monitor.py          # Tick file monitor implementation
│   ├── mq_monitor.py            # MQ summary monitor implementation
│   ├── output_generator.py     # XML/JSON output generation
│   └── monitor_service.py       # Main service coordinator
├── monitor_config.yaml          # Configuration file
├── requirements.txt             # Python dependencies
├── setup.sh                     # Installation script
├── FRAMEWORK_DOCUMENTATION.md   # This file
├── PROCESS_LOG_ANALYSIS_SUMMARY.md  # Initial data analysis
├── logs/                        # Log files (created at runtime)
├── output/                      # Output files (created at runtime)
│   ├── process_health.xml
│   ├── process_health_detailed.xml
│   ├── process_health.json
│   └── archive/                 # Historical outputs
└── models/                      # ML models (future enhancement)
```

---

## Installation

### Prerequisites

- Python 3.8 or higher
- Oracle Database access (for production)
- Sufficient disk space for logs and archives (~1GB recommended)

### Quick Start

```bash
# Clone or download the repository
cd psa_process_logger_tick_files

# Run setup script
chmod +x setup.sh
./setup.sh

# Activate virtual environment
source venv/bin/activate

# Start the service
python framework/monitor_service.py
```

### Manual Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir -p logs output output/archive models

# Configure settings
vi monitor_config.yaml

# Run service
python framework/monitor_service.py
```

### Installing as a System Service (Linux)

```bash
# Copy sample service file
sudo cp process-monitor.service.sample /etc/systemd/system/process-monitor.service

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable process-monitor

# Start service
sudo systemctl start process-monitor

# Check status
sudo systemctl status process-monitor

# View logs
sudo journalctl -u process-monitor -f
```

---

## Configuration

The framework is configured via `monitor_config.yaml`. All monitoring parameters, thresholds, and behaviors are externalized to this file.

### Configuration Sections

#### 1. Database Connection

```yaml
database:
  host: "localhost"
  port: 1521
  service_name: "ORCL"
  username: "etl_monitor"
  password: "${DB_PASSWORD}"  # Use environment variable
```

**Security Note**: Store passwords in environment variables, not in the YAML file.

```bash
export DB_PASSWORD="your_password"
```

#### 2. Monitoring Settings

```yaml
monitoring:
  check_interval: 300  # Check every 5 minutes
  lookback_days: 90    # Analyze 90 days of history
  recent_days: 2       # Last 2 days for immediate alerts

  features:
    failure_detection: true
    frequency_monitoring: true
    volume_anomaly_detection: true
    duration_monitoring: false  # Disabled (parsing issue)
    dependency_tracking: true
    message_analysis: true
```

**Key Parameters**:
- `check_interval`: How often to run checks (seconds)
- `lookback_days`: Historical window for baseline calculation
- `recent_days`: Window for immediate alert detection

#### 3. Output Settings

```yaml
output:
  xml_path: "./output/process_health.xml"
  xml_detailed_path: "./output/process_health_detailed.xml"
  json_path: "./output/process_health.json"

  archive_enabled: true
  archive_path: "./output/archive/"
  archive_retention_days: 30
```

**Output Files**:
- `process_health.xml`: Aggregate view for Power BI (primary)
- `process_health_detailed.xml`: Detailed view with all checks
- `process_health.json`: JSON format for debugging

#### 4. Process Definitions

Each process group has its own configuration section:

```yaml
processes:
  tick_files:
    enabled: true
    description: "Tick file ETL processes"
    table_name: "PROCESS_LOG_TICKS"
    process_ids: [603, 839, 840, 841, 842, 843, 844, 845, 846]

    frequency_thresholds:
      min_runs_per_day: 0.9
      max_runs_per_day: 1.5
      max_days_without_run: 2

    volume_thresholds:
      baseline_median: 5000000
      warning_decrease_pct: 50.0
      critical_decrease_pct: 80.0

    success_thresholds:
      warning_rate: 95.0
      critical_rate: 90.0
```

### Threshold Tuning Guidelines

#### Success Rate Thresholds

- **Excellent**: 95-100% success rate
- **Good/Fair**: 90-95% success rate
- **Critical**: <90% success rate

Adjust based on your process reliability:
- Mature, stable processes: Tighter thresholds (98%+)
- New or experimental processes: Looser thresholds (85%+)

#### Frequency Thresholds

Set based on expected schedule:
- **Daily processes**: `min_runs_per_day: 0.9, max_runs_per_day: 1.5`
- **Hourly processes**: `min_runs_per_day: 20, max_runs_per_day: 26`
- **Weekly processes**: `min_runs_per_day: 0.1, max_runs_per_day: 0.2`

#### Volume Thresholds

Initial baseline values should be set from historical analysis:

```bash
# Calculate baseline from historical data
SELECT
    MEDIAN(stat_value_1) as baseline_median,
    STDDEV(stat_value_1) as baseline_stddev
FROM process_log_table
WHERE stat_value_name_1 = 'Inserted records'
  AND process_date >= SYSDATE - 90
```

The framework automatically updates baselines over time if `adaptive_thresholds` is enabled.

---

## Running the Service

### Starting the Service

```bash
# Foreground (for testing)
python framework/monitor_service.py

# With custom config file
python framework/monitor_service.py /path/to/config.yaml

# Background (using nohup)
nohup python framework/monitor_service.py > monitor.out 2>&1 &

# Background (using screen)
screen -S monitor
python framework/monitor_service.py
# Press Ctrl+A, D to detach

# As systemd service
sudo systemctl start process-monitor
```

### Stopping the Service

```bash
# Graceful shutdown (if running in foreground)
Ctrl+C

# Kill background process
pkill -f monitor_service.py

# Stop systemd service
sudo systemctl stop process-monitor
```

### Monitoring the Service

```bash
# View live logs
tail -f logs/process_monitor.log

# View errors only
tail -f logs/process_monitor_errors.log

# View systemd service logs
sudo journalctl -u process-monitor -f

# Check output files
ls -lh output/

# Validate XML output
xmllint --noout output/process_health.xml
```

### Service Health Indicators

**Healthy Service**:
- Log shows regular "Monitoring cycle #N completed" messages
- Output files are updated every check_interval
- No repeated error messages
- Health scores are being calculated

**Unhealthy Service**:
- "Error in monitoring cycle" messages
- Output files not updating
- Database connection errors
- Exceptions in error log

---

## Power BI Integration

### Importing XML into Power BI

1. **Open Power BI Desktop**

2. **Get Data** → **XML**
   - Browse to: `output/process_health.xml`
   - Click **Load**

3. **Power Query Editor will open** with detected tables:
   - `ProcessGroups` (main table)
   - `Components` (component scores)
   - `Alerts` (active alerts)
   - `OverallHealth` (system-wide metrics)

4. **Transform Data** (recommended):

   **ProcessGroups Table**:
   ```
   - Change Score type → Decimal Number
   - Change Timestamp type → Date/Time
   - Change AlertCount type → Whole Number
   - Change Status type → Text (already is)
   ```

   **Components Table**:
   ```
   - Change Score type → Decimal Number
   - Add Index Column → Group By ProcessGroup
   ```

   **Alerts Table**:
   ```
   - Change Timestamp type → Date/Time
   ```

5. **Create Relationships**:
   - ProcessGroups[Name] ← Components[ProcessGroup]
   - ProcessGroups[Name] ← Alerts[ProcessGroup]

6. **Close & Apply**

### Recommended Visualizations

#### Dashboard Layout

```
┌──────────────────────────────────────────────────────────────┐
│  Overall Health Score (Card/Gauge)          Last Updated     │
├──────────────────────────────────────────────────────────────┤
│  Process Groups Health (Table)                               │
│  Name | Score | Status | Trend | Alerts                      │
├───────────────────────────────────┬──────────────────────────┤
│  Component Scores (Stacked Bar)   │  Active Alerts (Table)   │
│  By Process Group                 │  Sorted by Severity      │
├───────────────────────────────────┴──────────────────────────┤
│  Health Trend (Line Chart - Historical)                      │
└──────────────────────────────────────────────────────────────┘
```

#### Visualization Details

**1. Overall Health Gauge**
- Visual: Gauge or Card
- Field: OverallHealth[Score]
- Colors: 0-50 (Red), 50-70 (Orange), 70-85 (Yellow), 85-95 (Light Green), 95-100 (Green)

**2. Process Groups Table**
- Visual: Table or Matrix
- Columns:
  - Name (ProcessGroups[Name])
  - Score (ProcessGroups[Score]) - Conditional formatting by value
  - Status (ProcessGroups[Status]) - Conditional formatting by text
  - Trend (ProcessGroups[Trend]) - Custom icons
  - Alerts (ProcessGroups[AlertCount])
- Conditional Formatting:
  - Score: Data bars with color gradient
  - Status: Background color by status value

**3. Component Scores Bar Chart**
- Visual: Stacked Bar Chart
- Axis: ProcessGroups[Name]
- Legend: Components[Name]
- Values: Components[Score]
- Colors: Custom palette

**4. Active Alerts Table**
- Visual: Table
- Columns:
  - ProcessGroup (Alerts[ProcessGroup])
  - Message (Alerts[Message])
  - Time (Alerts[Timestamp])
- Sort: By Timestamp descending
- Conditional: Highlight rows with "CRITICAL"

**5. Historical Trend Line Chart**
- Visual: Line Chart
- Axis: Timestamp (from archived data)
- Values: Score by ProcessGroup
- Legend: ProcessGroup names
- Note: Requires importing archived XML files as separate queries

### Power BI Refresh Settings

**For Real-Time Monitoring**:

1. **File** → **Options** → **Data load**
   - Refresh data: Every 5 minutes

2. **For Power BI Service** (Cloud):
   - Publish report
   - Configure gateway (if using on-prem file)
   - Set scheduled refresh: Every 30 minutes to 1 hour
   - Enable automatic page refresh (5-10 minutes)

### Power BI Measures (DAX)

Create custom measures for enhanced analytics:

```dax
// Overall Health Status
Health Status =
SWITCH(
    TRUE(),
    [Overall Health Score] >= 95, "Excellent",
    [Overall Health Score] >= 85, "Good",
    [Overall Health Score] >= 70, "Fair",
    [Overall Health Score] >= 50, "Poor",
    "Critical"
)

// Alert Count Total
Total Alerts = COUNTROWS(Alerts)

// Critical Alerts Count
Critical Alerts =
CALCULATE(
    COUNTROWS(Alerts),
    SEARCH("CRITICAL", Alerts[Message], 1, 0) > 0
)

// Processes Below Threshold
Processes Below Threshold =
CALCULATE(
    COUNTROWS(ProcessGroups),
    ProcessGroups[Score] < 85
)
```

---

## Extending the Framework

The framework is designed to be easily extended with new process types and custom checks.

### Adding a New Process Type

**Step 1: Create Monitor Class**

Create a new file `framework/your_monitor.py`:

```python
from framework.base_monitor import (
    BaseProcessMonitor,
    MonitorResult,
    HealthStatus,
    AlertLevel,
    CheckType
)

class YourProcessMonitor(BaseProcessMonitor):
    """Monitor for your custom process type."""

    def get_process_data(self, lookback_days: int):
        # Query your database table
        # Return pandas DataFrame
        pass

    def check_failure_rate(self) -> MonitorResult:
        # Implement failure rate check
        pass

    def check_execution_frequency(self) -> MonitorResult:
        # Implement frequency check
        pass

    def check_data_volume(self) -> MonitorResult:
        # Implement volume check
        pass

    # Optional: Add custom checks
    def check_custom_metric(self) -> MonitorResult:
        # Your custom check logic
        pass
```

**Step 2: Add Configuration**

In `monitor_config.yaml`, add a new section:

```yaml
processes:
  your_process:
    enabled: true
    description: "Your custom process description"
    table_name: "YOUR_PROCESS_LOG_TABLE"
    process_ids: [101, 102, 103]
    process_names:
      - "Process 1"
      - "Process 2"
      - "Process 3"

    # Your custom thresholds
    frequency_thresholds:
      min_runs_per_day: 1.0
      max_runs_per_day: 1.0

    volume_thresholds:
      baseline_median: 1000
      warning_decrease_pct: 50.0

    success_thresholds:
      warning_rate: 95.0
      critical_rate: 90.0

    health_weights:
      success_rate: 0.40
      frequency: 0.30
      volume_consistency: 0.30
```

**Step 3: Register Monitor**

In `framework/monitor_service.py`, modify `_initialize_monitors()`:

```python
def _initialize_monitors(self):
    # ... existing code ...

    for process_group_name, process_config in processes_config.items():
        # ... existing code ...

        if process_group_name == 'your_process':
            from framework.your_monitor import YourProcessMonitor
            monitor = YourProcessMonitor(process_config, db_connection, self.logger)
```

**Step 4: Test**

```bash
python framework/monitor_service.py
# Check logs for your new monitor
tail -f logs/process_monitor.log | grep "your_process"
```

### Adding Custom Checks

To add a new check to an existing monitor:

```python
class TickFileMonitor(BaseProcessMonitor):
    # ... existing methods ...

    def check_file_naming_convention(self) -> Optional[MonitorResult]:
        """Check if files follow naming convention."""
        df = self._get_cached_data(90)

        # Your custom logic
        naming_violations = 0
        for filename in df['FILE_NAME']:
            if not filename.startswith('TICK_'):
                naming_violations += 1

        if naming_violations == 0:
            status = HealthStatus.EXCELLENT
            score = 100.0
            message = "All files follow naming convention"
        else:
            status = HealthStatus.FAIR
            score = 70.0
            message = f"{naming_violations} files violate naming convention"

        return MonitorResult(
            check_type=CheckType.MESSAGE_ANALYSIS,  # Or create new CheckType
            check_name="File Naming Convention Check",
            status=status,
            score=score,
            alert_level=AlertLevel.WARNING if naming_violations > 0 else AlertLevel.INFO,
            message=message,
            details={'violations': naming_violations}
        )
```

Then add to `health_weights` in config:

```yaml
health_weights:
  success_rate: 0.25
  frequency: 0.20
  volume_consistency: 0.20
  duration: 0.10
  message_quality: 0.10
  naming_convention: 0.15  # New check
```

### Adding New Output Formats

To add a new output format (e.g., CSV):

```python
class OutputGenerator:
    # ... existing methods ...

    def generate_csv(self, health_scores: List[HealthScore]) -> Path:
        """Generate CSV output."""
        import csv

        csv_path = self.csv_path  # Add to config
        tmp_file = csv_path.with_suffix('.tmp')

        with open(tmp_file, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(['ProcessGroup', 'Score', 'Status', 'Timestamp'])

            # Data
            for hs in health_scores:
                writer.writerow([
                    hs.process_name,
                    hs.overall_score,
                    hs.overall_status.value,
                    hs.timestamp.isoformat()
                ])

        tmp_file.replace(csv_path)
        return csv_path
```

---

## Monitoring Checks

### Check Types

The framework performs several types of checks:

#### 1. Failure Detection (SUCCESS_RATE)

**What it checks**:
- Overall success/failure rate
- Per-process success rates
- Consecutive failures

**Thresholds**:
```yaml
success_thresholds:
  warning_rate: 95.0    # Warn if < 95% success
  critical_rate: 90.0   # Critical if < 90% success
  min_sample_size: 10   # Need 10+ runs to evaluate
```

**Score Calculation**:
```
Score = Success Rate Percentage
```

#### 2. Frequency Monitoring (FREQUENCY_MONITORING)

**What it checks**:
- Runs per day vs expected
- Coverage (% of expected days with runs)
- Missing recent runs

**Thresholds**:
```yaml
frequency_thresholds:
  min_runs_per_day: 0.9
  max_runs_per_day: 1.5
  max_days_without_run: 2
  min_coverage_percentage: 65.0
```

**Score Calculation**:
```
Coverage Score = (actual_coverage / expected_coverage) * 100
Frequency Score = 100 if within range, else 70
Overall Score = (Coverage * 0.6) + (Frequency * 0.4)
```

#### 3. Volume Anomaly Detection (VOLUME_ANOMALY)

**What it checks**:
- Data volume (records, file size) vs baseline
- Standard deviation analysis
- Recent volume trends

**Thresholds**:
```yaml
volume_thresholds:
  warning_stddev_multiplier: 2.0   # 2 std devs
  critical_stddev_multiplier: 3.0  # 3 std devs
  warning_decrease_pct: 50.0
  critical_decrease_pct: 80.0
```

**Score Calculation**:
```
Deviation Score = max(0, 100 - (deviation_from_baseline / stddev * 10))
```

#### 4. Duration Monitoring (DURATION_MONITORING)

**What it checks**:
- Execution duration vs baseline
- Unusually long-running processes

**Note**: Currently disabled due to duration field parsing issues. Can be enabled once parsing is fixed.

#### 5. Dependency Checking (DEPENDENCY_CHECK)

**What it checks** (MQ processes only):
- Sequential execution order
- Time gaps between pipeline stages
- Missing processes in pipeline
- Orphaned downstream processes

**Thresholds**:
```yaml
dependencies:
  enabled: true
  pipeline_order: [438, 441, 442, 443]
  max_time_gap_minutes: 60
```

#### 6. Message Analysis (MESSAGE_ANALYSIS)

**What it checks**:
- ERROR message count
- WARNING message count
- Message type distribution

**Thresholds**:
```yaml
message_thresholds:
  max_error_percentage: 1.0
  max_warning_percentage: 5.0
  consecutive_failures_critical: 3
```

---

## Health Scoring System

### Score Calculation

Each process group receives an overall health score (0-100) calculated as a weighted average of component scores:

```
Overall Score = Σ (Component Score × Component Weight)
```

### Component Weights

Weights are configurable per process type. Example for Tick processes:

```yaml
health_weights:
  success_rate: 0.30         # 30% weight
  frequency: 0.20            # 20% weight
  volume_consistency: 0.20   # 20% weight
  duration: 0.10             # 10% weight
  message_quality: 0.10      # 10% weight
  preprocessing: 0.10        # 10% weight
```

Adjust weights based on what's most important for your processes. Example adjustments:

- **Mission-critical processes**: Increase `success_rate` weight to 0.50
- **Real-time processes**: Increase `duration` weight to 0.25
- **High-volume processes**: Increase `volume_consistency` weight to 0.30

### Status Mapping

Scores are mapped to status categories:

| Score Range | Status | Color | Meaning |
|-------------|--------|-------|---------|
| 95-100 | EXCELLENT | Green | Optimal performance |
| 85-94 | GOOD | Light Green | Normal performance |
| 70-84 | FAIR | Yellow | Minor issues |
| 50-69 | POOR | Orange | Significant issues |
| 0-49 | CRITICAL | Red | Severe issues |

### Example Calculation

**Tick File Process**:

```
Component Scores:
- Success Rate: 98.5% → Score: 98.5
- Frequency: Normal → Score: 100.0
- Volume: -10% from baseline → Score: 90.0
- Message Quality: 2 errors → Score: 98.0

Weights:
- Success Rate: 0.30
- Frequency: 0.20
- Volume: 0.20
- Message Quality: 0.30

Calculation:
Overall = (98.5 × 0.30) + (100.0 × 0.20) + (90.0 × 0.20) + (98.0 × 0.30)
        = 29.55 + 20.00 + 18.00 + 29.40
        = 96.95

Status: EXCELLENT (95-100)
```

---

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

**Symptom**: Service exits immediately or fails to start

**Possible Causes**:
- Configuration file not found
- Invalid YAML syntax
- Python version < 3.8
- Missing dependencies

**Solutions**:
```bash
# Check Python version
python3 --version

# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('monitor_config.yaml'))"

# Reinstall dependencies
pip install -r requirements.txt

# Check logs
cat logs/process_monitor.log
```

#### 2. No Data / Empty Results

**Symptom**: Monitors report "No data available"

**Possible Causes**:
- Database connection failure
- Wrong table name
- Wrong process IDs
- Lookback window too small

**Solutions**:
```bash
# Test database connection
python3 << EOF
import cx_Oracle
conn = cx_Oracle.connect('user/pass@host:port/service')
print("Connection successful")
EOF

# Verify table exists
SELECT COUNT(*) FROM PROCESS_LOG_TICKS;

# Check process IDs
SELECT DISTINCT PROCESS_ID FROM PROCESS_LOG_TICKS;

# Increase lookback window in config
lookback_days: 180  # Try 6 months
```

#### 3. Output Files Not Generated

**Symptom**: No XML/JSON files in output directory

**Possible Causes**:
- Permission issues
- Output directory doesn't exist
- OutputGenerator initialization failed

**Solutions**:
```bash
# Check permissions
ls -la output/

# Create directories
mkdir -p output output/archive

# Check service logs
grep -i "output" logs/process_monitor.log
grep -i "error" logs/process_monitor_errors.log
```

#### 4. All Scores Show 50.0

**Symptom**: Every health score is exactly 50.0

**Possible Causes**:
- Insufficient historical data
- All checks returning UNKNOWN status
- Database queries returning empty results

**Solutions**:
```bash
# Check data availability
SELECT
    PROCESS_ID,
    COUNT(*) as record_count,
    MIN(PROCESS_DATE) as earliest,
    MAX(PROCESS_DATE) as latest
FROM PROCESS_LOG_TICKS
GROUP BY PROCESS_ID;

# Reduce min_sample_size threshold
success_thresholds:
  min_sample_size: 5  # Lower from 10

# Check logs for UNKNOWN statuses
grep "UNKNOWN" logs/process_monitor.log
```

#### 5. High Memory Usage

**Symptom**: Service consumes excessive memory

**Possible Causes**:
- Large result sets from database
- Caching too much data
- Memory leaks

**Solutions**:
```bash
# Reduce lookback window
lookback_days: 30  # Lower from 90

# Disable caching
caching:
  enabled: false

# Monitor memory usage
ps aux | grep monitor_service
```

#### 6. Power BI Can't Import XML

**Symptom**: Power BI reports XML parsing errors

**Possible Causes**:
- Malformed XML
- Special characters in data
- File locked by another process

**Solutions**:
```bash
# Validate XML
xmllint --noout output/process_health.xml

# Check for special characters
grep -P "[\x00-\x08\x0B-\x0C\x0E-\x1F]" output/process_health.xml

# Ensure file isn't locked
lsof output/process_health.xml
```

### Debug Mode

Enable detailed logging for troubleshooting:

```yaml
logging:
  level: "DEBUG"  # Change from INFO to DEBUG
```

Then restart the service and check logs:

```bash
tail -f logs/process_monitor.log | grep DEBUG
```

### Health Check Script

Create a simple health check script:

```bash
#!/bin/bash
# health_check.sh

echo "=== Process Monitor Health Check ==="

# Check if service is running
if pgrep -f monitor_service.py > /dev/null; then
    echo "✓ Service is running"
else
    echo "✗ Service is NOT running"
fi

# Check last output file update
if [ -f "output/process_health.xml" ]; then
    AGE=$(($(date +%s) - $(stat -c %Y output/process_health.xml)))
    echo "✓ Last output: $AGE seconds ago"

    if [ $AGE -gt 600 ]; then
        echo "  ⚠ WARNING: Output is stale (>10 min)"
    fi
else
    echo "✗ No output file found"
fi

# Check for recent errors
ERROR_COUNT=$(grep -c ERROR logs/process_monitor.log | tail -1000)
echo "✓ Recent errors: $ERROR_COUNT"

if [ $ERROR_COUNT -gt 10 ]; then
    echo "  ⚠ WARNING: High error count"
fi

# Check disk space
DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
echo "✓ Disk usage: $DISK_USAGE%"

if [ $DISK_USAGE -gt 90 ]; then
    echo "  ⚠ WARNING: Disk space low"
fi
```

---

## Best Practices

### Configuration Management

1. **Version Control**: Store `monitor_config.yaml` in git
2. **Environment Variables**: Use for sensitive data (passwords)
3. **Documentation**: Comment your custom thresholds
4. **Backup**: Keep backup of working configuration

### Threshold Tuning

1. **Start Conservative**: Use default thresholds initially
2. **Analyze Baseline**: Review 90 days of history before tuning
3. **Iterate Gradually**: Adjust thresholds incrementally
4. **Document Changes**: Note why thresholds were changed
5. **Monitor Impact**: Watch for false positives/negatives

### Production Deployment

1. **Test First**: Run in test environment for 1-2 weeks
2. **Staged Rollout**: Monitor one process group first
3. **Alert Channels**: Configure email/webhook alerts
4. **Monitoring**: Monitor the monitor (meta-monitoring)
5. **Backup Plan**: Have rollback procedure ready

### Performance Optimization

1. **Caching**: Enable for repeated queries
2. **Parallel Processing**: Enable for multiple process groups
3. **Lookback Window**: Balance between accuracy and performance
4. **Database Indexes**: Ensure process log tables are indexed
5. **Archive Cleanup**: Regularly purge old archives

### Security

1. **Database Credentials**: Use environment variables or secrets manager
2. **File Permissions**: Restrict access to logs and output
3. **Network**: Use encrypted database connections
4. **Audit**: Log all configuration changes
5. **Principle of Least Privilege**: Use read-only database user

### Maintenance

1. **Log Rotation**: Configured automatically via rotating file handler
2. **Archive Cleanup**: Configured via `archive_retention_days`
3. **Dependency Updates**: Regularly update Python packages
4. **Configuration Review**: Quarterly review of thresholds
5. **Documentation Updates**: Keep docs in sync with code

---

## API Reference

### BaseProcessMonitor

Abstract base class for all process monitors.

**Methods**:

```python
def get_process_data(lookback_days: int) -> Any
    """Retrieve process data from database."""

def check_failure_rate() -> MonitorResult
    """Check success/failure rate."""

def check_execution_frequency() -> MonitorResult
    """Check execution frequency."""

def check_data_volume() -> MonitorResult
    """Check data volume anomalies."""

def calculate_health_score() -> HealthScore
    """Calculate overall health score."""
```

### MonitorResult

Data class for check results.

**Attributes**:
- `check_type: CheckType` - Type of check
- `check_name: str` - Human-readable name
- `status: HealthStatus` - Health status
- `score: float` - Numeric score (0-100)
- `alert_level: AlertLevel` - Alert severity
- `message: str` - Description message
- `details: Dict[str, Any]` - Additional data
- `timestamp: datetime` - When check was performed

### HealthScore

Data class for overall health assessment.

**Attributes**:
- `process_name: str` - Process group name
- `overall_score: float` - Overall score (0-100)
- `overall_status: HealthStatus` - Overall status
- `component_scores: Dict[str, float]` - Individual scores
- `checks: List[MonitorResult]` - All check results
- `timestamp: datetime` - When calculated
- `trend: Optional[str]` - Score trend
- `alerts: List[str]` - Active alerts

### OutputGenerator

Generates output files.

**Methods**:

```python
def generate_aggregate_xml(health_scores: List[HealthScore]) -> Path
    """Generate aggregate XML for Power BI."""

def generate_detailed_xml(health_scores: List[HealthScore]) -> Path
    """Generate detailed XML with all checks."""

def generate_json(health_scores: List[HealthScore]) -> Path
    """Generate JSON output."""

def generate_all_outputs(health_scores: List[HealthScore]) -> Dict[str, str]
    """Generate all output formats."""
```

### MonitorService

Main service coordinator.

**Methods**:

```python
def start()
    """Start the monitoring service (runs until stopped)."""

def get_status() -> Dict[str, Any]
    """Get current service status."""
```

---

## Appendix

### Example Power BI Report

A sample Power BI report file (`ETL_Monitor.pbix`) can be created with these components:

**Pages**:
1. **Overview Dashboard**: High-level health summary
2. **Process Details**: Drill-down by process group
3. **Alerts**: Active and historical alerts
4. **Trends**: Historical score trends
5. **Component Analysis**: Breakdown by component

**Filters**:
- Date range selector
- Process group selector
- Status filter (EXCELLENT, GOOD, FAIR, POOR, CRITICAL)

### Glossary

- **Check**: Individual monitoring test (e.g., failure rate check)
- **Component**: Category of checks (e.g., success_rate, frequency)
- **Health Score**: Numeric assessment (0-100) of process health
- **Monitor**: Class that performs checks for a process type
- **Process Group**: Collection of related processes (e.g., Tick Files)
- **Threshold**: Configurable limit for triggering alerts
- **Weight**: Relative importance of a component in overall score

### Changelog

**Version 1.0.0** (2025)
- Initial release
- Support for Tick File and MQ Summary processes
- XML/JSON output generation
- Configurable thresholds
- Health scoring system
- Power BI integration

---

## Support

For questions, issues, or contributions:
- Review this documentation
- Check logs in `logs/` directory
- Review configuration in `monitor_config.yaml`
- Consult `PROCESS_LOG_ANALYSIS_SUMMARY.md` for data insights

---

**Framework Version**: 1.0.0
**Last Updated**: 2025
**Author**: ETL Monitoring Framework
