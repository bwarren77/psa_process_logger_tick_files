#!/bin/bash
##############################################################################
# ETL Process Health Monitoring Framework - Setup Script
##############################################################################
#
# This script sets up the monitoring framework environment.
#
# Usage:
#   ./setup.sh [options]
#
# Options:
#   --dev       Install development dependencies
#   --oracle    Install Oracle database driver (cx_Oracle)
#   --help      Show this help message
#
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
INSTALL_DEV=false
INSTALL_ORACLE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            INSTALL_DEV=true
            shift
            ;;
        --oracle)
            INSTALL_ORACLE=true
            shift
            ;;
        --help)
            head -n 15 "$0" | tail -n 13
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================================================${NC}"
echo -e "${BLUE}ETL Process Health Monitoring Framework - Setup${NC}"
echo -e "${BLUE}========================================================================${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.8"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo -e "${RED}ERROR: Python 3.8 or higher is required${NC}"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION detected${NC}"
echo ""

# Create virtual environment (optional but recommended)
echo -e "${YELLOW}Creating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi
echo ""

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel
echo ""

# Install core dependencies
echo -e "${YELLOW}Installing core dependencies...${NC}"
pip install -r requirements.txt
echo -e "${GREEN}✓ Core dependencies installed${NC}"
echo ""

# Install Oracle driver if requested
if [ "$INSTALL_ORACLE" = true ]; then
    echo -e "${YELLOW}Installing Oracle database driver (cx_Oracle)...${NC}"
    pip install cx-Oracle>=8.3.0
    echo -e "${GREEN}✓ Oracle driver installed${NC}"
    echo ""
    echo -e "${YELLOW}NOTE: Oracle Instant Client is also required.${NC}"
    echo -e "${YELLOW}Please download and install from:${NC}"
    echo -e "${YELLOW}https://www.oracle.com/database/technologies/instant-client/downloads.html${NC}"
    echo ""
fi

# Install development dependencies if requested
if [ "$INSTALL_DEV" = true ]; then
    echo -e "${YELLOW}Installing development dependencies...${NC}"
    pip install pytest pytest-cov pylint black mypy
    echo -e "${GREEN}✓ Development dependencies installed${NC}"
    echo ""
fi

# Create necessary directories
echo -e "${YELLOW}Creating directory structure...${NC}"
mkdir -p logs
mkdir -p output
mkdir -p output/archive
mkdir -p models
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Set permissions
echo -e "${YELLOW}Setting permissions...${NC}"
chmod +x framework/monitor_service.py
chmod +x setup.sh
echo -e "${GREEN}✓ Permissions set${NC}"
echo ""

# Validate configuration
echo -e "${YELLOW}Validating configuration...${NC}"
if [ -f "monitor_config.yaml" ]; then
    echo -e "${GREEN}✓ Configuration file found${NC}"

    # Test YAML parsing
    python3 -c "import yaml; yaml.safe_load(open('monitor_config.yaml'))" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Configuration file is valid YAML${NC}"
    else
        echo -e "${RED}✗ Configuration file has YAML syntax errors${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Configuration file not found${NC}"
    echo -e "${YELLOW}  Please ensure monitor_config.yaml is present${NC}"
fi
echo ""

# Create sample systemd service file (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "${YELLOW}Creating sample systemd service file...${NC}"

    CURRENT_DIR=$(pwd)
    CURRENT_USER=$(whoami)

    cat > process-monitor.service.sample << EOF
[Unit]
Description=ETL Process Health Monitoring Service
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/framework/monitor_service.py $CURRENT_DIR/monitor_config.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    echo -e "${GREEN}✓ Sample systemd service file created: process-monitor.service.sample${NC}"
    echo ""
    echo -e "${YELLOW}To install as a system service:${NC}"
    echo -e "  1. sudo cp process-monitor.service.sample /etc/systemd/system/process-monitor.service"
    echo -e "  2. sudo systemctl daemon-reload"
    echo -e "  3. sudo systemctl enable process-monitor"
    echo -e "  4. sudo systemctl start process-monitor"
    echo ""
fi

# Print success message
echo -e "${GREEN}========================================================================${NC}"
echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${GREEN}========================================================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Review and customize monitor_config.yaml"
echo -e "  2. Update database connection settings"
echo -e "  3. Adjust thresholds for your environment"
echo -e "  4. Test the service: python framework/monitor_service.py"
echo ""
echo -e "${YELLOW}To run the monitoring service:${NC}"
echo -e "  ${BLUE}source venv/bin/activate${NC}"
echo -e "  ${BLUE}python framework/monitor_service.py${NC}"
echo ""
echo -e "${YELLOW}Output files will be generated in:${NC}"
echo -e "  - ./output/process_health.xml (for Power BI)"
echo -e "  - ./output/process_health_detailed.xml"
echo -e "  - ./output/process_health.json"
echo ""
echo -e "${YELLOW}Logs will be written to:${NC}"
echo -e "  - ./logs/process_monitor.log"
echo -e "  - ./logs/process_monitor_errors.log"
echo ""
