"""Pi USB Serial transport와 명령 검증. 모드 선택·prepare/arm 세션은 없다.
새 ROS 명령만 1회 전송한다. timeout은 STOP하고, 새 fresh 명령으로만 복구한다.
Serial/보드 하드웨어 오류는 종료 대상이며 자동 재연결하지 않는다.
"""
import math
import os
import re
import time
try:
    import termios
    import tty
    SERIAL_ERRORS = (OSError, termios.error)
except ImportError:  # Windows에서는 fake transport를 사용하는 단위 시험만 가능
    termios = tty = None
    SERIAL_ERRORS = (OSError,)
from .control_core import MAX_VELOCITY_RAD_S

class PosixSerial:
    """Linux/Pi transport: nonblocking 8N1 with exclusive ownership. baudrate = opencr_node baud."""
    def __init__(self, path, baudrate=115200):
        if termios is None:raise OSError('POSIX serial (termios) is required; run on Linux/Raspberry Pi')
        speed = getattr(termios, f'B{int(baudrate)}', None)
        if speed is None:raise ValueError(f'Unsupported serial baudrate: {baudrate}')
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
            attrs[4] = attrs[5] = speed
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
    r'^STATE (BOOT|READY|STOPPING|FAULT) GOAL=(-?\d+),(-?\d+) POS=(-?\d+),(-?\d+) '
    r'VEL=(-?\d+),(-?\d+) TORQUE=([01]),([01]) AGE_MS=(\d+) T_MS=(\d+)$')


def parse_state(line):
    match = PATTERN.fullmatch(line)
    if not match:
        raise ValueError('Malformed STATE response')
    v = match.groups()
    return dict(state=v[0], goal=(int(v[1]), int(v[2])), pos=(int(v[3]), int(v[4])),
                vel=(int(v[5]), int(v[6])), torque=(int(v[7]), int(v[8])),
                age_ms=int(v[9]), t_ms=int(v[10]))


class SerialBridge:
    COMMAND_AGE = 0.5
    STATUS_PERIOD = 0.1  # 상태 조회 주기이며 안전정지 timeout이 아니다.
    STARTUP_TIMEOUT = 3.0  # 기존 실측: 초기 모터 확인 약 1.25초. 시작 시에만 적용.

    def __init__(self, transport, log=None, clock=time.monotonic, command_timeout_sec=0.5):
        if not math.isfinite(command_timeout_sec) or command_timeout_sec <= 0:
            raise ValueError('command_timeout_sec must be finite and positive')
        self.transport, self.clock = transport, clock
        self.log = log or (lambda *args: None)
        self.COMMAND_AGE = command_timeout_sec
        self.closed = False
        self.reason = ''
        self.board = None
        self.buffer = b''
        self.last_stamp = self.deadline = self.last_status = None
        self.started = self.clock()
        self.last_poll = self.started
        self.timed_out = True
        self.send('STOP')  # 연결 즉시 이전 동작 STOP. 아직 non-zero는 보내지 않음.
        self.send('STATUS')

    def emit(self, direction, line):
        self.log(self.clock(), direction, line)

    def send(self, line):
        if self.closed or self.reason:
            return False
        try:
            self.transport.write((line + '\n').encode('ascii'))
        except SERIAL_ERRORS as exc:
            self.fail('TRANSPORT_WRITE: ' + str(exc))
            return False
        self.emit('TX', line)
        return True

    def stop(self):
        self.deadline = None
        self.timed_out = True
        self.send('STOP')

    def fail(self, reason):
        if self.reason:
            return
        self.reason = reason
        self.deadline = None
        self.emit('ERROR', reason)
        # Serial 장애에도 한 번 STOP을 시도. 전달 불가 시 board watchdog이 정지한다.
        try:
            self.transport.write(b'STOP\n')
            self.emit('TX', 'STOP')
        except SERIAL_ERRORS:
            pass

    def receive_command(self, stop, pan, tilt, stamp_ns, ros_now_ns):
        if self.closed or self.reason:
            return False
        age = (ros_now_ns - stamp_ns) / 1e9
        ordered = self.last_stamp is None or stamp_ns > self.last_stamp
        valid = (all(math.isfinite(v) for v in (pan, tilt)) and stamp_ns > 0
                 and 0 <= age < self.COMMAND_AGE and ordered)
        if not valid:
            self.emit('REJECT', 'INVALID_OR_STALE_COMMAND')
            self.stop()
            return False
        self.last_stamp = stamp_ns
        # 시작 대기 중 명령은 저장하지 않는다. 준비 후 새로운 fresh 명령만 적용.
        if not self.board or self.board['state'] == 'BOOT':
            return False
        limit = MAX_VELOCITY_RAD_S
        pan, tilt = (max(-limit, min(limit, v)) for v in (pan, tilt))
        line = 'STOP' if stop else f'VEL {pan:.6f} {tilt:.6f}'
        if not self.send(line):
            return False
        # 새 유효 명령마다 갱신. 20 Hz에서는 0.5초마다 모터가 멈추는 뜻이 아니다.
        self.deadline = self.clock() + self.COMMAND_AGE - age
        self.timed_out = False
        return True

    def on_line(self, line):
        self.emit('RX', line)
        if line.startswith('FAULT ') or line.startswith('ERR '):
            self.fail('BOARD_' + line)
        elif line.startswith('STATE '):
            try:
                board = parse_state(line)
            except ValueError:
                self.fail('MALFORMED_STATE')
                return
            if board['state'] == 'FAULT':
                self.fail('BOARD_FAULT')
                return
            if self.board and board['t_ms'] < self.board['t_ms'] and self.board['t_ms'] - board['t_ms'] < 2**31:
                self.fail('BOARD_REBOOT')
                return
            if board['state'] != 'BOOT' and (board['age_ms'] >= 500 or board['torque'] != (1, 1)):
                self.fail('INVALID_BOARD_FEEDBACK')
                return
            self.board, self.last_status = board, self.clock()
        # ACK / EVENT TIMEOUT / LIMIT를 구동 허가로 사용하지 않는다.
        # watchdog/경계 STOP 후에도 다음 fresh 명령만 전송한다.

    def tick(self):
        if self.closed or self.reason:
            return
        try:
            self.buffer += self.transport.read()
        except SERIAL_ERRORS as exc:
            self.fail('TRANSPORT_READ: ' + str(exc))
            return
        if len(self.buffer) > 4096:
            self.fail('SERIAL_BUFFER_OVERFLOW')
            return
        while b'\n' in self.buffer:
            raw, self.buffer = self.buffer.split(b'\n', 1)
            try:
                if len(raw) > 512:
                    raise ValueError('long line')
                self.on_line(raw.rstrip(b'\r').decode('ascii'))
            except (UnicodeDecodeError, ValueError):
                self.fail('INVALID_SERIAL_LINE')
            if self.reason:
                return
        now = self.clock()
        if self.deadline is not None and now >= self.deadline and not self.timed_out:
            self.emit('STOP', 'ROS_COMMAND_TIMEOUT')
            self.stop()  # timeout은 latch하지 않는다. 저장한 속도를 다시 보내지 않는다.
        if self.board is None or self.board['state'] == 'BOOT':
            if now - self.started >= self.STARTUP_TIMEOUT:
                self.fail('BOARD_STARTUP_TIMEOUT')
                return
        elif self.last_status is not None and now - self.last_status >= 0.5:
            self.fail('STATUS_TIMEOUT')
            return
        if now - self.last_poll >= self.STATUS_PERIOD:
            self.last_poll = now
            self.send('STATUS')  # STATUS는 펌웨어 command watchdog을 갱신하지 않는다.

    def snapshot(self):
        return dict(serial_opened=not self.closed, reason=self.reason,
                    timed_out=self.timed_out, board=self.board)

    def close(self):
        if self.closed:
            return
        try:
            self.transport.write(b'STOP\n')
            self.emit('TX', 'STOP')
        except SERIAL_ERRORS:
            pass
        finally:
            self.transport.close()
            self.closed = True
