"""
==============================================================================
Output Generator Module
==============================================================================

This module handles generating output files for consumption by Power BI and
other reporting tools.

Supported formats:
- XML (primary format for Power BI)
- JSON (for debugging and alternative consumers)

The output includes:
- Aggregate health scores and status
- Detailed check results
- Historical trends
- Alert summaries

Developer Notes:
- XML schema is designed for easy Power BI import
- Both aggregate and detailed outputs are generated
- Archives are maintained for historical analysis
- Output is transactional (tmp file + rename for atomicity)

Author: ETL Monitoring Framework
Version: 1.0.0
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import shutil

from framework.daily_escalation_generator import DailyEscalationGenerator


class OutputGenerator:
    """
    Generates monitoring output files in various formats.

    This class handles the creation of XML and JSON output files containing
    monitoring results, designed for consumption by Power BI dashboards.

    The output structure supports:
    - Aggregate view (overall health by process group)
    - Detailed view (individual check results)
    - Time-series data (for trending)
    - Alert summaries
    """

    def __init__(self, config: Dict[str, Any], processes_config: Dict[str, Any] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize Output Generator.

        Args:
            config: Output configuration from YAML
            processes_config: Process definitions from YAML (for daily escalation)
            logger: Logger instance (optional)
        """
        self.config = config
        self.processes_config = processes_config or {}
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Extract configuration
        self.xml_path = Path(config.get('xml_path', './output/process_health.xml'))
        self.xml_detailed_path = Path(config.get('xml_detailed_path',
                                                  './output/process_health_detailed.xml'))
        self.json_path = Path(config.get('json_path', './output/process_health.json'))

        self.archive_enabled = config.get('archive_enabled', True)
        self.archive_path = Path(config.get('archive_path', './output/archive/'))
        self.archive_retention_days = config.get('archive_retention_days', 30)

        # Initialize daily escalation generator if enabled
        self.daily_escalation = None
        escalation_config = config.get('daily_escalation', {})
        if escalation_config.get('enabled', False) and self.processes_config:
            try:
                self.daily_escalation = DailyEscalationGenerator(
                    config, self.processes_config, self.logger
                )
                self.logger.info("Daily escalation generator enabled")
            except Exception as e:
                self.logger.error(f"Failed to initialize daily escalation: {e}", exc_info=True)

        # Ensure output directories exist
        self._ensure_directories()

        self.logger.info("Initialized OutputGenerator")

    def _ensure_directories(self):
        """Create output and archive directories if they don't exist."""
        self.xml_path.parent.mkdir(parents=True, exist_ok=True)
        self.xml_detailed_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)

        if self.archive_enabled:
            self.archive_path.mkdir(parents=True, exist_ok=True)

    def generate_all_outputs(self, health_scores: List['HealthScore']) -> Dict[str, str]:
        """
        Generate all output formats.

        Args:
            health_scores: List of HealthScore objects from monitors

        Returns:
            Dictionary mapping format names to file paths
        """
        self.logger.info(f"Generating outputs for {len(health_scores)} process groups")

        output_files = {}

        try:
            # Generate aggregate XML (primary for Power BI)
            xml_file = self.generate_aggregate_xml(health_scores)
            output_files['aggregate_xml'] = str(xml_file)

            # Generate detailed XML
            xml_detailed_file = self.generate_detailed_xml(health_scores)
            output_files['detailed_xml'] = str(xml_detailed_file)

            # Generate JSON (for debugging/alternative use)
            json_file = self.generate_json(health_scores)
            output_files['json'] = str(json_file)

            # Generate daily failure escalation XML (if enabled)
            if self.daily_escalation:
                try:
                    escalation_file = self.daily_escalation.generate_daily_escalation_xml(health_scores)
                    output_files['daily_escalation_xml'] = str(escalation_file)
                    self.logger.info("Daily escalation XML generated successfully")
                except Exception as e:
                    self.logger.error(f"Failed to generate daily escalation XML: {e}", exc_info=True)

            # Archive old outputs
            if self.archive_enabled:
                self._archive_outputs()
                self._cleanup_old_archives()

            self.logger.info(f"Successfully generated {len(output_files)} output files")

        except Exception as e:
            self.logger.error(f"Error generating outputs: {e}", exc_info=True)
            raise

        return output_files

    def generate_aggregate_xml(self, health_scores: List['HealthScore']) -> Path:
        """
        Generate aggregate XML output for Power BI.

        This is the primary output format, containing high-level health metrics
        suitable for executive dashboards.

        Structure:
        <ProcessHealthMonitor>
          <GeneratedAt>timestamp</GeneratedAt>
          <OverallHealth>...</OverallHealth>
          <ProcessGroups>
            <ProcessGroup>...</ProcessGroup>
          </ProcessGroups>
          <Alerts>
            <Alert>...</Alert>
          </Alerts>
        </ProcessHealthMonitor>

        Args:
            health_scores: List of HealthScore objects

        Returns:
            Path to generated XML file
        """
        self.logger.debug("Generating aggregate XML")

        # Create root element
        root = ET.Element('ProcessHealthMonitor')

        # Add metadata
        ET.SubElement(root, 'GeneratedAt').text = datetime.now().isoformat()
        ET.SubElement(root, 'Version').text = '1.0.0'

        # Calculate overall health
        if health_scores:
            overall_score = sum(hs.overall_score for hs in health_scores) / len(health_scores)
            overall_status = self._score_to_status(overall_score)
        else:
            overall_score = 0
            overall_status = 'UNKNOWN'

        overall_health = ET.SubElement(root, 'OverallHealth')
        ET.SubElement(overall_health, 'Score').text = f"{overall_score:.2f}"
        ET.SubElement(overall_health, 'Status').text = overall_status
        ET.SubElement(overall_health, 'ProcessGroupCount').text = str(len(health_scores))

        # Add process groups
        process_groups_elem = ET.SubElement(root, 'ProcessGroups')

        for health_score in health_scores:
            process_group = ET.SubElement(process_groups_elem, 'ProcessGroup')

            # Basic info
            ET.SubElement(process_group, 'Name').text = health_score.process_name
            ET.SubElement(process_group, 'Score').text = f"{health_score.overall_score:.2f}"
            ET.SubElement(process_group, 'Status').text = health_score.overall_status.value
            ET.SubElement(process_group, 'Timestamp').text = health_score.timestamp.isoformat()
            ET.SubElement(process_group, 'Trend').text = health_score.trend or 'STABLE'

            # Component scores
            components = ET.SubElement(process_group, 'Components')
            for component_name, component_score in health_score.component_scores.items():
                component = ET.SubElement(components, 'Component')
                ET.SubElement(component, 'Name').text = component_name
                ET.SubElement(component, 'Score').text = f"{component_score:.2f}"

            # Alert count
            ET.SubElement(process_group, 'AlertCount').text = str(len(health_score.alerts))

            # Check summary (counts by type)
            check_summary = ET.SubElement(process_group, 'CheckSummary')
            check_counts = {}
            for check in health_score.checks:
                status = check.status.value
                check_counts[status] = check_counts.get(status, 0) + 1

            for status, count in check_counts.items():
                ET.SubElement(check_summary, status).text = str(count)

        # Add alerts section
        alerts_elem = ET.SubElement(root, 'Alerts')

        for health_score in health_scores:
            for alert in health_score.alerts:
                alert_elem = ET.SubElement(alerts_elem, 'Alert')
                ET.SubElement(alert_elem, 'ProcessGroup').text = health_score.process_name
                ET.SubElement(alert_elem, 'Message').text = alert
                ET.SubElement(alert_elem, 'Timestamp').text = health_score.timestamp.isoformat()

        # Write to file (atomically via temp file)
        xml_str = self._prettify_xml(root)
        tmp_file = self.xml_path.with_suffix('.tmp')

        with open(tmp_file, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        # Atomic rename
        tmp_file.replace(self.xml_path)

        self.logger.info(f"Generated aggregate XML: {self.xml_path}")
        return self.xml_path

    def generate_detailed_xml(self, health_scores: List['HealthScore']) -> Path:
        """
        Generate detailed XML output with all check results.

        This output includes full details of every check performed, suitable
        for detailed analysis and troubleshooting.

        Args:
            health_scores: List of HealthScore objects

        Returns:
            Path to generated detailed XML file
        """
        self.logger.debug("Generating detailed XML")

        # Create root element
        root = ET.Element('ProcessHealthMonitorDetailed')

        # Add metadata
        ET.SubElement(root, 'GeneratedAt').text = datetime.now().isoformat()
        ET.SubElement(root, 'Version').text = '1.0.0'

        # Add process groups
        process_groups_elem = ET.SubElement(root, 'ProcessGroups')

        for health_score in health_scores:
            process_group = ET.SubElement(process_groups_elem, 'ProcessGroup')

            # Basic info
            ET.SubElement(process_group, 'Name').text = health_score.process_name
            ET.SubElement(process_group, 'Score').text = f"{health_score.overall_score:.2f}"
            ET.SubElement(process_group, 'Status').text = health_score.overall_status.value
            ET.SubElement(process_group, 'Timestamp').text = health_score.timestamp.isoformat()

            # Detailed checks
            checks_elem = ET.SubElement(process_group, 'Checks')

            for check in health_score.checks:
                check_elem = ET.SubElement(checks_elem, 'Check')

                ET.SubElement(check_elem, 'Type').text = check.check_type.value
                ET.SubElement(check_elem, 'Name').text = check.check_name
                ET.SubElement(check_elem, 'Status').text = check.status.value
                ET.SubElement(check_elem, 'Score').text = f"{check.score:.2f}"
                ET.SubElement(check_elem, 'AlertLevel').text = check.alert_level.value
                ET.SubElement(check_elem, 'Message').text = check.message
                ET.SubElement(check_elem, 'Timestamp').text = check.timestamp.isoformat()

                # Add details as sub-elements
                if check.details:
                    details_elem = ET.SubElement(check_elem, 'Details')
                    self._dict_to_xml(check.details, details_elem)

        # Write to file
        xml_str = self._prettify_xml(root)
        tmp_file = self.xml_detailed_path.with_suffix('.tmp')

        with open(tmp_file, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        tmp_file.replace(self.xml_detailed_path)

        self.logger.info(f"Generated detailed XML: {self.xml_detailed_path}")
        return self.xml_detailed_path

    def generate_json(self, health_scores: List['HealthScore']) -> Path:
        """
        Generate JSON output.

        JSON format is provided for debugging and alternative consumption.

        Args:
            health_scores: List of HealthScore objects

        Returns:
            Path to generated JSON file
        """
        self.logger.debug("Generating JSON")

        output_data = {
            'generated_at': datetime.now().isoformat(),
            'version': '1.0.0',
            'overall_health': {
                'score': sum(hs.overall_score for hs in health_scores) / len(health_scores)
                        if health_scores else 0,
                'process_group_count': len(health_scores)
            },
            'process_groups': [hs.to_dict() for hs in health_scores]
        }

        # Write to file
        tmp_file = self.json_path.with_suffix('.tmp')

        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, default=str)

        tmp_file.replace(self.json_path)

        self.logger.info(f"Generated JSON: {self.json_path}")
        return self.json_path

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

    def _dict_to_xml(self, data: Dict[str, Any], parent: ET.Element):
        """
        Convert dictionary to XML elements.

        Args:
            data: Dictionary to convert
            parent: Parent XML element
        """
        for key, value in data.items():
            # Sanitize key for XML
            safe_key = key.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')

            if isinstance(value, dict):
                child = ET.SubElement(parent, safe_key)
                self._dict_to_xml(value, child)
            elif isinstance(value, list):
                for item in value:
                    child = ET.SubElement(parent, safe_key)
                    if isinstance(item, dict):
                        self._dict_to_xml(item, child)
                    else:
                        child.text = str(item)
            else:
                ET.SubElement(parent, safe_key).text = str(value)

    def _score_to_status(self, score: float) -> str:
        """Convert score to status string."""
        if score >= 95:
            return 'EXCELLENT'
        elif score >= 85:
            return 'GOOD'
        elif score >= 70:
            return 'FAIR'
        elif score >= 50:
            return 'POOR'
        else:
            return 'CRITICAL'

    def _archive_outputs(self):
        """Archive current output files."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        files_to_archive = [
            self.xml_path,
            self.xml_detailed_path,
            self.json_path
        ]

        for file_path in files_to_archive:
            if file_path.exists():
                archive_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
                archive_file = self.archive_path / archive_name

                try:
                    shutil.copy2(file_path, archive_file)
                    self.logger.debug(f"Archived {file_path.name} to {archive_file.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to archive {file_path}: {e}")

    def _cleanup_old_archives(self):
        """Remove archive files older than retention period."""
        if not self.archive_path.exists():
            return

        cutoff_time = datetime.now().timestamp() - (self.archive_retention_days * 24 * 3600)

        for archive_file in self.archive_path.glob('*'):
            try:
                if archive_file.stat().st_mtime < cutoff_time:
                    archive_file.unlink()
                    self.logger.debug(f"Deleted old archive: {archive_file.name}")
            except Exception as e:
                self.logger.warning(f"Failed to delete archive {archive_file}: {e}")


class PowerBISchemaHelper:
    """
    Helper class for Power BI integration.

    Provides documentation and helper methods for importing the monitoring
    XML into Power BI.
    """

    @staticmethod
    def get_aggregate_schema() -> Dict[str, Any]:
        """
        Get the schema description for aggregate XML.

        Returns:
            Dictionary describing the XML schema
        """
        return {
            'root': 'ProcessHealthMonitor',
            'tables': {
                'ProcessGroups': {
                    'path': 'ProcessHealthMonitor/ProcessGroups/ProcessGroup',
                    'columns': [
                        'Name',
                        'Score',
                        'Status',
                        'Timestamp',
                        'Trend',
                        'AlertCount'
                    ]
                },
                'Components': {
                    'path': 'ProcessHealthMonitor/ProcessGroups/ProcessGroup/Components/Component',
                    'columns': [
                        'Name',
                        'Score'
                    ]
                },
                'Alerts': {
                    'path': 'ProcessHealthMonitor/Alerts/Alert',
                    'columns': [
                        'ProcessGroup',
                        'Message',
                        'Timestamp'
                    ]
                }
            }
        }

    @staticmethod
    def get_powerbi_import_instructions() -> str:
        """
        Get instructions for importing XML into Power BI.

        Returns:
            Formatted instructions string
        """
        return """
Power BI Import Instructions
============================

1. Open Power BI Desktop

2. Get Data > XML
   - Select: process_health.xml
   - Click: Load

3. Power Query will detect tables:
   - ProcessGroups (main process health data)
   - Components (component scores)
   - Alerts (active alerts)

4. Transform Data (recommended):
   - ProcessGroups table:
     * Change Score type to Decimal Number
     * Change Timestamp type to Date/Time
     * Change AlertCount type to Whole Number

   - Components table:
     * Change Score type to Decimal Number

   - Alerts table:
     * Change Timestamp type to Date/Time

5. Create Relationships:
   - ProcessGroups[Name] to Components[ProcessGroup]
   - ProcessGroups[Name] to Alerts[ProcessGroup]

6. Suggested Visualizations:
   - Gauge: Overall Health Score
   - Table: Process Groups with Status
   - Bar Chart: Component Scores by Process
   - Card: Alert Count
   - Table: Recent Alerts

7. Refresh Data:
   - Set automatic refresh interval (e.g., 5 minutes)
   - The monitoring framework updates XML every 5 minutes
"""
