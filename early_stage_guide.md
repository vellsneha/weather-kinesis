# Key Concepts Guide - Weather Data Pipeline

## Understanding the Components

### 1. AWS Kinesis Data Streams

**What is it?**
- Real-time data streaming service
- Think of it as a "highway" for data to flow through
- Can handle massive amounts of data per second

**Key Concepts:**
- **Shards:** Partitions of the stream (like lanes on a highway)
  - Each shard: 1 MB/sec input, 2 MB/sec output
  - More shards = more throughput
  
- **Records:** Individual pieces of data
  - Max size: 1 MB per record
  - Contains: Data blob + Partition key
  
- **Partition Key:** Determines which shard gets the record
  - Same key → Same shard (helps maintain order)
  - We use `station_id` so all data from one station goes together

**Why Kinesis for this project?**
- Decouples producer and consumer (they can run independently)
- Buffers data (consumer can process at its own pace)
- Scales automatically (can handle variable data rates)

### 2. NOAA Weather API

**Data Hierarchy:**
```
Datasets (GHCND = Daily Summaries)
  └── Locations (Maryland = FIPS:24)
       └── Stations (Individual weather stations)
            └── Data Types (PRCP, SNOW, TMAX, etc.)
                 └── Observations (Actual measurements)
```

**Important Data Types:**
- `PRCP`: Precipitation (tenths of mm)
- `SNOW`: Snowfall (mm)
- `TMAX`: Maximum temperature (tenths of °C)
- `TMIN`: Minimum temperature (tenths of °C)
- `TOBS`: Temperature at observation time (tenths of °C)

**API Limitations:**
- Rate limit: 5 requests per second
- Max results per request: 1,000
- Requires pagination for large datasets

### 3. DynamoDB

**Why Two Tables?**
- Different access patterns for precipitation vs temperature
- Optimizes storage and query performance
- Some stations only report one type of data

**Table Design:**
```
Precipitation Table:
├── Partition Key: station_id (groups data by location)
└── Sort Key: timestamp (orders data by time)

Temperature Table:
├── Partition Key: station_id
└── Sort Key: timestamp
```

**Why This Design?**
- **Fast location-based queries:** "Give me all data for station X"
- **Time-sorted results:** Data automatically ordered by timestamp
- **Efficient range queries:** "Data for station X between date Y and Z"

### 4. Data Flow

```
Step 1: Producer starts
  ├── Queries NOAA for Maryland stations
  ├── For each station:
  │   ├── Fetches October 2021 data
  │   ├── Groups by date
  │   ├── Extracts relevant fields
  │   └── Sends to Kinesis
  
Step 2: Kinesis receives and stores
  ├── Assigns to shard based on partition key
  ├── Stores for 24 hours (default retention)
  └── Makes available for consumers

Step 3: Consumer processes
  ├── Reads from Kinesis shard(s)
  ├── For each record:
  │   ├── Checks for precipitation data → Precipitation table
  │   └── Checks for temperature data → Temperature table
  └── Continues reading until caught up
```

## Common Pitfalls and Solutions

### 1. API Rate Limiting
**Problem:** Getting 429 errors from NOAA
**Solution:** 
```python
time.sleep(0.2)  # 200ms between requests = 5/second
```

### 2. Missing Data
**Problem:** Not all stations have all data types
**Solution:**
```python
if 'precipitation_mm' in record:
    # Only store if data exists
    item['precipitation_mm'] = record['precipitation_mm']
```

### 3. Consumer Falling Behind
**Problem:** Records building up in Kinesis
**Solutions:**
- Increase shard count
- Optimize processing logic
- Run multiple consumer instances
- Use batch operations for DynamoDB

### 4. Data Unit Conversions
**Problem:** NOAA returns temperatures in tenths of degrees
**Solution:**
```python
temp_celsius = raw_value / 10.0  # 250 → 25.0°C
```

## Testing Strategy

### 1. Unit Testing
Test individual functions:
```python
def test_process_weather_record():
    raw_data = [
        {'datatype': 'TMAX', 'date': '2021-10-01', 'value': 250}
    ]
    result = producer.process_weather_record(raw_data, 'TEST', 'Test Station')
    assert result[0]['temp_max_c'] == 25.0
```

### 2. Integration Testing
Test component interactions:
- Producer → Kinesis
- Kinesis → Consumer
- Consumer → DynamoDB

### 3. End-to-End Testing
Test complete pipeline:
1. Send test record through producer
2. Verify it appears in Kinesis
3. Confirm consumer processes it
4. Check DynamoDB for result

## Performance Optimization

### Producer Optimizations

**Batch API Requests:**
```python
# Instead of one request per station
# Group stations and request in parallel
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(fetch_data, station) for station in stations]
```

**Batch Kinesis Writes:**
```python
# Instead of put_record (one at a time)
# Use put_records (up to 500 at once)
kinesis.put_records(
    StreamName='weather-data-stream',
    Records=[
        {'Data': json.dumps(record1), 'PartitionKey': 'key1'},
        {'Data': json.dumps(record2), 'PartitionKey': 'key2'},
        # ... up to 500 records
    ]
)
```

### Consumer Optimizations

**Batch DynamoDB Writes:**
```python
# Instead of put_item (one at a time)
# Use batch_write_item (up to 25 at once)
with table.batch_writer() as batch:
    for record in records:
        batch.put_item(Item=record)
```

**Parallel Shard Processing:**
```python
# Process multiple shards simultaneously
from concurrent.futures import ThreadPoolExecutor

def process_shard(shard_id):
    # Process one shard
    pass

with ThreadPoolExecutor(max_workers=num_shards) as executor:
    executor.map(process_shard, shard_ids)
```

## Monitoring Best Practices

### What to Monitor

1. **Producer Health:**
   - API request success rate
   - Records sent to Kinesis
   - Error rate

2. **Kinesis Metrics:**
   - Incoming records/bytes
   - Iterator age (consumer lag)
   - Throttling events

3. **Consumer Health:**
   - Records processed
   - DynamoDB write success rate
   - Processing latency

4. **DynamoDB Metrics:**
   - Item count growth
   - Throttled requests
   - Consumed capacity

### Setting Up Alarms

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# Alarm if consumer falls behind by more than 5 minutes
cloudwatch.put_metric_alarm(
    AlarmName='HighIteratorAge',
    MetricName='GetRecords.IteratorAgeMilliseconds',
    Namespace='AWS/Kinesis',
    Statistic='Maximum',
    Period=300,
    EvaluationPeriods=2,
    Threshold=300000,  # 5 minutes in milliseconds
    ComparisonOperator='GreaterThanThreshold'
)
```

## Cost Optimization

### Kinesis Costs
- **Shard hour:** ~$0.015/hour
- **PUT payload units:** ~$0.014 per 1M units
- **Strategy:** Use minimum shards needed, delete stream when done

### DynamoDB Costs
- **On-demand:** ~$1.25 per million writes
- **Provisioned:** Fixed cost but cheaper for predictable workloads
- **Strategy:** Use on-demand for this project (variable load)

### Data Transfer
- **Within region:** Free
- **Cross-region:** ~$0.02/GB
- **Strategy:** Keep all resources in same region

## Real-World Applications

This architecture is used for:

1. **IoT Data Processing**
   - Sensor data from devices
   - Real-time monitoring and alerts

2. **Log Analytics**
   - Application logs
   - Security event processing

3. **Financial Data**
   - Stock market data feeds
   - Transaction processing

4. **Social Media Analytics**
   - Tweet streams
   - User activity tracking

5. **Gaming**
   - Player activity events
   - Real-time leaderboards

## Next Steps

After completing this project, consider:

1. **Add Data Analytics:**
   - Connect DynamoDB to AWS Athena for SQL queries
   - Create visualizations with QuickSight

2. **Implement Lambda:**
   - Convert consumer to Lambda function
   - Trigger on Kinesis records

3. **Add Data Validation:**
   - Validate data quality
   - Handle outliers and anomalies

4. **Build Dashboard:**
   - Real-time monitoring dashboard
   - Historical data visualization

5. **Implement Data Lake:**
   - Archive to S3 for long-term storage
   - Use AWS Glue for ETL

## Troubleshooting Commands

```bash
# Check if stream exists
aws kinesis describe-stream --stream-name weather-data-stream

# Check if tables exist
aws dynamodb list-tables

# Get item count
aws dynamodb scan --table-name Precipitation --select COUNT

# Check CloudWatch logs
aws logs tail /aws/kinesis/weather-data-stream --follow

# Test IAM permissions
aws sts get-caller-identity

# Monitor real-time
aws kinesis get-records --shard-iterator <iterator>
```

## Additional Resources

- **AWS Documentation:** https://docs.aws.amazon.com/
- **NOAA Data Docs:** https://www1.ncdc.noaa.gov/pub/data/cdo/documentation/
- **Python Boto3 Docs:** https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- **DynamoDB Best Practices:** https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html