#!/usr/bin/env python3
"""Serial checks for explicit no-motor-output test firmware only; motor power OFF."""
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

# This test MUST use a no-output build and motor power OFF. Never run on normal firmware.
dry_confirmed = False
try:
    send('TEST_STATUS')
    assert 'TEST_ONLY NO_MOTOR_OUTPUT' in receive(.2), 'Upload the explicit no-output test build first'
    dry_confirmed = True
    receive(.15)
    require('STATE READY', 'GOAL=0,0')
    send('VEL .048 -.048'); receive(.03)
    require('GOAL=2,-2')
    send('VEL 0 nan'); receive(.03)
    require('GOAL=0,0')
    receive(.15)
    send('VEL .048 0'); receive(.6)
    require('GOAL=0,0')
    send('VEL -.048 0'); receive(.03)
    require('GOAL=-2,0')
    send('STOP'); receive(.15)
    require('GOAL=0,0')
    for text in ['VEL .01 inf', 'VEL .01 0 junk', 'x'*100]:
        send(text);receive(.15);require('GOAL=0,0')
    print('ALL TWO-AXIS DRY CHECKS PASSED')
finally:
    if dry_confirmed and s.is_open:
        s.write(b'STOP\n')
    s.close()
