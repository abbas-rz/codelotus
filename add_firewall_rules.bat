@echo off
echo Adding Windows Firewall rules for ESP32 communication...

:: Allow Python to receive UDP on port 9001 (inbound)
netsh advfirewall firewall add rule name="ESP32_Telemetry_In" dir=in action=allow protocol=UDP localport=9001

:: Allow Python to send UDP to port 9000 (outbound) 
netsh advfirewall firewall add rule name="ESP32_Control_Out" dir=out action=allow protocol=UDP remoteport=9000

:: Allow Python.exe through firewall
netsh advfirewall firewall add rule name="Python_ESP32" dir=in action=allow program="C:\Windows\System32\python.exe"
netsh advfirewall firewall add rule name="Python_ESP32_Out" dir=out action=allow program="C:\Windows\System32\python.exe"

echo.
echo Firewall rules added! Try running the test again.
echo If it still doesn't work, you may need to run this as Administrator.
pause