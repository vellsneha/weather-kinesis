"""
Kinesis Weather Data Consumer
Reads weather records from Kinesis stream and stores them in DynamoDB tables
"""

import json
import boto3
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def convert_floats_to_decimal(obj):
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility
    
    DynamoDB doesn't support Python float type, requires Decimal instead
    
    Args:
        obj: Object to convert (dict, list, or primitive)
    
    Returns:
        Object with all floats converted to Decimal
    """
    if isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))  # Convert float to Decimal via string to preserve precision
    else:
        return obj

class WeatherDataConsumer:
    """
    Consumer class that reads weather data from Kinesis stream
    and stores it in DynamoDB tables
    """
    
    def __init__(self, kinesis_stream_name: str, aws_region: str = 'us-east-1'):
        """
        Initialize the consumer with Kinesis stream and DynamoDB connections
        
        Args:
            kinesis_stream_name: Name of the Kinesis stream to read from
            aws_region: AWS region where resources are located
        """
        self.kinesis_stream_name = kinesis_stream_name
        self.aws_region = aws_region
        
        # Initialize AWS clients
        self.kinesis_client = boto3.client('kinesis', region_name=aws_region)
        self.dynamodb = boto3.resource('dynamodb', region_name=aws_region)
        
        # Get references to DynamoDB tables
        self.precipitation_table = self.dynamodb.Table('Precipitation')
        self.temperature_table = self.dynamodb.Table('Temperature')
        
        # Track processing statistics
        self.stats = {
            'records_processed': 0,
            'precipitation_records': 0,
            'temperature_records': 0,
            'errors': 0
        }
    
    def get_shard_iterator(self, shard_id: str) -> Optional[str]:
        """
        Get an iterator for reading from a specific Kinesis shard
        
        Args:
            shard_id: The shard identifier
            
        Returns:
            Shard iterator string or None if error
        """
        try:
            # TRIM_HORIZON means start reading from the oldest available record
            response = self.kinesis_client.get_shard_iterator(
                StreamName=self.kinesis_stream_name,
                ShardId=shard_id,
                ShardIteratorType='TRIM_HORIZON'
            )
            return response['ShardIterator']
        except Exception as e:
            logger.error(f"Error getting shard iterator for {shard_id}: {e}")
            return None
    
    def get_all_shards(self) -> List[str]:
        """
        Get all shard IDs for the Kinesis stream
        
        Returns:
            List of shard IDs
        """
        try:
            response = self.kinesis_client.describe_stream(
                StreamName=self.kinesis_stream_name
            )
            
            # Extract shard IDs from the stream description
            shards = response['StreamDescription']['Shards']
            shard_ids = [shard['ShardId'] for shard in shards]
            
            logger.info(f"Found {len(shard_ids)} shards in stream")
            return shard_ids
            
        except Exception as e:
            logger.error(f"Error describing stream: {e}")
            return []
    
    def process_weather_record(self, record: Dict) -> None:
        """
        Process a single weather record and store it in appropriate DynamoDB tables
        
        A record may contain precipitation/snow data, temperature data, or both.
        We split this into two separate database items.
        
        Args:
            record: Weather record dictionary from Kinesis
        """
        try:
            # Extract common fields
            station_id = record.get('station_id')
            station_name = record.get('station_name')
            timestamp = record.get('timestamp', record.get('date'))
            
            # Validate required fields
            if not station_id or not timestamp:
                logger.warning(f"Skipping record with missing station_id or timestamp: {record}")
                return
            
            # Process precipitation/snow data if present
            has_precipitation = 'precipitation_mm' in record or 'snowfall_mm' in record
            
            if has_precipitation:
                self.store_precipitation_record(
                    station_id=station_id,
                    station_name=station_name,
                    timestamp=timestamp,
                    precipitation_mm=record.get('precipitation_mm'),
                    snowfall_mm=record.get('snowfall_mm')
                )
                self.stats['precipitation_records'] += 1
            
            # Process temperature data if present
            has_temperature = any(key in record for key in ['temp_max_c', 'temp_min_c', 'temp_obs_c'])
            
            if has_temperature:
                self.store_temperature_record(
                    station_id=station_id,
                    station_name=station_name,
                    timestamp=timestamp,
                    temp_max_c=record.get('temp_max_c'),
                    temp_min_c=record.get('temp_min_c'),
                    temp_obs_c=record.get('temp_obs_c')
                )
                self.stats['temperature_records'] += 1
            
            self.stats['records_processed'] += 1
            
        except Exception as e:
            logger.error(f"Error processing record: {e}")
            logger.error(f"Problematic record: {record}")
            self.stats['errors'] += 1

    def store_precipitation_record(self, station_id: str, station_name: str, 
                               timestamp: str, precipitation_mm: Optional[float],
                               snowfall_mm: Optional[float]) -> None:
        """
        Store precipitation and snowfall data in DynamoDB Precipitation table
        
        Table schema:
        - Partition Key: station_id (allows querying by location)
        - Sort Key: timestamp (allows sorting by time for a given station)
        
        Args:
            station_id: Weather station identifier
            station_name: Human-readable station name
            timestamp: ISO format timestamp of observation
            precipitation_mm: Precipitation amount in millimeters
            snowfall_mm: Snowfall amount in millimeters
        """
        try:
            # Build the item to store
            item = {
                'station_id': station_id,
                'timestamp': timestamp,
                'station_name': station_name
            }
            
            # Only include precipitation if it has a value
            # Convert to Decimal for DynamoDB compatibility
            if precipitation_mm is not None:
                item['precipitation_mm'] = Decimal(str(precipitation_mm))
            
            # Only include snowfall if it has a value
            # Convert to Decimal for DynamoDB compatibility
            if snowfall_mm is not None:
                item['snowfall_mm'] = Decimal(str(snowfall_mm))
            
            # Store in DynamoDB
            self.precipitation_table.put_item(Item=item)

            logger.debug(f"Stored precipitation record for station {station_id} at {timestamp}")
            
        except Exception as e:
            logger.error(f"Error storing precipitation record: {e}")
            raise

    def store_temperature_record(self, station_id: str, station_name: str,
                            timestamp: str, temp_max_c: Optional[float],
                            temp_min_c: Optional[float], temp_obs_c: Optional[float]) -> None:
        """
        Store temperature data in DynamoDB Temperature table
        
        Table schema:
        - Partition Key: station_id (allows querying by location)
        - Sort Key: timestamp (allows sorting by time for a given station)
        
        Args:
            station_id: Weather station identifier
            station_name: Human-readable station name
            timestamp: ISO format timestamp of observation
            temp_max_c: Maximum temperature in Celsius
            temp_min_c: Minimum temperature in Celsius
            temp_obs_c: Observed temperature in Celsius
        """
        try:
            # Build the item to store
            item = {
                'station_id': station_id,
                'timestamp': timestamp,
                'station_name': station_name
            }
            
            # Only include temperature values that are present
            # Convert to Decimal for DynamoDB compatibility
            if temp_max_c is not None:
                item['temp_max_c'] = Decimal(str(temp_max_c))
            
            if temp_min_c is not None:
                item['temp_min_c'] = Decimal(str(temp_min_c))
            
            if temp_obs_c is not None:
                item['temp_obs_c'] = Decimal(str(temp_obs_c))
            
            # Store in DynamoDB
            self.temperature_table.put_item(Item=item)

            logger.debug(f"Stored temperature record for station {station_id} at {timestamp}")
            
        except Exception as e:
            logger.error(f"Error storing temperature record: {e}")
            raise

    def process_kinesis_records(self, kinesis_records: List[Dict]) -> None:
        """
        Process a batch of records retrieved from Kinesis
        
        Args:
            kinesis_records: List of Kinesis record objects
        """
        for kinesis_record in kinesis_records:
            try:
                # Extract and decode the data from the Kinesis record
                data = kinesis_record['Data']
                
                # Decode from bytes to string, then parse JSON
                weather_record = json.loads(data.decode('utf-8'))
                
                # Process the weather record
                self.process_weather_record(weather_record)
                
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from Kinesis record: {e}")
                self.stats['errors'] += 1
            except Exception as e:
                logger.error(f"Error processing Kinesis record: {e}")
                self.stats['errors'] += 1
    
    def run(self, duration_seconds: Optional[int] = None, max_records: Optional[int] = None):
        """
        Main execution method - continuously reads from Kinesis and processes records
        
        Args:
            duration_seconds: How long to run (None = run indefinitely)
            max_records: Maximum number of records to process (None = no limit)
        """
        logger.info(f"Starting consumer for stream: {self.kinesis_stream_name}")
        
        # Get all shards in the stream
        shard_ids = self.get_all_shards()
        
        if not shard_ids:
            logger.error("No shards found. Exiting.")
            return
        
        # Get shard iterators for all shards
        shard_iterators = {}
        for shard_id in shard_ids:
            iterator = self.get_shard_iterator(shard_id)
            if iterator:
                shard_iterators[shard_id] = iterator
        
        start_time = time.time()
        
        # Main processing loop
        while True:
            # Check if we should stop based on duration
            if duration_seconds and (time.time() - start_time) > duration_seconds:
                logger.info(f"Reached duration limit of {duration_seconds} seconds")
                break
            
            # Check if we should stop based on record count
            if max_records and self.stats['records_processed'] >= max_records:
                logger.info(f"Reached maximum record limit of {max_records}")
                break
            
            # Process records from each shard
            for shard_id, shard_iterator in list(shard_iterators.items()):
                try:
                    # Get records from this shard
                    # Limit: maximum number of records to retrieve in one call
                    response = self.kinesis_client.get_records(
                        ShardIterator=shard_iterator,
                        Limit=100  # Process up to 100 records at a time
                    )
                    
                    records = response['Records']
                    
                    # Process the records if any were returned
                    if records:
                        logger.info(f"Retrieved {len(records)} records from shard {shard_id}")
                        self.process_kinesis_records(records)
                    
                    # Update the shard iterator for the next call
                    next_iterator = response.get('NextShardIterator')
                    
                    if next_iterator:
                        shard_iterators[shard_id] = next_iterator
                    else:
                        # Shard is closed, remove it from our tracking
                        logger.info(f"Shard {shard_id} is closed")
                        del shard_iterators[shard_id]
                    
                    # MillisBehindLatest indicates how far behind we are
                    millis_behind = response.get('MillisBehindLatest', 0)
                    if millis_behind > 60000:  # More than 1 minute behind
                        logger.warning(f"Consumer is {millis_behind/1000:.1f} seconds behind")
                    
                except Exception as e:
                    logger.error(f"Error reading from shard {shard_id}: {e}")
            
            # If no shards left, exit
            if not shard_iterators:
                logger.info("All shards have been processed")
                break
            
            # Brief pause to avoid hammering the API
            # Adjust this based on your throughput needs
            time.sleep(1)
            
            # Log progress periodically
            if self.stats['records_processed'] % 100 == 0 and self.stats['records_processed'] > 0:
                self.print_stats()
        
        # Print final statistics
        self.print_stats()
        logger.info("Consumer shutdown complete")
    
    def print_stats(self):
        """
        Print processing statistics
        """
        logger.info("=" * 50)
        logger.info("Processing Statistics:")
        logger.info(f"  Total records processed: {self.stats['records_processed']}")
        logger.info(f"  Precipitation records: {self.stats['precipitation_records']}")
        logger.info(f"  Temperature records: {self.stats['temperature_records']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info("=" * 50)


def main():
    """
    Main entry point for the consumer script
    """
    # Configuration - REPLACE WITH YOUR VALUES
    KINESIS_STREAM_NAME = "weather-data-stream"
    AWS_REGION = "us-east-1"  # Change to your AWS region
    
    # Initialize the consumer
    consumer = WeatherDataConsumer(
        kinesis_stream_name=KINESIS_STREAM_NAME,
        aws_region=AWS_REGION
    )
    
    # Run the consumer
    # duration_seconds=None means run indefinitely
    # max_records=None means process all available records
    consumer.run(duration_seconds=3600, max_records=None)  # Run for 1 hour


if __name__ == "__main__":
    main()