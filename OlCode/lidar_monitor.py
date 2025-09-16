#!/usr/bin/env python3
# lidar_monitor.py - Advanced lidar data monitor with logging and statistics
import socket, json, time, sys, os
from datetime import datetime

# Network configuration
LOCAL_TELEM_PORT = 9001

# Statistics tracking
stats = {
    'total_packets': 0,
    'lidar_packets': 0,
    'min_distance': float('inf'),
    'max_distance': 0,
    'avg_distance': 0,
    'distance_sum': 0,
    'last_distances': [],  # Keep last 10 readings
    'packet_types': {}
}

def update_stats(telemetry):
    """Update running statistics"""
    stats['total_packets'] += 1
    
    # Track packet types
    packet_type = telemetry.get('type', 'unknown')
    stats['packet_types'][packet_type] = stats['packet_types'].get(packet_type, 0) + 1
    
    # Process lidar data
    if packet_type == 'tfluna':
        stats['lidar_packets'] += 1
        distance = telemetry.get('dist_mm')
        
        if isinstance(distance, (int, float)):
            # Update min/max
            stats['min_distance'] = min(stats['min_distance'], distance)
            stats['max_distance'] = max(stats['max_distance'], distance)
            
            # Update average
            stats['distance_sum'] += distance
            stats['avg_distance'] = stats['distance_sum'] / stats['lidar_packets']
            
            # Keep recent readings
            stats['last_distances'].append(distance)
            if len(stats['last_distances']) > 10:
                stats['last_distances'].pop(0)

def print_stats():
    """Print current statistics"""
    print("\n=== REAL-TIME STATISTICS ===")
    print(f"Total packets: {stats['total_packets']}")
    print(f"Lidar packets: {stats['lidar_packets']}")
    
    if stats['lidar_packets'] > 0:
        print(f"Distance - Min: {stats['min_distance']:.1f}cm, Max: {stats['max_distance']:.1f}cm, Avg: {stats['avg_distance']:.1f}cm")
        if stats['last_distances']:
            recent_avg = sum(stats['last_distances']) / len(stats['last_distances'])
            print(f"Recent 10 readings avg: {recent_avg:.1f}cm")
    
    print("Packet types:", dict(stats['packet_types']))
    print("=" * 30)

def log_to_file(telemetry, addr):
    """Log data to file"""
    timestamp = datetime.now().isoformat()
    log_entry = {
        'timestamp': timestamp,
        'source': f"{addr[0]}:{addr[1]}",
        'data': telemetry
    }
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Write to daily log file
    date_str = datetime.now().strftime('%Y-%m-%d')
    log_file = f"logs/lidar_log_{date_str}.json"
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

def main():
    # Create UDP socket for telemetry
    telem_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    telem_sock.bind(('', LOCAL_TELEM_PORT))
    
    print("=== ADVANCED LIDAR DATA MONITOR ===")
    print("Listening for telemetry data on port", LOCAL_TELEM_PORT)
    print("Features:")
    print("  - Real-time statistics")
    print("  - Data logging to logs/ directory")
    print("  - Distance zone classification")
    print("Press Ctrl+C to exit\n")
    
    start_time = time.time()
    last_stats_time = time.time()
    
    try:
        while True:
            try:
                # Receive data from Pi
                data, addr = telem_sock.recvfrom(2048)
                
                # Try to decode JSON
                try:
                    telemetry = json.loads(data.decode())
                    
                    # Update statistics
                    update_stats(telemetry)
                    
                    # Log to file
                    log_to_file(telemetry, addr)
                    
                    # Display telemetry data
                    current_time = time.strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds
                    
                    print(f"[{current_time}] {telemetry.get('type', 'unknown').upper()}")
                    
                    # Handle different packet types
                    if telemetry.get('type') == 'tfluna':
                        distance = telemetry.get('dist_mm', 'N/A')
                        timestamp = telemetry.get('ts', 'N/A')
                        
                        if isinstance(distance, (int, float)):
                            # Determine zone
                            if distance < 30:
                                zone = "🔴 CRITICAL"
                            elif distance < 50:
                                zone = "🟠 DANGER"
                            elif distance < 80:
                                zone = "🟡 WARNING"
                            elif distance < 120:
                                zone = "🟢 CAUTION"
                            else:
                                zone = "⚪ SAFE"
                            
                            print(f"  Distance: {distance} cm [{zone}]")
                        else:
                            print(f"  Distance: {distance}")
                        
                        print(f"  Timestamp: {timestamp}")
                    else:
                        # Display all other data
                        for key, value in telemetry.items():
                            if key != 'type':
                                print(f"  {key}: {value}")
                    
                    print()
                    
                    # Print stats every 10 seconds
                    if time.time() - last_stats_time > 10:
                        print_stats()
                        last_stats_time = time.time()
                        
                except json.JSONDecodeError:
                    # Raw data that's not JSON
                    print(f"[{time.strftime('%H:%M:%S')}] RAW DATA from {addr[0]}:{addr[1]}")
                    print(f"  {data}")
                    print()
                    
            except socket.timeout:
                pass
            except Exception as e:
                print(f"Error: {e}")
                
    except KeyboardInterrupt:
        elapsed_time = time.time() - start_time
        print(f"\n\n=== FINAL SUMMARY ===")
        print(f"Total runtime: {elapsed_time:.1f} seconds")
        print_stats()
        print("Data logs saved to logs/ directory")
        print("Shutting down...")
        
    finally:
        telem_sock.close()

if __name__ == '__main__':
    main()
