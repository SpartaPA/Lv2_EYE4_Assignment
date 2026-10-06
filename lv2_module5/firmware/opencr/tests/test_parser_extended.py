import time
import serial

PORT = (
    "/dev/serial/by-id/"
    "usb-ROBOTIS_OpenCR_Virtual_ComPort_in_FS_Mode_FFFFFFFEFFFF-if00"
)

with serial.Serial(PORT, 115200, timeout=0.01, write_timeout=1) as port:
    time.sleep(1)
    port.reset_input_buffer()
    pending = bytearray()

    def send(command):
        port.write((command + "\n").encode("ascii"))
        port.flush()

    def collect(seconds, repeated_command=None):
        """Receive complete lines; optionally send a command every 50 ms."""
        received = []
        deadline = time.monotonic() + seconds
        next_send = time.monotonic()

        while time.monotonic() < deadline:
            now = time.monotonic()
            if repeated_command is not None and now >= next_send:
                send(repeated_command)
                next_send = now + 0.05

            data = port.read(port.in_waiting or 1)
            pending.extend(data)

            while b"\n" in pending:
                raw, _, remainder = pending.partition(b"\n")
                pending[:] = remainder
                line = raw.decode("ascii", errors="replace").rstrip("\r")
                print("<", line, flush=True)
                received.append(line)

        return received

    def require(lines, expected):
        if expected not in lines:
            raise RuntimeError(f"Missing expected response: {expected}")

    def check_disarmed():
        send("STATUS")
        require(collect(0.1), "STATE DISARMED ZERO")

    def arm():
        send("ARM")
        require(collect(0.05), "ACK ARM")

    def passed(name):
        print(f"PASS: {name}\n", flush=True)

    try:
        print("1. Startup state after your manual reset")
        # No DISARM is sent before checking startup.
        check_disarmed()
        send("VEL 0.02")
        require(collect(0.1), "ERR DISARMED")
        passed("Startup is disarmed and rejects velocity")

        print("2. Continuous invalid commands")
        arm()
        lines = collect(0.7, repeated_command="VEL nan")
        require(lines, "ERR VALUE")
        require(lines, "EVENT TIMEOUT DISARMED")
        check_disarmed()
        passed("Invalid commands do not prevent timeout")

        print("3. Continuous STATUS commands")
        arm()
        lines = collect(0.7, repeated_command="STATUS")
        require(lines, "EVENT TIMEOUT DISARMED")
        require(lines, "STATE DISARMED ZERO")
        passed("STATUS does not prevent timeout")

        print("4. Incomplete command without a newline")
        arm()
        port.write(b"VEL 0.02")
        port.flush()
        require(collect(0.7), "EVENT TIMEOUT DISARMED")

        # Complete the buffered line after timeout.
        port.write(b"\n")
        port.flush()
        require(collect(0.1), "ERR DISARMED")
        check_disarmed()
        passed("Incomplete input does not block the watchdog")

        print("5. Oversized input and parser recovery")
        arm()
        port.write(b"X" * 100)  # No newline yet.
        port.flush()
        require(collect(0.7), "EVENT TIMEOUT DISARMED")

        # End the oversized line, then send a valid command.
        port.write(b"\nSTATUS\n")
        port.flush()
        lines = collect(0.2)
        require(lines, "ERR LINE")
        require(lines, "STATE DISARMED ZERO")
        passed("Oversized input is rejected and parsing recovers")

        print("ALL FIVE EXTENDED CHECKS PASSED", flush=True)

    finally:
        # Terminate any unfinished line, then leave the board disarmed.
        port.write(b"\nDISARM\n")
        port.flush()
        collect(0.1)
