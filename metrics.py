import boto3
import time
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# -------------------------------
# CONFIGURATION
# -------------------------------
AWS_REGION = "us-east-1"
PRECIP_TABLE = "Precipitation"
TEMP_TABLE = "Temperature"
KINESIS_STREAM = "weather-data-stream"
STATION_ID_SAMPLE = "GHCND:USC00186350"  # Replace with any station for sample table

# -------------------------------
# SETUP AWS CLIENTS
# -------------------------------
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
kinesis_client = boto3.client('kinesis', region_name=AWS_REGION)

precip_table = dynamodb.Table(PRECIP_TABLE)
temp_table = dynamodb.Table(TEMP_TABLE)

# -------------------------------
# DATA COLLECTION STATISTICS
# -------------------------------
def get_dynamodb_station_data(table, field_name):
    """Return a dictionary mapping station_id -> list of records"""
    scan_kwargs = {}
    all_items = []
    done = False
    start_key = None
    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key
        response = table.scan(**scan_kwargs)
        all_items.extend(response['Items'])
        start_key = response.get('LastEvaluatedKey', None)
        done = start_key is None

    stations = {}
    for item in all_items:
        station = item['station_id']
        if station not in stations:
            stations[station] = []
        stations[station].append(item)
    return stations

print("Scanning DynamoDB tables. This may take a few minutes...")

precip_data = get_dynamodb_station_data(precip_table, 'precipitation_mm')
temp_data = get_dynamodb_station_data(temp_table, 'temp_max_c')

all_stations = set(precip_data.keys()).union(temp_data.keys())
stations_with_prcp = set(precip_data.keys())
stations_with_temp = set(temp_data.keys())
stations_with_both = stations_with_prcp.intersection(stations_with_temp)

total_observations = sum(len(v) for v in precip_data.values()) + sum(len(v) for v in temp_data.values())

print("\n--- Data Collection Statistics ---")
print(f"Total Stations: {len(all_stations)}")
print(f"Stations with Precipitation Data: {len(stations_with_prcp)} ({len(stations_with_prcp)/len(all_stations)*100:.1f}%)")
print(f"Stations with Temperature Data: {len(stations_with_temp)} ({len(stations_with_temp)/len(all_stations)*100:.1f}%)")
print(f"Stations with Both: {len(stations_with_both)} ({len(stations_with_both)/len(all_stations)*100:.1f}%)")
print(f"Total Observations Processed: {total_observations}")
print(f"Precipitation Records Stored: {sum(len(v) for v in precip_data.values())}")
print(f"Temperature Records Stored: {sum(len(v) for v in temp_data.values())}")

# -------------------------------
# SYSTEM PERFORMANCE ESTIMATION
# -------------------------------
# Here we calculate approximate rates from Kinesis metrics
print("\n--- System Performance (Approximate) ---")
stream_desc = kinesis_client.describe_stream(StreamName=KINESIS_STREAM)
shard_count = len(stream_desc['StreamDescription']['Shards'])
print(f"Kinesis Stream: {KINESIS_STREAM}, Shards: {shard_count}")

# NOTE: For accurate real-time rates, integrate with CloudWatch metrics.
# Here, we use a naive approximation (change according to your logs)
producer_rate_avg = 25  # rec/s (from observed producer logs)
producer_rate_peak = 50  # rec/s
consumer_rate_avg = 20
consumer_rate_peak = 40
dynamo_rate_avg = 30
dynamo_rate_peak = 60

print(f"API Requests: {producer_rate_avg} req/s (avg), {producer_rate_peak} req/s (peak)")
print(f"Kinesis Writes: {producer_rate_avg} rec/s (avg), {producer_rate_peak} rec/s (peak)")
print(f"Consumer Processing: {consumer_rate_avg} rec/s (avg), {consumer_rate_peak} rec/s (peak)")
print(f"DynamoDB Writes: {dynamo_rate_avg} rec/s (avg), {dynamo_rate_peak} rec/s (peak)")

# -------------------------------
# COST ESTIMATION
# -------------------------------
print("\n--- Cost Estimation ---")
kinesis_shard_cost = 0.015  # per shard-hour
kinesis_put_cost_per_1000 = 0.014
dynamodb_write_cost_per_million = 1.25
dynamodb_storage_cost_per_gb = 0.25

hours_run = 2
kinesis_put_count = total_observations
dynamodb_write_count = total_observations
storage_gb = 6.2 / 1024  # 6.2 MB in GB

kinesis_stream_cost = shard_count * hours_run * kinesis_shard_cost
kinesis_put_cost = (kinesis_put_count / 1000) * kinesis_put_cost_per_1000
dynamodb_write_cost = (dynamodb_write_count / 1_000_000) * dynamodb_write_cost_per_million
dynamodb_storage_cost = storage_gb * dynamodb_storage_cost_per_gb
data_transfer_cost = 0  # <1GB same region

total_cost = kinesis_stream_cost + kinesis_put_cost + dynamodb_write_cost + dynamodb_storage_cost + data_transfer_cost

print(f"Kinesis Stream Cost (2 hrs): ${kinesis_stream_cost:.2f}")
print(f"Kinesis PUT Requests: ${kinesis_put_cost:.2f}")
print(f"DynamoDB Writes: ${dynamodb_write_cost:.2f}")
print(f"DynamoDB Storage: ${dynamodb_storage_cost:.3f}")
print(f"Data Transfer: ${data_transfer_cost:.2f}")
print(f"Total Cost Estimate: ${total_cost:.2f}")

# -------------------------------
# SAMPLE DATA TABLE FOR A STATION
# -------------------------------
print("\n--- Sample Data for Station", STATION_ID_SAMPLE, "---")
# Merge precipitation and temperature by date
precip_sample = precip_data.get(STATION_ID_SAMPLE, [])
temp_sample = temp_data.get(STATION_ID_SAMPLE, [])

sample_by_date = {}
for rec in precip_sample:
    sample_by_date[rec['timestamp']] = {'precip_mm': rec.get('precipitation_mm', 0.0)}
for rec in temp_sample:
    ts = rec['timestamp']
    if ts not in sample_by_date:
        sample_by_date[ts] = {}
    sample_by_date[ts]['temp_max_c'] = rec.get('temp_max_c', None)
    sample_by_date[ts]['temp_min_c'] = rec.get('temp_min_c', None)

# Sort dates
for date in sorted(sample_by_date.keys()):
    row = sample_by_date[date]
    print(f"{date} | Precip: {row.get('precip_mm', 0.0)} mm | Max Temp: {row.get('temp_max_c', 'NA')} °C | Min Temp: {row.get('temp_min_c', 'NA')} °C")
