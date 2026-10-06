"""Pure control logic. No ROS, serial, board, or DYNAMIXEL access."""
import math

class Controller:
    def __init__(self, kp_pan=0.1, kp_tilt=0.1, limit=0.05, deadband=0.03,
                 timeout=0.5, recovery_frames=3):
        values=(kp_pan,kp_tilt,limit,deadband,timeout)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Parameters must be finite')
        if min(kp_pan,kp_tilt)<0 or not 0<limit<=0.05 or not 0<=deadband<1 or timeout<=0 or recovery_frames<1:
            raise ValueError('Invalid control parameters')
        self.kp_pan,self.kp_tilt,self.limit=kp_pan,kp_tilt,limit
        self.deadband,self.timeout,self.recovery_frames=deadband,timeout,recovery_frames
        self.state='IDLE';self.count=0;self.last_received=None
        self.last_stamp=None;self.frame_stamp=None;self.xy=(0.0,0.0)

    def lose(self):
        self.state='LOST';self.count=0;self.xy=(0.0,0.0)

    def receive(self,x,y,z,stamp_ns,ros_now_ns,mono_now):
        # Timeout is evaluated BEFORE recovery, so an old TRACKING state
        # cannot resume on the first frame following a publisher interruption.
        self.output(mono_now,ros_now_ns)
        age=(ros_now_ns-stamp_ns)/1e9
        valid=all(math.isfinite(v) for v in (x,y,z)) and abs(x)<=1 and abs(y)<=1 and 0<=z<=1
        fresh=stamp_ns>0 and 0<=age<=self.timeout
        ordered=self.last_stamp is None or stamp_ns>self.last_stamp
        if not valid or not fresh or not ordered:
            self.lose();return
        self.last_stamp=stamp_ns;self.frame_stamp=stamp_ns;self.last_received=mono_now
        if z==0:
            self.lose();return
        self.xy=(x,y)
        if self.state!='TRACKING':
            self.count+=1
            if self.count>=self.recovery_frames:self.state='TRACKING'

    def output(self,mono_now,ros_now_ns):
        if self.last_received is not None:
            age=(ros_now_ns-self.frame_stamp)/1e9
            if mono_now-self.last_received>=self.timeout or not 0<=age<=self.timeout:
                self.lose()
        if self.state!='TRACKING':return True,0.0,0.0
        x,y=self.xy
        clamp=lambda v:max(-self.limit,min(self.limit,v))
        pan=0.0 if abs(x)<=self.deadband else clamp(-self.kp_pan*x)
        tilt=0.0 if abs(y)<=self.deadband else clamp(self.kp_tilt*y)
        return False,pan,tilt
