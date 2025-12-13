"""
Weather Dashboard for Weather Data Pipeline
Run with: python dashboard.py
Visit: http://<EC2_PUBLIC_IP>:5000
"""

from flask import Flask, render_template_string, jsonify, request
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
import json
from threading import Thread
import time

app = Flask(__name__)

# HTML Template (same as yours)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Weather Data Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-box h3 {
            font-size: 2em;
            margin-bottom: 5px;
        }
        .stat-box p {
            opacity: 0.9;
        }
        .search-box {
            margin-bottom: 20px;
        }
        .search-box input, .search-box select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            margin-bottom: 10px;
        }
        .search-box button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
        }
        .search-box button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: bold;
        }
        tr:hover {
            background: #f5f5f5;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #667eea;
            font-size: 1.2em;
        }
        .no-data {
            text-align: center;
            padding: 40px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌤️ Weather Data Dashboard</h1>
        
        <!-- Statistics -->
        <div class="card">
            <h2>Pipeline Statistics</h2>
            <div class="stats" id="stats">
                <div class="stat-box">
                    <h3 id="station-count">-</h3>
                    <p>Weather Stations</p>
                </div>
                <div class="stat-box">
                    <h3 id="precip-count">-</h3>
                    <p>Precipitation Records</p>
                </div>
                <div class="stat-box">
                    <h3 id="temp-count">-</h3>
                    <p>Temperature Records</p>
                </div>
            </div>
        </div>
        
        <!-- Search -->
        <div class="card">
            <h2>Search Data</h2>
            <div class="search-box">
                <select id="station-select">
                    <option value="">Loading stations...</option>
                </select>
                <select id="data-type">
                    <option value="temperature">Temperature</option>
                    <option value="precipitation">Precipitation</option>
                </select>
                <button onclick="searchData()">Search</button>
            </div>
            
            <div id="results">
                <p class="no-data">Select a station and click Search</p>
            </div>
        </div>
    </div>
    
    <script>
        // Load statistics on page load
        async function loadStats() {
            const response = await fetch('/api/stats');
            const stats = await response.json();
            
            document.getElementById('station-count').textContent = stats.stations;
            document.getElementById('precip-count').textContent = stats.precipitation_records;
            document.getElementById('temp-count').textContent = stats.temperature_records;
        }
        
        // Load stations for dropdown
        async function loadStations() {
            const response = await fetch('/api/stations');
            const stations = await response.json();
            
            const select = document.getElementById('station-select');
            select.innerHTML = '<option value="">-- Select a station --</option>';
            
            stations.forEach(station => {
                const option = document.createElement('option');
                option.value = station;
                option.textContent = station;
                select.appendChild(option);
            });
        }
        
        // Search data
        async function searchData() {
            const stationId = document.getElementById('station-select').value;
            const dataType = document.getElementById('data-type').value;
            
            if (!stationId) {
                alert('Please select a station');
                return;
            }
            
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<p class="loading">Loading data...</p>';
            
            const response = await fetch(`/api/data?station=${stationId}&type=${dataType}`);
            const data = await response.json();
            
            if (data.length === 0) {
                resultsDiv.innerHTML = '<p class="no-data">No data found for this station</p>';
                return;
            }
            
            // Build table
            let html = '<table><thead><tr>';
            html += '<th>Date</th><th>Station Name</th>';
            
            if (dataType === 'temperature') {
                html += '<th>Max Temp (°C)</th><th>Min Temp (°C)</th><th>Obs Temp (°C)</th>';
            } else {
                html += '<th>Precipitation (mm)</th><th>Snowfall (mm)</th>';
            }
            
            html += '</tr></thead><tbody>';
            
            data.forEach(record => {
                html += '<tr>';
                html += `<td>${record.timestamp}</td>`;
                html += `<td>${record.station_name}</td>`;
                
                if (dataType === 'temperature') {
                    html += `<td>${record.temp_max_c || '-'}</td>`;
                    html += `<td>${record.temp_min_c || '-'}</td>`;
                    html += `<td>${record.temp_obs_c || '-'}</td>`;
                } else {
                    html += `<td>${record.precipitation_mm || '-'}</td>`;
                    html += `<td>${record.snowfall_mm || '-'}</td>`;
                }
                
                html += '</tr>';
            });
            
            html += '</tbody></table>';
            resultsDiv.innerHTML = html;
        }
        
        // Initialize on page load
        window.onload = () => {
            loadStats();
            loadStations();
        };
    </script>
</body>
</html>
"""

# Helper to convert Decimal to float for JSON
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# Global placeholders for tables
precipitation_table = None
temperature_table = None

def init_aws_resources():
    """Initialize AWS clients in the background"""
    global precipitation_table, temperature_table
    try:
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        precipitation_table = dynamodb.Table('Precipitation')
        temperature_table = dynamodb.Table('Temperature')
        print("✅ AWS resources initialized")
    except Exception as e:
        print(f"[WARN] AWS initialization failed: {e}")

# Start AWS init in background
Thread(target=init_aws_resources, daemon=True).start()

@app.route('/')
def index():
    """Render the dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def get_stats():
    """Get pipeline statistics"""
    if not precipitation_table or not temperature_table:
        return jsonify({
            'stations': 0,
            'precipitation_records': 0,
            'temperature_records': 0
        })

    try:
        # Count precipitation records
        precip_count = precipitation_table.scan(Select='COUNT').get('Count', 0)
        
        # Count temperature records
        temp_count = temperature_table.scan(Select='COUNT').get('Count', 0)
        
        # Get unique stations
        stations = set()
        resp = precipitation_table.scan(ProjectionExpression='station_id')
        for item in resp.get('Items', []):
            stations.add(item['station_id'])
        while 'LastEvaluatedKey' in resp:
            resp = precipitation_table.scan(
                ProjectionExpression='station_id',
                ExclusiveStartKey=resp['LastEvaluatedKey']
            )
            for item in resp.get('Items', []):
                stations.add(item['station_id'])
        
        return jsonify({
            'stations': len(stations),
            'precipitation_records': precip_count,
            'temperature_records': temp_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stations')
def get_stations():
    """Get list of all stations"""
    if not precipitation_table:
        return jsonify([])

    try:
        stations = set()
        resp = precipitation_table.scan(ProjectionExpression='station_id')
        for item in resp.get('Items', []):
            stations.add(item['station_id'])
        while 'LastEvaluatedKey' in resp:
            resp = precipitation_table.scan(
                ProjectionExpression='station_id',
                ExclusiveStartKey=resp['LastEvaluatedKey']
            )
            for item in resp.get('Items', []):
                stations.add(item['station_id'])
        return jsonify(sorted(list(stations)))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data')
def get_data():
    """Get data for a specific station"""
    station_id = request.args.get('station')
    data_type = request.args.get('type', 'temperature')
    
    if not station_id:
        return jsonify({'error': 'Station ID required'}), 400
    
    table = temperature_table if data_type == 'temperature' else precipitation_table
    if not table:
        return jsonify([])

    try:
        response = table.query(
            KeyConditionExpression=Key('station_id').eq(station_id),
            Limit=31
        )
        items = response.get('Items', [])
        return json.dumps(items, cls=DecimalEncoder)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🌤️  Starting Weather Dashboard...")
    print("📊 Visit: http://<PUBLIC_IP>:5000")
    # Bind to all interfaces so it's accessible from EC2 public IP
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
