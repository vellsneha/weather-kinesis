#!/bin/bash

###############################################################################
# Weather Pipeline Deployment Script
# Automates the setup and running of the weather data pipeline on EC2
###############################################################################

set -e  # Exit on any error

echo "=========================================="
echo "Weather Data Pipeline Deployment"
echo "=========================================="
echo ""

# Configuration
NOAA_TOKEN="GxklPnjaSfzQhzeRcERLnZHpvxNKFJmX"  # Replace with your actual token
KINESIS_STREAM="weather-data-stream"
AWS_REGION="us-east-1"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: Check prerequisites
log_info "Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    log_error "Python 3 not found. Installing..."
    sudo yum install python3 -y
fi

if ! command -v pip3 &> /dev/null; then
    log_error "pip3 not found. Installing..."
    sudo yum install python3-pip -y
fi

log_info "✓ Prerequisites OK"

# Step 2: Install Python dependencies
log_info "Installing Python dependencies..."
pip3 install boto3 requests flask --user --quiet
log_info "✓ Dependencies installed"

# Step 3: Verify AWS resources exist
log_info "Verifying AWS resources..."

# Check Kinesis stream
if aws kinesis describe-stream --stream-name $KINESIS_STREAM --region $AWS_REGION &> /dev/null; then
    log_info "✓ Kinesis stream exists"
else
    log_warn "Kinesis stream not found. Creating..."
    aws kinesis create-stream \
        --stream-name $KINESIS_STREAM \
        --shard-count 1 \
        --region $AWS_REGION
    
    log_info "Waiting for stream to become active..."
    aws kinesis wait stream-exists --stream-name $KINESIS_STREAM --region $AWS_REGION
    log_info "✓ Kinesis stream created"
fi

# Check DynamoDB tables
for TABLE in "Precipitation" "Temperature"; do
    if aws dynamodb describe-table --table-name $TABLE --region $AWS_REGION &> /dev/null; then
        log_info "✓ Table $TABLE exists"
    else
        log_warn "Table $TABLE not found. Creating..."
        aws dynamodb create-table \
            --table-name $TABLE \
            --attribute-definitions \
                AttributeName=station_id,AttributeType=S \
                AttributeName=timestamp,AttributeType=S \
            --key-schema \
                AttributeName=station_id,KeyType=HASH \
                AttributeName=timestamp,KeyType=RANGE \
            --billing-mode PAY_PER_REQUEST \
            --region $AWS_REGION
        
        log_info "Waiting for table to become active..."
        aws dynamodb wait table-exists --table-name $TABLE --region $AWS_REGION
        log_info "✓ Table $TABLE created"
    fi
done

# Step 4: Run the pipeline
log_info "Starting pipeline..."

# Start consumer in background
log_info "Starting consumer..."
cd ~/weatherkinesis
python3 consumer.py > consumer.log 2>&1 &
CONSUMER_PID=$!
log_info "✓ Consumer started (PID: $CONSUMER_PID)"

# Wait a moment for consumer to initialize
sleep 5

# Run producer (takes 1-2 hours for full data)
log_info "Starting producer (this will take 1-2 hours)..."
python3 producer.py > producer.log 2>&1 &
PRODUCER_PID=$!
log_info "✓ Producer started (PID: $PRODUCER_PID)"

# Step 5: Start dashboard
log_info "Starting web dashboard..."
python3 dashboard.py > dashboard.log 2>&1 &
DASHBOARD_PID=$!
log_info "✓ Dashboard started (PID: $DASHBOARD_PID)"

# Get EC2 public IP
PUBLIC_IP="98.84.170.156"

# Print status
echo ""
echo "=========================================="
echo "Pipeline Status"
echo "=========================================="
echo "Consumer PID: $CONSUMER_PID"
echo "Producer PID: $PRODUCER_PID"
echo "Dashboard PID: $DASHBOARD_PID"
echo ""
echo "Logs:"
echo "  Consumer: ~/weatherkinesis/consumer.log"
echo "  Producer: ~/weatherkinesis/producer.log"
echo "  Dashboard: ~/weatherkinesis/dashboard.log"
echo ""
echo "Web Dashboard: http://$PUBLIC_IP:5000"
echo ""
echo "To monitor progress:"
echo "  tail -f ~/weatherkinesis/producer.log"
echo "  tail -f ~/weatherkinesis/consumer.log"
echo ""
echo "To stop pipeline:"
echo "  kill $CONSUMER_PID $PRODUCER_PID $DASHBOARD_PID"
echo ""
echo "=========================================="
echo "$PUBLIC_IP"

# Save PIDs for later
echo "$CONSUMER_PID" > ~/weatherkinesis/consumer.pid
echo "$PRODUCER_PID" > ~/weatherkinesis/producer.pid
echo "$DASHBOARD_PID" > ~/weatherkinesis/dashboard.pid

log_info "Deployment complete! Pipeline is now running."
log_info "Visit http://$PUBLIC_IP:5000 to view the dashboard"