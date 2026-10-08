import unittest
from realsense_tracker.control_core import Controller, MAX_VELOCITY_RAD_S

class CoreTests(unittest.TestCase):
    def frames(self,c,x=0.4,y=0,z=0.1,start=1.0,count=3):
        for i in range(count):
            now=start+i*0.05;c.receive(x,y,z,int(now*1e9),int(now*1e9),now)
        return now
    def test_seven_inputs(self):
        for x,y,p,t in [(0,0,0,0),(.4,0,-.04,0),(-.4,0,.04,0),(0,.4,0,.04),(0,-.4,0,-.04)]:
            c=Controller();now=self.frames(c,x,y);stop,a,b=c.output(now,int(now*1e9))
            self.assertFalse(stop);self.assertAlmostEqual(a,p);self.assertAlmostEqual(b,t)
        c=Controller();self.frames(c);c.receive(0,0,0,1200000000,1200000000,1.2)
        self.assertEqual(c.output(1.2,1200000000),(True,0,0));self.assertEqual(c.state,'LOST')
        c=Controller();self.frames(c);self.assertEqual(c.output(1.7,1700000000),(True,0,0))
        self.assertEqual(c.state,'LOST')
    def test_direction_parameters(self):
        c=Controller(pan_direction=1,tilt_direction=-1);now=self.frames(c,.4,.4)
        stop,pan,tilt=c.output(now,int(now*1e9));self.assertFalse(stop)
        self.assertAlmostEqual(pan,.04);self.assertAlmostEqual(tilt,-.04)
        with self.assertRaises(ValueError):Controller(pan_direction=0)
        with self.assertRaises(ValueError):Controller(tilt_direction=2)
    def test_recovery_after_silence(self):
        c=Controller();self.frames(c)
        self.frames(c,start=2,count=1);self.assertEqual(c.state,'LOST')
        self.frames(c,start=2.05,count=1);self.assertEqual(c.state,'LOST')
        self.frames(c,start=2.1,count=1);self.assertEqual(c.state,'TRACKING')
    def test_stale_duplicate_invalid_and_future(self):
        for args in [(0.4,0,.1,500000000,1200000000,1.2),
                     (0.4,0,.1,1100000000,1200000000,1.2),
                     (float('nan'),0,.1,1200000000,1200000000,1.2),
                     (0.4,0,.1,1300000000,1200000000,1.2)]:
            c=Controller();self.frames(c);c.receive(*args);self.assertEqual(c.state,'LOST')
    def test_deadband_clamp_and_initial_state(self):
        c=Controller();self.assertEqual(c.output(0,0),(True,0,0));self.assertEqual(c.state,'IDLE')
        now=self.frames(c,.02,-.02);self.assertEqual(c.output(now,int(now*1e9)),(False,0,0))
        now=self.frames(c,1,-1,start=1.2);self.assertEqual(c.output(now,int(now*1e9)),(False,-.05,-.05))
    def test_source_stamp_expires_even_if_receipt_recent(self):
        c=Controller()
        for i in range(3):
            now=1.0+i*.05
            c.receive(.4,0,.1,int((now-.4)*1e9),int(now*1e9),now)
        self.assertEqual(c.state,'TRACKING')
        self.assertEqual(c.output(1.21,1210000000),(True,0,0))

    def test_per_axis_limits_and_deadbands(self):
        c=Controller(pan_speed_limit=.02,tilt_speed_limit=.05,pan_deadband=.1,tilt_deadband=0)
        now=self.frames(c,.05,1);self.assertEqual(c.output(now,int(now*1e9)),(False,0,.05))
        now=self.frames(c,-1,.05,start=1.2);stop,pan,tilt=c.output(now,int(now*1e9))
        self.assertAlmostEqual(pan,.02);self.assertAlmostEqual(tilt,.005)
    def test_speed_limit_cannot_exceed_firmware_ceiling(self):
        with self.assertRaises(ValueError):Controller(pan_speed_limit=MAX_VELOCITY_RAD_S+.01)
        with self.assertRaises(ValueError):Controller(tilt_speed_limit=0)
    def test_explicit_disable_is_idle_and_needs_three_frames(self):
        c=Controller();self.frames(c);self.assertEqual(c.state,'TRACKING')
        c.set_enabled(False);self.assertEqual(c.output(1.11,1110000000),(True,0,0))
        self.frames(c,start=1.15,count=3);self.assertEqual(c.state,'IDLE')
        self.assertEqual(c.output(2.0,2000000000),(True,0,0));self.assertEqual(c.state,'IDLE')
        c.set_enabled(True);self.frames(c,start=2.0,count=2);self.assertNotEqual(c.state,'TRACKING')
        self.frames(c,start=2.1,count=1);self.assertEqual(c.state,'TRACKING')

if __name__=='__main__':unittest.main()
