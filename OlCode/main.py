#!/usr/bin/env python3
# pc_client.py
import socket, threading, json, time
from pynput import keyboard

RPI_IP = '192.168.0.126'   # <-- set to your Pi IP
RPI_CTRL_PORT = 9000
LOCAL_TELEM_PORT = 9001

ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telem_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telem_sock.bind(('', LOCAL_TELEM_PORT))

seq = 1
key_state = set()

def send_motor(left, right):
    global seq
    msg = {'type':'motor','left':int(left),'right':int(right),'seq':seq, 'ts': int(time.time()*1000)}
    seq += 1
    ctrl_sock.sendto(json.dumps(msg).encode(), (RPI_IP, RPI_CTRL_PORT))

def telem_loop():
    while True:
        data, addr = telem_sock.recvfrom(2048)
        try:
            j = json.loads(data.decode())
            if j.get('type') == 'tfluna':
                print("LIDAR:", j['dist_mm'], "mm  ts:", j['ts'])
        except Exception as e:
            pass

def on_press(key):
    try:
        k = key.char
    except:
        return
    key_state.add(k)

def on_release(key):
    try:
        k = key.char
    except:
        return
    if k in key_state:
        key_state.remove(k)
    if k == 'q':
        print("Quit requested")
        return False

def control_loop():
    # map keys to differential motor commands
    while True:
        left, right = 0,0
        if 'w' in key_state:
            left += 60; right += 60
        if 's' in key_state:
            left -= 60; right -= 60
        if 'a' in key_state:
            left -= 30; right += 30
        if 'd' in key_state:
            left += 30; right -= 30
        send_motor(left, right)
        time.sleep(0.05)

if __name__ == '__main__':
    threading.Thread(target=telem_loop,daemon=True).start()
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    control_loop()
