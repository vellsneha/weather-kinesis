"""
Monitoring script for the weather data pipeline
Checks Kinesis stream metrics and DynamoDB table status
"""

import boto3
from datetime import datetime, timedelta
import time

class PipelineMonitor:
    """
    Monitor class for tracking pipeline health and metrics
    """
    
    def __init__(self, stream_name, aws_region='us-east-1'):
        """
        Initialize monitor with AWS clients
        
        Args:
            stream_name: Kinesis stream name to monitor
            aws_region: AWS region
        """
        self.stream_name = stream_name
        self.kinesis = boto3.client('kinesis', region_name=aws_region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=aws_region)
        self.dynamodb = boto3.client('dynamodb', region_name=aws_region)
    
    def check_kinesis_stream_status(self):
        """
        Check the status of the Kinesis stream
        """
        print("\n=== Kinesis Stream Status ===")
        try:
            response = self.kinesis.describe_stream(StreamName=self.stream_name)
            stream_desc = response['StreamDescription']
            
            print(f"Stream Name: {stream_desc['StreamName']}")
            print(f"Status: {stream_desc['StreamStatus']}")
            print(f"Number of Shards: {len(stream_desc['Shards'])}")
            print(f"Retention Period: {stream_desc['RetentionPeriodHours']} hours")
            
            # Check each shard
            for shard in stream_desc['Shards']:
                print(f"\n  Shard ID: {shard['ShardId']}")
                print(f"    Sequence Range: {shard['SequenceNumberRange'].get('StartingSequenceNumber', 'N/A')}")
                if 'EndingSequenceNumber' in shard['SequenceNumberRange']:
                    print(f"    Status: CLOSED")
                else:
                    print(f"    Status: OPEN")
            
            return True
            
        except Exception as e:
            print(f"Error checking stream status: {e}")
            return False
    
    def get_kinesis_metrics(self, period_minutes=60):
        """
        Get CloudWatch metrics for Kinesis stream
        
        Args:
            period_minutes: Time period to look back for metrics
        """
        print(f"\n=== Kinesis Metrics (Last {period_minutes} minutes) ===")
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=period_minutes)
        
        metrics = [
            ('IncomingRecords', 'Sum', 'Total records sent to stream'),
            ('IncomingBytes', 'Sum', 'Total bytes sent to stream'),
            ('GetRecords.Success', 'Sum', 'Successful GetRecords calls'),
            ('PutRecord.Success', 'Sum', 'Successful PutRecord calls')
        ]
        
        for metric_name, stat, description in metrics:
            try:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Kinesis',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'StreamName',
                            'Value': self.stream_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period_minutes * 60,
                    Statistics=[stat]
                )
                
                datapoints = response.get('Datapoints', [])
                if datapoints:
                    value = datapoints[0].get(stat, 0)
                    print(f"{metric_name}: {value} ({description})")
                else:
                    print(f"{metric_name}: No data")
                    
            except Exception as e:
                print(f"Error getting metric {metric_name}: {e}")
    
    def check_dynamodb_tables(self):
        """
        Check status of DynamoDB tables
        """
        print("\n=== DynamoDB Tables Status ===")
        
        tables = ['Precipitation', 'Temperature']
        
        for table_name in tables:
            try:
                response = self.dynamodb.describe_table(TableName=table_name)
                table = response['Table']
                
                print(f"\nTable: {table_name}")
                print(f"  Status: {table['TableStatus']}")
                print(f"  Item Count: {table['ItemCount']}")
                print(f"  Size: {table['TableSizeBytes'] / 1024:.2f} KB")
                
                # Check provisioning
                if 'BillingModeSummary' in table:
                    print(f"  Billing Mode: {table['BillingModeSummary']['BillingMode']}")
                
            except Exception as e:
                print(f"Error checking table {table_name}: {e}")
    
    def check_iterator_age(self):
        """
        Check how far behind the consumer is (iterator age)
        """
        print("\n=== Iterator Age (Consumer Lag) ===")
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=10)
        
        try:
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Kinesis',
                MetricName='GetRecords.IteratorAgeMilliseconds',
                Dimensions=[
                    {
                        'Name': 'StreamName',
                        'Value': self.stream_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=600,  # 10 minutes
                Statistics=['Maximum']
            )
            
            datapoints = response.get('Datapoints', [])
            if datapoints:
                max_age_ms = datapoints[0].get('Maximum', 0)
                max_age_seconds = max_age_ms / 1000
                
                print(f"Maximum Iterator Age: {max_age_seconds:.2f} seconds")
                
                if max_age_seconds > 60:
                    print("⚠ WARNING: Consumer is falling behind!")
                elif max_age_seconds > 300:
                    print("⚠⚠ CRITICAL: Consumer is significantly behind!")
                else:
                    print("✓ Consumer is keeping up with the stream")
            else:
                print("No iterator age data available")
                
        except Exception as e:
            print(f"Error checking iterator age: {e}")
    
    def run_health_check(self):
        """
        Run complete health check of the pipeline
        """
        print("=" * 60)
        print("Pipeline Health Check")
        print(f"Time: {datetime.utcnow().isoformat()}")
        print("=" * 60)
        
        # Check all components
        self.check_kinesis_stream_status()
        self.get_kinesis_metrics(period_minutes=60)
        self.check_iterator_age()
        self.check_dynamodb_tables()
        
        print("\n" + "=" * 60)
        print("Health check complete")
        print("=" * 60)

def continuous_monitor(stream_name, interval_seconds=300, aws_region='us-east-1'):
    """
    Continuously monitor the pipeline at regular intervals
    
    Args:
        stream_name: Kinesis stream name
        interval_seconds: How often to check (default: 5 minutes)
        aws_region: AWS region
    """
    monitor = PipelineMonitor(stream_name, aws_region)
    
    print(f"Starting continuous monitoring (checking every {interval_seconds} seconds)")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            monitor.run_health_check()
            print(f"\nNext check in {interval_seconds} seconds...")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")

def main():
    """
    Main function - run a single health check
    """
    # Configuration
    STREAM_NAME = "weather-data-stream"
    AWS_REGION = "us-east-1"
    
    monitor = PipelineMonitor(STREAM_NAME, AWS_REGION)
    monitor.run_health_check()
    
    # Uncomment to enable continuous monitoring
    # continuous_monitor(STREAM_NAME, interval_seconds=300, aws_region=AWS_REGION)

if __name__ == "__main__":
    main()