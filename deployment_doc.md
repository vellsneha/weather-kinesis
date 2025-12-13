# Weather Data Pipeline - Deployment Guide for Testing

## 🎯 Quick Access

**Live Dashboard:** http://YOUR_EC2_IP:5000

**SSH Access (if provided):**
```bash
ssh -i weather-kinesis.pem ec2-user@YOUR_EC2_IP
```

**AWS Region:** us-east-1

**Resources:**
- Kinesis Stream: `weather-data-stream`
- DynamoDB Tables: `Precipitation`, `Temperature`

---

## 📊 What's Running

This deployment includes:
1. ✅ Producer: Collecting weather data from NOAA API for Maryland stations (Oct 2021)
2. ✅ Kinesis Stream: Real-time data streaming pipeline
3. ✅ Consumer: Processing and storing data in DynamoDB
4. ✅ Web Dashboard: Visualizing the data and pipeline status

---

## 🖥️ Viewing the Results

### Option 1: Web Dashboard (Easiest)

Visit: **http://YOUR_EC2_IP:5000**

The dashboard shows:
- Pipeline statistics (number of stations, records processed)
- Real-time data queries by station
- Sample weather data with temperature and precipitation

### Option 2: AWS Console

1. **DynamoDB Tables:**
   - Go to: https://console.aws.amazon.com/dynamodb/
   - Tables: `Precipitation` and `Temperature`
   - Click "Explore items" to see data

2. **Kinesis Stream:**
   - Go to: https://console.aws.amazon.com/kinesis/
   - Stream: `weather-data-stream`
   - View monitoring metrics

### Option 3: Command Line (via SSH)

```bash
# SSH into the instance
ssh -i weather-kinesis.pem ec2-user@YOUR_EC2_IP

# Check pipeline status
cd ~/weatherkinesis
tail -f producer.log    # See producer progress
tail -f consumer.log    # See consumer processing

# Query data directly
python3 query_dynamodb.py

# Check monitoring stats
python3 monitor_pipeline.py
```

---

## 🔍 Verification Steps

To verify the pipeline is working:

### 1. Check Data in DynamoDB

```bash
# Via AWS CLI
aws dynamodb scan --table-name Precipitation --select COUNT --region us-east-1
aws dynamodb scan --table-name Temperature --select COUNT --region us-east-1

# Should show increasing record counts
```

### 2. Sample Query

```bash
# Get data for a specific station
aws dynamodb query \
    --table-name Temperature \
    --key-condition-expression "station_id = :sid" \
    --expression-attribute-values '{":sid":{"S":"GHCND:USC00186350"}}' \
    --region us-east-1
```

### 3. Check Kinesis Metrics

```bash
aws kinesis describe-stream-summary \
    --stream-name weather-data-stream \
    --region us-east-1
```

---

## 📈 Expected Results

After running for 1-2 hours:
- **Stations processed:** ~245 Maryland weather stations
- **Precipitation records:** ~3,000-5,000 records
- **Temperature records:** ~2,500-4,000 records
- **Date range:** October 1-31, 2021

**Note:** Not all stations have data for all dates. This is expected behavior.

---

## 🏗️ Architecture

```
NOAA API → Producer (EC2) → Kinesis Stream → Consumer (EC2) → DynamoDB
                                                                ├─ Precipitation
                                                                └─ Temperature
                                 ↓
                         Web Dashboard (Flask)
```

**Data Flow:**
1. Producer queries NOAA API for Maryland weather stations
2. Processes and formats data (groups by date, converts units)
3. Sends records to Kinesis stream
4. Consumer reads from Kinesis
5. Splits data into precipitation and temperature records
6. Stores in appropriate DynamoDB tables

---

## 💰 Cost Estimate

For this deployment running 2-3 hours:
- EC2 t2.micro: ~$0.012/hour × 3 hours = $0.036
- Kinesis (on-demand): ~$0.015 per million payload units ≈ $0.10
- DynamoDB (on-demand): ~$1.25 per million writes ≈ $0.05
- **Total: < $0.25** for complete demonstration

---

## 🛠️ Troubleshooting

### Dashboard not loading?
- Check security group allows port 5000
- Verify dashboard is running: `ps aux | grep dashboard`
- Check logs: `tail -f ~/weather-pipeline/dashboard.log`

### No data in tables?
- Check producer is running: `ps aux | grep producer`
- View producer logs: `tail -f ~/weather-pipeline/producer.log`
- Producer needs 1-2 hours to collect all data

### Consumer errors?
- Check consumer logs: `tail -f ~/weather-pipeline/consumer.log`
- Verify IAM role has DynamoDB permissions

---

## 📞 Contact

**Student:** [Your Name]
**Email:** [Your Email]
**Course:** [Course Number]

**Source Code:** [GitHub URL if you have one]

---

## 🧹 Cleanup (After Grading)

To avoid ongoing charges, delete resources:

```bash
# Delete Kinesis stream
aws kinesis delete-stream --stream-name weather-data-stream --region us-east-1

# Delete DynamoDB tables
aws dynamodb delete-table --table-name Precipitation --region us-east-1
aws dynamodb delete-table --table-name Temperature --region us-east-1

# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids i-xxxxxxxxxxxxx --region us-east-1
```

Or via AWS Console:
1. EC2 → Terminate instance
2. Kinesis → Delete stream
3. DynamoDB → Delete tables
