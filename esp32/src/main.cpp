// 2-motor + 2-encoder UDP-controlled platform
#include <Arduino.h>
#include <WiFi.h>
#include <AsyncUDP.h>
#include <ArduinoJson.h>
#include <ESP32Encoder.h>
#include <ESPmDNS.h>
#include "config.h"

// PWM config
static constexpr uint8_t PWM_CH[2] = {0,1};

// Globals
AsyncUDP udp;
IPAddress lastCtlIp;
uint16_t lastCtlPort = 0;

ESP32Encoder enc[2];
volatile int64_t encZero[2] = {0,0};
int motorPct[2] = {0,0};

// Helpers
inline int clampPct(int v){ return v < -100 ? -100 : (v > 100 ? 100 : v); }
inline uint32_t pctToDuty(int pct){ pct = abs(clampPct(pct)); return (uint32_t)(pct * ((1<<PWM_RES_BITS)-1) / 100); }

void motorsSetup(){
  pinMode(PIN_STBY, OUTPUT); digitalWrite(PIN_STBY, HIGH);
  const int pwmPins[2] = { M1_PWM, M2_PWM };
  const int in1Pins[2] = { M1_IN1, M2_IN1 };
  const int in2Pins[2] = { M1_IN2, M2_IN2 };
  for(int i=0;i<2;i++){
    pinMode(in1Pins[i], OUTPUT);
    pinMode(in2Pins[i], OUTPUT);
    ledcSetup(PWM_CH[i], PWM_FREQ, PWM_RES_BITS);
    ledcAttachPin(pwmPins[i], PWM_CH[i]);
    ledcWrite(PWM_CH[i], 0);
  }
}

void setMotor(int i, int pct){
  i = constrain(i,0,1);
  motorPct[i] = clampPct(pct);
  const int in1Pins[2] = { M1_IN1, M2_IN1 };
  const int in2Pins[2] = { M1_IN2, M2_IN2 };
  if(motorPct[i] > 0){ digitalWrite(in1Pins[i], HIGH); digitalWrite(in2Pins[i], LOW); }
  else if(motorPct[i] < 0){ digitalWrite(in1Pins[i], LOW); digitalWrite(in2Pins[i], HIGH); }
  else { digitalWrite(in1Pins[i], LOW); digitalWrite(in2Pins[i], LOW); }
  ledcWrite(PWM_CH[i], pctToDuty(motorPct[i]));
}

void setPairLR(int leftPct, int rightPct){
  // Convention: m1 = left, m2 = right
  setMotor(0, leftPct);
  setMotor(1, rightPct);
}

void encodersSetup(){
  // Prefer internal pullups for non input-only pins
  pinMode(ENC1_A, INPUT);
  pinMode(ENC1_B, INPUT);
  pinMode(ENC2_A, INPUT);
  pinMode(ENC2_B, INPUT);

  enc[0].attachFullQuad(ENC1_A, ENC1_B);
  enc[1].attachFullQuad(ENC2_A, ENC2_B);
  for(int i=0;i<2;i++) encZero[i] = enc[i].getCount();
}

inline int32_t getCount(int i){ return (int32_t)(enc[i].getCount() - encZero[i]); }

void sendEncoders(){
  if(!lastCtlIp) return;
  StaticJsonDocument<256> doc;
  doc["type"] = "encoders";
  JsonObject counts = doc.createNestedObject("counts");
  counts["m1"] = getCount(0);  // Left motor
  counts["m2"] = getCount(1);  // Right motor
  counts["m3"] = getCount(0);  // Same as m1 for compatibility
  counts["m4"] = getCount(1);  // Same as m2 for compatibility
  char buf[256];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  udp.writeTo((uint8_t*)buf, n, lastCtlIp, TELEM_PORT);
}

void sendAliveMessage(){
  // Send alive message directly to PC
  StaticJsonDocument<128> doc;
  doc["type"] = "alive";
  doc["device"] = "ESP32_Robot";
  doc["ip"] = WiFi.localIP().toString();
  doc["ts"] = millis();
  char buf[128];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  
  Serial.printf("Sending alive message: %s\n", buf);
  
  // Send to broadcast address first
  IPAddress broadcast = WiFi.localIP();
  broadcast[3] = 255; // Make it x.x.x.255 for broadcast
  udp.writeTo((uint8_t*)buf, n, broadcast, TELEM_PORT);
  Serial.printf("Sent to broadcast %s:%d\n", broadcast.toString().c_str(), TELEM_PORT);
  
  // Try to resolve and send directly to PC hostname
  IPAddress pcIP;
  if(WiFi.hostByName(PC_HOSTNAME, pcIP)) {
    udp.writeTo((uint8_t*)buf, n, pcIP, TELEM_PORT);
    Serial.printf("Sent directly to PC %s (%s):%d\n", PC_HOSTNAME, pcIP.toString().c_str(), TELEM_PORT);
  } else {
    Serial.printf("Could not resolve %s\n", PC_HOSTNAME);
  }
  
  // Also send to lastCtlIp if we have one
  if(lastCtlIp) {
    udp.writeTo((uint8_t*)buf, n, lastCtlIp, TELEM_PORT);
    Serial.printf("Sent to known controller %s:%d\n", lastCtlIp.toString().c_str(), TELEM_PORT);
  }
}

void handlePacket(AsyncUDPPacket &p){
  lastCtlIp = p.remoteIP();
  lastCtlPort = p.remotePort();
  StaticJsonDocument<512> doc;
  if(deserializeJson(doc, p.data(), p.length())) return;
  const char* type = doc["type"] | "";
  if(!strcmp(type, "motor2")){
    setMotor(0, (int)doc["m1"] | 0);
    setMotor(1, (int)doc["m2"] | 0);
  } else if(!strcmp(type, "motor4")){
    // Support legacy 4-motor commands by mapping to 2 motors
    // Map m1+m3 -> left (m1), m2+m4 -> right (m2)
    int m1 = (int)doc["m1"] | 0;
    int m2 = (int)doc["m2"] | 0;
    int m3 = (int)doc["m3"] | 0;
    int m4 = (int)doc["m4"] | 0;
    int left_avg = (m1 + m3) / 2;
    int right_avg = (m2 + m4) / 2;
    setMotor(0, left_avg);
    setMotor(1, right_avg);
  } else if(!strcmp(type, "motor")){
    int l = doc["left"] | 0; int r = doc["right"] | 0; setPairLR(l, r);
  } else if(!strcmp(type, "move_ticks")){
    // convenience: use left on m1, right on m2; zero and run until targets reached
    int32_t lT = doc["left_ticks"] | 0, rT = doc["right_ticks"] | 0;
    int lS = doc["left_speed"] | 50, rS = doc["right_speed"] | 50;
    int32_t sL = getCount(0); int32_t sR = getCount(1);
    setPairLR(lS, rS);
    uint32_t t0 = millis();
    while(millis() - t0 < 10000){
      int32_t dL = getCount(0) - sL;
      int32_t dR = getCount(1) - sR;
      if(abs(dL) >= abs(lT) && abs(dR) >= abs(rT)) break;
      delay(1);
    }
    setPairLR(0,0);
  }
  // ack
  StaticJsonDocument<128> ack; ack["type"] = "ack"; ack["seq"] = doc["seq"] | 0; ack["ts"] = millis();
  char buf[128]; size_t n = serializeJson(ack, buf, sizeof(buf));
  udp.writeTo((uint8_t*)buf, n, p.remoteIP(), p.remotePort());
}

void setup(){
  Serial.begin(115200);
  delay(1000);
  Serial.println("ESP32 Robot Starting...");
  
  WiFi.mode(WIFI_STA);
  
  // Configure static IP if enabled
  #ifdef STATIC_IP_ENABLE
  if(STATIC_IP_ENABLE) {
    if(!WiFi.config(STATIC_IP, GATEWAY_IP, SUBNET_MASK, DNS_PRIMARY, DNS_SECONDARY)) {
      Serial.println("Failed to configure static IP");
    } else {
      Serial.println("Static IP configured");
    }
  }
  #endif
  
  Serial.printf("Connecting to WiFi: %s\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  int attempts = 0;
  while(WiFi.status() != WL_CONNECTED && attempts < 60) { // 30 second timeout
    Serial.print(".");
    delay(500);
    attempts++;
    
    // Print status every 10 attempts
    if(attempts % 10 == 0) {
      Serial.printf("\nWiFi Status: %d (attempt %d/60)\n", WiFi.status(), attempts);
      if(attempts == 20) {
        Serial.println("Still trying... Check if hotspot is running and credentials are correct");
      }
    }
  }
  
  if(WiFi.status() != WL_CONNECTED) {
    Serial.println("\nFailed to connect to WiFi!");
    Serial.printf("WiFi SSID: %s\n", WIFI_SSID);
    Serial.println("Please check:");
    Serial.println("1. Hotspot is running");  
    Serial.println("2. SSID and password are correct");
    Serial.println("3. ESP32 is in range");
    Serial.println("Restarting in 5 seconds...");
    delay(5000);
    ESP.restart();
  }
  
  Serial.println();
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());
  Serial.print("Gateway: ");
  Serial.println(WiFi.gatewayIP());
  Serial.print("Subnet: ");
  Serial.println(WiFi.subnetMask());
  Serial.print("RSSI: ");
  Serial.println(WiFi.RSSI());
  
  // Test PC hostname resolution
  Serial.printf("Testing connection to PC: %s\n", PC_HOSTNAME);
  IPAddress pcIP;
  if(WiFi.hostByName(PC_HOSTNAME, pcIP)) {
    Serial.printf("✅ Successfully resolved %s to %s\n", PC_HOSTNAME, pcIP.toString().c_str());
  } else {
    Serial.printf("❌ Could not resolve %s\n", PC_HOSTNAME);
    Serial.println("Make sure your PC is on the same network and mDNS is working");
  }
  
  // Initialize mDNS
  if (!MDNS.begin(MDNS_HOSTNAME)) {
    Serial.println("Error setting up mDNS responder!");
  } else {
    Serial.printf("mDNS responder started: %s.local\n", MDNS_HOSTNAME);
    // Add service to MDNS-SD
    MDNS.addService("esp32-robot", "udp", CTRL_PORT);
  }
  
  motorsSetup();
  encodersSetup();
  if(udp.listen(CTRL_PORT)){
    Serial.printf("Control UDP :%d\n", CTRL_PORT);
    udp.onPacket(handlePacket);
  }
  
  // Send initial "I'm alive!" message
  delay(1000); // Wait a second for everything to settle
  sendAliveMessage();
  Serial.println("Sent initial alive message");
}

uint32_t lastTelem=0;
uint32_t lastAlive=0;
void loop(){
  if(millis() - lastTelem >= ENCODER_TELEM_INTERVAL_MS){ lastTelem = millis(); sendEncoders(); }
  
  // Send alive message every 10 seconds
  if(millis() - lastAlive >= 10000){ 
    lastAlive = millis(); 
    sendAliveMessage();
    Serial.println("Sent alive message"); 
  }
}
