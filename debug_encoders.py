#!/usr/bin/env python3
"""
Debug script to test encoder data flow
"""
import time
from advanced import init_bot_control, get_latest_encoders

def test_encoder_data():
    print("🔍 Testing Encoder Data Flow")
    print("=" * 40)
    
    # Initialize the same way move_control.py does
    print("1. Initializing bot control...")
    init_bot_control(verbose_telemetry=True)
    
    print("2. Waiting 3 seconds for data...")
    time.sleep(3)
    
    print("3. Testing encoder data access...")
    for i in range(10):
        encoders, enc_time = get_latest_encoders()
        current_time = time.time()
        
        if enc_time > 0:
            age = current_time - enc_time
            print(f"   Test {i+1}: ✅ Data available")
            print(f"      m1={encoders['m1']}, m2={encoders['m2']}")
            print(f"      m3={encoders['m3']}, m4={encoders['m4']}")
            print(f"      Age: {age:.1f} seconds")
        else:
            print(f"   Test {i+1}: ❌ No data (enc_time = {enc_time})")
            
        time.sleep(1)
    
    print("\n📊 Final Summary:")
    encoders, enc_time = get_latest_encoders()
    if enc_time > 0:
        print("✅ Encoder data is available through imported functions")
    else:
        print("❌ No encoder data available through imported functions")
        print("This means the telemetry thread isn't updating the global variables")

if __name__ == '__main__':
    try:
        test_encoder_data()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()