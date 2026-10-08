"""ROS control -> serial bridge -> actual DRY firmware, all separate processes."""
import argparse
import csv
import json
import os
from pathlib import Path
import pty
import subprocess
import sys
import time
import tty
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from std_msgs.msg import String
from std_srvs.srv import Trigger
from ament_index_python.packages import get_package_share_directory
from .control_node import TARGET_QOS

# control_node는 모의 시험 고정값 파일(control_dry.yaml)로 실행한다 — 기대 명령(±0.04 rad/s)의 근거를 한 곳에 둠
DRY_PARAMS=str(Path(get_package_share_directory('realsense_tracker'))/'config'/'control_dry.yaml')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--firmware-executable',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();out=Path(args.output_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    children=[];streams=[];probe=None;master=None;slave=None
    rclpy.init(args=[])
    try:
        probe=Node('serial_ros_test_probe')
        pub=probe.create_publisher(PointStamped,'/target',TARGET_QOS)
        reports=[];states=[]
        bs=probe.create_subscription(String,'/opencr/bridge_status',lambda m:reports.append(json.loads(m.data)),1)
        ts=probe.create_subscription(String,'/tracking_status',lambda m:states.append(m.data),1)
        prepare=probe.create_client(Trigger,'/opencr/prepare')
        arm=probe.create_client(Trigger,'/opencr/arm')
        last_frame=0.0
        def spin(seconds,target=None):
            nonlocal last_frame
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                if target is not None and time.monotonic()-last_frame>=.05:
                    x,y,z=target;m=PointStamped();m.header.stamp=probe.get_clock().now().to_msg()
                    m.point.x=float(x);m.point.y=float(y);m.point.z=float(z)
                    pub.publish(m);last_frame=time.monotonic()
                rclpy.spin_once(probe,timeout_sec=.005)
        spin(1.)
        assert pub.get_subscription_count()==0 and bs.get_publisher_count()==0,'Other control/bridge nodes active; use isolated ROS domain'
        def child(command,name,pass_fds=()):
            stream=open(out/name,'x');streams.append(stream)
            process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,pass_fds=pass_fds)
            children.append(process);return process
        master,slave=pty.openpty();tty.setraw(slave);port=os.ttyname(slave)
        firmware=child([str(Path(args.firmware_executable).resolve()),str(master)],'firmware.log',(master,))
        os.close(master);master=None
        bridge=child([sys.executable,'-m','realsense_tracker.opencr_node','--ros-args',
                      '-p','dry_run:=true','-p','serial_mode:=true','-p','expected_board_mode:=DRY',
                      '-p',f'port:={port}','-p',f'csv_path:={out / "serial_ros.csv"}'],'serial_node.log')
        control=child([sys.executable,'-m','realsense_tracker.control_node','--ros-args','--params-file',DRY_PARAMS],'control_node.log')
        def wait(predicate,target=None,timeout=5,allow_fault=False):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                spin(.02,target)
                assert bridge.poll() is None,'Bridge exited; see serial_node.log'
                assert firmware.poll() is None,'Firmware exited; see firmware.log'
                if predicate():return
                if not allow_fault and reports and reports[-1]['phase']=='FAULT':raise AssertionError(reports[-1])
            raise AssertionError('Timeout; latest bridge report: '+str(reports[-1:] ))
        wait(lambda:reports and reports[-1]['phase']=='BOOT' and prepare.service_is_ready(),timeout=20)
        os.close(slave);slave=None
        print(f'PROCESSES controller={control.pid} bridge={bridge.pid} firmware={firmware.pid}',flush=True)
        def call(client,target=None):
            assert client.service_is_ready(),'Service missing'
            future=client.call_async(Trigger.Request())
            wait(lambda:future.done(),target,allow_fault=True)
            result=future.result();print('SERVICE '+result.message,flush=True);return result
        assert call(prepare).success
        wait(lambda:reports[-1]['phase']=='READY',(0,0,.1))
        # Explicit requests can be rejected while a STATUS transaction is pending.
        deadline=time.monotonic()+2
        while True:
            result=call(arm,(0,0,.1))
            if result.success:break
            assert time.monotonic()<deadline,result.message
            spin(.02,(0,0,.1))
        wait(lambda:reports[-1]['phase']=='ARMED',(0,0,.1))
        cases=[('1 center',0,0,(0,0)),('2 x +0.4',.4,0,(-2,0)),
               ('3 x -0.4',-.4,0,(2,0)),('4 y +0.4',0,.4,(0,2)),
               ('5 y -0.4',0,-.4,(0,-2))]
        for label,x,y,goal in cases:
            wait(lambda:reports[-1]['phase']=='ARMED' and reports[-1]['board']['goal']==list(goal),(x,y,.1))
            print('PASS serial ROS '+label,flush=True)
        wait(lambda:states and states[-1]=='LOST' and reports[-1]['board']['goal']==[0,0],(0,0,0))
        spin(.3,(0,0,0));assert reports[-1]['phase']=='ARMED',reports[-1]
        print('PASS serial ROS 6 no detection -> STOP, arming retained',flush=True)
        wait(lambda:states[-1]=='TRACKING' and reports[-1]['board']['goal']==[-2,0],(.4,0,.1))
        print('PASS normal three-frame recovery -> fresh VEL without another ARM',flush=True)
        spin(.8)
        assert states[-1]=='LOST' and reports[-1]['phase']=='ARMED' and reports[-1]['board']['goal']==[0,0],reports[-1]
        print('PASS serial ROS 7 target silence -> LOST and STOP',flush=True)
        wait(lambda:states[-1]=='TRACKING' and reports[-1]['board']['goal']==[-2,0],(.4,0,.1))
        control.terminate();control.wait(timeout=5)
        end=time.monotonic()+2
        while time.monotonic()<end:
            spin(.02)
            if reports[-1]['phase']=='FAULT':break
        assert reports[-1]['phase']=='FAULT' and reports[-1]['reason']=='ROS_COMMAND_TIMEOUT',reports[-1]
        # No auto recovery after fresh targets or service requests.
        assert not call(arm).success
        with open(out/'serial_ros.csv',newline='') as source:rows=list(csv.DictReader(source))
        tx=[r['line'] for r in rows if r['direction']=='TX']
        assert tx.count('ARM')==1,tx
        assert 'DISARM' in tx and 'SUPPORTED_OFF' not in tx
        assert all(r['line'].find('MODE=LIVE')<0 for r in rows if r['direction']=='RX')
        print('PASS controller termination -> DISARM attempt, latched command timeout, no re-arm',flush=True)
        print('ALL SERIAL ROS PTY CHECKS PASSED; FIRMWARE_MODE=DRY',flush=True)
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        for stream in streams:stream.close()
        if master is not None:os.close(master)
        if slave is not None:os.close(slave)
        if probe:probe.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
