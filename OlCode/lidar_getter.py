#!/usr/bin/env python3
# lidar_getter.py - Simple script to display all telemetry data from the Pi
import socket, json, time, sys

# Network configuration
LOCAL_TELEM_PORT = 9001

# Create UDP socket for telemetry
telem_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telem_sock.bind(('', LOCAL_TELEM_PORT))

print("=== LIDAR DATA MONITOR ===")
print("Listening for telemetry data on port", LOCAL_TELEM_PORT)
print("Press Ctrl+C to exit\n")

packet_count = 0
start_time = time.time()

try:
    while True:
        try:
            # Receive data from Pi
            data, addr = telem_sock.recvfrom(2048)
            packet_count += 1
            
            # Try to decode JSON
            try:
                telemetry = json.loads(data.decode())
                
                # Get current timestamp
                current_time = time.strftime("%H:%M:%S")
                
                # Display all telemetry data
                print(f"[{current_time}] Packet #{packet_count} from {addr[0]}:{addr[1]}")
                
                # Pretty print the JSON data
                for key, value in telemetry.items():
                    if key == 'type':
                        print(f"  Type: {value}")
                    elif key == 'dist_mm':
                        print(f"  Distance: {value} cm")
                    elif key == 'ts':
                        print(f"  Timestamp: {value}")
                    else:
                        print(f"  {key}: {value}")
                
                # Special handling for TF Luna lidar data
                if telemetry.get('type') == 'tfluna':
                    distance = telemetry.get('dist_mm', 'N/A')
                    if isinstance(distance, (int, float)):
                        if distance < 30:
                            status = "CRITICAL"
                        elif distance < 50:
                            status = "DANGER"
                        elif distance < 80:
                            status = "WARNING"
                        elif distance < 120:
                            status = "CAUTION"
                        else:
                            status = "SAFE"
                        print(f"  Status: {status}")
                
                print("-" * 50)
                
            except json.JSONDecodeError:
                # Raw data that's not JSON
                print(f"[{time.strftime('%H:%M:%S')}] Raw data from {addr[0]}:{addr[1]}")
                print(f"  Data: {data}")
                print("-" * 50)
                
        except socket.timeout:
            # Handle timeout (if we set one)
            pass
        except Exception as e:
            print(f"Error receiving data: {e}")
            
except KeyboardInterrupt:
    elapsed_time = time.time() - start_time
    print(f"\n\n=== SUMMARY ===")
    print(f"Total packets received: {packet_count}")
    print(f"Runtime: {elapsed_time:.1f} seconds")
    if elapsed_time > 0:
        print(f"Average rate: {packet_count/elapsed_time:.1f} packets/second")
    print("Shutting down...")
    
finally:
    telem_sock.close()
