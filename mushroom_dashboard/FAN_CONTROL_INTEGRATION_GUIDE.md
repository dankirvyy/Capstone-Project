# Fan Control Integration Guide
## Mushroom Dashboard - ESP32 + Relay Module

This guide covers the complete integration of a 5V USB fan with your mushroom farming dashboard using a relay module and ESP32.

---

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [Hardware Setup (Wiring)](#hardware-setup-wiring)
3. [Software Integration](#software-integration)
4. [Complete ESP32 Code](#complete-esp32-code)
5. [Safety Precautions](#safety-precautions)
6. [Troubleshooting](#troubleshooting)

---

## System Architecture Overview

```
┌─────────────────┐    HTTP GET     ┌──────────────────┐    WiFi    ┌─────────────────┐
│   Web Browser   │◄──────────────►│  Django Server   │◄──────────►│     ESP32       │
│   (Dashboard)   │    /api/env/   │  (Backend API)   │            │ (Microcontroller)│
└─────────────────┘                 └──────────────────┘            └────────┬────────┘
                                                                             │
        User toggles                Fan state stored in                GPIO Pin
        fan ON/OFF                  EnvironmentSettings                    │
                                         model                             ▼
                                                                    ┌─────────────────┐
                                                                    │  Relay Module   │
                                                                    └────────┬────────┘
                                                                             │
                                                                    Switches power
                                                                             │
                                                                             ▼
                                                                    ┌─────────────────┐
                                                                    │    5V USB Fan   │
                                                                    └─────────────────┘
```

### Communication Flow:
1. **User Action**: Admin toggles fan switch in "Environmental Control" tab
2. **Frontend → Backend**: JavaScript sends POST to `/api/environment/` with `fan_on: true/false`
3. **Backend Storage**: Django saves state to `EnvironmentSettings` model
4. **ESP32 Polling**: ESP32 periodically polls `/api/environment/control-state/` endpoint
5. **ESP32 → Relay**: ESP32 sets GPIO pin HIGH/LOW to control relay
6. **Relay → Fan**: Relay switches power to fan ON/OFF

---

## Hardware Setup (Wiring)

### Components Needed:
| Component | Specifications | Quantity |
|-----------|---------------|----------|
| ESP32 Development Board | Any variant | 1 |
| Relay Module | 5V, 1-channel (with optocoupler recommended) | 1 |
| 5V USB Fan | With USB connector | 1 |
| External 5V Power Supply | 5V 2A (recommended) | 1 |
| Jumper Wires | Male-to-Female | 5+ |
| USB Cable (for cutting) | Matches your fan | 1 |

### Understanding the Relay Module:

A typical relay module has these pins:
- **VCC**: Power supply (3.3V or 5V)
- **GND**: Ground
- **IN (or SIG)**: Control signal from ESP32
- **COM**: Common terminal (connects to power source)
- **NO**: Normally Open (disconnected when relay is OFF)
- **NC**: Normally Closed (connected when relay is OFF)

### Step-by-Step Wiring Instructions:

#### Step 1: Prepare the USB Cable
```
Standard USB Cable Wire Colors:
┌──────────────────────────────────────────┐
│  RED    = +5V (Positive/VCC)             │
│  BLACK  = GND (Ground/Negative)          │
│  WHITE  = Data- (Not needed, ignore)     │
│  GREEN  = Data+ (Not needed, ignore)     │
└──────────────────────────────────────────┘
```

**IMPORTANT**: Only cut the RED (+5V) wire. The BLACK (GND) should remain connected straight through.

1. Cut the USB cable somewhere in the middle
2. Strip about 1cm of insulation from the RED wire on BOTH cut ends
3. Leave the BLACK wire intact (you can reconnect it with a wire nut or solder)
4. Ignore WHITE and GREEN wires (data lines, not needed)

#### Step 2: Wire the Relay Module to ESP32

```
ESP32 Pin Connections:
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  ESP32 3.3V  ──────────────► Relay VCC                 │
│  ESP32 GND   ──────────────► Relay GND                 │
│  ESP32 GPIO 26 ────────────► Relay IN (Signal)         │
│                                                         │
│  NOTE: Some relay modules need 5V for VCC.             │
│        Check your relay specifications.                 │
│        If 5V needed, connect to ESP32 VIN pin.         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### Step 3: Wire the Fan Through the Relay

**Option A: Using External 5V Power Supply (RECOMMENDED)**
```
Wiring Diagram:
                                          
    External 5V             Relay Module                 USB Fan
    Power Supply                                         
    ┌─────────┐            ┌────────────┐             ┌─────────┐
    │  (+)────┼────────────┼──►COM      │             │         │
    │         │            │            │             │  RED ◄──┼───┐
    │         │            │    NO ─────┼─────────────┼─────────┘   │
    │         │            │            │             │             │
    │  (-)────┼────────┐   │    NC      │ (unused)    │             │
    │         │        │   │            │             │             │
    └─────────┘        │   │   VCC◄─────┼────ESP32 3.3V/5V         │
                       │   │   GND◄─────┼────ESP32 GND              │
                       │   │   IN ◄─────┼────ESP32 GPIO 26          │
                       │   └────────────┘                           │
                       │                                            │
                       │                              ┌─────────────┘
                       │                              │
                       └──────────────────────────────┼──► Fan BLACK (GND)
                                                      │
                                                      └── (through cut cable)
                                                          
Legend:
  ──► = Wire connection
  COM = Common (input power)
  NO  = Normally Open (fan gets power when relay activates)
```

**Option B: Powering from ESP32 USB (NOT recommended for continuous use)**
```
If your fan draws less than 500mA, you can use ESP32 VIN:

    ESP32 VIN (5V) ──────────► Relay COM
    ESP32 GND     ──────────┬─► Relay GND
                            └─► Fan GND (through cable)
    Relay NO      ──────────► Fan +5V (RED wire from fan side)
```

#### Step 4: Complete Wiring Summary

```
COMPLETE WIRING TABLE:
┌───────────────────────┬──────────────────────────────────────┐
│ Connection            │ Description                          │
├───────────────────────┼──────────────────────────────────────┤
│ ESP32 3.3V → Relay VCC│ Powers the relay module              │
│ ESP32 GND → Relay GND │ Common ground                        │
│ ESP32 GPIO 26 → Relay │ Control signal (HIGH = ON)           │
│ IN                    │                                      │
├───────────────────────┼──────────────────────────────────────┤
│ External 5V+ → Relay  │ Power source for fan                 │
│ COM                   │                                      │
│ External 5V- → Fan    │ Ground for fan (via cut black wire)  │
│ GND                   │                                      │
│ Relay NO → Fan RED    │ Switched power to fan                │
│ wire                  │                                      │
└───────────────────────┴──────────────────────────────────────┘
```

### Visual Wiring Diagram:

```
                                    ┌────────────────────┐
                     ┌──────────────┤   RELAY MODULE     │
                     │              │                    │
                     │   ┌──────────┤ VCC    COM ────────┼─────── External 5V (+)
                     │   │          │                    │
                     │   │   ┌──────┤ GND    NO  ────────┼──┐
                     │   │   │      │                    │  │
                     │   │   │  ┌───┤ IN     NC  ────────┼──┼──(unused)
                     │   │   │  │   │                    │  │
                     │   │   │  │   └────────────────────┘  │
                     │   │   │  │                           │
┌────────────────────┴───┴───┴──┴─┐                         │
│          ESP32                   │                         │
│                                  │                         │
│  3.3V ─────────────────────┘     │      ┌─────────────────┘
│                                  │      │
│  GND ──────────────────────┘     │      │   ┌─────────────────┐
│                                  │      │   │   USB FAN       │
│  GPIO 26 ──────────────────┘     │      │   │                 │
│                                  │      └───┤ RED (+5V)       │
│  GPIO 4 ◄──── DHT22 DATA         │          │                 │
│  GPIO 34 ◄──── MQ-135 AOUT       │      ┌───┤ BLACK (GND) ────┼── External 5V (-)
│                                  │      │   │                 │
│                                  │      │   └─────────────────┘
└──────────────────────────────────┘      │
                                          │
                                          └─── Common Ground with External PSU
```

---

## Software Integration

### Part 1: Backend API Endpoint (Django)

Your existing `/api/environment/` endpoint already handles the fan state. Add a new lightweight endpoint specifically for ESP32 to fetch control states:

#### Add to `sensor_api.py`:

```python
# Add this new endpoint for ESP32 to poll control states

@csrf_exempt
@require_http_methods(["GET"])
def get_control_states(request):
    """
    API endpoint for ESP32 to fetch current control states
    Returns: fan_on, humidifier_on, heater_on, etc.
    """
    try:
        from .models import EnvironmentSettings
        settings = EnvironmentSettings.load()
        
        return JsonResponse({
            'status': 'success',
            'controls': {
                'fan_on': settings.fan_on,
                'fan_value': settings.fan_value,
                'humidifier_on': settings.humidifier_on,
                'heater_on': settings.heater_on,
                'co2_on': settings.co2_on,
                'lights_on': settings.lights_on,
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def confirm_control_action(request):
    """
    ESP32 confirms it executed a control action
    Useful for logging and verification
    """
    try:
        data = json.loads(request.body)
        device_id = data.get('device_id', 'ESP32_001')
        action = data.get('action')  # e.g., 'FAN_ON', 'FAN_OFF'
        success = data.get('success', True)
        
        # Log the action
        from .models import AutomationLog
        AutomationLog.objects.create(
            action=action,
            reason=f'ESP32 device {device_id} executed command',
            triggered_by=f'ESP32_{device_id}'
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Action {action} logged'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
```

#### Add URLs to `urls.py`:

```python
# Add these new URL patterns
path('api/control-states/', sensor_api.get_control_states, name='control-states'),
path('api/control-confirm/', sensor_api.confirm_control_action, name='control-confirm'),
```

### Part 2: Frontend (Already Working)

Your `environment.html` already has the fan control toggle working. When you toggle:
- It calls `saveSettings()` which POSTs to `/api/environment/`
- Django saves `fan_on` to `EnvironmentSettings` model
- ESP32 polls and reads this state

---

## Complete ESP32 Code

Here's the updated Arduino code with relay control integrated:

```cpp
/*
 * ESP32 DHT22 + MQ-135 + Fan Control for Mushroom Farming Dashboard
 * 
 * Features:
 * - Reads temperature/humidity from DHT22
 * - Reads air quality from MQ-135
 * - Controls relay for fan based on dashboard settings
 * - Sends sensor data to Django server
 * - Polls control states from server
 * 
 * Hardware:
 * - ESP32 Development Board
 * - DHT22 Temperature & Humidity Sensor
 * - MQ-135 Air Quality Sensor
 * - 5V Relay Module (1-channel)
 * - 5V USB Fan (connected via relay)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ArduinoJson.h>  // Install via Library Manager

// ============== CONFIGURATION ==============

// WiFi credentials
const char* ssid = "Tenda_5E64C0";
const char* password = "xxx123xxx";

// Server settings - Update with your server IP
const char* serverBase = "http://192.168.0.111:8000";
const char* sensorDataUrl = "/api/sensor-data/receive/";
const char* controlStateUrl = "/api/control-states/";
const char* apiKey = "YOUR_API_KEY";

// ============== PIN DEFINITIONS ==============

// DHT22 Sensor
#define DHTPIN 4
#define DHTTYPE DHT22

// MQ-135 Air Quality Sensor
#define MQ135PIN 34

// Relay Control Pins (Active LOW for most relay modules)
#define FAN_RELAY_PIN 26
#define HUMIDIFIER_RELAY_PIN 27  // Optional: for future use
#define HEATER_RELAY_PIN 25      // Optional: for future use

// Relay behavior (set based on your relay module)
// Most relay modules are ACTIVE LOW (LOW = ON, HIGH = OFF)
// Some are ACTIVE HIGH (HIGH = ON, LOW = OFF)
#define RELAY_ACTIVE_LOW true

DHT dht(DHTPIN, DHTTYPE);

// ============== TIMING ==============

const unsigned long sensorReadInterval = 10000;   // Send sensor data every 10 sec
const unsigned long controlPollInterval = 2000;   // Poll control states every 2 sec
unsigned long lastSensorReadTime = 0;
unsigned long lastControlPollTime = 0;

// ============== CONTROL STATES ==============

bool fanOn = false;
int fanValue = 0;
bool humidifierOn = false;
bool heaterOn = false;

// ============== SETUP ==============

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n==========================================");
  Serial.println(" ESP32 Mushroom Farm Controller");
  Serial.println(" DHT22 + MQ-135 + Relay Control");
  Serial.println("==========================================\n");
  
  // Initialize DHT sensor
  dht.begin();
  Serial.println("[OK] DHT22 sensor initialized");
  
  // Initialize MQ-135
  pinMode(MQ135PIN, INPUT);
  Serial.println("[OK] MQ-135 air quality sensor initialized");
  
  // Initialize relay pins
  pinMode(FAN_RELAY_PIN, OUTPUT);
  pinMode(HUMIDIFIER_RELAY_PIN, OUTPUT);
  pinMode(HEATER_RELAY_PIN, OUTPUT);
  
  // Set relays to OFF initially
  setRelay(FAN_RELAY_PIN, false);
  setRelay(HUMIDIFIER_RELAY_PIN, false);
  setRelay(HEATER_RELAY_PIN, false);
  Serial.println("[OK] Relay pins initialized (all OFF)");
  
  // Connect to WiFi
  connectWiFi();
}

// ============== MAIN LOOP ==============

void loop() {
  unsigned long currentTime = millis();
  
  // Task 1: Read and send sensor data
  if (currentTime - lastSensorReadTime >= sensorReadInterval) {
    lastSensorReadTime = currentTime;
    readAndSendSensorData();
  }
  
  // Task 2: Poll control states from server
  if (currentTime - lastControlPollTime >= controlPollInterval) {
    lastControlPollTime = currentTime;
    pollControlStates();
  }
  
  // Small delay to prevent watchdog issues
  delay(10);
}

// ============== WIFI FUNCTIONS ==============

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[OK] WiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal Strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\n[ERROR] WiFi connection failed!");
    Serial.println("Restarting in 10 seconds...");
    delay(10000);
    ESP.restart();
  }
}

void ensureWiFiConnected() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WARNING] WiFi disconnected. Reconnecting...");
    connectWiFi();
  }
}

// ============== RELAY CONTROL ==============

void setRelay(int pin, bool on) {
  if (RELAY_ACTIVE_LOW) {
    // Active LOW: LOW = ON, HIGH = OFF
    digitalWrite(pin, on ? LOW : HIGH);
  } else {
    // Active HIGH: HIGH = ON, LOW = OFF
    digitalWrite(pin, on ? HIGH : LOW);
  }
}

void updateFanState(bool shouldBeOn) {
  if (fanOn != shouldBeOn) {
    fanOn = shouldBeOn;
    setRelay(FAN_RELAY_PIN, fanOn);
    
    Serial.print("\n[CONTROL] Fan turned ");
    Serial.println(fanOn ? "ON" : "OFF");
    
    // Optional: Confirm action to server
    // confirmControlAction(fanOn ? "FAN_ON" : "FAN_OFF");
  }
}

// ============== SENSOR READING ==============

void readAndSendSensorData() {
  // Read sensors
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();
  int airQualityRaw = analogRead(MQ135PIN);
  float airQualityPPM = map(airQualityRaw, 0, 4095, 0, 1000);
  
  // Validate readings
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("[ERROR] Failed to read from DHT sensor!");
    return;
  }
  
  // Display readings
  Serial.println("\n--- Sensor Readings ---");
  Serial.printf("Temperature: %.1f C\n", temperature);
  Serial.printf("Humidity: %.1f %%\n", humidity);
  Serial.printf("Air Quality: %d (raw) | ~%.0f PPM\n", airQualityRaw, airQualityPPM);
  
  // Check conditions
  checkGrowingConditions(temperature, humidity, airQualityPPM);
  
  // Send to server
  ensureWiFiConnected();
  if (WiFi.status() == WL_CONNECTED) {
    sendSensorData(temperature, humidity, airQualityPPM);
  }
}

void sendSensorData(float temperature, float humidity, float airQuality) {
  HTTPClient http;
  String url = String(serverBase) + String(sensorDataUrl);
  
  Serial.println("\n[SENDING] Sensor data to server...");
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  
  // Create JSON payload
  StaticJsonDocument<200> doc;
  doc["temperature"] = temperature;
  doc["humidity"] = humidity;
  doc["air_quality_ppm"] = (int)airQuality;
  doc["device_id"] = "ESP32_DHT22_MQ135";
  
  String jsonPayload;
  serializeJson(doc, jsonPayload);
  
  int httpCode = http.POST(jsonPayload);
  
  if (httpCode > 0) {
    Serial.printf("[OK] Server response: %d\n", httpCode);
    if (httpCode == 200 || httpCode == 201) {
      Serial.println(http.getString());
    }
  } else {
    Serial.printf("[ERROR] HTTP error: %s\n", http.errorToString(httpCode).c_str());
  }
  
  http.end();
}

// ============== CONTROL STATE POLLING ==============

void pollControlStates() {
  ensureWiFiConnected();
  if (WiFi.status() != WL_CONNECTED) return;
  
  HTTPClient http;
  String url = String(serverBase) + String(controlStateUrl);
  
  http.begin(url);
  http.addHeader("X-API-Key", apiKey);
  
  int httpCode = http.GET();
  
  if (httpCode == 200) {
    String response = http.getString();
    
    // Parse JSON response
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, response);
    
    if (!error) {
      JsonObject controls = doc["controls"];
      
      bool newFanState = controls["fan_on"];
      int newFanValue = controls["fan_value"];
      bool newHumidifierState = controls["humidifier_on"];
      bool newHeaterState = controls["heater_on"];
      
      // Update fan
      updateFanState(newFanState);
      fanValue = newFanValue;
      
      // Update humidifier (if connected)
      if (humidifierOn != newHumidifierState) {
        humidifierOn = newHumidifierState;
        setRelay(HUMIDIFIER_RELAY_PIN, humidifierOn);
        Serial.print("[CONTROL] Humidifier turned ");
        Serial.println(humidifierOn ? "ON" : "OFF");
      }
      
      // Update heater (if connected)
      if (heaterOn != newHeaterState) {
        heaterOn = newHeaterState;
        setRelay(HEATER_RELAY_PIN, heaterOn);
        Serial.print("[CONTROL] Heater turned ");
        Serial.println(heaterOn ? "ON" : "OFF");
      }
      
    } else {
      Serial.print("[ERROR] JSON parse failed: ");
      Serial.println(error.c_str());
    }
  } else if (httpCode > 0) {
    Serial.printf("[WARNING] Control poll returned: %d\n", httpCode);
  } else {
    Serial.printf("[ERROR] Control poll failed: %s\n", http.errorToString(httpCode).c_str());
  }
  
  http.end();
}

// ============== CONDITION CHECKING ==============

void checkGrowingConditions(float temperature, float humidity, float airQuality) {
  Serial.println("--- Condition Analysis ---");
  
  // Temperature check (optimal: 13-18°C)
  if (temperature < 13) {
    Serial.println("TEMP: TOO LOW for optimal growth");
  } else if (temperature > 18) {
    Serial.println("TEMP: TOO HIGH for optimal growth");
  } else {
    Serial.println("TEMP: OPTIMAL");
  }
  
  // Humidity check (optimal: 80-95%)
  if (humidity < 80) {
    Serial.println("HUMIDITY: TOO LOW - increase misting");
  } else if (humidity > 95) {
    Serial.println("HUMIDITY: TOO HIGH - risk of contamination");
  } else {
    Serial.println("HUMIDITY: OPTIMAL");
  }
  
  // Air Quality check
  if (airQuality < 400) {
    Serial.println("AIR QUALITY: GOOD");
  } else if (airQuality < 800) {
    Serial.println("AIR QUALITY: ACCEPTABLE - consider ventilation");
  } else {
    Serial.println("AIR QUALITY: POOR - activate ventilation!");
  }
  
  Serial.println("--------------------------");
}
```

---

## Safety Precautions

### Electrical Safety:

1. **Always disconnect power before wiring**
   - Unplug the USB power supply before making connections

2. **Use proper wire gauges**
   - For 5V fan (typically <500mA), standard USB cable wires are sufficient

3. **Don't exceed relay ratings**
   - Check your relay module's maximum current rating (usually 10A)
   - A USB fan draws much less (typically 100-300mA), so this is safe

4. **Use external power for the fan**
   - Recommended: Use separate 5V power supply for the fan
   - The ESP32's USB port shouldn't power the fan directly if >500mA

5. **Isolate with optocoupler relay**
   - Use relay modules with optocoupler isolation for safety

### Fire Prevention:

1. **Proper connections**
   - Ensure all wire connections are tight and secure
   - Use proper crimp connectors or solder joints

2. **Fuse protection**
   - Consider adding an inline fuse on the power supply line

3. **Heat management**
   - Ensure the relay module has ventilation
   - Don't enclose the relay in a sealed box

### Code Safety:

1. **Fail-safe default**
   - The code initializes all relays to OFF state
   - If WiFi disconnects, the last state is maintained

2. **Watchdog timer**
   - ESP32 has built-in watchdog to prevent freezing

---

## Troubleshooting

### Problem: Fan doesn't turn on/off

| Check | Solution |
|-------|----------|
| Relay LED | If relay LED doesn't change, check GPIO connection |
| Relay type | Verify if ACTIVE_LOW or ACTIVE_HIGH and set constant |
| Wiring | Ensure NO (Normally Open) connection, not NC |
| Power | Check external power supply is working |

### Problem: ESP32 not connecting to server

| Check | Solution |
|-------|----------|
| WiFi credentials | Verify SSID and password |
| Server IP | Confirm Django server IP address |
| Firewall | Ensure port 8000 is open |
| Same network | ESP32 must be on same network as server |

### Problem: Control states not updating

| Check | Solution |
|-------|----------|
| Endpoint URL | Verify `/api/control-states/` is added to urls.py |
| Server running | Confirm Django server is running |
| Serial monitor | Check ESP32 output for errors |

### Testing the Relay Manually:

Add this test code to verify relay works:

```cpp
void testRelay() {
  Serial.println("Testing relay - ON");
  setRelay(FAN_RELAY_PIN, true);
  delay(2000);
  
  Serial.println("Testing relay - OFF");
  setRelay(FAN_RELAY_PIN, false);
  delay(2000);
}

// Call testRelay() in setup() after initialization
```

---

## Quick Reference

### Pin Summary:
| Component | ESP32 Pin |
|-----------|-----------|
| DHT22 Data | GPIO 4 |
| MQ-135 AOUT | GPIO 34 |
| Fan Relay IN | GPIO 26 |
| Humidifier Relay IN | GPIO 27 |
| Heater Relay IN | GPIO 25 |

### API Endpoints:
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sensor-data/receive/` | POST | Send sensor data |
| `/api/control-states/` | GET | Get control states |
| `/api/environment/` | GET/POST | Dashboard settings |

### Required Libraries:
- DHT sensor library by Adafruit
- ArduinoJson by Benoit Blanchon

Install via: **Sketch → Include Library → Manage Libraries**

---

## Summary

1. **Hardware**: Cut USB cable RED wire, route through relay NO terminal
2. **Backend**: Add `/api/control-states/` endpoint for ESP32 polling
3. **ESP32**: Poll server every 2 seconds, control relay based on response
4. **Dashboard**: Toggle already works - saves to EnvironmentSettings model

The system is now fully integrated!
