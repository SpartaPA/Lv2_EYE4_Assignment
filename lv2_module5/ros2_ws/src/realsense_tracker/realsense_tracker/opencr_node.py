"""Dry sink by default; explicit serial mode accepts DRY firmware ONLY."""
import csv
import json
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger
from realsense_tracker_interfaces.msg import PanTiltCommand
from .dry_bridge import DryBridge
from .serial_core import PosixSerial, SerialBridge


class SerialNode(Node):
    def __init__(self):
        super().__init__('opencr_node')
        self.declare_parameter('dry_run',True)
        self.declare_parameter('serial_mode',False)
        self.declare_parameter('expected_board_mode','DRY')
        self.declare_parameter('port','')
        self.declare_parameter('usb_serial_baudrate',115200)
        self.declare_parameter('csv_path','')
        get=lambda key:self.get_parameter(key).value
        if get('dry_run') is not True:raise RuntimeError('LIVE hardware mode is not implemented; dry_run must be true')
        if get('serial_mode') is not True:raise RuntimeError('SerialNode requires explicit serial_mode=true')
        if get('expected_board_mode')!='DRY':raise RuntimeError('Only expected_board_mode=DRY is supported')
        if get('usb_serial_baudrate')!=115200:raise RuntimeError('USB baud must be 115200')
        if not get('port'):raise RuntimeError('Explicit serial port required')
        self.file=None;self.writer=None;self.link=None;self.transport=None
        try:
            if get('csv_path'):
                self.file=open(get('csv_path'),'x',newline='')
                self.writer=csv.writer(self.file,lineterminator='\n')
                self.writer.writerow(['monotonic_sec','direction','line'])
            self.status=self.create_publisher(String,'/opencr/bridge_status',1)
            self.sub=self.create_subscription(PanTiltCommand,'/control/pan_tilt_cmd',self.command,1)
            self.prepare_service=self.create_service(Trigger,'/opencr/prepare',self.prepare)
            self.arm_service=self.create_service(Trigger,'/opencr/arm',self.arm)
            self.disarm_service=self.create_service(Trigger,'/opencr/disarm',self.disarm)
            self.transport=PosixSerial(get('port'))
            self.link=SerialBridge(self.transport,log=self.record)
            self.timer=self.create_timer(.01,self.tick)
            self.get_logger().info('SERIAL DRY ONLY: initial STATUS; explicit prepare and arm required; no LIVE support')
        except Exception:
            if self.transport:self.transport.close()
            if self.file:self.file.close()
            raise

    def record(self,now,direction,line):
        if self.writer:self.writer.writerow([now,direction,line]);self.file.flush()

    def command(self,msg):
        stamp=msg.header.stamp.sec*1000000000+msg.header.stamp.nanosec
        self.link.receive_command(msg.stop,float(msg.pan_velocity_rad_s),float(msg.tilt_velocity_rad_s),
                                  stamp,self.get_clock().now().nanoseconds)

    def prepare(self,request,response):
        response.success,response.message=self.link.prepare();return response

    def arm(self,request,response):
        response.success,response.message=self.link.arm();return response

    def disarm(self,request,response):
        response.success,response.message=self.link.disarm();return response

    def tick(self):
        self.link.tick();msg=String();msg.data=json.dumps(self.link.snapshot());self.status.publish(msg)

    def destroy_node(self):
        if self.link:self.link.close()
        if self.file:self.file.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args);selector=None;node=None
    try:
        # Inspect parameters before constructing a node that could open a port.
        selector=Node('opencr_node')
        selector.declare_parameter('serial_mode',False)
        use_serial=selector.get_parameter('serial_mode').value
        selector.destroy_node();selector=None
        node=SerialNode() if use_serial else DryBridge()
        rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        if selector:selector.destroy_node()
        if node:node.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
