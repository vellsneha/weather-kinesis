"""
NOAA Weather Data Producer for AWS Kinesis
This script fetches weather data from NOAA API and streams it to AWS Kinesis
"""

import json
import os
import time
import boto3
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NOAAWeatherProducer:
    """
    Producer class that fetches weather data from NOAA API 
    and sends it to AWS Kinesis stream
    """
    
    def __init__(self, noaa_token: str, kinesis_stream_name: str, aws_region: str = 'us-east-1'):
        """
        Initialize the producer with necessary credentials and configurations
        
        Args:
            noaa_token: NOAA API authentication token
            kinesis_stream_name: Name of the Kinesis stream to send data to
            aws_region: AWS region where Kinesis stream is located
        """
        self.noaa_token = noaa_token
        self.kinesis_stream_name = kinesis_stream_name
        self.base_url = "https://www.ncdc.noaa.gov/cdo-web/api/v2"
        
        # Initialize AWS Kinesis client
        self.kinesis_client = boto3.client('kinesis', region_name=aws_region)
        
        # NOAA API headers with authentication token
        self.headers = {
            'token': self.noaa_token
        }
        
        # Dataset ID for daily weather summaries
        self.dataset_id = "GHCND"
        
        # Data types we want to retrieve
        # PRCP = Precipitation, SNOW = Snowfall
        # TMAX = Maximum temperature, TMIN = Minimum temperature, TOBS = Temperature at observation time
        self.datatypes = ['PRCP', 'SNOW', 'TMAX', 'TMIN', 'TOBS']
        
    def get_maryland_stations(self) -> List[str]:
        """
        Retrieve all weather station IDs in Maryland
        
        Returns:
            List of station IDs
        """
        logger.info("Fetching Maryland weather stations...")
        
        # API endpoint for stations
        url = f"{self.base_url}/stations"
        
        # Query parameters: limit to Maryland (locationid), dataset GHCND, max results per page
        params = {
            'locationid': 'FIPS:24',  # FIPS code for Maryland
            'datasetid': self.dataset_id,
            'limit': 1000  # Maximum allowed per request
        }
        
        all_stations = []
        offset = 1
        
        # NOAA API uses pagination, so we need to loop through all pages
        while True:
            params['offset'] = offset
            
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()  # Raise exception for HTTP errors
                
                data = response.json()
                
                # Extract station IDs from response
                if 'results' in data:
                    stations = [station['id'] for station in data['results']]
                    all_stations.extend(stations)
                    logger.info(f"Retrieved {len(stations)} stations (Total: {len(all_stations)})")
                    
                    # Check if there are more pages
                    if len(stations) < 1000:
                        break
                    offset += 1000
                else:
                    break
                    
                # Respect API rate limits (5 requests per second)
                time.sleep(0.2)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching stations: {e}")
                break
        
        logger.info(f"Total stations found: {len(all_stations)}")
        return all_stations
    
    def get_station_info(self, station_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific station
        
        Args:
            station_id: The station identifier
            
        Returns:
            Dictionary with station details or None if not found
        """
        url = f"{self.base_url}/stations/{station_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not fetch info for station {station_id}: {e}")
            return None
    
    def fetch_weather_data(self, station_id: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Fetch weather data for a specific station and date range
        
        Args:
            station_id: Weather station identifier
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of weather observation dictionaries
        """
        url = f"{self.base_url}/data"
        
        params = {
            'datasetid': self.dataset_id,
            'stationid': station_id,
            'startdate': start_date,
            'enddate': end_date,
            'units': 'metric',  # Use metric units (Celsius, mm)
            'limit': 1000
        }
        
        all_data = []
        offset = 1
        
        # Paginate through all results
        while True:
            params['offset'] = offset
            
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if 'results' in data:
                    all_data.extend(data['results'])
                    
                    # Check if there are more pages
                    if len(data['results']) < 1000:
                        break
                    offset += 1000
                else:
                    break
                
                # Respect API rate limits
                time.sleep(0.2)
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Error fetching data for station {station_id}: {e}")
                break
        
        return all_data
    
    def process_weather_record(self, raw_data: List[Dict], station_id: str, 
                               station_name: str) -> List[Dict]:
        """
        Process raw NOAA data into structured weather records
        Groups data by date and aggregates different measurement types
        
        Args:
            raw_data: List of raw observation dictionaries from NOAA API
            station_id: Station identifier
            station_name: Human-readable station name
            
        Returns:
            List of processed weather record dictionaries
        """
        # Group data by date
        records_by_date = {}
        
        for observation in raw_data:
            datatype = observation.get('datatype')
            date = observation.get('date', '').split('T')[0]  # Extract just the date part
            value = observation.get('value')
            
            # Skip if this isn't a datatype we're interested in
            if datatype not in self.datatypes:
                continue
            
            # Initialize date entry if it doesn't exist
            if date not in records_by_date:
                records_by_date[date] = {
                    'date': date,
                    'station_id': station_id,
                    'station_name': station_name,
                    'timestamp': observation.get('date')
                }
            
            # Add the measurement to the record
            # PRCP = Precipitation in mm
            if datatype == 'PRCP':
                records_by_date[date]['precipitation_mm'] = value
            # SNOW = Snowfall in mm
            elif datatype == 'SNOW':
                records_by_date[date]['snowfall_mm'] = value
            # TMAX = Maximum temperature in Celsius (tenths of degrees)
            elif datatype == 'TMAX':
                records_by_date[date]['temp_max_c'] = value / 10.0
            # TMIN = Minimum temperature in Celsius (tenths of degrees)
            elif datatype == 'TMIN':
                records_by_date[date]['temp_min_c'] = value / 10.0
            # TOBS = Temperature at observation time in Celsius (tenths of degrees)
            elif datatype == 'TOBS':
                records_by_date[date]['temp_obs_c'] = value / 10.0
        
        # Convert dictionary to list
        return list(records_by_date.values())
    
    def send_to_kinesis(self, record: Dict) -> bool:
        """
        Send a weather record to AWS Kinesis stream
        
        Args:
            record: Weather record dictionary to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert record to JSON string
            data = json.dumps(record)
            
            # Use station_id as partition key to ensure records from same station 
            # go to the same shard (helps with ordered processing)
            response = self.kinesis_client.put_record(
                StreamName=self.kinesis_stream_name,
                Data=data,
                PartitionKey=record['station_id']
            )
            
            logger.debug(f"Sent record to Kinesis. Shard: {response['ShardId']}, "
                        f"Sequence: {response['SequenceNumber']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending record to Kinesis: {e}")
            return False
    
    def run(self, start_date: str = "2021-10-01", end_date: str = "2021-10-31"):
        """
        Main execution method - orchestrates the entire data collection process
        
        Args:
            start_date: Start date for weather data (YYYY-MM-DD)
            end_date: End date for weather data (YYYY-MM-DD)
        """
        logger.info(f"Starting weather data collection from {start_date} to {end_date}")
        
        # Step 1: Get all weather stations in Maryland
        stations = self.get_maryland_stations()
        
        if not stations:
            logger.error("No stations found. Exiting.")
            return
        
        total_records = 0
        successful_sends = 0
        
        # Step 2: For each station, fetch and process weather data
        for idx, station_id in enumerate(stations, 1):
            logger.info(f"Processing station {idx}/{len(stations)}: {station_id}")
            
            # Get station details (name, location, etc.)
            station_info = self.get_station_info(station_id)
            station_name = station_info.get('name', 'Unknown') if station_info else 'Unknown'
            
            # Fetch weather data for this station
            raw_data = self.fetch_weather_data(station_id, start_date, end_date)
            
            if not raw_data:
                logger.info(f"No data available for station {station_id}")
                continue
            
            # Process raw data into structured records
            processed_records = self.process_weather_record(raw_data, station_id, station_name)
            
            # Step 3: Send each record to Kinesis
            for record in processed_records:
                total_records += 1
                if self.send_to_kinesis(record):
                    successful_sends += 1
            
            logger.info(f"Sent {len(processed_records)} records from station {station_id}")
            
            # Be respectful of API rate limits
            time.sleep(0.5)
        
        logger.info(f"Data collection complete. Total records: {total_records}, "
                   f"Successfully sent: {successful_sends}")


def main():
    """
    Main entry point for the producer script
    """
    # Configuration
    NOAA_TOKEN = os.getenv("NOAA_TOKEN", "GxklPnjaSfzQhzeRcERLnZHpvxNKFJmX")  # Get from https://www.ncdc.noaa.gov/cdo-web/token
    KINESIS_STREAM_NAME = os.getenv("KINESIS_STREAM_NAME", "weather-data-stream")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    
    # Date range for data collection
    START_DATE = "2021-10-01"
    END_DATE = "2021-10-31"
    
    # Initialize and run the producer
    producer = NOAAWeatherProducer(
        noaa_token=NOAA_TOKEN,
        kinesis_stream_name=KINESIS_STREAM_NAME,
        aws_region=AWS_REGION
    )
    
    producer.run(start_date=START_DATE, end_date=END_DATE)


if __name__ == "__main__":
    main()