"""Dry OpenCR bridge: serial conversion and hardware output are NOT implemented."""
import csv
import json
import math
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from realsense_tracker_interfaces.msg import PanTiltCommand

class DryBridge(Node):
    def __init__(self):
        super().__init__('opencr_node')
        self.declare_parameter('dry_run',True)
        if self.get_parameter('dry_run').value is not True:
            raise RuntimeError('Hardware mode is not implemented: dry_run must remain true')
        self.declare_parameter('csv_path','')
        self.last_received=None;self.last_stamp=None;self.goal=(0.0,0.0)
        self.history=[];self.file=None;self.writer=None
        self.status_pub=self.create_publisher(String,'/opencr/dry_status',1)
        path=self.get_parameter('csv_path').value
        if path:
            self.file=open(path,'x',newline='')
            self.writer=csv.writer(self.file,lineterminator="\n")
            self.writer.writerow(['monotonic_sec','stop','pan_rad_s','tilt_rad_s','reason','serial_opened'])
        self.sub=self.create_subscription(PanTiltCommand,'/control/pan_tilt_cmd',self.command,1)
        self.timer=self.create_timer(0.05,self.watchdog)
        self.get_logger().info('DRY_ONLY: serial port is never opened; no ARM or VEL sent')

    def record(self,stop,pan,tilt,reason):
        self.goal=(pan,tilt);row=(time.monotonic(),stop,pan,tilt,reason,False)
        self.history.append(row)
        msg=String();msg.data=json.dumps({'mode':'DRY','serial_opened':False,
            'stop':bool(stop),'pan_rad_s':pan,'tilt_rad_s':tilt,'reason':reason,
            'monotonic_sec':row[0]})
        self.status_pub.publish(msg)
        if len(self.history)>1000:self.history=self.history[-1000:]
        if self.writer:self.writer.writerow(row);self.file.flush()

    def command(self,msg):
        stamp=msg.header.stamp.sec*1000000000+msg.header.stamp.nanosec
        age=(self.get_clock().now().nanoseconds-stamp)/1e9
        p,t=float(msg.pan_velocity_rad_s),float(msg.tilt_velocity_rad_s)
        ordered=self.last_stamp is None or stamp>self.last_stamp
        if not all(math.isfinite(v) and abs(v)<=0.05+1e-8 for v in (p,t)) or not 0<=age<=0.15 or not ordered:
            self.record(True,0.0,0.0,'REJECTED_COMMAND');return
        self.last_received=time.monotonic();self.last_stamp=stamp
        if msg.stop:p=t=0.0
        self.record(bool(msg.stop),p,t,'STOP' if msg.stop else 'ACCEPTED')

    def watchdog(self):
        if self.last_received is None or time.monotonic()-self.last_received>=0.15:
            self.record(True,0.0,0.0,'COMMAND_TIMEOUT')

    def destroy_node(self):
        if self.file:self.file.close()
        return super().destroy_node()
