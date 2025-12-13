"""
Test script for the NOAA Weather Producer
Tests with a small subset of data before running the full pipeline
"""

import sys
import os
import logging
from producer import NOAAWeatherProducer

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_api_connection(producer):
    """Test basic API connectivity"""
    print("\n=== Testing API Connection ===")
    try:
        stations = producer.get_maryland_stations()
        print(f"✓ Successfully retrieved {len(stations)} stations")
        return True
    except Exception as e:
        print(f"✗ API connection failed: {e}")
        return False

def test_station_info(producer):
    """Test fetching station details"""
    print("\n=== Testing Station Info Retrieval ===")
    try:
        # Test with a known Maryland station
        test_station = "GHCND:USC00186350"  # Example station
        info = producer.get_station_info(test_station)
        if info:
            print(f"✓ Retrieved info for station: {info.get('name', 'Unknown')}")
            return True
        else:
            print("✗ Could not retrieve station info")
            return False
    except Exception as e:
        print(f"✗ Station info test failed: {e}")
        return False

def test_data_fetch(producer):
    """Test fetching weather data"""
    print("\n=== Testing Weather Data Fetch ===")
    try:
        # Test with a single day of data
        test_station = "GHCND:USC00186350"
        data = producer.fetch_weather_data(
            station_id=test_station,
            start_date="2021-10-01",
            end_date="2021-10-01"
        )
        print(f"✓ Retrieved {len(data)} observations")
        if data:
            print(f"  Sample observation: {data[0]}")
        return True
    except Exception as e:
        print(f"✗ Data fetch test failed: {e}")
        return False

def test_kinesis_connection(producer):
    """Test Kinesis connectivity"""
    print("\n=== Testing Kinesis Connection ===")
    try:
        test_record = {
            'station_id': 'TEST',
            'station_name': 'Test Station',
            'date': '2021-10-01',
            'timestamp': '2021-10-01T00:00:00',
            'precipitation_mm': 10.5
        }
        success = producer.send_to_kinesis(test_record)
        if success:
            print("✓ Successfully sent test record to Kinesis")
            return True
        else:
            print("✗ Failed to send test record")
            return False
    except Exception as e:
        print(f"✗ Kinesis connection test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("NOAA Weather Producer Test Suite")
    print("=" * 60)
    
    # Replace with your actual configuration
    NOAA_TOKEN = os.getenv("NOAA_TOKEN", "GxklPnjaSfzQhzeRcERLnZHpvxNKFJmX")
    KINESIS_STREAM_NAME = os.getenv("KINESIS_STREAM_NAME", "weather-data-stream")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    
    
    if not NOAA_TOKEN:
        print("\n✗ ERROR: Please set your NOAA_TOKEN environment variable or update the test script")
        sys.exit(1)
    
    # Initialize producer
    producer = NOAAWeatherProducer(
        noaa_token=NOAA_TOKEN,
        kinesis_stream_name=KINESIS_STREAM_NAME,
        aws_region=AWS_REGION
    )
    
    # Run tests
    tests = [
        ("API Connection", lambda: test_api_connection(producer)),
        ("Station Info", lambda: test_station_info(producer)),
        ("Data Fetch", lambda: test_data_fetch(producer)),
        ("Kinesis Connection", lambda: test_kinesis_connection(producer))
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            results.append((test_name, test_func()))
        except Exception as e:
            print(f"\n✗ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n✓ All tests passed! Ready to run full pipeline.")
    else:
        print("\n✗ Some tests failed. Please fix issues before running full pipeline.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())