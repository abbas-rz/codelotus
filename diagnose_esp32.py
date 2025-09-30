#!/usr/bin/env python3
"""
Comprehensive ESP32 diagnostics
"""
import socket
import subprocess
import time
import json
import ipaddress

def get_network_info():
    """Get current network configuration"""
    print("=== Network Configuration ===")
    try:
        result = subprocess.run(['ipconfig'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        wifi_section = False
        for line in lines:
            if 'Wireless LAN adapter Wi-Fi:' in line:
                wifi_section = True
                print(line)
            elif wifi_section and 'Wireless LAN adapter' in line and 'Wi-Fi' not in line:
                wifi_section = False
            elif wifi_section and line.strip():
                print(line)
        
    except Exception as e:
        print(f"Error getting network info: {e}")

def scan_network_for_esp32():
    """Scan the local network for potential ESP32 devices"""
    print("\n=== Scanning Network for ESP32 ===")
    
    # Get our IP and subnet
    try:
        # Get our local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        print(f"Your IP: {local_ip}")
        
        # Determine network range
        network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
        print(f"Scanning network: {network}")
        
        # Test common ESP32 IPs
        esp32_candidates = [
            "192.168.1.100",  # Our configured static IP
            "192.168.1.101", 
            "192.168.1.102",
            "192.168.1.200",
        ]
        
        for ip in esp32_candidates:
            if ipaddress.IPv4Address(ip) in network:
                print(f"Testing {ip}...", end=" ")
                result = subprocess.run(['ping', ip, '-n', '1', '-w', '1000'], 
                                      capture_output=True, text=True)
                if 'Reply from' in result.stdout and 'Destination host unreachable' not in result.stdout:
                    print("✅ REACHABLE")
                    test_esp32_ports(ip)
                else:
                    print("❌ No response")
                    
    except Exception as e:
        print(f"Error scanning network: {e}")

def test_esp32_ports(ip):
    """Test if ESP32 ports are responding"""
    print(f"  Testing UDP ports on {ip}:")
    
    # Test control port (should accept commands)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        
        test_cmd = {
            'type': 'motor',
            'left': 0,
            'right': 0,
            'seq': 999,
            'ts': int(time.time() * 1000)
        }
        
        sock.sendto(json.dumps(test_cmd).encode(), (ip, 9000))
        print(f"  ✅ Sent test command to {ip}:9000")
        
        # Try to receive ack
        try:
            data, addr = sock.recvfrom(1024)
            response = json.loads(data.decode())
            print(f"  ✅ Received response: {response}")
        except socket.timeout:
            print(f"  ⚠️ No ack received (but command sent)")
            
        sock.close()
        
    except Exception as e:
        print(f"  ❌ Error testing control port: {e}")

def listen_for_broadcasts():
    """Listen for any UDP broadcasts that might be from ESP32"""
    print("\n=== Listening for ESP32 Broadcasts ===")
    
    ports_to_try = [9001, 9000, 8080, 80]  # Common ports
    
    for port in ports_to_try:
        print(f"Listening on port {port} for 5 seconds...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', port))
            sock.settimeout(5.0)
            
            try:
                data, addr = sock.recvfrom(1024)
                print(f"✅ Received data on port {port} from {addr}: {data}")
                try:
                    msg = json.loads(data.decode())
                    print(f"   Parsed JSON: {msg}")
                except:
                    print(f"   Raw data: {data}")
                sock.close()
                return True
                
            except socket.timeout:
                print(f"❌ No data on port {port}")
                
            sock.close()
            
        except Exception as e:
            print(f"❌ Error on port {port}: {e}")
    
    return False

def check_mdns():
    """Check if mDNS resolution works"""
    print("\n=== Testing mDNS Resolution ===")
    
    hostnames = ['fruitbot.local', 'esp32-robot.local', 'esp32.local']
    
    for hostname in hostnames:
        try:
            result = socket.getaddrinfo(hostname, 9000)
            print(f"✅ {hostname} resolves to: {result[0][4][0]}")
        except socket.gaierror:
            print(f"❌ Cannot resolve {hostname}")

def main():
    print("ESP32 Network Diagnostics")
    print("=" * 50)
    
    get_network_info()
    check_mdns()
    scan_network_for_esp32()
    found = listen_for_broadcasts()
    
    print("\n=== Summary ===")
    if found:
        print("✅ Found ESP32 communication!")
    else:
        print("❌ No ESP32 communication detected")
        print("\nTroubleshooting steps:")
        print("1. Check ESP32 is powered on and running")
        print("2. Check ESP32 serial output for WiFi connection status")
        print("3. Run firewall script as Administrator")
        print("4. Verify ESP32 and PC are on same WiFi network")

if __name__ == '__main__':
    main()