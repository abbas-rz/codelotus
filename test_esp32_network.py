#!/usr/bin/env python3
"""
Simple UDP test to debug ESP32 connectivity issues
"""
import socket
import time
import json

ESP32_IP = 'esp32-robot.local'  # ESP32 mDNS hostname
CTRL_PORT = 9000
TELEM_PORT = 9001

def test_esp32_connectivity():
    print("=== ESP32 Network Test ===")
    print(f"ESP32 IP: {ESP32_IP}")
    print(f"Control Port: {CTRL_PORT}")
    print(f"Telemetry Port: {TELEM_PORT}")
    print()
    
    # Test 1: Listen for broadcast messages
    print("Test 1: Listening for alive messages...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', TELEM_PORT))
        sock.settimeout(10.0)  # 10 second timeout
        
        print(f"Listening on port {TELEM_PORT} for 10 seconds...")
        
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                print(f"✅ Received from {addr}: {msg}")
                
                if msg.get('type') == 'alive':
                    print(f"🤖 ESP32 is alive at {msg.get('ip')}!")
                    break
                    
            except socket.timeout:
                print("⏰ Timeout - no messages received")
                break
                
        sock.close()
        
    except Exception as e:
        print(f"❌ Error listening: {e}")
        return False
    
    # Test 2: Send a command to ESP32
    print("\nTest 2: Sending test command to ESP32...")
    try:
        ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_cmd = {
            'type': 'motor',
            'left': 0,
            'right': 0,
            'seq': 1,
            'ts': int(time.time() * 1000)
        }
        
        ctrl_sock.sendto(json.dumps(test_cmd).encode(), (ESP32_IP, CTRL_PORT))
        print(f"✅ Sent test command to {ESP32_IP}:{CTRL_PORT}")
        ctrl_sock.close()
        
    except Exception as e:
        print(f"❌ Error sending command: {e}")
        return False
    
    print("\n=== Test Complete ===")
    print("If you see '✅ Received' messages above, the ESP32 is communicating!")
    print("If not, check:")
    print("1. ESP32 is connected to WiFi")
    print("2. ESP32 has correct IP address")
    print("3. Windows Firewall isn't blocking UDP")
    print("4. Both devices are on same network")
    
    return True

if __name__ == '__main__':
    test_esp32_connectivity()