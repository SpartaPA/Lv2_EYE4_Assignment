"""DRY-board-only asynchronous bridge; no automatic prepare, arm, or reconnect."""
import math
import os
import re
import termios
import time
import tty


class PosixSerial:
    """Linux/Pi transport: nonblocking 115200 8N1 with exclusive ownership."""
    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            termios.tcgetattr(self.fd)
            if hasattr(termios, 'TIOCEXCL'):
                import fcntl
                fcntl.ioctl(self.fd, termios.TIOCEXCL)
            tty.setraw(self.fd)
            attrs = termios.tcgetattr(self.fd)
            attrs[2] |= termios.CLOCAL | termios.CREAD
            attrs[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE)
            attrs[2] |= termios.CS8
            if hasattr(termios, 'CRTSCTS'):attrs[2] &= ~termios.CRTSCTS
            attrs[4] = attrs[5] = termios.B115200
            termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
            termios.tcflush(self.fd, termios.TCIOFLUSH)
        except Exception:
            os.close(self.fd);self.fd = None;raise

    def read(self):
        try:
            data = os.read(self.fd, 4096)
            if not data:raise OSError('Serial peer closed')
            return data
        except BlockingIOError:return b''

    def write(self, data):
        if os.write(self.fd, data) != len(data):raise OSError('Partial serial write')

    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd = None


PATTERN = re.compile(
    r'^STATE (BOOT|READY|STOPPING|DISARMED|ARMED|FAULT) MODE=(DRY|LIVE) '
    r'ARMED=([01]) GOAL=(-?\d+),(-?\d+) POS=(-?\d+),(-?\d+) '
    r'VEL=(-?\d+),(-?\d+) TORQUE=([01]),([01]) AGE_MS=(\d+) T_MS=(\d+)$')


def parse_state(line):
    match = PATTERN.fullmatch(line)
    if not match:raise ValueError('Malformed STATE response')
    v = match.groups()
    return dict(state=v[0], mode=v[1], armed=int(v[2]),
                goal=(int(v[3]), int(v[4])), pos=(int(v[5]), int(v[6])),
                vel=(int(v[7]), int(v[8])), torque=(int(v[9]), int(v[10])),
                age_ms=int(v[11]), t_ms=int(v[12]))


class SerialBridge:
    """Tick from a 10 ms timer. Every VEL/STOP uses a new, fresh ROS message."""
    COMMAND_AGE = 0.15
    ACK_TIMEOUT = 0.20
    STATUS_PERIOD = 0.10
    STATUS_MAX_AGE = 0.40

    def __init__(self, transport, log=None, clock=time.monotonic):
        self.transport=transport;self.clock=clock;self.log=log or (lambda *args:None)
        self.phase='CONNECTING';self.reason='';self.board=None;self.mode_verified=False
        self.pending=None;self.buffer=b'';self.last_status=None;self.last_poll=0.0
        self.last_stamp=None;self.latest=None;self.sequence=0;self.sent_sequence=0
        self.stopping=False;self.previous_goal=(0,0);self.closed=False
        self.phase_deadline=None
        self.send('STATUS', 'STATUS')

    def emit(self, direction, line):self.log(self.clock(), direction, line)

    def send(self, command, expected, timeout=None):
        if self.closed:return False
        if self.pending:raise RuntimeError('Only one outstanding transaction permitted')
        try:self.transport.write((command+'\n').encode('ascii'))
        except (OSError, termios.error) as exc:
            self.fail('TRANSPORT_WRITE: '+str(exc), try_stop=False);return False
        self.emit('TX',command)
        self.pending=(expected,self.clock()+(timeout or self.ACK_TIMEOUT))
        if expected=='STATUS':self.last_poll=self.clock()
        return True

    def fail(self, reason, try_stop=True):
        if self.phase=='FAULT':return
        self.phase='FAULT';self.reason=reason;self.pending=None;self.latest=None
        self.emit('FAULT',reason)
        # Best effort once, never repeat a nonzero command or auto-enable torque.
        if try_stop and self.mode_verified and not self.closed:
            try:
                self.transport.write(b'DISARM\n');self.emit('TX','DISARM')
            except (OSError, termios.error):pass

    def receive_command(self, stop, pan, tilt, stamp_ns, ros_now_ns):
        age=(ros_now_ns-stamp_ns)/1e9
        valid=all(math.isfinite(v) and abs(v)<=0.05+1e-8 for v in (pan,tilt))
        ordered=self.last_stamp is None or stamp_ns>self.last_stamp
        if self.phase=='FAULT':return False
        if not valid or stamp_ns<=0 or not 0<=age<=self.COMMAND_AGE or not ordered:
            self.latest=None
            if self.phase in ('ARMING','VERIFY_ARM','ARMED','DISARMING'):self.fail('INVALID_OR_STALE_COMMAND')
            self.emit('REJECT','INVALID_OR_STALE_COMMAND');return False
        self.last_stamp=stamp_ns;self.sequence+=1
        # Account for both receipt age and source age even without newer callbacks.
        deadline=self.clock()+min(self.COMMAND_AGE,self.COMMAND_AGE-age)
        self.latest=(bool(stop),max(-.05,min(.05,pan)),max(-.05,min(.05,tilt)),deadline,self.sequence)
        return True

    def prepare(self):
        if self.phase!='BOOT':return False,'Requires a fresh DRY BOOT; reset firmware first'
        self.phase='CHECKING';self.phase_deadline=self.clock()+0.8
        self.send('CHECK','CHECK',0.6);return True,'CHECK/HOLD requested; wait for READY status'

    def arm(self):
        if self.phase!='READY' or self.pending:return False,'Requires READY with no outstanding transaction'
        if not self.latest or self.latest[0] or self.clock()>=self.latest[3]:
            return False,'Requires a fresh stop=false ROS command; no automatic ARM'
        self.phase='ARMING';self.phase_deadline=self.clock()+0.4
        self.send('ARM','ARM');return True,'ARM requested; wait for ARMED confirmation'

    def disarm(self):
        if self.phase not in ('ARMED','ARMING','READY'):return False,'Not in a disarmable session'
        # Stop requests preempt outstanding ACKs; never use those ACKs to re-arm.
        self.pending=None;self.phase='DISARMING';self.phase_deadline=self.clock()+0.7
        self.send('DISARM','DISARM');return True,'DISARM requested; torque retained by firmware'

    def on_state(self, line):
        try:board=parse_state(line)
        except ValueError:self.fail('MALFORMED_STATE');return
        if board['mode']!='DRY':self.fail('MODE_MISMATCH: only DRY firmware supported',try_stop=False);return
        if self.board and board['t_ms']<self.board['t_ms'] and self.board['t_ms']-board['t_ms']<2**31:
            self.fail('BOARD_REBOOT');return
        self.mode_verified=True;self.board=board;self.last_status=self.clock()
        if board['state']=='FAULT':self.fail('BOARD_FAULT: original reason may be unavailable');return
        status_response = bool(self.pending and self.pending[0]=='STATUS')
        if status_response:self.pending=None
        if self.phase=='CONNECTING':
            if board['state']!='BOOT' or board['armed'] or board['torque']!=(0,0):
                self.fail('STARTUP_NOT_BOOT: reset board, no session adoption');return
            self.phase='BOOT'
        elif self.phase=='VERIFY_READY':
            if board['state']=='DISARMED' and not board['armed'] and board['goal']==(0,0) and board['vel']==(0,0) and board['torque']==(1,1):
                self.phase='READY';self.phase_deadline=None
            else:self.fail('HOLD_NOT_CONFIRMED')
        elif self.phase=='VERIFY_ARM':
            if board['state']=='ARMED' and board['armed'] and board['torque']==(1,1):
                self.phase='ARMED';self.phase_deadline=None
            else:self.fail('ARM_NOT_CONFIRMED')
        elif self.phase=='VERIFY_DISARM':
            if board['state']=='DISARMED' and not board['armed'] and board['goal']==(0,0) and board['vel']==(0,0):
                self.phase='READY';self.phase_deadline=None;self.previous_goal=(0,0)
            else:self.fail('DISARM_NOT_CONFIRMED')
        elif self.phase=='ARMED':
            if not board['armed']:self.fail('BOARD_DISARMED');return
        # A STOPPED event can belong to an earlier STOP. Only a newer,
        # solicited STATUS proves the current stopping cycle has completed.
        if self.phase=='ARMED':
            if board['state']=='STOPPING':self.stopping=True
            elif status_response and board['state']=='ARMED' and board['goal']==(0,0) and board['vel']==(0,0):
                self.stopping=False;self.previous_goal=(0,0)
        if self.phase in ('READY','ARMED') and board['age_ms']>100:
            self.fail('STALE_BOARD_FEEDBACK')

    def on_line(self, line):
        self.emit('RX',line)
        if self.phase=='FAULT':return
        if line.startswith('FAULT '):self.fail('BOARD_'+line);return
        if line.startswith('EVENT TIMEOUT') or line.startswith('EVENT LIMIT'):
            self.fail('BOARD_'+line);return
        if line.startswith('STATE '):self.on_state(line);return
        if line.startswith('ERR '):self.fail('BOARD_'+line);return
        if line=='EVENT STOPPED TORQUE_RETAINED':
            # Do not unlock normal VEL here: this event may predate a newer STOP.
            if self.phase=='WAIT_HOLD':
                self.phase='VERIFY_READY';self.pending=None;self.send('STATUS','STATUS')
            elif self.phase=='WAIT_DISARM':
                self.phase='VERIFY_DISARM';self.pending=None;self.send('STATUS','STATUS')
            return
        if not self.pending:return
        expected=self.pending[0]
        if expected=='CHECK' and line=='CHECK_OK BOTH_TORQUES_OFF':
            self.pending=None;self.phase='HOLDING';self.send('HOLD','HOLD');return
        if expected=='HOLD' and line=='ACK HOLD ZERO_REQUESTED':
            self.pending=None;self.phase='WAIT_HOLD';self.phase_deadline=self.clock()+0.65;return
        if expected=='ARM' and line=='ACK ARM':
            self.pending=None;self.phase='VERIFY_ARM';self.send('STATUS','STATUS');return
        if expected=='DISARM' and line=='ACK DISARM ZERO_REQUESTED':
            self.pending=None;self.phase='WAIT_DISARM';return
        if expected=='VEL' and line=='ACK VEL':self.pending=None;return
        if expected=='STOP' and line=='ACK STOP ZERO_REQUESTED':
            self.stopping=True;self.pending=None;return
        if line.startswith('ACK ') or line.startswith('CHECK_OK '):
            self.emit('IGNORED','Unmatched acknowledgement; no state advance')

    def tick(self):
        if self.closed or self.phase=='FAULT':return
        try:data=self.transport.read()
        except (OSError,termios.error) as exc:self.fail('TRANSPORT_READ: '+str(exc));return
        self.buffer+=data
        if len(self.buffer)>4096:self.fail('SERIAL_BUFFER_OVERFLOW');return
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            if len(line)>512:self.fail('SERIAL_LINE_OVERFLOW');return
            try:text=line.rstrip(b'\r').decode('ascii')
            except UnicodeDecodeError:self.fail('NON_ASCII_SERIAL');return
            self.on_line(text)
            if self.phase=='FAULT':return
        now=self.clock()
        if self.phase_deadline and now>=self.phase_deadline:self.fail('SESSION_TRANSITION_TIMEOUT');return
        if self.phase in ('ARMING','VERIFY_ARM','ARMED'):
            if not self.latest or now>=self.latest[3]:self.fail('ROS_COMMAND_TIMEOUT');return
        if self.last_status is not None and now-self.last_status>=self.STATUS_MAX_AGE:
            self.fail('STATUS_TIMEOUT');return
        if self.pending:
            if now>=self.pending[1]:self.fail('RESPONSE_TIMEOUT: '+self.pending[0])
            return
        if self.phase in ('WAIT_HOLD','WAIT_DISARM'):return
        if self.mode_verified and now-self.last_poll>=(0.02 if self.stopping else self.STATUS_PERIOD):
            self.send('STATUS','STATUS');return
        if self.phase=='ARMED' and self.latest and self.latest[4]!=self.sent_sequence:
            stop,pan,tilt,deadline,sequence=self.latest
            if now>=deadline:self.fail('ROS_COMMAND_TIMEOUT');return
            self.sent_sequence=sequence
            if self.stopping:
                # Repeating STOP restarts the board's completion window.
                # Poll STATUS above; never send VEL until completion is confirmed.
                return
            if stop:
                self.stopping=True;self.send('STOP','STOP')
            else:
                next_goal=(int(math.floor(abs(pan)/.0239808239+.5))* (1 if pan>=0 else -1),
                           int(math.floor(abs(tilt)/.0239808239+.5))* (1 if tilt>=0 else -1))
                if next_goal==(0,0) and self.previous_goal!=(0,0):self.stopping=True
                self.previous_goal=next_goal
                self.send(f'VEL {pan:.6f} {tilt:.6f}','VEL')
            return
        if self.mode_verified and now-self.last_poll>=(0.02 if self.stopping else self.STATUS_PERIOD):
            self.send('STATUS','STATUS')
        if self.last_status is not None and now-self.last_status>=self.STATUS_MAX_AGE:
            self.fail('STATUS_TIMEOUT')

    def snapshot(self):
        return dict(phase=self.phase,reason=self.reason,serial_opened=not self.closed,
                    expected_mode='DRY',board=self.board,
                    board_receipt_age_sec=None if self.last_status is None else self.clock()-self.last_status)

    def close(self):
        if self.closed:return
        if self.mode_verified:
            try:self.transport.write(b'DISARM\n');self.emit('TX','DISARM')
            except (OSError,termios.error):pass
        self.transport.close();self.closed=True
