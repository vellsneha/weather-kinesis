# AWS Kinesis Weather Data Processing Pipeline

A complete data engineering pipeline that collects weather data from NOAA's API, streams it through AWS Kinesis, and stores it in DynamoDB for analysis.

## Project Structure

```
weather-kinesis-pipeline/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── producer.py               # NOAA data producer
├── consumer.py               # Kinesis consumer
├── test_producer.py          # Producer test suite
├── query_dynamodb.py         # Query and verify data
├── monitor_pipeline.py       # Pipeline monitoring
└── setup/
    ├── create_kinesis.sh     # Create Kinesis stream
    └── create_dynamodb.sh    # Create DynamoDB tables
```

## Architecture

```
NOAA API → Producer (EC2) → Kinesis Stream → Consumer (EC2) → DynamoDB
                                                                ├─ Precipitation Table
                                                                └─ Temperature Table
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **NOAA API Token** - Get from https://www.ncdc.noaa.gov/cdo-web/token
3. **Python 3.7+**
4. **AWS CLI configured** with credentials

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create AWS Resources

**Create Kinesis Stream:**
```bash
aws kinesis create-stream \
    --stream-name weather-data-stream \
    --shard-count 1
```

**Create DynamoDB Tables:**
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
    --billing-mode PAY_PER_REQUEST

# Temperature table
aws dynamodb create-table \
    --table-name Temperature \
    --attribute-definitions \
        AttributeName=station_id,AttributeType=S \
        AttributeName=timestamp,AttributeType=S \
    --key-schema \
        AttributeName=station_id,KeyType=HASH \
        AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST
```

### 3. Configure Credentials

**Option A: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

**Option B: AWS CLI Configuration**
```bash
aws configure
```

### 4. Update Configuration

Edit `producer.py` and `consumer.py` to set:
- `NOAA_TOKEN`: Your NOAA API token
- `AWS_REGION`: Your AWS region
- `KINESIS_STREAM_NAME`: Your stream name

## Running the Pipeline

### Step 1: Test the Producer

```bash
python test_producer.py
```

This will verify:
- API connectivity
- Kinesis connection
- Data retrieval

### Step 2: Run the Producer

```bash
python producer.py
```

This will:
- Fetch all Maryland weather stations
- Retrieve weather data for October 2021
- Stream records to Kinesis

**Expected output:**
```
2024-01-15 10:00:00 - INFO - Starting weather data collection from 2021-10-01 to 2021-10-31
2024-01-15 10:00:01 - INFO - Fetching Maryland weather stations...
2024-01-15 10:00:05 - INFO - Total stations found: 245
2024-01-15 10:00:10 - INFO - Processing station 1/245: GHCND:USC00186350
...
```

### Step 3: Run the Consumer

In a separate terminal:

```bash
python consumer.py
```

This will:
- Read records from Kinesis
- Process weather data
- Store in DynamoDB tables

**Expected output:**
```
2024-01-15 10:05:00 - INFO - Starting consumer for stream: weather-data-stream
2024-01-15 10:05:01 - INFO - Found 1 shards in stream
2024-01-15 10:05:05 - INFO - Retrieved 100 records from shard shardId-000000000000
...
```

### Step 4: Verify Data

```bash
python query_dynamodb.py
```

This will show:
- Table statistics
- Sample records
- Available stations

### Step 5: Monitor Pipeline

```bash
python monitor_pipeline.py
```

This displays:
- Stream status
- Metrics (records processed, throughput)
- Consumer lag
- Table statistics

## Data Schema

### Precipitation Table

| Field | Type | Description |
|-------|------|-------------|
| station_id (PK) | String | Weather station identifier |
| timestamp (SK) | String | ISO 8601 timestamp |
| station_name | String | Human-readable station name |
| precipitation_mm | Number | Precipitation in millimeters |
| snowfall_mm | Number | Snowfall in millimeters |

### Temperature Table

| Field | Type | Description |
|-------|------|-------------|
| station_id (PK) | String | Weather station identifier |
| timestamp (SK) | String | ISO 8601 timestamp |
| station_name | String | Human-readable station name |
| temp_max_c | Number | Maximum temperature (Celsius) |
| temp_min_c | Number | Minimum temperature (Celsius) |
| temp_obs_c | Number | Observed temperature (Celsius) |

## Querying Data

### Query by Station

```python
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('Temperature')

response = table.query(
    KeyConditionExpression=Key('station_id').eq('GHCND:USC00186350')
)

for item in response['Items']:
    print(f"{item['timestamp']}: {item.get('temp_max_c')}°C")
```

### Query by Date Range

```python
from boto3.dynamodb.conditions import Key

response = table.query(
    KeyConditionExpression=
        Key('station_id').eq('GHCND:USC00186350') &
        Key('timestamp').between('2021-10-01', '2021-10-15')
)
```

## Troubleshooting

### Producer Issues

**Problem:** API rate limit errors
- **Solution:** NOAA allows 5 requests/second. The code includes delays, but you may need to increase them.

**Problem:** No data for certain stations
- **Solution:** Not all stations have data for October 2021. This is expected.

**Problem:** Authentication errors
- **Solution:** Verify your NOAA API token is correct and active.

### Consumer Issues

**Problem:** Consumer falling behind
- **Solution:** Increase shard count or optimize processing logic.

**Problem:** DynamoDB throttling
- **Solution:** Use PAY_PER_REQUEST billing mode or increase provisioned capacity.

### AWS Issues

**Problem:** Access denied errors
- **Solution:** Ensure IAM role/user has necessary permissions:
  - `kinesis:PutRecord`
  - `kinesis:GetRecords`
  - `dynamodb:PutItem`

## Performance Optimization

### For Large-Scale Processing

1. **Increase Kinesis Shards:**
   ```bash
   aws kinesis update-shard-count \
       --stream-name weather-data-stream \
       --target-shard-count 4 \
       --scaling-type UNIFORM_SCALING
   ```

2. **Batch Processing:**
   - Use `put_records` instead of `put_record`
   - Process multiple records in parallel

3. **DynamoDB Optimization:**
   - Use batch write operations
   - Enable DynamoDB Streams for downstream processing

## Cost Estimation

For this project (October 2021 data):
- **Kinesis:** ~$0.01-0.10 (depends on data volume)
- **DynamoDB:** ~$0.25-1.00 (on-demand pricing)
- **EC2:** Free tier eligible or ~$0.01/hour
- **Total:** Less than $2 for one-time run

## Cleanup

To avoid ongoing charges:

```bash
# Delete Kinesis stream
aws kinesis delete-stream --stream-name weather-data-stream

# Delete DynamoDB tables
aws dynamodb delete-table --table-name Precipitation
aws dynamodb delete-table --table-name Temperature
```

## Additional Resources

- [AWS Kinesis Documentation](https://docs.aws.amazon.com/kinesis/)
- [NOAA API Documentation](https://www.ncdc.noaa.gov/cdo-web/webservices/v2)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)

## License

This project is for educational purposes.

## Author

Created as part of AWS data engineering coursework.