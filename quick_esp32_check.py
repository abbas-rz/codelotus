#!/usr/bin/env python3
"""
Quick ESP32 Connection Diagnostic
"""
import socket
import time
import json
import subprocess

def check_esp32_connection():
    """Check if we can connect to ESP32"""
    print("🔍 ESP32 Connection Diagnostic")
    print("=" * 40)
    
    # 1. Check if we can ping ESP32
    print("1. Testing ping to ESP32...")
    try:
        result = subprocess.run(['ping', '192.168.4.1', '-n', '2'], 
                              capture_output=True, text=True, timeout=10)
        if 'Reply from' in result.stdout:
            print("✅ ESP32 is reachable at 192.168.4.1")
        else:
            print("❌ Cannot ping ESP32 at 192.168.4.1")
            print("   Make sure you're connected to 'ESP32-FruitBot' WiFi network")
            return False
    except Exception as e:
        print(f"❌ Ping failed: {e}")
        return False
    
    # 2. Check if we can receive UDP data
    print("\n2. Testing UDP telemetry reception...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', 9001))
        sock.settimeout(10.0)
        
        print("   Listening on port 9001 for 10 seconds...")
        
        received_count = 0
        encoder_received = False
        alive_received = False
        
        start_time = time.time()
        while time.time() - start_time < 10.0:
            try:
                data, addr = sock.recvfrom(1024)
                received_count += 1
                
                try:
                    msg = json.loads(data.decode())
                    msg_type = msg.get('type', 'unknown')
                    
                    if msg_type == 'encoders':
                        encoder_received = True
                        counts = msg.get('counts', {})
                        print(f"   ✅ Encoder data: m1={counts.get('m1', 0)}, m2={counts.get('m2', 0)}")
                    elif msg_type == 'alive':
                        alive_received = True
                        device = msg.get('device', 'Unknown')
                        esp_ip = msg.get('ip', 'Unknown')
                        print(f"   ✅ Alive message: {device} at {esp_ip}")
                    else:
                        print(f"   📡 Received: {msg_type} from {addr}")
                        
                except json.JSONDecodeError:
                    print(f"   📡 Non-JSON data from {addr}: {data}")
                    
            except socket.timeout:
                continue
                
        sock.close()
        
        print(f"\n📊 Results:")
        print(f"   Total messages: {received_count}")
        print(f"   Encoder data: {'✅ YES' if encoder_received else '❌ NO'}")
        print(f"   Alive messages: {'✅ YES' if alive_received else '❌ NO'}")
        
        if received_count == 0:
            print("\n❌ No UDP data received!")
            print("Possible issues:")
            print("- ESP32 is not running or crashed")
            print("- ESP32 firmware not uploaded correctly")
            print("- Windows Firewall blocking UDP port 9001")
            print("- Not connected to ESP32's WiFi network")
            return False
        elif not encoder_received:
            print("\n⚠️ No encoder data received!")
            print("ESP32 is alive but not sending encoder telemetry")
            return False
        else:
            print("\n✅ Connection is working!")
            return True
            
    except Exception as e:
        print(f"❌ UDP test failed: {e}")
        return False

def check_wifi_connection():
    """Check current WiFi connection"""
    print("\n3. Checking WiFi connection...")
    try:
        result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], 
                              capture_output=True, text=True)
        
        lines = result.stdout.split('\n')
        connected_ssid = None
        
        for line in lines:
            if 'SSID' in line and ':' in line:
                ssid = line.split(':', 1)[1].strip()
                if ssid and ssid != 'SSID':  # Skip the header line
                    connected_ssid = ssid
                    break
        
        if connected_ssid:
            print(f"   Current WiFi: {connected_ssid}")
            if 'ESP32-FruitBot' in connected_ssid:
                print("   ✅ Connected to ESP32's WiFi network")
                return True
            else:
                print("   ❌ NOT connected to ESP32's WiFi network")
                print("   Please connect to 'ESP32-FruitBot' (password: fruitbot123)")
                return False
        else:
            print("   ❌ No WiFi connection detected")
            return False
            
    except Exception as e:
        print(f"   Error checking WiFi: {e}")
        return False

if __name__ == '__main__':
    wifi_ok = check_wifi_connection()
    if wifi_ok:
        esp32_ok = check_esp32_connection()
        if esp32_ok:
            print("\n🎉 Everything looks good! Try running move_robot.bat again.")
        else:
            print("\n🔧 Fix the ESP32 connection issues above and try again.")
    else:
        print("\n📶 Connect to ESP32's WiFi first, then run this diagnostic again.")