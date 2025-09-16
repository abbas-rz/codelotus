# Pi Setup and Services

## 1. Enable Interfaces
- raspi-config: enable I2C and Serial (disable login shell over serial; enable serial hardware)

## 2. Install Packages
```
sudo apt update
sudo apt install -y python3-pip python3-smbus python3-rpi.gpio avahi-daemon
pip3 install pyserial
```

## 3. mDNS (.local) name
- Set the Pi hostname: `sudo raspi-config` -> System Options -> Hostname
- Reboot. Your Pi will be `<hostname>.local`
- Ensure avahi-daemon is running: `systemctl status avahi-daemon`

## 4. Project layout on Pi
Place repo (or just `codeonthepi/`) somewhere like `/home/pi/IHFCprepsuite/`.

## 5. Configuring PC host (no SSH edits)
- Edit `codeonthepi/config.json` on your PC, commit/push, or copy to Pi. Set `pc_host` to your Windows PC mDNS host, e.g. `abbas-pc.local`.
- Alternatively, set env vars in systemd (below), or pass CLI args to `pi_control.py`.

## 6. Systemd service: pi_control
Create `/etc/systemd/system/pi_control.service`:
```
[Unit]
Description=IHFC Pi Control Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pi/IHFCprepsuite/codeonthepi
ExecStart=/usr/bin/python3 /home/pi/IHFCprepsuite/codeonthepi/pi_control.py
Restart=on-failure
Environment=PC_HOST=abbas-pc.local
# Optional: TELEM_PORT=9001 CTRL_PORT=9000 PWM_FREQ=155 SERIAL_PORT=/dev/serial0

[Install]
WantedBy=multi-user.target
```
Enable + start:
```
sudo systemctl daemon-reload
sudo systemctl enable pi_control
sudo systemctl start pi_control
```

## 7. Systemd service: button launcher (optional)
Create `/etc/systemd/system/button_launcher.service`:
```
[Unit]
Description=IHFC Button Launcher
After=multi-user.target

[Service]
Type=simple
WorkingDirectory=/home/pi/IHFCprepsuite/codeonthepi
ExecStart=/usr/bin/python3 /home/pi/IHFCprepsuite/codeonthepi/button_launcher.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
Enable + start:
```
sudo systemctl daemon-reload
sudo systemctl enable button_launcher
sudo systemctl start button_launcher
Double-tap update + Shutdown permissions:
- The button script runs `git fetch/pull` in the repo root on double-tap. Ensure the working copy is clean, or it will fallback to `reset --hard origin/main`.
- For long-press shutdown without password, add a sudoers entry:
```
sudo visudo
```
Add line:
```
pi ALL=(ALL) NOPASSWD: /sbin/shutdown
```
Replace `pi` with your user.
```

## 8. Test
- From PC, run your controller (advanced.py users): send motor commands; telemetry should flow back.
- If control arrives from a new IP, telemetry destination auto-updates to that IP.

## 9. Troubleshooting
- Check logs: `journalctl -u pi_control -f`
- Verify UART: `ls -l /dev/serial0`
- Verify I2C: `sudo i2cdetect -y 1` (expect 0x68)
- Firewall: ensure PC allows UDP 9000/9001
