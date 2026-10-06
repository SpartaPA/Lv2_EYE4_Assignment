"""
tracking_control / control_node.py

[역할]
인지(perception) 노드에서 발행하는 /target 토픽을 수신하여
제어(control) 파트에서 사용할 수 있는 형태로 전달받는
최소 ROS 2 subscriber 노드이다.

현재 단계에서는 인지 → 제어 인터페이스와 제어 parameter 설정 기반을 준비한다.
parameter는 선언·검증만 하며 P Control이나 모터 제어에는 아직 사용하지 않는다.

[입력]
Topic:
    /target

Message:
    geometry_msgs/msg/PointStamped

Message field:
    msg.point.x
        → 화면 중심 기준 가로 오차 (ex)

    msg.point.y
        → 화면 중심 기준 세로 오차 (ey)

    msg.point.z
        → 타겟 면적 비율 (area_ratio)

    msg.header.stamp
        → 인지 노드에서 전달된 Color image 기준 timestamp

[Target 상태]
    z <= 0
        → target miss
        → 타겟을 찾지 못한 상태

    z > 0
        → target detected
        → 유효한 타겟이 검출된 상태

[QoS]
/target publisher와 동일한 QoS 조건을 사용한다.

    Reliability : BEST_EFFORT
    History     : KEEP_LAST
    Depth       : 1
    Durability  : VOLATILE

[현재 구현 범위]
    1. ROS 2 control_node 생성
    2. /target subscriber 생성
    3. PointStamped 메시지 수신
    4. x, y, z 값 확인
    5. header timestamp 확인
    6. target miss / detected 상태 로그 출력
    7. Kp, 방향, 속도 제한, deadband parameter 선언
    8. 설정된 parameter의 타입·명백한 유효성 검사

[현재 구현하지 않는 기능]
    - P Control 계산 (다음 단계)
    - Motor command 생성
    - OpenCR 통신
    - Dynamixel 제어
    - Watchdog
    - 상태 머신
    - /tracking_status
    - /control/pan_tilt_cmd
    - Custom PanTiltCommand 메시지

[다음 단계]
parameter 값이 확정된 뒤 P Control 계산을 별도 단계에서 추가한다.
"""

import math

import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)


class ControlNode(Node):
    def __init__(self):
        super().__init__("control_node")

        self.control_parameters = {}
        for name in ("kp_pan", "kp_tilt", "pan_speed_limit", "tilt_speed_limit",
                     "pan_deadband", "tilt_deadband"):
            value = self.declare_parameter(name, Parameter.Type.DOUBLE).value
            self._validate_finite_parameter(name, value)
            if value is not None and name.endswith("speed_limit") and value < 0.0:
                raise ValueError(f"{name} must be non-negative")
            if value is not None and name.endswith("deadband") and value < 0.0:
                raise ValueError(f"{name} must be non-negative")
            self.control_parameters[name] = value

        for name in ("pan_direction", "tilt_direction"):
            value = self.declare_parameter(name, Parameter.Type.INTEGER).value
            if value is not None and value not in (-1, 1):
                raise ValueError(f"{name} must be either -1 or 1")
            self.control_parameters[name] = value

        target_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.target_subscription = self.create_subscription(
            PointStamped,
            "/target",
            self.target_callback,
            target_qos,
        )

    def _validate_finite_parameter(self, name: str, value):
        if value is not None and not math.isfinite(value):
            raise ValueError(f"{name} must be finite")

    def target_callback(self, msg: PointStamped):
        x = msg.point.x
        y = msg.point.y
        z = msg.point.z
        stamp = msg.header.stamp
        timestamp = f"{stamp.sec}.{stamp.nanosec:09d}"

        if z <= 0.0:
            self.get_logger().info(
                f"target miss: z={z:.4f}, timestamp={timestamp}"
            )
            return

        self.get_logger().info(
            f"target detected: x={x:.4f}, y={y:.4f}, z={z:.4f}, "
            f"timestamp={timestamp}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = ControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()