import time
import serial

PORT = (
    "/dev/serial/by-id/"
    "usb-ROBOTIS_OpenCR_Virtual_ComPort_in_FS_Mode_FFFFFFFEFFFF-if00"
)

with serial.Serial(PORT, 115200, timeout=0.02, write_timeout=1) as port:
    time.sleep(1)
    port.reset_input_buffer()

    def send(command):
        print(f"> {command}", flush=True)
        port.write((command + "\n").encode("ascii"))
        port.flush()

    def listen(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            line = port.readline()
            if line:
                print("<", line.decode(errors="replace").strip(), flush=True)

    try:
        print("\n1. Commands while disarmed")
        send("DISARM")
        send("VEL 0.02")
        listen(0.1)

        print("\n2. Valid commands keep the controller armed")
        send("ARM")
        for _ in range(10):
            send("VEL 0.02")
            listen(0.05)
        send("STATUS")
        listen(0.05)

        print("\n3. Silence must trigger the watchdog")
        listen(0.5)
        send("STATUS")
        send("VEL 0.02")
        listen(0.1)

        print("\n4. Invalid commands must not feed the watchdog")
        send("ARM")
        for command in ["VEL nan", "VEL 1.0", "VEL abc", "HELLO"]:
            send(command)
            listen(0.05)
        listen(0.4)
        send("STATUS")
        listen(0.1)

        print("\n5. STOP clears velocity; DISARM clears arming")
        send("ARM")
        send("VEL -0.02")
        send("STOP")
        send("STATUS")
        send("DISARM")
        send("STATUS")
        listen(0.2)

    finally:
        send("DISARM")
        listen(0.1)
