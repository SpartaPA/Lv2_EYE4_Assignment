"""Separate-process Problem2 test: repository control_node and test-only dry_bridge; no serial."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from std_msgs.msg import String
from realsense_tracker_interfaces.msg import PanTiltCommand
from ament_index_python.packages import get_package_share_directory
from .control_node import TARGET_QOS

# control_node는 모의 시험 고정값 파일(control_dry.yaml)로 실행한다 — 기대 명령(±0.04 rad/s)의 근거를 한 곳에 둠
DRY_PARAMS=str(Path(get_package_share_directory('realsense_tracker'))/'config'/'control_dry.yaml')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='results/logs/control/p2_' + time.strftime('%Y%m%d_%H%M%S'))
    args=parser.parse_args()
    out=Path(args.output_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    # Each retry uses a new directory. Never overwrite captured child output.
    streams=[];children=[];probe=None
    rclpy.init(args=[])
    try:
        probe=Node('control_dry_test_probe')
        pub=probe.create_publisher(PointStamped,'/target',TARGET_QOS)
        commands=[];states=[];feedback=[]
        sc=probe.create_subscription(PanTiltCommand,'/control/pan_tilt_cmd',commands.append,1)
        ss=probe.create_subscription(String,'/tracking_status',lambda m:states.append(m.data),1)
        sf=probe.create_subscription(String,'/opencr/dry_status',lambda m:feedback.append(json.loads(m.data)),1)
        def spin(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:rclpy.spin_once(probe,timeout_sec=0.01)
        # Reject a running manual launch/bridge/controller before spawning children.
        spin(1.0)
        assert pub.get_subscription_count()==0,'Existing /target subscriber: stop other nodes or use an isolated domain'
        assert sc.get_publisher_count()==0,'Existing command publisher: stop other nodes'
        assert sf.get_publisher_count()==0,'Existing dry status publisher: stop other nodes'
        def child(module,log,extra=()):
            stream=open(out/log,'x');streams.append(stream)
            process=subprocess.Popen([sys.executable,'-m',module,*extra],stdout=stream,stderr=subprocess.STDOUT)
            children.append(process);return process
        control=child('realsense_tracker.control_node','control_node.log',
                      ['--ros-args','--params-file',DRY_PARAMS])
        bridge=child('realsense_tracker.dry_bridge','opencr_node.log',
                     ['--ros-args','-p',f'csv_path:={out / "commands.csv"}'])
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            assert control.poll() is None,'Controller exited; see control_node.log'
            assert bridge.poll() is None,'Dry bridge exited; see opencr_node.log'
            spin(0.1)
            if states and commands and feedback and pub.get_subscription_count()==1:break
        assert states and commands and feedback,'ROS graph discovery timed out; see child logs'
        assert sc.get_publisher_count()==1 and sf.get_publisher_count()==1,'Competing ROS publishers'
        print(f'PROCESSES controller_pid={control.pid} bridge_pid={bridge.pid} probe_pid={__import__("os").getpid()}',flush=True)
        def frame(x,y,z):
            m=PointStamped();m.header.stamp=probe.get_clock().now().to_msg()
            m.point.x=float(x);m.point.y=float(y);m.point.z=float(z)
            pub.publish(m);spin(0.07)
        def expect(state,stop,p,t):
            spin(0.15)
            assert states[-1]==state,(state,states[-5:])
            m=commands[-1]
            assert m.stop==stop and math.isclose(m.pan_velocity_rad_s,p,abs_tol=1e-6) and math.isclose(m.tilt_velocity_rad_s,t,abs_tol=1e-6),(state,m)
            f=feedback[-1]
            assert f['mode']=='DRY' and f['serial_opened'] is False,f
            assert f['stop']==stop and math.isclose(f['pan_rad_s'],p,abs_tol=1e-6) and math.isclose(f['tilt_rad_s'],t,abs_tol=1e-6),f
        expect('IDLE',True,0,0)
        def tracking(x,y):
            for _ in range(5):frame(x,y,0.1)
        for label,x,y,p,t in [('1 center',0,0,0,0),('2 x +0.4',.4,0,-.04,0),
                             ('3 x -0.4',-.4,0,.04,0),('4 y +0.4',0,.4,0,.04),
                             ('5 y -0.4',0,-.4,0,-.04)]:
            tracking(x,y);expect('TRACKING',False,p,t);print('PASS '+label,flush=True)
        frame(0,0,0);expect('LOST',True,0,0);print('PASS 6 z=0',flush=True)
        frame(.4,0,.1);expect('LOST',True,0,0)
        frame(.4,0,.1);expect('LOST',True,0,0)
        frame(.4,0,.1);expect('TRACKING',False,-.04,0)
        print('PASS three-frame recovery',flush=True)
        spin(.7);expect('LOST',True,0,0);print('PASS 7 target publisher silence',flush=True)
        tracking(.4,0);expect('TRACKING',False,-.04,0)
        # Actual termination of the separate controller process, not timer removal.
        control.terminate();control.wait(timeout=5);spin(.65)
        f=feedback[-1]
        assert bridge.poll() is None,'Bridge unexpectedly exited'
        assert f['reason']=='COMMAND_TIMEOUT' and f['stop'] and f['pan_rad_s']==0 and f['tilt_rad_s']==0,f
        assert all(f['serial_opened'] is False for f in feedback)
        print('PASS actual controller termination -> dry bridge timeout and zero',flush=True)
        print('ALL REPOSITORY SEPARATE-PROCESS DRY CHECKS PASSED; SERIAL_OPENED=FALSE',flush=True)
    finally:
        for process in children:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        for stream in streams:stream.close()
        if probe:probe.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
