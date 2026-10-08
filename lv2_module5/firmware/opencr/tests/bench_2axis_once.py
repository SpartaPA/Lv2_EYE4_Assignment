#!/usr/bin/env python3
"""Explicit LIVE one-shot, not a ROS bridge. Firmware initializes automatically; requires physically supported camera.
Never disables torque automatically; user must support then SUPPORTED_OFF.
"""
import argparse
import time
import serial

p = argparse.ArgumentParser()
p.add_argument('--port', required=True)
p.add_argument('--execute-live', action='store_true')
p.add_argument('--case', required=True, choices=[
    'zero', 'pan-left', 'pan-right', 'tilt-up', 'tilt-down', 'both'])
a = p.parse_args()
if not a.execute_live:
    p.error('This intentionally moves hardware; --execute-live is required')
pairs = {'zero': (0, 0), 'pan-left': (.024, 0), 'pan-right': (-.024, 0),
         'tilt-up': (0, -.024), 'tilt-down': (0, .024), 'both': (-.024, .024)}
s = serial.Serial(a.port, 115200, timeout=.02, write_timeout=.2)
start = time.monotonic()

def send(cmd):
    print(f'{time.monotonic()-start:.3f} > {cmd}', flush=True)
    s.write((cmd+'\n').encode())

def read_for(seconds):
    rows = []
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        row = s.readline().decode(errors='replace').strip()
        if row:
            print(f'{time.monotonic()-start:.3f} < {row}', flush=True)
            rows.append(row)
    return rows

attempted_command = False
try:
    read_for(.1)
    send('STATUS')
    rows = read_for(.1)
    assert any('STATE READY' in r and 'TORQUE=1,1' in r and 'GOAL=0,0' in r
               for r in rows), 'Automatic initial check/hold not ready'
    attempted_command = True
    pan, tilt = pairs[a.case]
    send(f'VEL {pan:.3f} {tilt:.3f}')
    # No keepalive: exercise the 500 ms board command timeout.
    read_for(1.0)
    send('STATUS')
    rows = read_for(.15)
    assert any('STATE READY' in r and 'GOAL=0,0' in r
               and 'VEL=0,0' in r and 'TORQUE=1,1' in r for r in rows), \
        'Zero/retained-torque feedback not confirmed'
    print('PASS reported timeout end-state; verify physical stop separately')
finally:
    if attempted_command and s.is_open:
        send('STOP')
        read_for(.2)
    s.close()
    print('Support camera, reconnect miniterm, then SUPPORTED_OFF. Torque may remain ON.')
