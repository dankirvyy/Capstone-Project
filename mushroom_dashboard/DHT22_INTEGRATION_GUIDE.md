# DHT22 Sensor Integration Guide
## ESP32 + Django Mushroom Farming Dashboard

---

## 📋 Table of Contents
1. [Hardware Requirements](#hardware-requirements)
2. [Arduino Setup](#arduino-setup)
3. [Django Backend Setup](#django-backend-setup)
4. [Testing the Integration](#testing-the-integration)
5. [Troubleshooting](#troubleshooting)
6. [API Documentation](#api-documentation)

---

## 🔧 Hardware Requirements

### Components Needed
- **ESP32 Development Board** (or ESP8266)
- **DHT22 Temperature & Humidity Sensor** (AM2302)
- **10kΩ Resistor** (pull-up resistor, often built into DHT22 modules)
- **Breadboard and jumper wires**
- **USB cable** for programming

### Wiring Diagram
```
DHT22 Sensor -> ESP32
-----------------------
VCC (Red)    -> 3.3V
GND (Black)  -> GND
DATA (Yellow)-> GPIO 4 (configurable)
```

**Note:** If using a bare DHT22 sensor (not a module), add a 10kΩ pull-up resistor between VCC and DATA.

---

## 🖥️ Arduino Setup

### Step 1: Install Arduino IDE
1. Download from: https://www.arduino.cc/en/software
2. Install for your operating system

### Step 2: Install ESP32 Board Support
1. Open Arduino IDE
2. Go to **File → Preferences**
3. Add this URL to "Additional Board Manager URLs":
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Go to **Tools → Board → Boards Manager**
5. Search for "ESP32" and install **ESP32 by Espressif Systems**

### Step 3: Install Required Libraries
1. Go to **Sketch → Include Library → Manage Libraries**
2. Install the following:
   - **DHT sensor library** by Adafruit
   - **Adafruit Unified Sensor** by Adafruit

### Step 4: Configure the Arduino Sketch
1. Open `arduino_esp32_dht22.ino`
2. Update these settings:
   ```cpp
   const char* ssid = "Your_WiFi_Name";
   const char* password = "Your_WiFi_Password";
   const char* serverUrl = "http://192.168.1.100:8000/api/sensor-data/";
   const char* apiKey = "your-secret-api-key";
   ```

3. If using a different GPIO pin, change:
   ```cpp
   #define DHTPIN 4  // Change to your pin number
   ```

### Step 5: Upload to ESP32
1. Connect ESP32 via USB
2. Select **Tools → Board → ESP32 Dev Module**
3. Select the correct **Port**
4. Click **Upload** button (→)
5. Open **Serial Monitor** (Tools → Serial Monitor) at 115200 baud to see output

---

## 🐍 Django Backend Setup

### Step 1: Apply Database Migration
Run the migration to update the SensorReading model:
```bash
python manage.py migrate
```

This will:
- Add `device_id` field to track sensor devices
- Make `co2_ppm` optional (DHT22 doesn't measure CO2)
- Add database indexes for better performance
- Add help text to fields

### Step 2: Update API Key (Optional)
Edit `core/sensor_api.py` and set a secure API key:
```python
API_KEY = "your-super-secret-api-key-here"
```

**Important:** Use the same key in both:
- Arduino sketch (`apiKey` variable)
- Django API (`API_KEY` in sensor_api.py)

### Step 3: Configure Django for External Access

#### Option A: Local Network Access
To allow ESP32 on your local network to access Django:

```bash
python manage.py runserver 0.0.0.0:8000
```

Find your computer's IP address:
- **Windows:** `ipconfig` in Command Prompt (look for IPv4)
- **Mac/Linux:** `ifconfig` or `ip addr`

Use this IP in the ESP32 sketch.

#### Option B: Production Deployment
For production, deploy to a server with a public IP or domain name.

### Step 4: Update ALLOWED_HOSTS
In `mushroom_dashboard/settings.py`:
```python
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'YOUR_SERVER_IP', '*']
```

---

## 🧪 Testing the Integration

### Test 1: Manual API Test
Test the API endpoint using curl or Postman:

```bash
curl -X POST http://localhost:8000/api/sensor-data/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{"temperature": 16.5, "humidity": 85.2}'
```

Expected response:
```json
{
  "status": "success",
  "message": "Sensor data received successfully",
  "data": {
    "id": 1,
    "timestamp": "2026-01-30T10:30:00Z",
    "temperature": 16.5,
    "humidity": 85.2,
    "condition_status": "OPTIMAL",
    "alerts": []
  }
}
```

### Test 2: Verify Data in Database
```bash
python manage.py shell
```

```python
from core.models import SensorReading
readings = SensorReading.objects.all()
for r in readings:
    print(f"{r.timestamp}: {r.temperature}°C, {r.humidity}% - {r.condition_status}")
```

### Test 3: ESP32 Serial Monitor
Open the Serial Monitor in Arduino IDE. You should see:
```
=================================
ESP32 DHT22 Sensor Node
Mushroom Farming Dashboard
=================================

DHT22 sensor initialized
Connecting to WiFi: YourNetworkName
..........
✓ WiFi connected!
IP Address: 192.168.1.50

--- Sensor Reading ---
Temperature: 16.5 °C
Humidity: 85.2 %

--- Condition Analysis ---
✓ Temperature is OPTIMAL
✓ Humidity is OPTIMAL

📡 Sending data to server...
✓ Server Response Code: 201
```

---

## 🔍 Troubleshooting

### ESP32 Won't Connect to WiFi
- **Check credentials:** Ensure SSID and password are correct
- **Signal strength:** Move ESP32 closer to router
- **2.4GHz only:** ESP32 doesn't support 5GHz networks
- **Hidden networks:** Make sure network is visible

### "Failed to read from DHT sensor"
- **Check wiring:** Verify VCC, GND, and DATA connections
- **Power supply:** Ensure 3.3V or 5V is stable
- **Wait time:** Add delay(2000) in setup() before first reading
- **Sensor quality:** Some cheap DHT22 sensors are unreliable

### HTTP Error 401 (Unauthorized)
- **API Key mismatch:** Ensure Arduino and Django use same key
- **Header name:** Check that header is "X-API-Key"

### HTTP Error 400 (Bad Request)
- **JSON format:** Verify data is valid JSON
- **Required fields:** Must include "temperature" and "humidity"

### HTTP Error 500 (Server Error)
- **Django logs:** Check terminal where Django is running
- **Database:** Ensure migrations are applied
- **ALLOWED_HOSTS:** Add ESP32's IP to settings

### No Data Appearing in Dashboard
- **Check database:** Run manual query to verify data is saved
- **View refresh:** Template might need updating to show new fields
- **CORS issues:** If using frontend framework, check CORS settings

---

## 📚 API Documentation

### POST /api/sensor-data/
Receive sensor data from ESP32

**Headers:**
```
Content-Type: application/json
X-API-Key: your-secret-api-key
```

**Request Body:**
```json
{
  "temperature": 16.5,
  "humidity": 85.2,
  "device_id": "ESP32_001"  // optional
}
```

**Response (201 Created):**
```json
{
  "status": "success",
  "message": "Sensor data received successfully",
  "data": {
    "id": 123,
    "timestamp": "2026-01-30T10:30:00Z",
    "temperature": 16.5,
    "humidity": 85.2,
    "condition_status": "OPTIMAL",
    "alerts": []
  }
}
```

### GET /api/sensor-data/latest/
Get the latest sensor readings

**Query Parameters:**
- `limit` (optional): Number of readings to return (default: 10)

**Example:**
```
GET /api/sensor-data/latest/?limit=20
```

**Response:**
```json
{
  "status": "success",
  "count": 20,
  "data": [
    {
      "id": 123,
      "timestamp": "2026-01-30T10:30:00Z",
      "temperature": 16.5,
      "humidity": 85.2,
      "device_id": "DHT22_ESP32",
      "condition_status": "OPTIMAL"
    }
  ]
}
```

### GET /api/sensor-data/stats/
Get statistics for a time period

**Query Parameters:**
- `hours` (optional): Hours to look back (default: 24)

**Example:**
```
GET /api/sensor-data/stats/?hours=48
```

**Response:**
```json
{
  "status": "success",
  "period_hours": 48,
  "statistics": {
    "temperature": {
      "average": 16.2,
      "minimum": 14.5,
      "maximum": 18.0
    },
    "humidity": {
      "average": 85.5,
      "minimum": 78.0,
      "maximum": 92.0
    }
  }
}
```

---

## 🌡️ Growing Conditions Reference

### Optimal Conditions (Most Mushroom Varieties)
- **Temperature:** 13-18°C (55-64°F)
- **Humidity:** 80-95%

### Status Levels
- **OPTIMAL:** Temperature 13-18°C AND Humidity 80-95%
- **ACCEPTABLE:** Temperature 10-21°C AND Humidity 70-98%
- **CRITICAL:** Outside acceptable ranges

### Automatic Alerts
The system creates notifications when:
- Temperature < 10°C or > 21°C (CRITICAL)
- Humidity < 70% or > 98% (WARNING)

---

## 📊 Database Schema

The enhanced `SensorReading` model:

| Field       | Type            | Description                     |
|-------------|-----------------|---------------------------------|
| id          | AutoField       | Primary key                     |
| timestamp   | DateTimeField   | Auto-set on creation            |
| temperature | DecimalField    | Temperature in Celsius (XX.X)   |
| humidity    | DecimalField    | Humidity percentage (XX.X)      |
| co2_ppm     | IntegerField    | CO2 level (optional, nullable)  |
| device_id   | CharField(50)   | Device identifier               |

**Indexes:**
- timestamp (DESC) for fast recent queries
- device_id + timestamp for per-device queries

---

## 🔐 Security Recommendations

1. **Change the API key** from default value
2. **Use HTTPS** in production (not HTTP)
3. **Firewall rules:** Only allow necessary ports
4. **Rate limiting:** Add to prevent abuse
5. **Authentication:** Consider token-based auth for production

---

## 🚀 Next Steps

1. **Add more sensors:** Multiple ESP32 devices with unique `device_id`
2. **Real-time dashboard:** Use WebSockets for live updates
3. **Historical charts:** Visualize temperature/humidity trends
4. **Email alerts:** Send notifications for critical conditions
5. **Automation:** Control fans/heaters based on readings
6. **Mobile app:** Create mobile interface for monitoring

---

## 📞 Support

If you encounter issues:
1. Check Serial Monitor for ESP32 debug output
2. Check Django development server logs
3. Verify database migration status: `python manage.py showmigrations`
4. Test API manually with curl/Postman

---

**Created for:** Mushroom Farming Dashboard
**Date:** January 30, 2026
**Hardware:** ESP32 + DHT22
**Framework:** Django + Arduino
