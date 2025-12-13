# Troubleshooting Guide

This document details all issues encountered during development and their solutions.

---

## 🐛 Issue 1: DynamoDB Float Type Error

### Problem

**Error Message:**
```
ERROR - Error storing precipitation record: Float types are not supported. Use Decimal types instead.
```

**When it occurred:**
- When consumer tried to write data to DynamoDB
- Happened for both Precipitation and Temperature tables

**Log output:**
```
2025-12-12 02:37:31,208 - ERROR - Error storing precipitation record: Float types are not supported. Use Decimal types instead.
2025-12-12 02:37:31,209 - ERROR - Problematic record: {'station_id': 'TEST', 'station_name': 'Test Station', 'date': '2021-10-01', 'timestamp': '2021-10-01T00:00:00', 'precipitation_mm': 10.5}
```

### Root Cause

**DynamoDB doesn't accept Python `float` type** - it requires `Decimal` type for numbers to maintain precision.

**Why this happens:**
- Python uses binary floating-point (IEEE 754)
- DynamoDB uses decimal arithmetic for exact numeric values
- Automatic conversion not supported by boto3 library

### Solution

Convert all numeric values to `Decimal` before storing in DynamoDB.

**Code Change in `consumer.py`:**

```python
# Import Decimal at the top
from decimal import Decimal

# In store_precipitation_record method
if precipitation_mm is not None:
    item['precipitation_mm'] = Decimal(str(precipitation_mm))  # Convert float to Decimal

if snowfall_mm is not None:
    item['snowfall_mm'] = Decimal(str(snowfall_mm))

# In store_temperature_record method
if temp_max_c is not None:
    item['temp_max_c'] = Decimal(str(temp_max_c))

if temp_min_c is not None:
    item['temp_min_c'] = Decimal(str(temp_min_c))

if temp_obs_c is not None:
    item['temp_obs_c'] = Decimal(str(temp_obs_c))
```

**Why use `str()` in between?**
```python
# Bad - can lose precision:
Decimal(10.5)  # May become 10.500000000001

# Good - preserves exact value:
Decimal(str(10.5))  # Becomes exactly 10.5
```

### Verification

After the fix:
```
2025-12-12 02:45:01,050 - DEBUG - Stored precipitation record for station TEST at 2021-10-01T00:00:00
```

**Lesson Learned:** Always check database type requirements before writing data.

---

## 🐛 Issue 2: NOAA API Token Not Recognized

### Problem

**Error Message:**
```
✗ ERROR: Please set your NOAA_TOKEN environment variable or update the test script
```

**When it occurred:**
- When running `test_producer.py`
- Even after updating the token in the file

### Root Cause

The test script had TWO places checking for the token:
1. Setting the default value: `NOAA_TOKEN = os.getenv("NOAA_TOKEN", "GxklPnjaSfzQhzeRcERLnZHpvxNKFJmX")`
2. Validation check: `if NOAA_TOKEN == "GxklPnjaSfzQhzeRcERLnZHpvxNKFJmX":`

When token was updated in line 1, the check in line 2 still had the old placeholder value.

### Solution

**Option 1:** Remove the validation check entirely
```python
# Delete or comment out these lines:
# if NOAA_TOKEN == "GxklPnjaSfzQhzeRcERLnZHpvxNKFJmX":
#     print("\n✗ ERROR: Please set your NOAA_TOKEN...")
#     sys.exit(1)
```

**Option 2:** Update both places
```python
# Line 1: Set your token
NOAA_TOKEN = os.getenv("NOAA_TOKEN", "your_actual_token_here")

# Line 2: Update the check
if NOAA_TOKEN == "your_actual_token_here":
    print("\n✗ ERROR: Please update token")
    sys.exit(1)
```

**Option 3:** Simplify to direct assignment
```python
# Remove os.getenv, just use direct value
NOAA_TOKEN = "your_actual_token_here"

# Simple check
if not NOAA_TOKEN:
    print("\n✗ ERROR: Please set token")
    sys.exit(1)
```

### Verification

After fix:
```
============================================================
NOAA Weather Producer Test Suite
============================================================

=== Testing API Connection ===
✓ Successfully retrieved 245 stations
```

**Lesson Learned:** When using placeholder values, ensure validation logic matches.

---

## 🐛 Issue 3: AWS CLI Installation Error on macOS

### Problem

**Error Message:**
```
Error: The following formula cannot be installed from bottle and must be
built from source.
  awscli
Install the Command Line Tools:
  xcode-select --install
```

**When it occurred:**
- When trying to install AWS CLI using Homebrew
- On macOS system

### Root Cause

AWS CLI has C/C++ dependencies that need compilation. macOS requires Xcode Command Line Tools for compilation, which weren't installed.

### Solution

**Option 1:** Install Xcode Command Line Tools (then retry Homebrew)
```bash
xcode-select --install
# Wait for installation to complete
brew install awscli
```

**Option 2:** Install via pip instead (faster, easier)
```bash
pip3 install awscli --user
```

**Option 3:** Use manual configuration (skip AWS CLI entirely)
```bash
mkdir -p ~/.aws
nano ~/.aws/credentials  # Add credentials manually
nano ~/.aws/config       # Add region settings
```

### What We Chose

Used **Option 2** (pip install) because:
- ✅ No Xcode needed (saves ~5GB disk space)
- ✅ Installs in seconds
- ✅ Works exactly the same as Homebrew version
- ✅ Easier to update (`pip3 install --upgrade awscli`)

### Verification

```bash
aws --version
# Output: aws-cli/2.15.0 Python/3.11.0 Darwin/23.0.0
```

**Lesson Learned:** pip is often simpler than package managers for Python tools.

---

## 🐛 Issue 4: AWS Credentials Not Found

### Problem

**Error Message:**
```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**When it occurred:**
- When running any script that accesses AWS (producer, consumer, test)
- Before configuring AWS credentials

### Root Cause

Scripts use boto3 which requires AWS credentials to be configured. No credentials were set up initially.

### Solution

**Step 1:** Get AWS credentials from AWS Console
1. Go to IAM → Users → Your User → Security Credentials
2. Create Access Key
3. Save Access Key ID and Secret Access Key

**Step 2:** Configure using AWS CLI
```bash
aws configure
```

Enter:
- AWS Access Key ID: `AKIAIOSFODNN7EXAMPLE`
- AWS Secret Access Key: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`
- Default region: `us-east-1`
- Default output format: `json`

This creates:
- `~/.aws/credentials` - Stores access keys
- `~/.aws/config` - Stores region and preferences

### Verification

```bash
aws sts get-caller-identity
```

Output:
```json
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/yourname"
}
```

**Lesson Learned:** Always verify AWS credentials before running boto3 scripts.

---

## 🐛 Issue 5: Module Not Found Errors

### Problem

**Error Messages:**
```
ModuleNotFoundError: No module named 'boto3'
ModuleNotFoundError: No module named 'requests'
```

**When it occurred:**
- When first trying to run any Python script
- After creating virtual environment

### Root Cause

Required Python packages were not installed.

### Solution

```bash
# Install required packages
pip install boto3 requests

# Or use requirements.txt
pip install -r requirements.txt
```

**requirements.txt content:**
```
boto3==1.34.20
requests==2.31.0
```

### Verification

```python
# Test imports
python3 -c "import boto3; import requests; print('All modules installed')"
```

Output: `All modules installed`

**Lesson Learned:** Always install dependencies before running code.

---

## 🐛 Issue 6: IAM Permission Denied Errors

### Problem

**Error Messages:**
```
botocore.exceptions.ClientError: An error occurred (AccessDeniedException) when calling the DescribeStream operation
```

**When it occurred:**
- When trying to access Kinesis stream
- When trying to write to DynamoDB

### Root Cause

AWS IAM user didn't have necessary permissions for Kinesis and DynamoDB operations.

### Solution

Attach required policies to IAM user:

**Via AWS Console:**
1. Go to IAM → Users → Your User
2. Click "Add permissions"
3. Attach policies:
   - `AmazonKinesisFullAccess`
   - `AmazonDynamoDBFullAccess`
   - `CloudWatchLogsFullAccess`

**Via AWS CLI:**
```bash
aws iam attach-user-policy \
    --user-name YOUR_USERNAME \
    --policy-arn arn:aws:iam::aws:policy/AmazonKinesisFullAccess

aws iam attach-user-policy \
    --user-name YOUR_USERNAME \
    --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
```

### Verification

```bash
# Test Kinesis access
aws kinesis list-streams

# Test DynamoDB access
aws dynamodb list-tables
```

**Lesson Learned:** Check IAM permissions before debugging code issues.

---

## 🐛 Issue 7: NOAA API Rate Limiting

### Problem

**Error Message:**
```
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests
```

**When it occurred:**
- When producer was fetching data too quickly
- During initial testing without delays

### Root Cause

NOAA API has a rate limit of **5 requests per second**. Without delays, the producer exceeded this limit.

### Solution

Add delays between API requests in `producer.py`:

```python
# After each API call
time.sleep(0.2)  # 200ms delay = max 5 requests/second

# In fetch_weather_data method
try:
    response = requests.get(url, headers=self.headers, params=params)
    response.raise_for_status()
    data = response.json()
    
    # Process data...
    
    time.sleep(0.2)  # Respect rate limit
    
except requests.exceptions.RequestException as e:
    logger.warning(f"Error fetching data: {e}")
```

### Verification

Producer runs without 429 errors:
```
2024-01-15 10:00:20 - INFO - Processing station 1/245
2024-01-15 10:00:25 - INFO - Processing station 2/245
# ~5 second intervals between stations
```

**Lesson Learned:** Always check and respect API rate limits.

---

## 🐛 Issue 8: Kinesis Stream Not Found

### Problem

**Error Message:**
```
botocore.exceptions.ClientError: An error occurred (ResourceNotFoundException) when calling the DescribeStream operation: Stream weather-data-stream under account XXXX not found.
```

**When it occurred:**
- When running consumer or producer
- Before creating Kinesis stream

### Root Cause

Kinesis stream wasn't created yet or was created in wrong region.

### Solution

**Create the stream:**
```bash
aws kinesis create-stream \
    --stream-name weather-data-stream \
    --shard-count 1 \
    --region us-east-1
```

**Wait for it to become active:**
```bash
aws kinesis describe-stream \
    --stream-name weather-data-stream \
    --region us-east-1
```

Look for `"StreamStatus": "ACTIVE"`

### Common Variations

**Wrong region:**
- Stream created in `us-east-1` but scripts configured for `us-west-2`
- **Solution:** Ensure consistent region across all configurations

**Wrong stream name:**
- Created `weather-stream` but code looks for `weather-data-stream`
- **Solution:** Use exact same name everywhere

### Verification

```python
python verify_setup.py
```

Output:
```
✅ Stream is ACTIVE
   Shards: 1
   Region: us-east-1
```

**Lesson Learned:** Create all AWS resources before running pipeline.

---

## 🐛 Issue 9: DynamoDB Tables Missing

### Problem

**Error Message:**
```
botocore.exceptions.ClientError: An error occurred (ResourceNotFoundException) when calling the PutItem operation: Requested resource not found
```

**When it occurred:**
- When consumer tried to write data
- Before creating DynamoDB tables

### Root Cause

DynamoDB tables weren't created yet.

### Solution

Create both tables:

```bash
# Precipitation table
aws dynamodb create-table \
    --table-name Precipitation \
    --attribute-definitions \
        AttributeName=station_id,AttributeType=S \
        AttributeName=timestamp,AttributeType=S \
    --key-schema \
        AttributeName=station_id,KeyType=HASH \
        AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Temperature table
aws dynamodb create-table \
    --table-name Temperature \
    --attribute-definitions \
        AttributeName=station_id,AttributeType=S \
        AttributeName=timestamp,AttributeType=S \
    --key-schema \
        AttributeName=station_id,KeyType=HASH \
        AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

**Wait for tables to be ready:**
```bash
aws dynamodb wait table-exists --table-name Precipitation --region us-east-1
aws dynamodb wait table-exists --table-name Temperature --region us-east-1
```

### Verification

```bash
aws dynamodb list-tables --region us-east-1
```

Output:
```json
{
    "TableNames": [
        "Precipitation",
        "Temperature"
    ]
}
```

**Lesson Learned:** Verify all infrastructure exists before starting data pipeline.

---

## 📋 Pre-Flight Checklist

Use this before running the pipeline:

```
□ Python 3.7+ installed
□ boto3 and requests installed
□ AWS credentials configured (~/.aws/credentials exists)
□ IAM permissions attached (Kinesis, DynamoDB, CloudWatch)
□ NOAA API token obtained and added to scripts
□ Kinesis stream created and ACTIVE
□ DynamoDB Precipitation table created and ACTIVE
□ DynamoDB Temperature table created and ACTIVE
□ All resources in same AWS region (us-east-1)
□ verify_setup.py runs successfully
□ test_producer.py runs successfully
```

---

## 🔍 Debugging Tips

### Check AWS Resource Status

```bash
# Kinesis
aws kinesis describe-stream --stream-name weather-data-stream

# DynamoDB
aws dynamodb describe-table --table-name Precipitation
aws dynamodb describe-table --table-name Temperature

# IAM
aws sts get-caller-identity
```

### Check Python Environment

```bash
# Python version
python3 --version

# Installed packages
pip list | grep -E "boto3|requests"

# Test imports
python3 -c "import boto3, requests; print('OK')"
```

### View Logs

```bash
# Producer logs (if running in background)
tail -f producer.log

# Consumer logs
tail -f consumer.log

# Or run with increased verbosity
python consumer.py --log-level DEBUG
```

### Test Components Individually

```bash
# Test NOAA API
curl -H "token: YOUR_TOKEN" \
  "https://www.ncdc.noaa.gov/cdo-web/api/v2/datasets"

# Test Kinesis write
aws kinesis put-record \
  --stream-name weather-data-stream \
  --partition-key test \
  --data '{"test": "data"}'

# Test DynamoDB write
aws dynamodb put-item \
  --table-name Precipitation \
  --item '{"station_id": {"S": "TEST"}, "timestamp": {"S": "2021-10-01"}}'
```

---

## 💡 Lessons Learned Summary

1. **Type Compatibility:** Check database type requirements (float vs Decimal)
2. **Credentials First:** Configure AWS before running any code
3. **Rate Limits:** Always respect API rate limits with delays
4. **Infrastructure First:** Create all AWS resources before running pipeline
5. **Consistent Regions:** Use same AWS region for all resources
6. **Error Handling:** Implement robust try-catch blocks
7. **Validation:** Validate data before storage operations
8. **Logging:** Add detailed logging for debugging
9. **Testing:** Test components individually before integration
10. **Documentation:** Document all issues and solutions for future reference
