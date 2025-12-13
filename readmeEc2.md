# EC2 Deployment Guide for Weather Data Pipeline

This guide documents the steps to deploy the Weather Data Pipeline (Producer, Consumer, and Dashboard) on an AWS EC2 instance.

## Prerequisites

1.  **AWS Account**: Active AWS account with permissions to create EC2 instances, Kinesis Streams, and DynamoDB tables.
2.  **EC2 Instance**:
    *   OS: Amazon Linux 2023 (or similar).
    *   Type: `t2.micro` or larger.
    *   Security Group: Allow Inbound TCP on port **22** (SSH) and **5000** (Web Dashboard).
    *   IAM Role: Attached role with permissions for `kinesis:*`, `dynamodb:*`, and `cloudwatch:*`.
3.  **Local Environment**:
    *   Terminal with `ssh` and `scp` installed.
    *   The SSH private key (`weather-kinesis.pem`) for your EC2 instance.

## Deployment Steps

### 1. Prepare Local Files
Ensure you have the following files ready in your project directory:
*   `producer.py`
*   `consumer.py`
*   `monitor_pipeline.py`
*   `dashboard.py`
*   `deploy_pipeline.sh`

### 2. Transfer Files to EC2
Use `scp` to upload the code to your EC2 instance. Replace `98.84.170.156` with your instance's Public IP.

```bash
# Set key permissions if not already set
chmod 400 weather-kinesis.pem

# Create directory on server (optional, or let scp create it if recursive)
ssh -i weather-kinesis.pem ec2-user@98.84.170.156 "mkdir -p ~/weatherkinesis"

# Copy files
scp -i weather-kinesis.pem producer.py ec2-user@98.84.170.156:~/weatherkinesis/
scp -i weather-kinesis.pem consumer.py ec2-user@98.84.170.156:~/weatherkinesis/
scp -i weather-kinesis.pem monitor_pipeline.py ec2-user@98.84.170.156:~/weatherkinesis/
scp -i weather-kinesis.pem dashboard.py ec2-user@98.84.170.156:~/weatherkinesis/
scp -i weather-kinesis.pem deploy_pipeline.sh ec2-user@98.84.170.156:~/weatherkinesis/
```

### 3. Connect to EC2
SSH into the instance:
```bash
ssh -i weather-kinesis.pem ec2-user@98.84.170.156
```

### 4. Run Deployment Script
Once inside the EC2 instance, navigate to the folder and run the automated deployment script.

```bash
cd weatherkinesis

# Make the script executable
chmod +x deploy_pipeline.sh

# Run the deployment
./deploy_pipeline.sh
```

**What the script does:**
1.  Installs system dependencies (`python3`, `git`).
2.  Installs Python libraries (`boto3`, `requests`, `flask`).
3.  Checks/Creates AWS Resources:
    *   Kinesis Stream: `weather-data-stream`
    *   DynamoDB Tables: `Precipitation`, `Temperature`
4.  Starts background processes:
    *   Consumer
    *   Producer
    *   Web Dashboard

### 5. Verify Deployment
The script will output the PIDs of the running processes and the dashboard URL.

**Access Dashboard:**
Open your browser and visit: `http://98.84.170.156:5000`

**Check Logs:**
You can follow the logs in real-time to see data flowing:
```bash
# Monitor Producer (Data Ingestion)
tail -f producer.log

# Monitor Consumer (Data Processing)
tail -f consumer.log
```

## Maintenance

### Stopping the Pipeline
To stop all running processes, use the `kill` command with the PIDs provided at the end of the deployment script output, or find them manually:

```bash
# Find PIDs
ps -ef | grep python

# Kill processes (example IDs)
kill 30452 30456 30457
```

### Updates
If you modify code locally, re-upload the specific file using `scp` and restart the specific python process on the server.
