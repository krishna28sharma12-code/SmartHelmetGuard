/*
 * Smart Helmet Guard - NodeMCU ESP8266 Firmware
 * File: firmware/nodemcu_servo.ino
 * 
 * Hardware:
 * - NodeMCU v3 / v1.0 (ESP8266 / ESP-12E)
 * - SG90 Micro Servo (Simulates Vehicle Starter Relay)
 * - 5V Power Bank (External supply for Servo)
 * 
 * Safety Boundary:
 * The servo is only an exhibition prototype simulating a starter relay.
 * NEVER connect this system to any real vehicle ignition, engine, or fuel system.
 * 
 * Wiring Diagram:
 * ┌──────────────────┐               ┌────────────────────────┐
 * │  NodeMCU ESP8266 │               │  SG90 Micro Servo      │
 * │                  │               │                        │
 * │  Pin D4 (GPIO 2) ├───────────────┤  Orange / Yellow (PWM) │
 * │  GND (Ground)    ├───┬───────────┤  Brown / Black (GND)   │
 * └──────────────────┘   │           └────────────────────────┘
 *                        │
 * ┌──────────────────┐   │
 * │ 5V Power Bank    │   │
 * │  5V (VCC)        ├───┼───────────► Red (VCC) [Servo Power]
 * │  GND (Ground)    └───┴───────────► Common Ground
 * └──────────────────┘
 * 
 * CRITICAL HARDWARE NOTE:
 * Never power the servo directly from a NodeMCU GPIO pin or 3.3V rail.
 * Servos draw high current spikes that will cause board resets and brownouts.
 * Always share a common ground between the NodeMCU and the external power bank.
 * 
 * Features:
 * 1. Self-test sweep on power-on (0° -> 90° -> 0°).
 * 2. Route 1 (Primary): Local HTTP server on port 80 (/servo?angle=90&key=SECRET).
 *    Includes CORS headers (Access-Control-Allow-Origin: *) for browser calls.
 * 3. Route 2 (Backup): Background polling from cloud backend (/api/command/poll?key=SECRET).
 * 4. LED indicators: Blinks during Wi-Fi connection, solid when connected.
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h>
#include <Servo.h>

// ==========================================
// 1. NETWORK & AUTH CONFIGURATION
// ==========================================
// Set your phone hotspot credentials (Hotspot MUST be 2.4 GHz)
const char* WIFI_SSID     = "Your_Phone_Hotspot";      // Replace with your Hotspot Name
const char* WIFI_PASSWORD = "your_hotspot_password";  // Replace with your Hotspot Password

// Shared secret key matching backend .env NODEMCU_SECRET
const char* SHARED_SECRET = "smart_guard_secret_123";

// Route 2: Backend Cloud Relay URL (Optional / Backup)
// Example: "http://192.168.43.1:8000/api/command/poll?key=smart_guard_secret_123"
const char* BACKEND_POLL_URL = "http://192.168.43.1:8000/api/command/poll?key=smart_guard_secret_123";
const bool ENABLE_ROUTE_2_POLL = false; // Set to true if using Route 2 Cloud Relay

// ==========================================
// 2. HARDWARE PINS & CONSTANTS
// ==========================================
const int SERVO_PIN = D4;       // GPIO2 on ESP-12E (NodeMCU D4)
const int LED_PIN   = LED_BUILTIN; // Active LOW on NodeMCU

Servo starterServo;
ESP8266WebServer server(80);

int currentAngle = 0;           // 0° = START BLOCKED, 90° = START AUTHORIZED
unsigned long lastPollTime = 0;
const unsigned long POLL_INTERVAL_MS = 1500; // Poll cloud every 1.5 seconds

// ==========================================
// 3. SERVO CONTROLLER FUNCTION
// ==========================================
void setServoAngle(int angle) {
  if (angle != 0 && angle != 90) {
    Serial.printf("[SERVO WARNING] Invalid angle requested: %d. Clamping to 0 or 90.\n", angle);
    if (angle > 45) angle = 90;
    else angle = 0;
  }

  currentAngle = angle;
  starterServo.write(angle);
  
  Serial.println("----------------------------------------");
  if (angle == 90) {
    Serial.println("[STATE] START AUTHORIZED (Servo at 90°)");
  } else {
    Serial.println("[STATE] START BLOCKED (Servo at 0°)");
  }
  Serial.printf("[HARDWARE] Servo Position: %d°\n", currentAngle);
  Serial.println("----------------------------------------");
}

// ==========================================
// 4. ROUTE 1 HTTP HANDLERS (Direct Local Server)
// ==========================================
void sendCORSHeaders() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type, X-Requested-With");
}

void handleOptions() {
  sendCORSHeaders();
  server.send(204);
}

void handleRoot() {
  sendCORSHeaders();
  String html = "<!DOCTYPE html><html><head><title>NodeMCU Servo Guard</title></head>";
  html += "<body style='font-family:sans-serif; text-align:center; padding:20px;'>";
  html += "<h2>NodeMCU Smart Helmet Guard - Servo Controller</h2>";
  html += "<p>Status: <strong>CONNECTED</strong></p>";
  html += "<p>Current Servo Position: <strong>" + String(currentAngle) + "&deg;</strong> (" + (currentAngle == 90 ? "AUTHORIZED" : "BLOCKED") + ")</p>";
  html += "<hr>";
  html += "<p><em>Use the phone camera app to send servo commands.</em></p>";
  html += "<p><small>Route 1 endpoint: <code>/servo?angle=90&amp;key=&lt;secret&gt;</code></small></p>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleServoCommand() {
  sendCORSHeaders();

  // Validate Secret Key
  if (!server.hasArg("key") || server.arg("key") != SHARED_SECRET) {
    Serial.println("[AUTH ERROR] Unauthorized request! Secret key mismatch or missing.");
    server.send(401, "application/json", "{\"error\": \"Unauthorized: Invalid or missing secret key\"}");
    return;
  }

  // Validate Angle Parameter
  if (!server.hasArg("angle")) {
    server.send(400, "application/json", "{\"error\": \"Missing required 'angle' parameter (0 or 90)\"}");
    return;
  }

  int targetAngle = server.arg("angle").toInt();
  if (targetAngle != 0 && targetAngle != 90) {
    server.send(400, "application/json", "{\"error\": \"Invalid angle. Must be 0 (blocked) or 90 (authorized)\"}");
    return;
  }

  setServoAngle(targetAngle);

  String response = "{\"status\":\"ok\",\"angle\":" + String(targetAngle) + ",\"state\":\"" + (targetAngle == 90 ? "AUTHORIZED" : "BLOCKED") + "\"}";
  server.send(200, "application/json", response);
}

void handleStatus() {
  sendCORSHeaders();
  String response = "{\"status\":\"online\",\"angle\":" + String(currentAngle) + ",\"ip\":\"" + WiFi.localIP().toString() + "\"}";
  server.send(200, "application/json", response);
}

// ==========================================
// 5. ROUTE 2 POLLING (Cloud Relay Backup)
// ==========================================
void pollRoute2Command() {
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;

  if (http.begin(client, BACKEND_POLL_URL)) {
    http.setTimeout(1200);
    int httpCode = http.GET();

    if (httpCode == HTTP_CODE_OK) {
      String payload = http.getString();
      // Simple parser for {"angle": 90, ...} or {"angle": 0, ...}
      int angleIdx = payload.indexOf("\"angle\":");
      if (angleIdx != -1) {
        int parsedAngle = payload.substring(angleIdx + 8, angleIdx + 11).toInt();
        if ((parsedAngle == 0 || parsedAngle == 90) && parsedAngle != currentAngle) {
          Serial.printf("[ROUTE 2] Cloud relay command received: %d°\n", parsedAngle);
          setServoAngle(parsedAngle);
        }
      }
    }
    http.end();
  }
}

// ==========================================
// 6. SETUP & POWER-ON SELF TEST
// ==========================================
void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH); // LED OFF initially

  Serial.println("\n\n========================================");
  Serial.println("  Smart Helmet Guard - NodeMCU Firmware ");
  Serial.println("========================================");

  // Attach Servo to pin
  starterServo.attach(SERVO_PIN);
  
  // Power-on self test sweep
  Serial.println("[TEST] Running power-on servo sweep test...");
  setServoAngle(0);
  delay(600);
  setServoAngle(90);
  delay(600);
  setServoAngle(0);
  Serial.println("[TEST] Servo sweep test complete. Starter initialized to BLOCKED (0°).");

  // Connect to Wi-Fi Hotspot
  Serial.print("[WIFI] Connecting to hotspot: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(400);
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Blink LED
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, LOW); // LED ON (Active Low) = Connected!
    Serial.println("\n[WIFI SUCCESS] Connected to hotspot!");
    Serial.print("[WIFI] NodeMCU IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.println("-> Enter this IP into the phone app under 'NodeMCU Local IP'!");
  } else {
    Serial.println("\n[WIFI WARNING] Could not connect to hotspot. Check SSID, password, and ensure hotspot is 2.4 GHz.");
  }

  // Setup Web Server Routes
  server.on("/", HTTP_GET, handleRoot);
  server.on("/servo", HTTP_GET, handleServoCommand);
  server.on("/servo", HTTP_OPTIONS, handleOptions);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/status", HTTP_OPTIONS, handleOptions);

  server.begin();
  Serial.println("[SERVER] Route 1 HTTP server started on port 80.");
  Serial.println("[READY] System ready for commands from phone app.\n");
}

// ==========================================
// 7. MAIN LOOP
// ==========================================
void loop() {
  // Handle incoming Route 1 HTTP requests from phone
  server.handleClient();

  // Route 2 polling (if enabled)
  if (ENABLE_ROUTE_2_POLL) {
    unsigned long now = millis();
    if (now - lastPollTime >= POLL_INTERVAL_MS) {
      lastPollTime = now;
      pollRoute2Command();
    }
  }
}
