"""새 Serial runtime: fresh 명령/자동 STOP/복구/고장 종료. 실제 모터 없음."""
import unittest
from realsense_tracker.serial_core import SerialBridge, parse_state


def state(name='READY', goal='0,0', age=0, t=10):
    return f'STATE {name} GOAL={goal} POS=3078,4096 VEL=0,0 TORQUE=1,1 AGE_MS={age} T_MS={t}'


class Fake:
    def __init__(self):
        self.rx = b''; self.tx = []; self.closed = False
    def read(self):
        data = self.rx; self.rx = b''; return data
    def write(self, data):
        self.tx.append(data.decode().strip())
    def close(self):
        self.closed = True


class SerialTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.; self.io = Fake(); self.logs = []
        self.bridge = SerialBridge(self.io, lambda *r: self.logs.append(r), lambda: self.now)
    def line(self, text):
        self.io.rx += (text+'\n').encode(); self.bridge.tick()
    def command(self, p=.04, t=0, stop=False, stamp=1_000_000_000, age=0):
        return self.bridge.receive_command(stop, p, t, stamp, stamp+int(age*1e9))
    def ready(self):
        self.line(state())

    def test_startup_stop_and_no_session_or_cached_motion(self):
        self.assertEqual(self.io.tx, ['STOP', 'STATUS'])
        self.assertFalse(self.command())
        self.ready(); self.bridge.tick()
        self.assertFalse(any(x.startswith('VEL') for x in self.io.tx))
        self.assertTrue(self.command(-.04,.04,stamp=2_000_000_000))
        self.assertEqual(self.io.tx[-1], 'VEL -0.040000 0.040000')
        self.assertFalse(any(x in self.io.tx for x in ['ARM','CHECK','HOLD','DISARM']))

    def test_twenty_hz_keeps_motion_beyond_half_second(self):
        self.ready()
        for i in range(40):
            self.now += .05
            self.line(state(t=10+i))
            self.assertTrue(self.command(stamp=1_000_000_000+i*50_000_000))
            self.bridge.tick()
        self.assertFalse(self.bridge.timed_out)
        self.assertEqual(sum(x.startswith('VEL') for x in self.io.tx),40)

    def test_timeout_boundary_and_fresh_recovery_no_replay(self):
        self.ready(); self.command()
        self.now += .499; self.line(state(t=11))
        self.assertFalse(self.bridge.timed_out)
        self.now += .0011; self.line(state(t=12))
        self.assertTrue(self.bridge.timed_out)
        count = sum(x.startswith('VEL') for x in self.io.tx)
        self.bridge.tick(); self.bridge.tick()
        self.assertEqual(sum(x.startswith('VEL') for x in self.io.tx),count)
        self.assertFalse(self.command())  # 이전 stamp 재사용 금지
        self.assertTrue(self.command(-.02,.02,stamp=2_000_000_000))
        self.assertFalse(self.bridge.timed_out)
        self.assertEqual(self.io.tx[-1],'VEL -0.020000 0.020000')

    def test_source_age_shortens_receipt_deadline(self):
        self.ready(); self.command(age=.4)
        self.now += .101; self.line(state(t=11))
        self.assertTrue(self.bridge.timed_out)

    def test_nan_inf_stale_duplicate_and_future_stop(self):
        for p,t,stamp,age in [(float('nan'),0,2_000_000_000,0),
                              (0,float('inf'),2_000_000_000,0),
                              (.04,0,2_000_000_000,.5),(.04,0,1_000_000_000,0),
                              (.04,0,2_000_000_000,-.1),(.04,0,0,0)]:
            self.setUp(); self.ready(); self.command()
            self.assertFalse(self.command(p,t,stamp=stamp,age=age))
            self.assertEqual(self.io.tx[-1],'STOP')
            self.assertTrue(self.bridge.timed_out)
            self.assertEqual(self.bridge.reason,'')

    def test_clamp_and_stop_priority(self):
        self.ready(); self.command(1,-1)
        self.assertEqual(self.io.tx[-1],'VEL 0.050000 -0.050000')
        self.command(1,1,stop=True,stamp=2_000_000_000)
        self.assertEqual(self.io.tx[-1],'STOP')

    def test_board_watchdog_and_limit_do_not_replay(self):
        self.ready(); self.command()
        for line in ['EVENT TIMEOUT ZERO_REQUESTED','EVENT LIMIT ZERO_REQUESTED']:
            count=len(self.io.tx); self.line(line)
            self.assertEqual(len(self.io.tx),count)
            self.assertEqual(self.bridge.reason,'')
        self.command(-.04,stamp=2_000_000_000)
        self.assertEqual(self.io.tx[-1],'VEL -0.040000 0.000000')

    def test_fragmented_and_malformed_state(self):
        raw=(state()+'\n').encode(); self.io.rx=raw[:20]; self.bridge.tick()
        self.assertIsNone(self.bridge.board)
        self.io.rx=raw[20:]; self.bridge.tick()
        self.assertEqual(self.bridge.board['state'],'READY')
        self.line('STATE broken'); self.assertEqual(self.bridge.reason,'MALFORMED_STATE')

    def test_status_timeout_and_startup_timeout(self):
        self.ready(); self.now+=.501; self.bridge.tick()
        self.assertEqual(self.bridge.reason,'STATUS_TIMEOUT')
        self.setUp(); self.now+=3.01; self.bridge.tick()
        self.assertEqual(self.bridge.reason,'BOARD_STARTUP_TIMEOUT')

    def test_board_reboot_fault_and_bad_feedback(self):
        for line in [state(t=1), state(age=500),'FAULT READ SUPPORT_CAMERA',state('FAULT')]:
            self.setUp();self.ready();self.line(line)
            self.assertTrue(self.bridge.reason)
            self.assertFalse(self.command())
            self.assertEqual(self.io.tx[-1],'STOP')

    def test_transport_disconnect_and_write_failure_no_reconnect(self):
        self.ready()
        def broken(*args):raise OSError('disconnected')
        self.io.read=broken;self.bridge.tick()
        self.assertIn('TRANSPORT_READ',self.bridge.reason)
        self.assertFalse(self.command())
        self.setUp();self.ready();self.io.write=broken
        self.assertFalse(self.command());self.assertIn('TRANSPORT_WRITE',self.bridge.reason)

    def test_close_stops_without_torque_release(self):
        self.ready();self.command();self.bridge.close();self.bridge.close()
        self.assertTrue(self.io.closed);self.assertEqual(self.io.tx[-1],'STOP')
        self.assertNotIn('SUPPORTED_OFF',self.io.tx)

    def test_oversized_non_ascii_and_invalid_timeout(self):
        for data in [b'x'*4097,b'\xff\n',b'x'*513+b'\n']:
            self.setUp();self.io.rx=data;self.bridge.tick();self.assertTrue(self.bridge.reason)
        for value in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):SerialBridge(Fake(),command_timeout_sec=value)
        self.assertEqual(parse_state(state())['pos'],(3078,4096))

if __name__=='__main__':unittest.main()
