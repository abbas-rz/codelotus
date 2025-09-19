#!/usr/bin/env python3
"""
pi_control.py — Raspberry Pi robot control and telemetry service

Features:
- Motor control:
    - L298N dual H-bridge (legacy)
    - TB6612FNG dual H-bridge (supports 4 motors via 2 chips)
- TF-Luna LIDAR telemetry over UART
- MPU6050 IMU telemetry over I2C
- UDP control listener (receives motor commands)
- UDP telemetry sender (sends IMU + LIDAR)
 - Encoders telemetry (for N20 with encoders)
 - SG90 servo control
 - 28BYJ-48 stepper control

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
    "pwm_freq": 155,
    "driver": "TB6612",  
    "tb6612": {
        "stby": 23,
        "A": {"pwm": 12, "in1": 20, "in2": 21},
        "B": {"pwm": 13, "in1": 19, "in2": 26}
    },
    "tb6612_2": {
        "A": {"pwm": 18, "in1": 24, "in2": 25},
        "B": {"pwm": 16, "in1": 5,  "in2": 6}
    },
    "encoders": {
        "m1": {"a": 4},
        "m2": {"a": 17},
        "m3": {"a": 27},
        "m4": {"a": 22}
    },
    "servo": {"pin": 7, "freq": 50},
    "stepper": {"pins": [14, 15, 8, 9], "step_delay_ms": 3}
}

Motor pins (BCM): ENA=12 IN1=20 IN2=21 ENB=13 IN3=19 IN4=26

"""
import argparse, os, json, socket, threading, time
import serial # pyright: ignore[reportMissingModuleSource]
import RPi.GPIO as GPIO # pyright: ignore[reportMissingModuleSource]
import smbus # pyright: ignore[reportMissingImports]
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
    "driver": "TB6612",
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
    cfg["driver"] = os.getenv("DRIVER", cfg.get("driver", "TB6612"))
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


class TB6612:
    """TB6612FNG driver handling 4 motors via two chips (A/B channels each)."""
    def __init__(self, cfg):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self.channels = {}
        self.stby = cfg.get('tb6612', {}).get('stby')
        # First chip
        for label in ('A', 'B'):
            ch = cfg.get('tb6612', {}).get(label, {})
            if ch:
                self._setup_channel(f"1{label}", ch)
        # Second chip
        for label in ('A', 'B'):
            ch = cfg.get('tb6612_2', {}).get(label, {})
            if ch:
                self._setup_channel(f"2{label}", ch)
        # Map logical motors m1..m4 to channels 1A,1B,2A,2B
        self.order = ["1A", "1B", "2A", "2B"]
        if self.stby is not None:
            GPIO.setup(self.stby, GPIO.OUT, initial=GPIO.HIGH)

    def _setup_channel(self, name, ch):
        pwm_pin, in1, in2 = ch.get('pwm'), ch.get('in1'), ch.get('in2')
        if pwm_pin is None or in1 is None or in2 is None:
            return
        GPIO.setup(in1, GPIO.OUT)
        GPIO.setup(in2, GPIO.OUT)
        GPIO.setup(pwm_pin, GPIO.OUT)
        pwm = GPIO.PWM(pwm_pin, 2000)  # 2kHz PWM for TB6612
        pwm.start(0)
        self.channels[name] = {"in1": in1, "in2": in2, "pwm": pwm, "last": 0}

    def set_motor(self, idx: int, speed: int):
        # idx: 0..3 maps to m1..m4
        if idx < 0 or idx >= len(self.order):
            return
        name = self.order[idx]
        ch = self.channels.get(name)
        if not ch:
            return
        s = max(-100, min(100, int(speed)))
        in1, in2, pwm = ch['in1'], ch['in2'], ch['pwm']
        if s >= 0:
            GPIO.output(in1, GPIO.HIGH)
            GPIO.output(in2, GPIO.LOW)
        else:
            GPIO.output(in1, GPIO.LOW)
            GPIO.output(in2, GPIO.HIGH)
        pwm.ChangeDutyCycle(abs(s))
        ch['last'] = s

    def set_pair(self, left: int, right: int):
        # Assume m1+m3 = left side, m2+m4 = right side
        self.set_motor(0, left)
        self.set_motor(2, left)
        self.set_motor(1, right)
        self.set_motor(3, right)

    def stop(self):
        for ch in self.channels.values():
            ch['pwm'].ChangeDutyCycle(0)
        if self.stby is not None:
            GPIO.output(self.stby, GPIO.LOW)


class Encoders:
    def __init__(self, cfg, tb: TB6612 | None = None):
        self.counts = [0, 0, 0, 0]
        self.tb = tb
        self.pins = []
        enc_cfg = cfg.get('encoders', {})
        order = ['m1','m2','m3','m4']
        for i, key in enumerate(order):
            a = enc_cfg.get(key, {}).get('a')
            self.pins.append(a)
            if a is not None:
                GPIO.setup(a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(a, GPIO.BOTH, callback=self._make_cb(i), bouncetime=1)

    def _make_cb(self, idx):
        def cb(channel):
            # Simple single-channel count; direction from motor last command if tb available
            direction = 1
            if self.tb is not None and idx < len(self.tb.order):
                name = self.tb.order[idx]
                ch = self.tb.channels.get(name)
                if ch and ch.get('last', 0) < 0:
                    direction = -1
            self.counts[idx] += direction
        return cb

    def reset(self):
        self.counts = [0, 0, 0, 0]

    def snapshot(self):
        return list(self.counts)


class ServoSG90:
    def __init__(self, pin: int, freq: int = 50):
        self.pin = pin
        GPIO.setup(pin, GPIO.OUT)
        self.pwm = GPIO.PWM(pin, freq)
        self.pwm.start(0)

    def angle(self, deg: float):
        d = max(0.0, min(180.0, float(deg)))
        duty = 2.5 + (d / 180.0) * 10.0
        self.pwm.ChangeDutyCycle(duty)


class Stepper28BYJ:
    # Half-step sequence
    SEQ = [
        (1,0,0,0), (1,1,0,0), (0,1,0,0), (0,1,1,0),
        (0,0,1,0), (0,0,1,1), (0,0,0,1), (1,0,0,1),
    ]
    def __init__(self, pins: list[int], step_delay_ms: int = 3):
        self.pins = pins
        self.delay = max(1, step_delay_ms) / 1000.0
        for p in pins:
            GPIO.setup(p, GPIO.OUT, initial=GPIO.LOW)

    def step(self, steps: int):
        seq = Stepper28BYJ.SEQ
        count = abs(int(steps))
        direction = 1 if steps >= 0 else -1
        idx = 0 if direction > 0 else len(seq)-1
        for _ in range(count):
            pattern = seq[idx]
            for pin, val in zip(self.pins, pattern):
                GPIO.output(pin, GPIO.HIGH if val else GPIO.LOW)
            time.sleep(self.delay)
            idx = (idx + direction) % len(seq)
        # de-energize
        for p in self.pins:
            GPIO.output(p, GPIO.LOW)


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


def telemetry_sender(pc_host: str, telem_port: int, imu: IMU, lidar: TFLuna, enc: 'Encoders|None', ctrl_sock: socket.socket):
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

    def enc_loop():
        if enc is None:
            return
        while True:
            ts = int(time.time() * 1000)
            counts = enc.snapshot()
            send({"type": "encoders", "ts": ts, "counts": counts})
            time.sleep(0.05)

    t1 = threading.Thread(target=imu_loop, daemon=True)
    t2 = threading.Thread(target=lidar_loop, daemon=True)
    t3 = threading.Thread(target=enc_loop, daemon=True)
    t1.start(); t2.start(); t3.start()

    return dest, update_dest_from_ctrl


def control_server(ctrl_port: int, driver, on_sender_ip, servo: 'ServoSG90|None'=None, stepper: 'Stepper28BYJ|None'=None, enc: 'Encoders|None'=None):
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
            # Back-compat: two-wheel differential. Use driver.set_pair when TB6612, else legacy Motors.set
            if hasattr(driver, 'set_pair'):
                driver.set_pair(left, right)
            else:
                driver.set(left, right)
            on_sender_ip(sender_ip)  # update telem destination to whoever is driving us
            sock.sendto(json.dumps({'type': 'ack', 'seq': j.get('seq'), 'ts': int(time.time()*1000)}).encode(), addr)
        elif j.get('type') == 'motor4':
            # Individual motors m1..m4
            speeds = j.get('speeds', [0,0,0,0])
            if hasattr(driver, 'set_motor'):
                for i, s in enumerate(speeds[:4]):
                    driver.set_motor(i, int(s))
            on_sender_ip(sender_ip)
            sock.sendto(json.dumps({'type': 'ack', 'seq': j.get('seq')}).encode(), addr)
        elif j.get('type') == 'move_ticks':
            # Simple blocking move by encoder ticks on left/right sides
            target = j.get('target', [0,0])  # [left_ticks, right_ticks]
            speeds = j.get('speeds', [50,50])
            if enc is not None and hasattr(driver, 'set_pair'):
                enc.reset()
                left_goal, right_goal = int(target[0]), int(target[1])
                left_speed, right_speed = int(speeds[0]), int(speeds[1])
                driver.set_pair(left_speed, right_speed)
                start = time.time()
                while time.time() - start < 10.0:  # timeout
                    c = enc.snapshot()
                    if abs(c[0]) >= abs(left_goal) and abs(c[1]) >= abs(right_goal):
                        break
                    time.sleep(0.01)
                driver.set_pair(0, 0)
            sock.sendto(json.dumps({'type': 'ack', 'seq': j.get('seq')}).encode(), addr)
        elif j.get('type') == 'servo':
            if servo is not None:
                servo.angle(float(j.get('angle', 90)))
            on_sender_ip(sender_ip)
            sock.sendto(json.dumps({'type': 'ack', 'seq': j.get('seq')}).encode(), addr)
        elif j.get('type') == 'stepper':
            if stepper is not None:
                steps = int(j.get('steps', 0))
                stepper.step(steps)
            on_sender_ip(sender_ip)
            sock.sendto(json.dumps({'type': 'ack', 'seq': j.get('seq')}).encode(), addr)
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

    # Choose driver
    driver_kind = (cfg.get('driver') or 'TB6612').upper()
    driver = None
    if driver_kind == 'TB6612':
        driver = TB6612(cfg)
    else:
        driver = Motors(pwm_freq)
    imu = IMU()
    lidar = TFLuna(serial_port, baud)
    # Encoders (optional)
    enc = Encoders(cfg, driver if isinstance(driver, TB6612) else None)
    # Servo (optional)
    servo_cfg = cfg.get('servo', {})
    servo = None
    if 'pin' in servo_cfg:
        servo = ServoSG90(servo_cfg.get('pin'), servo_cfg.get('freq', 50))
    # Stepper (optional)
    step_cfg = cfg.get('stepper', {})
    stepper = None
    if 'pins' in step_cfg:
        stepper = Stepper28BYJ(step_cfg.get('pins'), step_cfg.get('step_delay_ms', 3))

    # A control socket for telemetry (needed only for port awareness; data goes via txsock inside telemetry_sender)
    ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    dest, update_dest = telemetry_sender(pc_host, telem_port, imu, lidar, enc, ctrl_sock)

    # Start control server, with callback to update telemetry destination to last controller IP
    t_ctrl = threading.Thread(target=control_server, args=(ctrl_port, driver, update_dest, servo, stepper, enc), daemon=True)
    t_ctrl.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        if hasattr(driver, 'stop'):
            driver.stop()


if __name__ == "__main__":
    main()
