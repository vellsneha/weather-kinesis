"""
NOAA API Explorer - Interactive Tool
This script helps you understand what data the NOAA API returns

Usage:
    python api_explorer.py

You'll need your NOAA API token (get it from https://www.ncdc.noaa.gov/cdo-web/token)
"""

import requests
import json
from datetime import datetime
import sys

class NOAAExplorer:
    """Interactive explorer for NOAA API"""
    
    def __init__(self, token):
        self.token = token
        self.base_url = "https://www.ncdc.noaa.gov/cdo-web/api/v2"
        self.headers = {'token': token}
    
    def make_request(self, endpoint, params=None):
        """
        Make API request and display formatted response
        
        Args:
            endpoint: API endpoint (e.g., '/datasets', '/stations')
            params: Query parameters dictionary
        """
        url = f"{self.base_url}{endpoint}"
        
        print(f"\n{'='*80}")
        print(f"🌐 REQUEST")
        print(f"{'='*80}")
        print(f"URL: {url}")
        print(f"Parameters: {json.dumps(params, indent=2)}")
        print(f"{'='*80}\n")
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            # Show response status
            print(f"📡 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Success!\n")
                return data
            else:
                print(f"❌ Error: {response.text}\n")
                return None
                
        except Exception as e:
            print(f"❌ Exception: {e}\n")
            return None
    
    def pretty_print(self, data, title="RESPONSE DATA"):
        """Pretty print JSON data"""
        print(f"\n{'='*80}")
        print(f"📄 {title}")
        print(f"{'='*80}")
        print(json.dumps(data, indent=2))
        print(f"{'='*80}\n")
    
    def explore_datasets(self):
        """Explore available datasets"""
        print("\n" + "🔍 EXPLORING DATASETS".center(80, "="))
        
        data = self.make_request('/datasets')
        
        if data and 'results' in data:
            print(f"Found {len(data['results'])} datasets\n")
            
            for dataset in data['results']:
                print(f"Dataset ID: {dataset['id']}")
                print(f"  Name: {dataset.get('name', 'N/A')}")
                print(f"  Coverage: {dataset.get('mindate', 'N/A')} to {dataset.get('maxdate', 'N/A')}")
                print()
            
            # Show detail for GHCND
            print("\n📊 Details for GHCND (Daily Summaries) - The one we use:")
            ghcnd = next((d for d in data['results'] if d['id'] == 'GHCND'), None)
            if ghcnd:
                self.pretty_print(ghcnd, "GHCND DATASET DETAILS")
        
        return data
    
    def explore_maryland_stations(self, limit=10):
        """Explore weather stations in Maryland"""
        print("\n" + "🔍 EXPLORING MARYLAND STATIONS".center(80, "="))
        
        params = {
            'locationid': 'FIPS:24',  # FIPS code for Maryland
            'datasetid': 'GHCND',
            'limit': limit
        }
        
        data = self.make_request('/stations', params)
        
        if data and 'results' in data:
            print(f"Showing {len(data['results'])} of many Maryland stations\n")
            
            for idx, station in enumerate(data['results'], 1):
                print(f"\n{idx}. Station ID: {station['id']}")
                print(f"   Name: {station.get('name', 'N/A')}")
                print(f"   Elevation: {station.get('elevation', 'N/A')} meters")
                print(f"   Coordinates: ({station.get('latitude', 'N/A')}, {station.get('longitude', 'N/A')})")
                print(f"   Data Coverage: {station.get('mindate', 'N/A')} to {station.get('maxdate', 'N/A')}")
            
            # Save first station ID for next exploration
            if data['results']:
                self.sample_station = data['results'][0]['id']
                print(f"\n💡 Saved '{self.sample_station}' for detailed exploration")
        
        return data
    
    def explore_station_detail(self, station_id=None):
        """Get detailed information about a specific station"""
        if station_id is None:
            station_id = getattr(self, 'sample_station', None)
        
        if station_id is None:
            print("❌ No station ID available. Run explore_maryland_stations() first.")
            return None
        
        print(f"\n" + f"🔍 EXPLORING STATION: {station_id}".center(80, "="))
        
        data = self.make_request(f'/stations/{station_id}')
        
        if data:
            self.pretty_print(data, f"STATION DETAILS: {station_id}")
        
        return data
    
    def explore_weather_data(self, station_id=None, start_date="2021-10-01", end_date="2021-10-03"):
        """
        Explore actual weather data for a station
        
        Args:
            station_id: Station to query (uses sample if None)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        if station_id is None:
            station_id = getattr(self, 'sample_station', None)
        
        if station_id is None:
            print("❌ No station ID available. Run explore_maryland_stations() first.")
            return None
        
        print(f"\n" + f"🔍 EXPLORING WEATHER DATA".center(80, "="))
        print(f"Station: {station_id}")
        print(f"Date Range: {start_date} to {end_date}\n")
        
        params = {
            'datasetid': 'GHCND',
            'stationid': station_id,
            'startdate': start_date,
            'enddate': end_date,
            'limit': 1000,
            'units': 'metric'
        }
        
        data = self.make_request('/data', params)
        
        if data and 'results' in data:
            print(f"Found {len(data['results'])} observations\n")
            
            # Group by datatype
            by_type = {}
            for obs in data['results']:
                datatype = obs.get('datatype')
                if datatype not in by_type:
                    by_type[datatype] = []
                by_type[datatype].append(obs)
            
            # Show summary
            print("📊 Data Types Found:")
            for datatype, observations in by_type.items():
                print(f"  • {datatype}: {len(observations)} observations")
            
            print("\n" + "="*80)
            print("🌡️  SAMPLE OBSERVATIONS (First 5)")
            print("="*80)
            
            for idx, obs in enumerate(data['results'][:5], 1):
                print(f"\n{idx}. Observation:")
                print(f"   Date: {obs.get('date')}")
                print(f"   Type: {obs.get('datatype')} ({self.get_datatype_description(obs.get('datatype'))})")
                print(f"   Value: {obs.get('value')}")
                print(f"   Attributes: {obs.get('attributes', 'None')}")
            
            # Show detailed breakdown by type
            print("\n" + "="*80)
            print("📈 BREAKDOWN BY DATA TYPE")
            print("="*80)
            
            for datatype, observations in by_type.items():
                print(f"\n{datatype} - {self.get_datatype_description(datatype)}:")
                print(f"  Count: {len(observations)}")
                print(f"  Sample values: {[obs.get('value') for obs in observations[:3]]}")
                
                if datatype in ['TMAX', 'TMIN', 'TOBS']:
                    # Convert temperatures to Celsius
                    print(f"  (Note: Values are in tenths of degrees C)")
                    print(f"  Converted: {[obs.get('value')/10 for obs in observations[:3]]} °C")
            
            # Show one complete observation
            if data['results']:
                print("\n" + "="*80)
                print("🔬 COMPLETE OBSERVATION STRUCTURE (First Record)")
                print("="*80)
                self.pretty_print(data['results'][0], "FULL OBSERVATION OBJECT")
        
        return data
    
    def get_datatype_description(self, datatype):
        """Get human-readable description of data types"""
        descriptions = {
            'PRCP': 'Precipitation (mm)',
            'SNOW': 'Snowfall (mm)',
            'SNWD': 'Snow depth (mm)',
            'TMAX': 'Maximum temperature (tenths of °C)',
            'TMIN': 'Minimum temperature (tenths of °C)',
            'TOBS': 'Temperature at observation time (tenths of °C)',
            'AWND': 'Average wind speed',
            'PRCP': 'Precipitation',
            'TAVG': 'Average temperature',
        }
        return descriptions.get(datatype, 'Unknown')
    
    def explore_datatypes(self):
        """Explore available data types"""
        print("\n" + "🔍 EXPLORING DATA TYPES".center(80, "="))
        
        params = {
            'datasetid': 'GHCND',
            'limit': 100
        }
        
        data = self.make_request('/datatypes', params)
        
        if data and 'results' in data:
            print(f"Found {len(data['results'])} data types\n")
            
            # Show the ones we care about
            important_types = ['PRCP', 'SNOW', 'TMAX', 'TMIN', 'TOBS']
            
            print("📊 Data Types Used in Our Project:\n")
            for dtype in data['results']:
                if dtype['id'] in important_types:
                    print(f"  • {dtype['id']}: {dtype.get('name', 'N/A')}")
                    print(f"    Units: {dtype.get('datacoverage', 'N/A')}")
                    print()
        
        return data
    
    def run_full_exploration(self):
        """Run complete exploration sequence"""
        print("\n" + "🌟 NOAA API FULL EXPLORATION".center(80, "="))
        print("\nThis will walk through all API endpoints to show you the data structure.\n")
        
        input("Press Enter to start...")
        
        # 1. Explore datasets
        print("\n\n" + "STEP 1: DATASETS".center(80, "="))
        self.explore_datasets()
        input("\nPress Enter to continue to stations...")
        
        # 2. Explore stations
        print("\n\n" + "STEP 2: MARYLAND STATIONS".center(80, "="))
        self.explore_maryland_stations(limit=5)
        input("\nPress Enter to continue to station details...")
        
        # 3. Explore specific station
        print("\n\n" + "STEP 3: STATION DETAILS".center(80, "="))
        self.explore_station_detail()
        input("\nPress Enter to continue to weather data...")
        
        # 4. Explore weather data
        print("\n\n" + "STEP 4: WEATHER DATA".center(80, "="))
        self.explore_weather_data()
        input("\nPress Enter to continue to data types...")
        
        # 5. Explore data types
        print("\n\n" + "STEP 5: DATA TYPES".center(80, "="))
        self.explore_datatypes()
        
        print("\n\n" + "✅ EXPLORATION COMPLETE!".center(80, "="))
        print("\nYou now understand:")
        print("  1. What datasets are available (we use GHCND)")
        print("  2. How to find stations in Maryland")
        print("  3. What data each station provides")
        print("  4. The structure of weather observations")
        print("  5. What data types exist and what they mean")
        print("\nYou're ready to build the pipeline! 🚀\n")


def main():
    """Main entry point"""
    print("=" * 80)
    print("NOAA API EXPLORER".center(80))
    print("=" * 80)
    print("\nThis tool helps you understand the NOAA API before building the pipeline.\n")
    
    # Get API token
    token = input("Enter your NOAA API token (or 'demo' for limited access): ").strip()
    
    if not token:
        print("❌ Token is required!")
        sys.exit(1)
    
    # Create explorer
    explorer = NOAAExplorer(token)
    
    # Show menu
    while True:
        print("\n" + "="*80)
        print("MAIN MENU".center(80))
        print("="*80)
        print("\n1. 📚 Explore Datasets")
        print("2. 🏢 Explore Maryland Stations")
        print("3. 🔍 Explore Specific Station Details")
        print("4. 🌡️  Explore Weather Data")
        print("5. 📊 Explore Data Types")
        print("6. 🌟 Run Full Exploration (All Steps)")
        print("7. ❌ Exit")
        
        choice = input("\nSelect option (1-7): ").strip()
        
        if choice == '1':
            explorer.explore_datasets()
        elif choice == '2':
            limit = input("How many stations to show? (default 10): ").strip()
            limit = int(limit) if limit else 10
            explorer.explore_maryland_stations(limit)
        elif choice == '3':
            station_id = input("Enter station ID (or press Enter for sample): ").strip()
            explorer.explore_station_detail(station_id or None)
        elif choice == '4':
            station_id = input("Enter station ID (or press Enter for sample): ").strip()
            start = input("Start date (YYYY-MM-DD, default 2021-10-01): ").strip()
            end = input("End date (YYYY-MM-DD, default 2021-10-03): ").strip()
            explorer.explore_weather_data(
                station_id or None,
                start or "2021-10-01",
                end or "2021-10-03"
            )
        elif choice == '5':
            explorer.explore_datatypes()
        elif choice == '6':
            explorer.run_full_exploration()
        elif choice == '7':
            print("\n👋 Goodbye!\n")
            break
        else:
            print("❌ Invalid option. Please select 1-7.")


if __name__ == "__main__":
    main()