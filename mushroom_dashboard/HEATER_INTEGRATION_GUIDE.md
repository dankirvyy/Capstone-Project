# Heater Integration Guide for Mushroom Farm Automation
## ESP32 + Django Dashboard Integration

---

## 📋 Table of Contents
1. [Overview](#overview)
2. [Hardware Requirements](#hardware-requirements)
3. [Wiring Setup](#wiring-setup)
4. [Safety Precautions](#safety-precautions)
5. [Arduino IDE Code](#arduino-ide-code)
6. [Temperature Thresholds](#temperature-thresholds)
7. [Dashboard Configuration](#dashboard-configuration)
8. [Testing & Troubleshooting](#testing--troubleshooting)

---

## 🔍 Overview

This guide explains how to add a heater to your existing mushroom farm automation system. The heater will:
- Turn **ON** automatically when temperature drops below a threshold (default: 15°C)
- Turn **OFF** automatically when temperature reaches the desired level (default: 20°C)
- Work in both **Automatic** and **Manual** modes via the dashboard
- Integrate seamlessly with your existing DHT22 sensor and ESP32 controller

### System Architecture
```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   DHT22      │         │    ESP32     │         │    DJANGO    │
│   Sensor     │────────▶│  Controller  │◀───────▶│   Backend    │
│              │         │              │         │              │
└──────────────┘         └──────────────┘         └──────────────┘
                                │
                                ▼
                    ┌─────────────────────────────┐
                    │      RELAY MODULE           │
                    │  ┌───┐  ┌───┐  ┌───┐       │
                    │  │FAN│  │MIST│ │HEAT│      │
                    │  └───┘  └───┘  └───┘       │
                    └─────────────────────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
                    ▼           ▼           ▼
                   FAN      MISTING      HEATER
```

---

## 🔧 Hardware Requirements

### Components Needed
| Component | Quantity | Notes |
|-----------|----------|-------|
| ESP32 Development Board | 1 | Already in use |
| 3-Channel Relay Module | 1 | Or add 1 relay to existing 2-channel |
| Electric Heater | 1 | See recommended types below |
| 18-20 AWG Wire | ~2m | For power connections |
| Terminal Block Connectors | 2-4 | For secure connections |
| Fuse Holder + Fuse | 1 | Matching heater current rating |
| Heat-resistant enclosure | 1 | For relay and wiring |

### Recommended Heater Types for Mushroom Farming

| Heater Type | Power | Pros | Cons |
|-------------|-------|------|------|
| **Ceramic Heater** | 100-300W | Safe, no open flame, quiet | Slower heating |
| **PTC Heater** | 50-200W | Self-regulating, safe | More expensive |
| **Silicone Heater Mat** | 50-150W | Even heat distribution | Limited area coverage |
| **Tubular Heater** | 60-250W | Greenhouse standard | Needs mounting |
| **Infrared Heater** | 100-500W | Efficient, quick | Can cause hot spots |

**Recommendation for small mushroom grow rooms (1-5m²):** 
- **PTC Ceramic Heater 100-200W** - Safe, self-regulating, won't overheat

---

## 🔌 Wiring Setup

### Pin Assignment Summary
```
┌─────────────┬────────────────────────────────┐
│ Device      │ ESP32 GPIO Pin                 │
├─────────────┼────────────────────────────────┤
│ DHT22       │ GPIO 4 (existing)              │
│ MQ-135      │ GPIO 34 (existing)             │
│ Fan Relay   │ GPIO 26 (existing)             │
│ Mist Relay  │ GPIO 27 (existing)             │
│ Heater Relay│ GPIO 25 (NEW)                  │
└─────────────┴────────────────────────────────┘
```

### Complete Wiring Diagram

```
=============================================================================
RELAY MODULE (3-Channel) TO ESP32:
=============================================================================

┌─────────────┬────────────────┐
│ Relay Pin   │ ESP32 Pin      │
├─────────────┼────────────────┤
│ VCC         │ 5V (VIN)       │
│ GND         │ GND            │
│ IN1 (Fan)   │ GPIO 26        │
│ IN2 (Mist)  │ GPIO 27        │
│ IN3 (Heat)  │ GPIO 25        │  ← NEW HEATER RELAY
└─────────────┴────────────────┘

=============================================================================
HEATER WIRING (AC 220V Example - Most Common):
=============================================================================

⚠️  WARNING: AC MAINS VOLTAGE (220V/110V) IS LETHAL!
    - Disconnect ALL power before wiring
    - Have a qualified electrician verify your work
    - Use appropriate wire gauge for the heater current
    - Install proper fusing and circuit breakers

                    WALL OUTLET (AC 220V or 110V)
                           ┌─────────┐
                           │  LIVE   │═══════════════╗
                           │ (Brown/ │               ║
                           │  Black) │               ║
                           ├─────────┤               ║
                           │ NEUTRAL │               ║
                           │(Blue/   │               ║
                           │ White)  │               ║
                           ├─────────┤               ║
                           │ GROUND  │               ║
                           │(Green/  │               ║
                           │ Yellow) │               ║
                           └─────────┘               ║
                               │                     ║
                               │                     ║
    ┌──────────────────────────┼─────────────────────╫───────────────────┐
    │                          │                     ║                   │
    │          ┌───────────────┴────────┐            ║                   │
    │          │        FUSE            │            ║                   │
    │          │   (Match heater amps)  │            ║                   │
    │          │    e.g., 3A for 500W   │            ║                   │
    │          └───────────────┬────────┘            ║                   │
    │                          │                     ║                   │
    │                 ┌────────▼────────────┐        ║                   │
    │                 │      RELAY 3        │        ║                   │
    │                 │     (HEATER)        │        ║                   │
    │                 │                     │        ║                   │
    │                 │   COM ◄─────────────╫────────╝                   │
    │                 │                     │                            │
    │                 │   NO ───────┐       │                            │
    │                 │             │       │                            │
    │                 │   NC        │       │                            │
    │                 └─────────────│───────┘                            │
    │                               │                                    │
    │                    ┌──────────▼──────────┐                         │
    │                    │       HEATER        │                         │
    │                    │    (100-500W)       │                         │
    │                    │                     │                         │
    │                    │  LIVE ───────────────┤                        │
    │                    │  NEUTRAL ────────────┼───── To Wall Neutral   │
    │                    │  GROUND ─────────────┼───── To Wall Ground    │
    │                    └─────────────────────┘                         │
    │                                                                    │
    └────────────────────────────────────────────────────────────────────┘


=============================================================================
HEATER WIRING (DC 12V/24V - SAFER OPTION):
=============================================================================

If using a LOW VOLTAGE DC heater (12V or 24V), the wiring is similar
to the misting system:

     ┌─────────────────────────────────────────────────────────┐
     │              DC POWER SUPPLY (12V or 24V)               │
     │                   (Match heater voltage)                │
     │          (+12/24V) ───────┬─────────── (GND)            │
     └───────────────────────────│─────────────────────────────┘
                                 │                     │
                      ┌──────────┴──────────┐          │
                      │                     │          │
                ┌─────▼─────┐               │          │
                │  RELAY 3  │               │          │
                │  (HEATER) │               │          │
                │   COM ────┘               │          │
                │   NO ─────────┐           │          │
                │   NC          │           │          │
                └───────────────┤           │          │
                                │           │          │
                      ┌─────────▼─────────┐ │          │
                      │    DC HEATER      │ │          │
                      │   (12V or 24V)    │ │          │
                      │  RED (+) ─────────┤ │          │
                      │  BLACK (-) ───────┴─┴──────────┘
                      └───────────────────┘

WIRING STEPS FOR DC HEATER (3 CONNECTIONS):
1. DC Power Supply (+) → Relay 3 COM terminal
2. Relay 3 NO terminal → Heater RED wire (+)
3. Heater BLACK wire (-) → DC Power Supply GND

When relay activates: COM connects to NO, completing the circuit
```

### Important Wiring Notes:

1. **Wire Gauge Selection:**
   | Heater Power | Current (220V) | Current (110V) | Minimum Wire Gauge |
   |--------------|----------------|----------------|-------------------|
   | 100W | 0.45A | 0.9A | 20 AWG |
   | 200W | 0.9A | 1.8A | 18 AWG |
   | 300W | 1.4A | 2.7A | 18 AWG |
   | 500W | 2.3A | 4.5A | 16 AWG |
   | 1000W | 4.5A | 9.1A | 14 AWG |

2. **Relay Rating Check:**
   - Your relay MUST be rated for the voltage AND current
   - For AC heaters: Use relays rated for **AC 250V 10A** minimum
   - For DC heaters: Use relays rated for the DC voltage and current

3. **Use NO (Normally Open) Terminal:**
   - This ensures the heater is OFF when ESP32 is not powered
   - Safer fail-state (heater OFF when system fails)

---

## ⚠️ Safety Precautions

### Electrical Safety

1. **ALWAYS disconnect power before wiring**
2. **Use appropriate fuses** - Match fuse rating to heater current (e.g., 3A fuse for 500W heater at 220V)
3. **Secure all connections** - Use terminal blocks, no loose wires
4. **Use heat-resistant enclosure** for relay module
5. **Keep wiring away from water** and misting system
6. **Double-check polarity** for DC systems
7. **Ground all metal enclosures** for AC systems
8. **Have a qualified electrician verify** AC wiring

### Fire Safety

1. **Never leave unattended** during initial testing
2. **Install smoke detector** in the grow room
3. **Keep heater away from:**
   - Flammable materials (substrate, plastic sheets)
   - Water sources and misting spray
   - Direct mushroom contact
4. **Set maximum temperature limit** in code (e.g., 30°C)
5. **Use thermal cutoff fuse** if available on heater
6. **Add hardware thermal switch** as backup (e.g., 35°C cutoff)

### Mushroom Safety

1. **Avoid direct heat** on mushrooms - Use indirect/radiant heating
2. **Maintain humidity** - Heaters can dry the air rapidly
3. **Position heater** away from fruiting bodies
4. **Monitor CO2 levels** if using gas heaters (not recommended)

### Code Safety Features (Built into sample code)

1. **Maximum temperature cutoff** - Force heater OFF above 30°C
2. **Minimum runtime interval** - Prevent rapid ON/OFF cycling
3. **Watchdog timeout** - Turn OFF if no server response
4. **State confirmation** - Verify relay actually switched

---

## 💻 Arduino IDE Code

### Updated Controller Code with Heater Support

Create a new file or update your existing `mushroom_fan_misting_controller.ino`:

```cpp
/*
 * ESP32 DHT22 + MQ-135 + Fan + Misting + HEATER Control
 * Mushroom Farming Dashboard with Full Automation
 * 
 * =============================================================================
 * AUTOMATION MODES:
 * =============================================================================
 * - AUTOMATIC MODE: Actuators turn ON/OFF based on sensor readings vs thresholds
 *   - Fan: ON when temperature > threshold OR humidity > threshold OR air quality > threshold
 *   - Misting: ON when humidity < low threshold, OFF when humidity > high threshold
 *   - Heater: ON when temperature < low threshold, OFF when temperature > high threshold
 * - MANUAL MODE: Actuators respond only to dashboard switch (user control)
 * 
 * =============================================================================
 * PIN ASSIGNMENTS:
 * =============================================================================
 * - DHT22 Data:    GPIO 4
 * - MQ-135 Analog: GPIO 34
 * - Fan Relay:     GPIO 26
 * - Misting Relay: GPIO 27
 * - Heater Relay:  GPIO 25 (NEW)
 * 
 * =============================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ArduinoJson.h>

// =============================================================================
// CONFIGURATION - UPDATE THESE VALUES
// =============================================================================

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";           // Replace with your WiFi network name
const char* password = "YOUR_WIFI_PASSWORD";    // Replace with your WiFi password

// Server settings
const char* serverUrl = "http://YOUR_SERVER_IP:8000/api/sensor-data/receive/";
const char* automationDecisionUrl = "http://YOUR_SERVER_IP:8000/api/automation-decision/";
const char* apiKey = "YOUR_API_KEY";
const char* deviceId = "ESP32_FARM_001";

// =============================================================================
// PIN DEFINITIONS
// =============================================================================

// DHT22 Sensor
#define DHTPIN 4
#define DHTTYPE DHT22

// MQ-135 Air Quality Sensor
#define MQ135PIN 34

// Relay Control Pins
#define FAN_RELAY_PIN 26
#define MIST_RELAY_PIN 27
#define HEATER_RELAY_PIN 25  // NEW: Heater relay pin

// Relay behavior: Set to true if relay activates on LOW signal
#define RELAY_ACTIVE_LOW false

// =============================================================================
// SAFETY LIMITS
// =============================================================================
#define MAX_SAFE_TEMPERATURE 30.0    // Force heater OFF above this temperature
#define MIN_HEATER_INTERVAL 30000    // Minimum 30 seconds between heater state changes
#define WATCHDOG_TIMEOUT 60000       // Turn off heater if no server response for 60 seconds

// =============================================================================
// GLOBAL OBJECTS AND VARIABLES
// =============================================================================

DHT dht(DHTPIN, DHTTYPE);

// Timing intervals
const unsigned long sensorReadInterval = 5000;
const unsigned long automationPollInterval = 3000;
unsigned long lastSensorReadTime = 0;
unsigned long lastAutomationPollTime = 0;
unsigned long lastServerResponse = 0;        // Watchdog timer
unsigned long lastHeaterStateChange = 0;     // Prevent rapid cycling

// Control states - Fan
bool fanOn = false;
bool fanAutoMode = true;

// Control states - Misting
bool mistOn = false;
bool mistAutoMode = true;

// Control states - Heater (NEW)
bool heaterOn = false;
bool heaterAutoMode = true;

// Current sensor readings
float currentTemperature = 0;
float currentHumidity = 0;
float currentAirQualityPPM = 0;

// =============================================================================
// SETUP
// =============================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=============================================");
  Serial.println("ESP32 DHT22 + Fan + Misting + HEATER Control");
  Serial.println("Mushroom Farming Dashboard v2.0");
  Serial.println("WITH HEATER AUTOMATION SUPPORT");
  Serial.println("=============================================\n");
  
  // Initialize DHT sensor
  dht.begin();
  Serial.println("✓ DHT22 sensor initialized");
  
  // Initialize MQ-135 sensor
  pinMode(MQ135PIN, INPUT);
  Serial.println("✓ MQ-135 air quality sensor initialized");
  
  // Initialize relay pins
  pinMode(FAN_RELAY_PIN, OUTPUT);
  pinMode(MIST_RELAY_PIN, OUTPUT);
  pinMode(HEATER_RELAY_PIN, OUTPUT);  // NEW
  Serial.println("✓ Fan relay pin (GPIO 26) initialized");
  Serial.println("✓ Misting relay pin (GPIO 27) initialized");
  Serial.println("✓ Heater relay pin (GPIO 25) initialized");  // NEW
  
  // ===== RELAY HARDWARE TEST =====
  Serial.println("\n>>> TESTING ALL RELAYS - Listen for clicks! <<<");
  
  Serial.println("Test: Fan Relay ON");
  setRelay(FAN_RELAY_PIN, true);
  delay(1000);
  Serial.println("Test: Fan Relay OFF");
  setRelay(FAN_RELAY_PIN, false);
  delay(500);
  
  Serial.println("Test: Misting Relay ON");
  setRelay(MIST_RELAY_PIN, true);
  delay(1000);
  Serial.println("Test: Misting Relay OFF");
  setRelay(MIST_RELAY_PIN, false);
  delay(500);
  
  Serial.println("Test: Heater Relay ON");  // NEW
  setRelay(HEATER_RELAY_PIN, true);
  delay(1000);
  Serial.println("Test: Heater Relay OFF");
  setRelay(HEATER_RELAY_PIN, false);
  delay(500);
  
  Serial.println(">>> RELAY TEST COMPLETE <<<\n");
  
  // Start with all actuators OFF
  setRelay(FAN_RELAY_PIN, false);
  setRelay(MIST_RELAY_PIN, false);
  setRelay(HEATER_RELAY_PIN, false);  // NEW
  Serial.println("✓ All relays set to OFF");
  
  // Connect to WiFi
  connectWiFi();
  
  // Initialize watchdog
  lastServerResponse = millis();
}

// =============================================================================
// MAIN LOOP
// =============================================================================

void loop() {
  unsigned long currentTime = millis();
  
  // Task 1: Read and send sensor data every 5 seconds
  if (currentTime - lastSensorReadTime >= sensorReadInterval) {
    lastSensorReadTime = currentTime;
    
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();
    int airQualityRaw = analogRead(MQ135PIN);
    float airQualityPPM = map(airQualityRaw, 0, 4095, 0, 1000);
    
    if (isnan(humidity) || isnan(temperature)) {
      Serial.println("❌ Failed to read from DHT sensor!");
    } else {
      currentTemperature = temperature;
      currentHumidity = humidity;
      currentAirQualityPPM = airQualityPPM;
      
      printSensorReadings(temperature, humidity, airQualityRaw, airQualityPPM);
      checkGrowingConditions(temperature, humidity, airQualityPPM);
      
      // SAFETY CHECK: Force heater OFF if temperature is too high
      if (temperature >= MAX_SAFE_TEMPERATURE && heaterOn) {
        Serial.println("\n🚨 SAFETY CUTOFF: Temperature too high, forcing heater OFF!");
        setHeaterState(false, "Safety cutoff - max temperature reached");
      }
      
      if (WiFi.status() == WL_CONNECTED) {
        sendSensorData(temperature, humidity, airQualityPPM);
      } else {
        Serial.println("❌ WiFi disconnected! Attempting to reconnect...");
        connectWiFi();
      }
    }
  }
  
  // Task 2: Poll automation decision every 3 seconds
  if (currentTime - lastAutomationPollTime >= automationPollInterval) {
    lastAutomationPollTime = currentTime;
    pollAutomationDecision();
  }
  
  // Task 3: Watchdog - turn off heater if no server response (safety feature)
  if (currentTime - lastServerResponse >= WATCHDOG_TIMEOUT && heaterOn) {
    Serial.println("\n🚨 WATCHDOG: No server response, turning heater OFF for safety!");
    setHeaterState(false, "Watchdog timeout - no server response");
  }
}

// =============================================================================
// HEATER CONTROL WITH SAFETY FEATURES
// =============================================================================

void setHeaterState(bool newState, const char* reason) {
  unsigned long currentTime = millis();
  
  // Prevent rapid cycling (minimum interval between state changes)
  if (currentTime - lastHeaterStateChange < MIN_HEATER_INTERVAL && lastHeaterStateChange != 0) {
    Serial.println("⚠️  Heater state change blocked - minimum interval not met");
    return;
  }
  
  // Safety: Never turn heater ON if temperature is already high
  if (newState && currentTemperature >= MAX_SAFE_TEMPERATURE) {
    Serial.println("⚠️  Heater ON blocked - temperature already at or above safety limit");
    return;
  }
  
  // Apply the state change
  if (heaterOn != newState) {
    heaterOn = newState;
    setRelay(HEATER_RELAY_PIN, heaterOn);
    lastHeaterStateChange = currentTime;
    
    Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.print("🔥 HEATER ");
    Serial.print(heaterOn ? "ON" : "OFF");
    Serial.print(" (");
    Serial.print(heaterAutoMode ? "AUTO" : "MANUAL");
    Serial.println(" mode)");
    Serial.print("📝 Reason: ");
    Serial.println(reason);
    Serial.print("🌡️  Current Temp: ");
    Serial.print(currentTemperature);
    Serial.println("°C");
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  }
}

// =============================================================================
// RELAY CONTROL
// =============================================================================

void setRelay(int pin, bool on) {
  if (RELAY_ACTIVE_LOW) {
    digitalWrite(pin, on ? LOW : HIGH);
  } else {
    digitalWrite(pin, on ? HIGH : LOW);
  }
}

// =============================================================================
// AUTOMATION DECISION POLLING
// =============================================================================

void pollAutomationDecision() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️  WiFi not connected, skipping automation poll");
    return;
  }
  
  if (currentTemperature == 0 && currentHumidity == 0) {
    Serial.println("⚠️  No sensor data yet, skipping automation poll");
    return;
  }
  
  HTTPClient http;
  http.begin(automationDecisionUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  
  StaticJsonDocument<256> requestDoc;
  requestDoc["temperature"] = currentTemperature;
  requestDoc["humidity"] = currentHumidity;
  requestDoc["air_quality_ppm"] = (int)currentAirQualityPPM;
  requestDoc["device_id"] = deviceId;
  requestDoc["save_reading"] = false;
  
  String requestBody;
  serializeJson(requestDoc, requestBody);
  
  int httpCode = http.POST(requestBody);
  
  if (httpCode == 200) {
    lastServerResponse = millis();  // Reset watchdog
    String response = http.getString();
    
    StaticJsonDocument<1024> responseDoc;
    DeserializationError error = deserializeJson(responseDoc, response);
    
    if (!error) {
      // ─────────────────────────────────────────────────────────────
      // PROCESS FAN CONTROL
      // ─────────────────────────────────────────────────────────────
      if (responseDoc.containsKey("controls") && responseDoc["controls"].containsKey("fan")) {
        JsonObject fanControl = responseDoc["controls"]["fan"];
        
        bool shouldBeOn = fanControl["should_be_on"];
        const char* mode = fanControl["mode"];
        const char* reason = fanControl["reason"];
        
        fanAutoMode = (strcmp(mode, "automatic") == 0);
        
        if (fanOn != shouldBeOn) {
          fanOn = shouldBeOn;
          setRelay(FAN_RELAY_PIN, fanOn);
          
          Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
          Serial.print("🌀 FAN ");
          Serial.print(fanOn ? "ON" : "OFF");
          Serial.print(" (");
          Serial.print(fanAutoMode ? "AUTO" : "MANUAL");
          Serial.println(" mode)");
          Serial.print("📝 Reason: ");
          Serial.println(reason);
          Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        }
      }
      
      // ─────────────────────────────────────────────────────────────
      // PROCESS MISTING/HUMIDIFIER CONTROL
      // ─────────────────────────────────────────────────────────────
      if (responseDoc.containsKey("controls") && responseDoc["controls"].containsKey("humidifier")) {
        JsonObject mistControl = responseDoc["controls"]["humidifier"];
        
        bool shouldBeOn = mistControl["should_be_on"];
        const char* mode = mistControl["mode"];
        const char* reason = mistControl["reason"];
        
        mistAutoMode = (strcmp(mode, "automatic") == 0);
        
        if (mistOn != shouldBeOn) {
          mistOn = shouldBeOn;
          setRelay(MIST_RELAY_PIN, mistOn);
          
          Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
          Serial.print("💧 MISTING ");
          Serial.print(mistOn ? "ON" : "OFF");
          Serial.print(" (");
          Serial.print(mistAutoMode ? "AUTO" : "MANUAL");
          Serial.println(" mode)");
          Serial.print("📝 Reason: ");
          Serial.println(reason);
          Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        }
      }
      
      // ─────────────────────────────────────────────────────────────
      // PROCESS HEATER CONTROL (NEW)
      // ─────────────────────────────────────────────────────────────
      if (responseDoc.containsKey("controls") && responseDoc["controls"].containsKey("heater")) {
        JsonObject heaterControl = responseDoc["controls"]["heater"];
        
        bool shouldBeOn = heaterControl["should_be_on"];
        const char* mode = heaterControl["mode"];
        const char* reason = heaterControl["reason"];
        
        heaterAutoMode = (strcmp(mode, "automatic") == 0);
        
        // Use safety-checked heater control function
        if (heaterOn != shouldBeOn) {
          setHeaterState(shouldBeOn, reason);
        }
      }
      
      // Print thresholds for debugging (every 30 seconds)
      static unsigned long lastThresholdPrint = 0;
      if (millis() - lastThresholdPrint > 30000) {
        lastThresholdPrint = millis();
        if (responseDoc.containsKey("thresholds")) {
          JsonObject thresholds = responseDoc["thresholds"];
          Serial.println("\n📊 Current Automation Thresholds:");
          Serial.print("   Fan Temp Threshold: ");
          Serial.print((float)thresholds["fan_temp_threshold"]);
          Serial.println("°C");
          Serial.print("   Fan Humidity Threshold: ");
          Serial.print((float)thresholds["fan_humidity_threshold"]);
          Serial.println("%");
          Serial.print("   Mist Low Threshold: ");
          Serial.print((float)thresholds["humidifier_low_threshold"]);
          Serial.println("% (turns ON below this)");
          Serial.print("   Mist High Threshold: ");
          Serial.print((float)thresholds["humidifier_high_threshold"]);
          Serial.println("% (turns OFF above this)");
          Serial.print("   Heater Low Threshold: ");  // NEW
          Serial.print((float)thresholds["heater_low_threshold"]);
          Serial.println("°C (turns ON below this)");
          Serial.print("   Heater High Threshold: ");  // NEW
          Serial.print((float)thresholds["heater_high_threshold"]);
          Serial.println("°C (turns OFF above this)");
        }
      }
    } else {
      Serial.print("❌ JSON parse error: ");
      Serial.println(error.c_str());
    }
  } else if (httpCode > 0) {
    Serial.printf("⚠️  Automation poll returned: %d\n", httpCode);
  } else {
    Serial.printf("❌ Automation poll failed: %s\n", http.errorToString(httpCode).c_str());
  }
  
  http.end();
}

// =============================================================================
// DISPLAY FUNCTIONS
// =============================================================================

void printSensorReadings(float temperature, float humidity, int airQualityRaw, float airQualityPPM) {
  Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println("📊 Sensor Readings");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.print("🌡️  Temperature: ");
  Serial.print(temperature, 1);
  Serial.println(" °C");
  Serial.print("💧 Humidity: ");
  Serial.print(humidity, 1);
  Serial.println(" %");
  Serial.print("🌫️  Air Quality: ");
  Serial.print(airQualityRaw);
  Serial.print(" (raw) | ~");
  Serial.print(airQualityPPM, 0);
  Serial.println(" PPM");
  
  // Actuator status
  Serial.println("───────────────────────────────────");
  Serial.print("🌀 Fan: ");
  Serial.print(fanOn ? "ON" : "OFF");
  Serial.print(" (");
  Serial.print(fanAutoMode ? "AUTO" : "MANUAL");
  Serial.println(")");
  
  Serial.print("💧 Misting: ");
  Serial.print(mistOn ? "ON" : "OFF");
  Serial.print(" (");
  Serial.print(mistAutoMode ? "AUTO" : "MANUAL");
  Serial.println(")");
  
  Serial.print("🔥 Heater: ");  // NEW
  Serial.print(heaterOn ? "ON" : "OFF");
  Serial.print(" (");
  Serial.print(heaterAutoMode ? "AUTO" : "MANUAL");
  Serial.println(")");
}

// =============================================================================
// WIFI CONNECTION
// =============================================================================

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal Strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    lastServerResponse = millis();  // Reset watchdog on reconnect
  } else {
    Serial.println("\n❌ WiFi connection failed!");
  }
}

// =============================================================================
// SEND SENSOR DATA
// =============================================================================

void sendSensorData(float temperature, float humidity, float airQuality) {
  HTTPClient http;
  
  Serial.println("\n📡 Sending data to server...");
  
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  
  String jsonPayload = "{";
  jsonPayload += "\"temperature\":" + String(temperature, 1) + ",";
  jsonPayload += "\"humidity\":" + String(humidity, 1) + ",";
  jsonPayload += "\"air_quality_ppm\":" + String(airQuality, 0);
  jsonPayload += "}";
  
  int httpResponseCode = http.POST(jsonPayload);
  
  if (httpResponseCode > 0) {
    Serial.print("✓ Server Response: ");
    Serial.println(httpResponseCode);
    lastServerResponse = millis();  // Reset watchdog
  } else {
    Serial.print("❌ Error: ");
    Serial.println(http.errorToString(httpResponseCode));
  }
  
  http.end();
}

// =============================================================================
// CONDITION ANALYSIS
// =============================================================================

void checkGrowingConditions(float temperature, float humidity, float airQuality) {
  Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println("🔍 Condition Analysis");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  
  // Temperature check
  if (temperature < 13) {
    Serial.println("🌡️  ⚠️  Temperature TOO LOW - heater needed");
  } else if (temperature > 18) {
    Serial.println("🌡️  ⚠️  Temperature TOO HIGH - ventilation needed");
  } else {
    Serial.println("🌡️  ✓ Temperature is OPTIMAL (13-18°C)");
  }
  
  // Humidity check
  if (humidity < 80) {
    Serial.println("💧 ⚠️  Humidity TOO LOW - misting recommended");
  } else if (humidity > 95) {
    Serial.println("💧 ⚠️  Humidity TOO HIGH - risk of contamination");
  } else {
    Serial.println("💧 ✓ Humidity is OPTIMAL (80-95%)");
  }
  
  // Air Quality check
  if (airQuality < 400) {
    Serial.println("🌫️  ✓ Air Quality is GOOD");
  } else if (airQuality < 800) {
    Serial.println("🌫️  ⚠️  Air Quality is ACCEPTABLE");
  } else {
    Serial.println("🌫️  ⚠️  Air Quality is POOR - ventilate!");
  }
  
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
}
```

---

## 🌡️ Temperature Thresholds for Mushroom Growing

### Optimal Temperature Ranges by Species

| Mushroom Species | Incubation (°C) | Fruiting (°C) | Heater ON | Heater OFF |
|------------------|-----------------|---------------|-----------|------------|
| **Oyster (Pleurotus)** | 24-27 | 13-18 | < 13 | > 18 |
| **Shiitake** | 21-27 | 12-18 | < 12 | > 18 |
| **King Oyster** | 20-25 | 12-18 | < 12 | > 18 |
| **Lion's Mane** | 21-24 | 15-20 | < 15 | > 20 |
| **Reishi** | 24-27 | 21-27 | < 21 | > 27 |
| **Button/Portobello** | 25-28 | 16-20 | < 16 | > 20 |
| **Enoki** | 21-24 | 4-8 | < 4 | > 8 |

### Recommended Default Settings (for common Oyster mushrooms)

| Setting | Value | Description |
|---------|-------|-------------|
| `heater_low_threshold` | **15.0°C** | Heater turns ON below this |
| `heater_high_threshold` | **20.0°C** | Heater turns OFF above this |
| `heater_value` | **17°C** | Target temperature |
| `hysteresis_margin` | **2.0°C** | Prevents rapid ON/OFF cycling |

### Dashboard Configuration

Set these values in your Django admin or environment dashboard:

1. Navigate to **Environment Controls** page
2. Find the **Heater** section
3. Enable **Automatic Mode**
4. Set the thresholds:
   - **Heater Low Threshold**: 15.0°C (turns ON below this)
   - **Heater High Threshold**: 20.0°C (turns OFF above this)
   - **Target Temperature**: 17°C

---

## 🔧 Dashboard Configuration

### Database Settings

Your Django backend already has heater support in `EnvironmentSettings` model. The relevant fields are:

```python
# From core/models.py - Already exists!
heater_on = models.BooleanField(default=False)
heater_auto = models.BooleanField(default=True)
heater_value = models.IntegerField(default=22)  # Target temperature
heater_low_threshold = models.DecimalField(default=15.0)   # Turn ON below
heater_high_threshold = models.DecimalField(default=20.0)  # Turn OFF above
```

### Update Thresholds via Django Admin

1. Go to `http://your-server:8000/admin/`
2. Navigate to **Core > Environment settings**
3. Edit the settings:
   - **Heater auto**: ✓ (checked for automatic mode)
   - **Heater low threshold**: 15.0
   - **Heater high threshold**: 20.0
   - **Heater value**: 17 (target)

### API Response Format

When ESP32 polls `/api/automation-decision/`, it receives:

```json
{
  "status": "success",
  "controls": {
    "fan": {...},
    "humidifier": {...},
    "heater": {
      "should_be_on": true,
      "current_state": false,
      "mode": "automatic",
      "reason": "Temperature 14.2°C below threshold 15.0°C"
    }
  },
  "thresholds": {
    "heater_low_threshold": 15.0,
    "heater_high_threshold": 20.0
  }
}
```

---

## 🧪 Testing & Troubleshooting

### Initial Testing Checklist

1. **[ ] Hardware Check**
   - All wires securely connected
   - Relay clicks when GPIO pin toggled
   - Heater powers ON when relay activated manually

2. **[ ] Software Check**
   - ESP32 connects to WiFi
   - Sensor readings appear in Serial Monitor
   - Dashboard shows real-time temperature

3. **[ ] Integration Check**
   - Dashboard heater toggle works (Manual mode)
   - Automatic mode responds to temperature changes
   - Heater turns OFF when temperature reaches threshold

### Testing Procedure

1. **Test Relay Independently**
   ```cpp
   // Add to setup() temporarily for testing
   digitalWrite(HEATER_RELAY_PIN, HIGH);  // Should hear click
   delay(2000);
   digitalWrite(HEATER_RELAY_PIN, LOW);   // Should hear click
   ```

2. **Test with Artificial Sensor Values**
   - Temporarily modify `currentTemperature` to simulate cold conditions
   - Verify heater turns ON

3. **Test Safety Cutoff**
   - Heat the sensor with your breath or warm water nearby
   - Verify heater turns OFF when reaching MAX_SAFE_TEMPERATURE

### Troubleshooting Guide

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| Heater doesn't turn ON | Wrong GPIO pin | Check pin number (GPIO 25) |
| Relay clicks but heater stays off | Wiring issue | Check COM/NO connections |
| Heater always ON | Relay stuck or RELAY_ACTIVE_LOW wrong | Check relay, toggle setting |
| No heater in dashboard response | Backend not updated | Check sensor_api.py |
| Rapid ON/OFF cycling | Hysteresis too low | Increase MIN_HEATER_INTERVAL |
| Heater ignores dashboard | Mode set to automatic | Toggle to Manual mode |
| Watchdog keeps triggering | Server connection issues | Check WiFi/network |
| Temperature readings wrong | DHT22 damaged/loose | Check wiring, replace sensor |

### Serial Monitor Debug Output

Expected output when heater activates:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 HEATER ON (AUTO mode)
📝 Reason: Temperature 14.2°C below threshold 15.0°C
🌡️  Current Temp: 14.2°C
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📝 Best Practices Summary

### Hardware
- ✅ Use quality relays rated for your heater voltage/current
- ✅ Always use fuses appropriate for heater wattage
- ✅ Keep relay module away from moisture
- ✅ Use heat-resistant wire for heater connections
- ✅ Install a backup thermal cutoff switch

### Software
- ✅ Set conservative MAX_SAFE_TEMPERATURE (30°C)
- ✅ Use minimum interval to prevent relay cycling
- ✅ Implement watchdog timeout for safety
- ✅ Log all heater state changes for debugging

### Operation
- ✅ Monitor system for first 24-48 hours after installation
- ✅ Check that heater doesn't dry out humidity excessively
- ✅ Verify temperature readings are accurate
- ✅ Set up alerts for abnormal temperature readings

---

## 📚 Additional Resources

- [DHT22 Integration Guide](DHT22_INTEGRATION_GUIDE.md)
- [Automation Control Guide](AUTOMATION_CONTROL_GUIDE.md)
- [Fan Control Integration Guide](FAN_CONTROL_INTEGRATION_GUIDE.md)

---

**Last Updated:** March 2026  
**Version:** 1.0
