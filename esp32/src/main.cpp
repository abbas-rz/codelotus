// 4-motor + 4-encoder UDP-controlled platform
#include <Arduino.h>
#include <WiFi.h>
#include <AsyncUDP.h>
#include <ArduinoJson.h>
#include <ESP32Encoder.h>
#include "config.h"

static constexpr uint16_t CTRL_PORT = 9000;
static constexpr uint16_t TELEM_PORT = 9001;

// PWM config
static constexpr uint8_t PWM_CH[4] = {0,1,2,3};

// Globals
AsyncUDP udp;
IPAddress lastCtlIp;
uint16_t lastCtlPort = 0;

ESP32Encoder enc[4];
volatile int64_t encZero[4] = {0,0,0,0};
int motorPct[4] = {0,0,0,0};

// Helpers
inline int clampPct(int v){ return v < -100 ? -100 : (v > 100 ? 100 : v); }
inline uint32_t pctToDuty(int pct){ pct = abs(clampPct(pct)); return (uint32_t)(pct * ((1<<PWM_RES_BITS)-1) / 100); }

void motorsSetup(){
  pinMode(PIN_STBY, OUTPUT); digitalWrite(PIN_STBY, HIGH);
  const int pwmPins[4] = { M1_PWM, M2_PWM, M3_PWM, M4_PWM };
  const int in1Pins[4] = { M1_IN1, M2_IN1, M3_IN1, M4_IN1 };
  const int in2Pins[4] = { M1_IN2, M2_IN2, M3_IN2, M4_IN2 };
  for(int i=0;i<4;i++){
    pinMode(in1Pins[i], OUTPUT);
    pinMode(in2Pins[i], OUTPUT);
    ledcSetup(PWM_CH[i], PWM_FREQ, PWM_RES_BITS);
    ledcAttachPin(pwmPins[i], PWM_CH[i]);
    ledcWrite(PWM_CH[i], 0);
  }
}

void setMotor(int i, int pct){
  i = constrain(i,0,3);
  motorPct[i] = clampPct(pct);
  const int in1Pins[4] = { M1_IN1, M2_IN1, M3_IN1, M4_IN1 };
  const int in2Pins[4] = { M1_IN2, M2_IN2, M3_IN2, M4_IN2 };
  if(motorPct[i] > 0){ digitalWrite(in1Pins[i], HIGH); digitalWrite(in2Pins[i], LOW); }
  else if(motorPct[i] < 0){ digitalWrite(in1Pins[i], LOW); digitalWrite(in2Pins[i], HIGH); }
  else { digitalWrite(in1Pins[i], LOW); digitalWrite(in2Pins[i], LOW); }
  ledcWrite(PWM_CH[i], pctToDuty(motorPct[i]));
}

void setPairLR(int leftPct, int rightPct){
  // Convention: m1+m3 = left, m2+m4 = right
  setMotor(0, leftPct);
  setMotor(2, leftPct);
  setMotor(1, rightPct);
  setMotor(3, rightPct);
}

void encodersSetup(){
  // Prefer internal pullups for non input-only pins
  pinMode(ENC1_A, INPUT);
  pinMode(ENC1_B, INPUT);
  pinMode(ENC2_A, INPUT);
  pinMode(ENC2_B, INPUT);
  pinMode(ENC3_A, INPUT_PULLUP);
  pinMode(ENC3_B, INPUT_PULLUP);
  pinMode(ENC4_A, INPUT_PULLUP);
  pinMode(ENC4_B, INPUT_PULLUP);

  enc[0].attachFullQuad(ENC1_A, ENC1_B);
  enc[1].attachFullQuad(ENC2_A, ENC2_B);
  enc[2].attachFullQuad(ENC3_A, ENC3_B);
  enc[3].attachFullQuad(ENC4_A, ENC4_B);
  for(int i=0;i<4;i++) encZero[i] = enc[i].getCount();
}

inline int32_t getCount(int i){ return (int32_t)(enc[i].getCount() - encZero[i]); }

void sendEncoders(){
  if(!lastCtlIp) return;
  StaticJsonDocument<256> doc;
  doc["type"] = "encoders";
  JsonObject counts = doc.createNestedObject("counts");
  counts["m1"] = getCount(0);
  counts["m2"] = getCount(1);
  counts["m3"] = getCount(2);
  counts["m4"] = getCount(3);
  char buf[256];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  udp.writeTo((uint8_t*)buf, n, lastCtlIp, TELEM_PORT);
}

void handlePacket(AsyncUDPPacket &p){
  lastCtlIp = p.remoteIP();
  lastCtlPort = p.remotePort();
  StaticJsonDocument<512> doc;
  if(deserializeJson(doc, p.data(), p.length())) return;
  const char* type = doc["type"] | "";
  if(!strcmp(type, "motor4")){
    setMotor(0, (int)doc["m1"] | 0);
    setMotor(1, (int)doc["m2"] | 0);
    setMotor(2, (int)doc["m3"] | 0);
    setMotor(3, (int)doc["m4"] | 0);
  } else if(!strcmp(type, "motor")){
    int l = doc["left"] | 0; int r = doc["right"] | 0; setPairLR(l, r);
  } else if(!strcmp(type, "move_ticks")){
    // convenience: use left on m1+m3, right on m2+m4; zero and run until targets reached
    int32_t lT = doc["left_ticks"] | 0, rT = doc["right_ticks"] | 0;
    int lS = doc["left_speed"] | 50, rS = doc["right_speed"] | 50;
    int32_t sL = (getCount(0)+getCount(2))/2; int32_t sR = (getCount(1)+getCount(3))/2;
    setPairLR(lS, rS);
    uint32_t t0 = millis();
    while(millis() - t0 < 10000){
      int32_t dL = ((getCount(0)+getCount(2))/2) - sL;
      int32_t dR = ((getCount(1)+getCount(3))/2) - sR;
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
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting"); while(WiFi.status()!=WL_CONNECTED){ Serial.print("."); delay(500);} Serial.println();
  Serial.println(WiFi.localIP());
  motorsSetup();
  encodersSetup();
  if(udp.listen(CTRL_PORT)){
    Serial.printf("Control UDP :%d\n", CTRL_PORT);
    udp.onPacket(handlePacket);
  }
}

uint32_t lastTelem=0;
void loop(){
  if(millis() - lastTelem >= ENCODER_TELEM_INTERVAL_MS){ lastTelem = millis(); sendEncoders(); }
}
