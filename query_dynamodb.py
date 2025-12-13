"""
Script to query and verify data stored in DynamoDB tables
"""

import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
import json

class DecimalEncoder(json.JSONEncoder):
    """Helper class to convert Decimal to float for JSON serialization"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def query_precipitation_by_station(table, station_id, limit=10):
    """
    Query precipitation data for a specific station
    
    Args:
        table: DynamoDB table resource
        station_id: Station identifier to query
        limit: Maximum number of records to return
    """
    print(f"\n=== Precipitation Data for Station: {station_id} ===")
    
    try:
        response = table.query(
            KeyConditionExpression=Key('station_id').eq(station_id),
            Limit=limit,
            ScanIndexForward=True  # Sort by timestamp ascending
        )
        
        items = response.get('Items', [])
        print(f"Found {len(items)} records")
        
        for item in items:
            print(f"\nTimestamp: {item.get('timestamp')}")
            print(f"  Station: {item.get('station_name')}")
            if 'precipitation_mm' in item:
                print(f"  Precipitation: {item.get('precipitation_mm')} mm")
            if 'snowfall_mm' in item:
                print(f"  Snowfall: {item.get('snowfall_mm')} mm")
        
        return items
        
    except Exception as e:
        print(f"Error querying precipitation table: {e}")
        return []

def query_temperature_by_station(table, station_id, limit=10):
    """
    Query temperature data for a specific station
    
    Args:
        table: DynamoDB table resource
        station_id: Station identifier to query
        limit: Maximum number of records to return
    """
    print(f"\n=== Temperature Data for Station: {station_id} ===")
    
    try:
        response = table.query(
            KeyConditionExpression=Key('station_id').eq(station_id),
            Limit=limit,
            ScanIndexForward=True  # Sort by timestamp ascending
        )
        
        items = response.get('Items', [])
        print(f"Found {len(items)} records")
        
        for item in items:
            print(f"\nTimestamp: {item.get('timestamp')}")
            print(f"  Station: {item.get('station_name')}")
            if 'temp_max_c' in item:
                print(f"  Max Temperature: {item.get('temp_max_c')}°C")
            if 'temp_min_c' in item:
                print(f"  Min Temperature: {item.get('temp_min_c')}°C")
            if 'temp_obs_c' in item:
                print(f"  Observed Temperature: {item.get('temp_obs_c')}°C")
        
        return items
        
    except Exception as e:
        print(f"Error querying temperature table: {e}")
        return []

def scan_table_sample(table, limit=5):
    """
    Scan table and return a sample of records
    
    Args:
        table: DynamoDB table resource
        limit: Maximum number of records to return
    """
    try:
        response = table.scan(Limit=limit)
        items = response.get('Items', [])
        print(f"Sample of {len(items)} records:")
        for item in items:
            print(json.dumps(item, indent=2, cls=DecimalEncoder))
        return items
    except Exception as e:
        print(f"Error scanning table: {e}")
        return []

def get_table_stats(table):
    """
    Get basic statistics about a DynamoDB table
    
    Args:
        table: DynamoDB table resource
    """
    try:
        # Reload table to get latest metadata
        table.reload()
        
        print(f"\nTable: {table.table_name}")
        print(f"  Item Count: {table.item_count}")
        print(f"  Table Size: {table.table_size_bytes / 1024:.2f} KB")
        print(f"  Table Status: {table.table_status}")
        
    except Exception as e:
        print(f"Error getting table stats: {e}")

def get_all_stations(table):
    """
    Get a list of all unique station IDs in the table
    
    Args:
        table: DynamoDB table resource
    """
    try:
        # Scan table and collect unique station IDs
        stations = set()
        
        response = table.scan(
            ProjectionExpression='station_id'
        )
        
        for item in response.get('Items', []):
            stations.add(item['station_id'])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                ProjectionExpression='station_id',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            for item in response.get('Items', []):
                stations.add(item['station_id'])
        
        return sorted(list(stations))
        
    except Exception as e:
        print(f"Error getting stations: {e}")
        return []

def main():
    """
    Main function to demonstrate querying DynamoDB tables
    """
    # Configuration
    AWS_REGION = "us-east-1"  # Change to your region
    
    # Initialize DynamoDB resource
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    
    # Get table references
    precipitation_table = dynamodb.Table('Precipitation')
    temperature_table = dynamodb.Table('Temperature')
    
    print("=" * 60)
    print("DynamoDB Query Tool")
    print("=" * 60)
    
    # Get table statistics
    print("\n--- Table Statistics ---")
    get_table_stats(precipitation_table)
    get_table_stats(temperature_table)
    
    # Get list of stations
    print("\n--- Available Stations ---")
    print("\nGetting stations from Precipitation table...")
    precip_stations = get_all_stations(precipitation_table)
    print(f"Found {len(precip_stations)} stations with precipitation data")
    
    print("\nGetting stations from Temperature table...")
    temp_stations = get_all_stations(temperature_table)
    print(f"Found {len(temp_stations)} stations with temperature data")
    
    # Show sample of stations
    if precip_stations:
        print(f"\nSample stations: {precip_stations[:5]}")
    
    # Query specific station if available
    if precip_stations:
        print("\n--- Sample Station Data ---")
        sample_station = precip_stations[0]
        
        # Query precipitation data
        query_precipitation_by_station(precipitation_table, sample_station, limit=5)
        
        # Query temperature data if this station has it
        if sample_station in temp_stations:
            query_temperature_by_station(temperature_table, sample_station, limit=5)
    
    # Show sample records
    print("\n--- Sample Records from Precipitation Table ---")
    scan_table_sample(precipitation_table, limit=3)
    
    print("\n--- Sample Records from Temperature Table ---")
    scan_table_sample(temperature_table, limit=3)
    
    print("\n" + "=" * 60)
    print("Query complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()