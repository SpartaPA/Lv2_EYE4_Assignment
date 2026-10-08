"""제어 노드 (담당: 제어) — /target → Pan/Tilt 속도 명령. 시리얼·모터 버스에 접근하지 않음

실행 위치: Raspberry Pi (perception_node·opencr_node와 같은 ROS 2 runtime)
구독
  /target                 geometry_msgs/PointStamped  QoS best effort, depth 1 (perception 발행과 호환)
발행
  /control/pan_tilt_cmd   realsense_tracker_interfaces/PanTiltCommand  20 Hz + LOST 전환 즉시
                          header.stamp = 명령 생성 시각, 단위 rad/s (모터 원시 부호, direction 적용 후)
                          stop=true 이면 두 축 0
  /tracking_status        std_msgs/String  IDLE / TRACKING / LOST (명령과 같은 주기)
서비스
  /control/enable         std_srvs/SetBool  false = 명시적 중지(IDLE, 정지), true = 재개(3프레임 복귀 필요)

판단 로직은 control_core.Controller에 있다. 파라미터: config/control.yaml (실제 추적),
config/control_dry.yaml (모의 시험).
"""
import time

import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from std_srvs.srv import SetBool

from realsense_tracker_interfaces.msg import PanTiltCommand

from .control_core import Controller

# 발제문 /target QoS: best effort, depth 1. reliable로 구독하면 best effort 발행과 연결되지 않는다.
TARGET_QOS = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                        durability=DurabilityPolicy.VOLATILE)
COMMAND_PERIOD_SEC = 0.05  # 20 Hz: 정상 명령은 이 타이머만 발행. 매 fresh 명령이 0.5초 watchdog을 갱신한다.

PARAM_DEFAULTS = {
    'kp_pan': 0.1, 'kp_tilt': 0.1,
    'pan_speed_limit_rad_s': 0.05, 'tilt_speed_limit_rad_s': 0.05,
    'pan_deadband': 0.03, 'tilt_deadband': 0.03,
    'target_timeout_sec': 0.5, 'recovery_frames': 3,
    'pan_direction': -1, 'tilt_direction': 1,
}


class ControlNode(Node):
    def __init__(self):
        super().__init__('control_node')
        for key, value in PARAM_DEFAULTS.items():
            self.declare_parameter(key, value)

        def p(key):
            return self.get_parameter(key).value

        self.core = Controller(
            kp_pan=p('kp_pan'), kp_tilt=p('kp_tilt'),
            pan_speed_limit=p('pan_speed_limit_rad_s'), tilt_speed_limit=p('tilt_speed_limit_rad_s'),
            pan_deadband=p('pan_deadband'), tilt_deadband=p('tilt_deadband'),
            timeout=p('target_timeout_sec'), recovery_frames=p('recovery_frames'),
            pan_direction=p('pan_direction'), tilt_direction=p('tilt_direction'))
        # depth 1: 오래된 명령이 큐에 쌓여 뒤늦게 전달되지 않게 한다.
        self.cmd = self.create_publisher(PanTiltCommand, '/control/pan_tilt_cmd', 1)
        self.status = self.create_publisher(String, '/tracking_status', 1)
        self.sub = self.create_subscription(PointStamped, '/target', self.target, TARGET_QOS)
        self.enable_service = self.create_service(SetBool, '/control/enable', self.enable)
        self.timer = self.create_timer(COMMAND_PERIOD_SEC, self.publish_output)
        self.get_logger().info(
            f"control_node: kp_pan={p('kp_pan')} kp_tilt={p('kp_tilt')} rad/s, "
            f"limit pan/tilt={p('pan_speed_limit_rad_s')}/{p('tilt_speed_limit_rad_s')} rad/s, "
            f"deadband pan/tilt={p('pan_deadband')}/{p('tilt_deadband')}, "
            f"direction pan/tilt={p('pan_direction')}/{p('tilt_direction')}, "
            f"timeout={p('target_timeout_sec')} s, recovery={p('recovery_frames')} frames")

    def target(self, msg):
        previous_state = self.core.state
        stamp = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
        self.core.receive(msg.point.x, msg.point.y, msg.point.z, stamp,
                          self.get_clock().now().nanoseconds, time.monotonic())
        # 정상 추적은 20 Hz로만 발행. LOST 전환은 다음 타이머를 기다리지 않고 즉시 STOP을 보낸다.
        if previous_state != 'LOST' and self.core.state == 'LOST':
            self.publish_output()

    def enable(self, request, response):
        self.core.set_enabled(request.data)
        self.publish_output()
        response.success = True
        response.message = ('tracking enabled; 3 fresh frames required' if request.data
                            else 'tracking disabled; IDLE and stop')
        self.get_logger().info(response.message)
        return response

    def publish_output(self):
        now = self.get_clock().now()
        stop, pan, tilt = self.core.output(time.monotonic(), now.nanoseconds)
        msg = PanTiltCommand()
        msg.header.stamp = now.to_msg()
        msg.stop = stop
        msg.pan_velocity_rad_s = pan
        msg.tilt_velocity_rad_s = tilt
        self.cmd.publish(msg)
        state = String()
        state.data = self.core.state
        self.status.publish(state)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ControlNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node:
            node.core.set_enabled(False)
            if rclpy.ok():
                node.publish_output()  # 종료 시 가능한 범위에서 두 축 STOP
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
