#!/usr/bin/env python3
"""
Gyro Calibration System
This script helps calibrate the gyro by measuring the bias when the robot is stationary.
"""
import json
import time
import statistics
from advanced import init_bot_control, get_latest_imu, cleanup

CALIBRATION_FILE = "gyro_calibration.json"
DEFAULT_SAMPLE_TIME = 10.0  # seconds
DEFAULT_MIN_SAMPLES = 100

class GyroCalibrator:
    def __init__(self):
        self.bias_x = 0.0
        self.bias_y = 0.0
        self.bias_z = 0.0
        self.calibrated = False
        self.sample_count = 0
        self.calibration_time = 0.0
        
    def save_calibration(self, filename=CALIBRATION_FILE):
        """Save calibration data to file"""
        data = {
            "bias_x": self.bias_x,
            "bias_y": self.bias_y,
            "bias_z": self.bias_z,
            "calibrated": self.calibrated,
            "sample_count": self.sample_count,
            "calibration_time": self.calibration_time,
            "timestamp": time.time()
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Calibration saved to {filename}")
            return True
        except Exception as e:
            print(f"Error saving calibration: {e}")
            return False
    
    def load_calibration(self, filename=CALIBRATION_FILE):
        """Load calibration data from file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            self.bias_x = data.get("bias_x", 0.0)
            self.bias_y = data.get("bias_y", 0.0)
            self.bias_z = data.get("bias_z", 0.0)
            self.calibrated = data.get("calibrated", False)
            self.sample_count = data.get("sample_count", 0)
            self.calibration_time = data.get("calibration_time", 0.0)
            
            print(f"Calibration loaded from {filename}")
            print(f"Bias: X={self.bias_x:.4f}, Y={self.bias_y:.4f}, Z={self.bias_z:.4f}")
            print(f"Samples: {self.sample_count}, Time: {self.calibration_time:.1f}s")
            return True
        except FileNotFoundError:
            print(f"No calibration file found: {filename}")
            return False
        except Exception as e:
            print(f"Error loading calibration: {e}")
            return False
    
    def calibrate(self, sample_time=DEFAULT_SAMPLE_TIME, min_samples=DEFAULT_MIN_SAMPLES):
        """
        Perform gyro calibration by collecting samples while stationary
        """
        print(f"=== GYRO CALIBRATION ===")
        print(f"Keep the robot completely stationary for {sample_time} seconds")
        print("Press Ctrl+C to abort\n")
        
        # Initialize system
        init_bot_control(verbose_telemetry=False)
        
        # Wait for IMU data to start flowing
        print("Waiting for IMU data...")
        start_wait = time.time()
        while True:
            _, _, imu_time = get_latest_imu()
            if imu_time > 0:
                break
            if time.time() - start_wait > 5.0:
                print("Timeout waiting for IMU data!")
                cleanup()
                return False
            time.sleep(0.1)
        
        print("IMU data detected. Starting calibration in 3 seconds...")
        time.sleep(3)
        
        # Collect samples
        samples_x = []
        samples_y = []
        samples_z = []
        
        start_time = time.time()
        last_print = start_time
        
        try:
            while True:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Check if we're done
                if elapsed >= sample_time and len(samples_z) >= min_samples:
                    break
                
                # Get gyro data
                _, gyro, imu_time = get_latest_imu()
                if imu_time > 0:
                    samples_x.append(gyro['x'])
                    samples_y.append(gyro['y'])
                    samples_z.append(gyro['z'])
                
                # Print progress
                if current_time - last_print >= 1.0:
                    remaining = max(0, sample_time - elapsed)
                    samples_needed = max(0, min_samples - len(samples_z))
                    print(f"Progress: {elapsed:.1f}s | Samples: {len(samples_z)} | "
                          f"Remaining: {remaining:.1f}s | Need: {samples_needed} more samples")
                    last_print = current_time
                
                time.sleep(0.01)  # 100Hz sampling
                
        except KeyboardInterrupt:
            print("\nCalibration aborted by user")
            cleanup()
            return False
        
        # Calculate bias
        if len(samples_z) < min_samples:
            print(f"Insufficient samples: {len(samples_z)} < {min_samples}")
            cleanup()
            return False
        
        self.bias_x = statistics.mean(samples_x)
        self.bias_y = statistics.mean(samples_y)
        self.bias_z = statistics.mean(samples_z)
        self.calibrated = True
        self.sample_count = len(samples_z)
        self.calibration_time = elapsed
        
        # Calculate standard deviations to assess quality
        std_x = statistics.stdev(samples_x) if len(samples_x) > 1 else 0
        std_y = statistics.stdev(samples_y) if len(samples_y) > 1 else 0
        std_z = statistics.stdev(samples_z) if len(samples_z) > 1 else 0
        
        print(f"\n=== CALIBRATION RESULTS ===")
        print(f"Samples collected: {self.sample_count}")
        print(f"Calibration time: {self.calibration_time:.1f} seconds")
        print(f"Gyro bias (degrees/second):")
        print(f"  X: {self.bias_x:+7.4f} ± {std_x:.4f}")
        print(f"  Y: {self.bias_y:+7.4f} ± {std_y:.4f}")
        print(f"  Z: {self.bias_z:+7.4f} ± {std_z:.4f}")
        
        # Quality assessment
        max_std = max(std_x, std_y, std_z)
        if max_std < 0.1:
            print("✓ Excellent calibration quality")
        elif max_std < 0.5:
            print("✓ Good calibration quality")
        elif max_std < 1.0:
            print("⚠ Fair calibration quality")
        else:
            print("⚠ Poor calibration quality - robot may not have been stationary")
        
        cleanup()
        return True
    
    def get_corrected_gyro(self, raw_gyro):
        """Apply bias correction to raw gyro data"""
        if not self.calibrated:
            return raw_gyro
        
        return {
            'x': raw_gyro['x'] - self.bias_x,
            'y': raw_gyro['y'] - self.bias_y,
            'z': raw_gyro['z'] - self.bias_z
        }

def main():
    print("Gyro Calibration Tool")
    print("1. Perform new calibration")
    print("2. Load existing calibration")
    print("3. Test current calibration")
    
    try:
        choice = input("Enter choice (1-3): ").strip()
        
        calibrator = GyroCalibrator()
        
        if choice == '1':
            # New calibration
            sample_time = input(f"Sample time in seconds (default {DEFAULT_SAMPLE_TIME}): ").strip()
            if sample_time:
                sample_time = float(sample_time)
            else:
                sample_time = DEFAULT_SAMPLE_TIME
            
            if calibrator.calibrate(sample_time):
                save_choice = input("Save calibration? (y/n): ").strip().lower()
                if save_choice in ('y', 'yes'):
                    calibrator.save_calibration()
        
        elif choice == '2':
            # Load existing
            if calibrator.load_calibration():
                print("Calibration loaded successfully")
            else:
                print("Failed to load calibration")
        
        elif choice == '3':
            # Test calibration
            if calibrator.load_calibration():
                print("\nTesting calibration...")
                print("Move the robot and observe corrected vs raw gyro values")
                print("Press Ctrl+C to stop\n")
                
                init_bot_control(verbose_telemetry=False)
                
                try:
                    while True:
                        _, raw_gyro, imu_time = get_latest_imu()
                        if imu_time > 0:
                            corrected = calibrator.get_corrected_gyro(raw_gyro)
                            print(f"\rRaw Z: {raw_gyro['z']:+7.3f}°/s | "
                                  f"Corrected Z: {corrected['z']:+7.3f}°/s | "
                                  f"Bias: {calibrator.bias_z:+7.4f}°/s", end="", flush=True)
                        time.sleep(0.1)
                        
                except KeyboardInterrupt:
                    print("\nTest completed")
                finally:
                    cleanup()
            else:
                print("No calibration to test")
        
        else:
            print("Invalid choice")
    
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
