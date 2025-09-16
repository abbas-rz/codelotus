#!/usr/bin/env python3
# test_vision.py - Test red object detection with GStreamer feed
import cv2
import numpy as np
import time

# Vision config
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
RED_LOWER = np.array([0, 50, 50])     # Lower HSV threshold for red
RED_UPPER = np.array([10, 255, 255])  # Upper HSV threshold for red
RED_LOWER2 = np.array([170, 50, 50])  # Second red range (wraps around hue)
RED_UPPER2 = np.array([180, 255, 255])
MIN_CONTOUR_AREA = 500  # Minimum area for red object detection

def setup_camera():
    """Setup camera capture using GStreamer pipeline"""
    # GStreamer pipeline for UDP H.264 stream
    gst_pipeline = (
        "udpsrc port=5000 caps=\"application/x-rtp,encoding-name=H264,payload=96\" ! "
        "rtph264depay ! avdec_h264 ! videoconvert ! appsink sync=false"
    )
    
    try:
        cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            print("Camera initialized successfully")
            print("Pipeline:", gst_pipeline)
            return cap
        else:
            print("Failed to open camera stream")
            return None
    except Exception as e:
        print(f"Camera setup error: {e}")
        return None

def detect_red_objects(frame):
    """Detect red objects in the frame and return detection info"""
    # Convert BGR to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Create mask for red color (two ranges due to hue wrapping)
    mask1 = cv2.inRange(hsv, RED_LOWER, RED_UPPER)
    mask2 = cv2.inRange(hsv, RED_LOWER2, RED_UPPER2)
    mask = cv2.bitwise_or(mask1, mask2)
    
    # Apply morphological operations to reduce noise
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    detections = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > MIN_CONTOUR_AREA:
            # Get centroid
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                detections.append({
                    'center': (cx, cy),
                    'area': area,
                    'bbox': (x, y, w, h),
                    'contour': contour
                })
                
                # Draw detection on frame
                cv2.drawContours(frame, [contour], -1, (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 0), 2)
                cv2.putText(frame, f"Area: {area}", (cx-50, cy-20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, f"({cx},{cy})", (cx-30, cy+15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    # Show mask for debugging
    cv2.imshow('Red Mask', mask)
    
    return frame, detections

def main():
    print("=== RED OBJECT DETECTION TEST ===")
    print("This will test the vision system with the GStreamer camera feed")
    print("Make sure the camera stream is running on port 5000")
    print("Press 'q' to quit, 's' to save current frame")
    
    cap = setup_camera()
    if cap is None:
        print("Failed to initialize camera. Make sure:")
        print("1. Camera stream is running (use streamcode.bat)")
        print("2. Stream is on port 5000")
        print("3. GStreamer is properly installed")
        return
    
    frame_count = 0
    fps_start = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame")
            time.sleep(0.1)
            continue
        
        # Process frame
        processed_frame, detections = detect_red_objects(frame)
        
        # Add info overlay
        frame_count += 1
        current_time = time.time()
        if current_time - fps_start > 1.0:
            fps = frame_count / (current_time - fps_start)
            frame_count = 0
            fps_start = current_time
        else:
            fps = 0
        
        info_text = f"FPS: {fps:.1f} | Detections: {len(detections)}"
        cv2.putText(processed_frame, info_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Add center line for reference
        center_x = CAMERA_WIDTH // 2
        cv2.line(processed_frame, (center_x, 0), (center_x, CAMERA_HEIGHT), (0, 0, 255), 2)
        cv2.putText(processed_frame, "CENTER", (center_x-30, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Print detection info
        if detections:
            largest = max(detections, key=lambda d: d['area'])
            center_offset = largest['center'][0] - center_x
            direction = "RIGHT" if center_offset > 0 else "LEFT"
            print(f"Largest red object: Area={largest['area']}, "
                  f"Center={largest['center']}, Offset={center_offset} ({direction})")
        
        # Show frame
        cv2.imshow('Red Object Detection', processed_frame)
        
        # Handle key presses
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            filename = f"vision_test_{int(time.time())}.jpg"
            cv2.imwrite(filename, processed_frame)
            print(f"Saved frame as {filename}")
    
    cap.release()
    cv2.destroyAllWindows()
    print("Vision test completed")

if __name__ == '__main__':
    main()
