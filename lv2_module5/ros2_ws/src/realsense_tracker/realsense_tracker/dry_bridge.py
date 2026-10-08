"""DRY sink bridge (담당: 통합 + 제어) — 시리얼 포트를 절대 열지 않는 opencr_node 기본 모드

용도: 문제 2 모의 입력 시험(test_control_dry)과 모터 없는 연결 확인.
/control/pan_tilt_cmd 를 받아 실제 bridge와 같은 규칙(속도 상한·명령 나이 0.15초·역순 거부)으로 검사하고,
받아들인 명령/거부/수신 timeout(0.15초 동안 명령 없음 → 정지)을 /opencr/dry_status(JSON)와 CSV로 남긴다.
출력값은 모의 처리 결과이며 실제 모터 피드백이 아니다. dry_run=false이면 시작을 거부한다.
"""
import csv
import json
import math
import time
from rclpy.node import Node
from std_msgs.msg import String
from realsense_tracker_interfaces.msg import PanTiltCommand

from .control_core import MAX_VELOCITY_RAD_S
from .serial_core import SerialBridge

COMMAND_AGE_SEC = SerialBridge.COMMAND_AGE  # 실제 시리얼 bridge와 같은 명령 나이 규칙

class DryBridge(Node):
    def __init__(self):
        super().__init__('opencr_node')
        self.declare_parameter('dry_run',True)
        if self.get_parameter('dry_run').value is not True:
            raise RuntimeError('DRY sink requires dry_run=true; motor output uses serial_mode=true with opencr_live.yaml')
        self.declare_parameter('csv_path','')
        self.last_received=None;self.last_stamp=None;self.goal=(0.0,0.0)
        self.timed_out=False  # COMMAND_TIMEOUT은 정상→timeout 전이 때 한 번만 기록 (20 Hz 반복 기록 방지)
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
        if not all(math.isfinite(v) and abs(v)<=MAX_VELOCITY_RAD_S+1e-8 for v in (p,t)) or not 0<=age<=COMMAND_AGE_SEC or not ordered:
            self.record(True,0.0,0.0,'REJECTED_COMMAND');return
        self.last_received=time.monotonic();self.last_stamp=stamp;self.timed_out=False
        if msg.stop:p=t=0.0
        self.record(bool(msg.stop),p,t,'STOP' if msg.stop else 'ACCEPTED')

    def watchdog(self):
        expired=self.last_received is None or time.monotonic()-self.last_received>=COMMAND_AGE_SEC
        if expired and not self.timed_out:
            self.timed_out=True
            self.record(True,0.0,0.0,'COMMAND_TIMEOUT')

    def destroy_node(self):
        if self.file:self.file.close()
        return super().destroy_node()
