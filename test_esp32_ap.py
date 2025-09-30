#!/usr/bin/env python3
"""
ESP32 Access Point Mode Test
This script tests communication with ESP32 when it's running as a WiFi hotspot
"""
import socket
import time
import json
import subprocess
import sys

# ESP32 AP Configuration (must match config.h)
ESP32_AP_SSID = "ESP32-FruitBot"
ESP32_AP_PASSWORD = "fruitbot123"
ESP32_AP_IP = "192.168.4.1"  # ESP32's IP in AP mode
CTRL_PORT = 9000
TELEM_PORT = 9001

def check_wifi_connection():
    """Check if we're connected to the ESP32's WiFi network"""
    print("=== Checking WiFi Connection ===")
    
    try:
        # Check current WiFi connection on Windows
        result = subprocess.run(['netsh', 'wlan', 'show', 'profile'], 
                              capture_output=True, text=True)
        
        if ESP32_AP_SSID in result.stdout:
            print(f"✅ WiFi profile for {ESP32_AP_SSID} exists")
        else:
            print(f"❌ WiFi profile for {ESP32_AP_SSID} not found")
            print(f"Please connect to WiFi network: {ESP32_AP_SSID}")
            print(f"Password: {ESP32_AP_PASSWORD}")
            return False
            
        # Check if we can reach the ESP32
        result = subprocess.run(['ping', ESP32_AP_IP, '-n', '2'], 
                              capture_output=True, text=True)
        if 'Reply from' in result.stdout:
            print(f"✅ Can ping ESP32 at {ESP32_AP_IP}")
            return True
        else:
            print(f"❌ Cannot ping ESP32 at {ESP32_AP_IP}")
            print("Make sure you're connected to the ESP32's WiFi network")
            return False
            
    except Exception as e:
        print(f"Error checking WiFi: {e}")
        return False

def test_esp32_communication():
    """Test UDP communication with ESP32"""
    print("\n=== Testing ESP32 Communication ===")
    
    # Test 1: Listen for messages
    print("Test 1: Listening for ESP32 messages...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', TELEM_PORT))
        sock.settimeout(5.0)
        
        print(f"Listening on port {TELEM_PORT} for 5 seconds...")
        
        messages_received = 0
        start_time = time.time()
        
        while time.time() - start_time < 5.0:
            try:
                data, addr = sock.recvfrom(1024)
                messages_received += 1
                
                try:
                    msg = json.loads(data.decode())
                    print(f"✅ Received from {addr}: {msg}")
                    
                    if msg.get('type') == 'alive':
                        print(f"🤖 ESP32 is alive! Mode: {msg.get('mode', 'unknown')}")
                    elif msg.get('type') == 'encoders':
                        counts = msg.get('counts', {})
                        print(f"📊 Encoder data - M1: {counts.get('m1', 0)}, M2: {counts.get('m2', 0)}")
                        
                except json.JSONDecodeError:
                    print(f"✅ Received non-JSON from {addr}: {data}")
                    
            except socket.timeout:
                continue
                
        sock.close()
        
        if messages_received > 0:
            print(f"✅ Received {messages_received} message(s) - ESP32 is working!")
        else:
            print("❌ No messages received")
            return False
            
    except Exception as e:
        print(f"❌ Error in Test 1: {e}")
        return False
    
    # Test 2: Send command to ESP32
    print("\nTest 2: Sending motor command...")
    try:
        ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ctrl_sock.settimeout(3.0)
        
        test_cmd = {
            'type': 'motor',
            'left': 0,
            'right': 0,
            'seq': 42,
            'ts': int(time.time() * 1000)
        }
        
        ctrl_sock.sendto(json.dumps(test_cmd).encode(), (ESP32_AP_IP, CTRL_PORT))
        print(f"✅ Sent command to {ESP32_AP_IP}:{CTRL_PORT}")
        
        # Try to receive acknowledgment
        try:
            ack_data, ack_addr = ctrl_sock.recvfrom(1024)
            ack = json.loads(ack_data.decode())
            print(f"✅ Received ACK: {ack}")
        except socket.timeout:
            print("⚠️ No ACK received (but command sent)")
            
        ctrl_sock.close()
        return True
        
    except Exception as e:
        print(f"❌ Error in Test 2: {e}")
        return False

def show_connection_instructions():
    """Show instructions for connecting to ESP32 AP"""
    print("\n" + "="*60)
    print("🤖 ESP32 ACCESS POINT MODE SETUP")
    print("="*60)
    print()
    print("1. Power on your ESP32 and wait for it to start")
    print("2. On your PC, look for WiFi network:")
    print(f"   📶 Network Name: {ESP32_AP_SSID}")
    print(f"   🔐 Password: {ESP32_AP_PASSWORD}")
    print()
    print("3. Connect to this network")
    print("4. Your PC will get an IP like 192.168.4.2")
    print(f"5. ESP32 will be at: {ESP32_AP_IP}")
    print()
    print("6. Run this test script again")
    print("="*60)

def main():
    print("ESP32 Access Point Communication Test")
    print("="*50)
    
    # Check if we're connected to ESP32's network
    if not check_wifi_connection():
        show_connection_instructions()
        return False
    
    # Test communication
    success = test_esp32_communication()
    
    print("\n=== Test Results ===")
    if success:
        print("✅ ESP32 communication successful!")
        print("You can now use the robot control scripts.")
    else:
        print("❌ Communication failed")
        print("Troubleshooting:")
        print("1. Make sure ESP32 is powered and running")
        print("2. Check serial output for WiFi AP startup messages")
        print("3. Verify you're connected to the ESP32's WiFi network")
        print("4. Try running this script again")
    
    return success

if __name__ == '__main__':
    main()