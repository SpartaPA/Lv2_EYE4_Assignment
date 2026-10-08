#!/usr/bin/env python3
"""Serial checks for MODE=DRY firmware only. Never runs on MODE=LIVE."""
import argparse
import time
import serial

p = argparse.ArgumentParser()
p.add_argument('--port', required=True)
a = p.parse_args()
s = serial.Serial(a.port, 115200, timeout=0.02, write_timeout=0.2)

def receive(duration=0.1):
    lines = []
    end = time.monotonic() + duration
    while time.monotonic() < end:
        line = s.readline().decode('ascii', errors='replace').strip()
        if line:
            print('<', line, flush=True)
            lines.append(line)
    return lines

def send(text):
    print('>', text, flush=True)
    s.write((text + '\n').encode('ascii'))

def state():
    for _ in range(3):
        send('STATUS')
        lines = receive(0.08)
        states = [x for x in lines if x.startswith('STATE ')]
        if states:
            return states[-1]
    raise AssertionError('No STATUS response')

def require(*parts):
    line = state()
    assert all(part in line for part in parts), (parts, line)
    return line

def arm():
    send('ARM')
    receive(0.04)

dry_confirmed = False
try:
    receive(0.1)
    require('MODE=DRY', 'STATE BOOT')
    dry_confirmed = True
    send('CHECK'); receive()
    send('HOLD'); receive(0.25)
    require('STATE DISARMED', 'GOAL=0,0')
    send('VEL 0.02 0'); receive()
    require('STATE DISARMED', 'GOAL=0,0')
    arm(); send('VEL 0.048 -0.048'); receive(0.03)
    require('STATE ARMED', 'GOAL=2,-2')
    # Bad second values cannot partly apply the valid first value.
    send('VEL 0 nan'); receive(0.02)
    require('GOAL=2,-2')
    receive(0.5)
    require('STATE DISARMED', 'GOAL=0,0')
    print('PASS pair validation and silence timeout')

    for label, bad in [('invalid stream', 'VEL 0 nan'),
                       ('STATUS stream', 'STATUS')]:
        arm()
        until = time.monotonic() + 0.7
        while time.monotonic() < until:
            send(bad); receive(0.045)
        require('STATE DISARMED', 'GOAL=0,0')
        print('PASS', label, 'does not refresh command timer')

    arm()
    for _ in range(4):
        send('ARM'); receive(0.04)
    receive(0.4)
    require('STATE DISARMED', 'GOAL=0,0')
    print('PASS ARM while armed does not renew timer')

    arm(); s.write(b'VEL 0.02 0'); receive(0.7)
    s.write(b'\n'); receive()
    require('STATE DISARMED', 'GOAL=0,0')
    arm(); s.write(b'x' * 100); receive(0.7)
    s.write(b'\n'); receive()
    require('STATE DISARMED', 'GOAL=0,0')
    print('PASS incomplete/oversized input and parser recovery')

    arm(); send('VEL 0.024 0.024'); receive(0.03)
    send('STOP'); receive(0.16)
    require('STATE ARMED', 'GOAL=0,0')
    send('DISARM'); receive(0.2)
    require('STATE DISARMED', 'GOAL=0,0')
    send('SUPPORTED_OFF'); receive()
    print('ALL TWO-AXIS DRY CHECKS PASSED')
finally:
    if dry_confirmed and s.is_open:
        s.write(b'DISARM\n')
    s.close()
