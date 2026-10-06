"""
tracking_control / control_node.py

[역할]
인지(perception) 노드에서 발행하는 /target 토픽을 수신하여
제어(control) 파트에서 사용할 수 있는 형태로 전달받는
최소 ROS 2 subscriber 노드이다.

현재 단계에서는 인지 → 제어 인터페이스 연결만 검증한다.
따라서 실제 제어 알고리즘이나 모터 제어는 구현하지 않는다.

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

[현재 구현하지 않는 기능]
    - P Control
    - Kp / 제어 게인
    - Deadband
    - Motor command 생성
    - OpenCR 통신
    - Dynamixel 제어
    - Watchdog
    - 상태 머신
    - /tracking_status
    - /control/pan_tilt_cmd
    - Custom PanTiltCommand 메시지

[다음 단계]
현재 노드의 /target 수신 구조를 검증한 후
ROS 2 package entry point를 등록하고 build 및 실제 topic 수신을 검증한다.
"""

import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)


class ControlNode(Node):
    def __init__(self):
        super().__init__("control_node")

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