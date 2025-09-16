#!/usr/bin/env python3
"""
pi_control.py — Raspberry Pi robot control and telemetry service

Features:
- Motor control (L298N dual H-bridge via GPIO PWM)
- TF-Luna LIDAR telemetry over UART
- MPU6050 IMU telemetry over I2C
- UDP control listener (receives motor commands)
- UDP telemetry sender (sends IMU + LIDAR)

Configurable:
- PC host/IP (supports IPv4 or mDNS .local)
- Telemetry and control ports
- Motor PWM frequency
- GPIO pins mapping

Runtime configuration: CLI args > environment vars > config.json defaults

Environment variables:
- PC_HOST, TELEM_PORT, CTRL_PORT, PWM_FREQ, SERIAL_PORT

Config file (optional): codeonthepi/config.json
{
  "pc_host": "abbas-pc.local",
  "telem_port": 9001,
  "ctrl_port": 9000,
  "serial_port": "/dev/serial0",
  "baud": 115200,
  "pwm_freq": 155
}

Motor pins (BCM): ENA=12 IN1=20 IN2=21 ENB=13 IN3=19 IN4=26

"""
import argparse, os, json, socket, threading, time
import serial
import RPi.GPIO as GPIO
import smbus
from typing import Optional


# ----------------------
# Defaults
# ----------------------
DEFAULT_CFG = {
    "pc_host": "abbas-pc.local",  # mDNS hostname or IPv4
    "telem_port": 9001,
    "ctrl_port": 9000,
    "serial_port": "/dev/serial0",
    "baud": 115200,
    "pwm_freq": 155,
}

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    cfg = dict(DEFAULT_CFG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    # Env overrides
    cfg["pc_host"] = os.getenv("PC_HOST", cfg["pc_host"])  # may be .local
    cfg["telem_port"] = int(os.getenv("TELEM_PORT", cfg["telem_port"]))
    cfg["ctrl_port"] = int(os.getenv("CTRL_PORT", cfg["ctrl_port"]))
    cfg["serial_port"] = os.getenv("SERIAL_PORT", cfg["serial_port"]) 
    cfg["baud"] = int(os.getenv("BAUD", cfg["baud"]))
    cfg["pwm_freq"] = int(os.getenv("PWM_FREQ", cfg["pwm_freq"]))
    return cfg


def resolve_host(host: str) -> str:
    """Resolve IPv4 or .local mDNS hostname to IP; returns original if resolution fails."""
    try:
        return socket.gethostbyname(host)
    except Exception:
        return host


class Motors:
    def __init__(self, pwm_freq: int):
        # L298N mapping (BCM)
        self.ENA = 12
        self.IN1 = 20
        self.IN2 = 21
        self.ENB = 13
        self.IN3 = 19
        self.IN4 = 26

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in [self.IN1, self.IN2, self.IN3, self.IN4]:
            GPIO.setup(pin, GPIO.OUT)
        GPIO.setup(self.ENA, GPIO.OUT)
        GPIO.setup(self.ENB, GPIO.OUT)

        self.pwm_left = GPIO.PWM(self.ENA, pwm_freq)
        self.pwm_right = GPIO.PWM(self.ENB, pwm_freq)
        self.pwm_left.start(0)
        self.pwm_right.start(0)

    def set(self, left: int, right: int):
        left = max(-100, min(100, int(left)))
        right = max(-100, min(100, int(right)))
        # Left
        if left >= 0:
            GPIO.output(self.IN1, GPIO.HIGH)
            GPIO.output(self.IN2, GPIO.LOW)
        else:
            GPIO.output(self.IN1, GPIO.LOW)
            GPIO.output(self.IN2, GPIO.HIGH)
        self.pwm_left.ChangeDutyCycle(abs(left))
        # Right
        if right >= 0:
            GPIO.output(self.IN3, GPIO.HIGH)
            GPIO.output(self.IN4, GPIO.LOW)
        else:
            GPIO.output(self.IN3, GPIO.LOW)
            GPIO.output(self.IN4, GPIO.HIGH)
        self.pwm_right.ChangeDutyCycle(abs(right))

    def stop(self):
        try:
            self.pwm_left.stop(); self.pwm_right.stop()
        finally:
            GPIO.cleanup()


class IMU:
    def __init__(self, bus_id=1, addr=0x68):
        self.bus = smbus.SMBus(bus_id)
        self.addr = addr
        # Wake MPU6050
        self.bus.write_byte_data(self.addr, 0x6B, 0)

    def read(self):
        def read_word(adr):
            high = self.bus.read_byte_data(self.addr, adr)
            low = self.bus.read_byte_data(self.addr, adr+1)
            val = (high << 8) + low
            if val >= 0x8000:
                val = -((65535 - val) + 1)
            return val
        accel_x = read_word(0x3B) / 16384.0
        accel_y = read_word(0x3D) / 16384.0
        accel_z = read_word(0x3F) / 16384.0
        gyro_x = read_word(0x43) / 131.0
        gyro_y = read_word(0x45) / 131.0
        gyro_z = read_word(0x47) / 131.0
        return {
            'accel': {'x': accel_x, 'y': accel_y, 'z': accel_z},
            'gyro': {'x': gyro_x, 'y': gyro_y, 'z': gyro_z}
        }


class TFLuna:
    def __init__(self, serial_port: str, baud: int):
        self.ser = serial.Serial(serial_port, baud, timeout=0.1)

    def read_frame(self) -> Optional[dict]:
        buf = b''
        # Read continuously until a valid frame is assembled
        while True:
            buf += self.ser.read(9 - len(buf))
            if len(buf) < 9:
                return None
            if buf[0:2] != b'\x59\x59':
                buf = buf[1:]
                continue
            frame = buf[:9]
            # dist in cm in TF-Luna standard frame
            dist_cm = frame[2] + (frame[3] << 8)
            strength = frame[4] + (frame[5] << 8)
            temp_raw = frame[6] + (frame[7] << 8)
            temp_c = temp_raw / 8.0 - 256
            ts = int(time.time() * 1000)
            return {"type": "tfluna", "ts": ts, "dist_mm": int(dist_cm * 10), "strength": strength, "temp_c": temp_c}


def telemetry_sender(pc_host: str, telem_port: int, imu: IMU, lidar: TFLuna, ctrl_sock: socket.socket):
    txsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (resolve_host(pc_host), telem_port)

    last_ctrl_sender = None  # (ip, port) of last control message; used to update dest IP dynamically

    def update_dest_from_ctrl(sender_ip: str):
        nonlocal dest
        try:
            # keep telem_port same; swap IP to control sender
            dest = (sender_ip, dest[1])
        except Exception:
            pass

    def ctrl_observer():
        # peeks messages from ctrl_sock without consuming by main control loop is tricky; instead, rely on main to call this hook
        pass

    def send(pkt: dict):
        try:
            txsock.sendto(json.dumps(pkt).encode(), dest)
        except Exception as e:
            print("telemetry send error:", e)

    def imu_loop():
        while True:
            data = imu.read()
            ts = int(time.time() * 1000)
            send({"type": "imu", "ts": ts, **data})
            time.sleep(0.05)

    def lidar_loop():
        while True:
            frame = lidar.read_frame()
            if frame:
                send(frame)
            # small sleep to avoid busy loop
            time.sleep(0.01)

    t1 = threading.Thread(target=imu_loop, daemon=True)
    t2 = threading.Thread(target=lidar_loop, daemon=True)
    t1.start(); t2.start()

    return dest, update_dest_from_ctrl


def control_server(ctrl_port: int, motors: Motors, on_sender_ip):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', ctrl_port))
    print(f"Control listen on :{ctrl_port}")
    while True:
        data, addr = sock.recvfrom(1024)
        sender_ip, _ = addr
        try:
            j = json.loads(data.decode())
        except Exception:
            continue
        if j.get('type') == 'motor':
            left = int(j.get('left', 0))
            right = int(j.get('right', 0))
            motors.set(left, right)
            on_sender_ip(sender_ip)  # update telem destination to whoever is driving us
            sock.sendto(json.dumps({'type': 'ack', 'seq': j.get('seq'), 'ts': int(time.time()*1000)}).encode(), addr)
        else:
            sock.sendto(json.dumps({'type': 'error', 'msg': 'unknown', 'seq': j.get('seq')}).encode(), addr)


def main():
    cfg = load_config()

    # CLI overrides
    parser = argparse.ArgumentParser(description="IHFC Pi Control")
    parser.add_argument("--pc-host", dest="pc_host")
    parser.add_argument("--telem-port", dest="telem_port", type=int)
    parser.add_argument("--ctrl-port", dest="ctrl_port", type=int)
    parser.add_argument("--serial-port", dest="serial_port")
    parser.add_argument("--baud", dest="baud", type=int)
    parser.add_argument("--pwm-freq", dest="pwm_freq", type=int)
    args = parser.parse_args()
    for k in ["pc_host", "telem_port", "ctrl_port", "serial_port", "baud", "pwm_freq"]:
        v = getattr(args, k)
        if v is not None:
            cfg[k] = v

    pc_host = cfg['pc_host']
    telem_port = cfg['telem_port']
    ctrl_port = cfg['ctrl_port']
    serial_port = cfg['serial_port']
    baud = cfg['baud']
    pwm_freq = cfg['pwm_freq']

    print(f"pi_control starting → host={pc_host} telem={telem_port} ctrl={ctrl_port}")

    motors = Motors(pwm_freq)
    imu = IMU()
    lidar = TFLuna(serial_port, baud)

    # A control socket for telemetry (needed only for port awareness; data goes via txsock inside telemetry_sender)
    ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    dest, update_dest = telemetry_sender(pc_host, telem_port, imu, lidar, ctrl_sock)

    # Start control server, with callback to update telemetry destination to last controller IP
    t_ctrl = threading.Thread(target=control_server, args=(ctrl_port, motors, update_dest), daemon=True)
    t_ctrl.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        motors.stop()


if __name__ == "__main__":
    main()
