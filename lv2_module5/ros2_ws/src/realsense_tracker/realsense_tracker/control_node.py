"""Two-axis image control. No serial or motor bus access."""
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import PointStamped
from std_msgs.msg import String
from realsense_tracker_interfaces.msg import PanTiltCommand
from .control_core import Controller

TARGET_QOS=QoSProfile(depth=1,reliability=ReliabilityPolicy.BEST_EFFORT,
                      durability=DurabilityPolicy.VOLATILE)

class ControlNode(Node):
    def __init__(self):
        super().__init__('control_node')
        params={'kp_pan':0.1,'kp_tilt':0.1,'max_velocity_rad_s':0.05,
                'deadband':0.03,'target_timeout_sec':0.5,'recovery_frames':3}
        for key,val in params.items():self.declare_parameter(key,val)
        p=lambda k:self.get_parameter(k).value
        self.core=Controller(p('kp_pan'),p('kp_tilt'),p('max_velocity_rad_s'),
                             p('deadband'),p('target_timeout_sec'),p('recovery_frames'))
        self.cmd=self.create_publisher(PanTiltCommand,'/control/pan_tilt_cmd',1)
        self.status=self.create_publisher(String,'/tracking_status',1)
        self.sub=self.create_subscription(PointStamped,'/target',self.target,TARGET_QOS)
        self.timer=self.create_timer(0.05,self.publish_output)

    def target(self,msg):
        stamp=msg.header.stamp.sec*1000000000+msg.header.stamp.nanosec
        self.core.receive(msg.point.x,msg.point.y,msg.point.z,stamp,
                          self.get_clock().now().nanoseconds,time.monotonic())
        # Publish immediately on loss instead of waiting for the 20 Hz timer.
        self.publish_output()

    def publish_output(self):
        now=self.get_clock().now()
        stop,pan,tilt=self.core.output(time.monotonic(),now.nanoseconds)
        msg=PanTiltCommand();msg.header.stamp=now.to_msg();msg.stop=stop
        msg.pan_velocity_rad_s=pan;msg.tilt_velocity_rad_s=tilt
        self.cmd.publish(msg);state=String();state.data=self.core.state;self.status.publish(state)

def main(args=None):
    rclpy.init(args=args);node=None
    try:
        node=ControlNode();rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        if node:node.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
