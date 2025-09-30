#!/usr/bin/env python3
"""
Simple UDP test to debug ESP32 connectivity issues
"""
import socket
import time
import json

# Try multiple ways to reach the ESP32
ESP32_ADDRESSES = [
    'fruitbot.local',  # mDNS hostname
    '192.168.1.100',   # Static IP from config.h
]
CTRL_PORT = 9000
TELEM_PORT = 9001

def resolve_esp32_ip():
    """Try to resolve ESP32 IP address using different methods"""
    print("=== Resolving ESP32 Address ===")
    
    for addr in ESP32_ADDRESSES:
        print(f"Trying: {addr}")
        try:
            # Test if we can resolve the address
            socket.getaddrinfo(addr, CTRL_PORT)
            print(f"✅ Successfully resolved: {addr}")
            return addr
        except socket.gaierror as e:
            print(f"❌ Failed to resolve {addr}: {e}")
            continue
    
    print("❌ Could not resolve any ESP32 address")
    return None

def test_esp32_connectivity():
    print("=== ESP32 Network Test ===")
    
    # First try to resolve the ESP32 address
    esp32_ip = resolve_esp32_ip()
    if not esp32_ip:
        print("Cannot proceed without a valid ESP32 address")
        return False
    
    print(f"Using ESP32 IP: {esp32_ip}")
    print(f"Control Port: {CTRL_PORT}")
    print(f"Telemetry Port: {TELEM_PORT}")
    print()
    
    # Test 1: Listen for broadcast messages
    print("Test 1: Listening for alive messages...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', TELEM_PORT))
        sock.settimeout(10.0)  # 10 second timeout
        
        print(f"Listening on port {TELEM_PORT} for 10 seconds...")
        print("(ESP32 sends alive messages every 10 seconds and encoder data every 50ms)")
        
        messages_received = 0
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                messages_received += 1
                try:
                    msg = json.loads(data.decode())
                    print(f"✅ Received from {addr}: {msg}")
                    
                    if msg.get('type') == 'alive':
                        print(f"🤖 ESP32 is alive at {msg.get('ip')}!")
                        sock.close()
                        return True
                    elif msg.get('type') == 'encoders':
                        print(f"📊 ESP32 encoder data received - ESP32 is working!")
                        if messages_received >= 3:  # Got several encoder messages
                            break
                except json.JSONDecodeError:
                    print(f"✅ Received non-JSON data from {addr}: {data.decode()}")
                    
            except socket.timeout:
                print("⏰ Timeout - no messages received")
                break
                
        sock.close()
        
        if messages_received > 0:
            print(f"✅ Received {messages_received} message(s) - ESP32 is communicating!")
        
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
        
        ctrl_sock.sendto(json.dumps(test_cmd).encode(), (esp32_ip, CTRL_PORT))
        print(f"✅ Sent test command to {esp32_ip}:{CTRL_PORT}")
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