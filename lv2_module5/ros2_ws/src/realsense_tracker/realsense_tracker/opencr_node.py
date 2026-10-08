"""정상 runtime 전용 OpenCR bridge: 설정 읽기 → Serial 연결 → fresh command 전송.
Problem2는 dry_bridge.py만 사용하며 이 노드와 모터 포트에 접근하지 않는다.
"""
import csv
import json
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from std_msgs.msg import String
from realsense_tracker_interfaces.msg import PanTiltCommand
from .serial_core import PosixSerial, SerialBridge


class SerialNode(Node):
    def __init__(self):
        super().__init__('opencr_node')
        self.link = None
        self.file = self.writer = None
        for name, default in [('port', ''), ('baud', 115200), ('command_timeout_sec', 0.5), ('csv_path', '')]:
            self.declare_parameter(name, default)
        get = lambda key: self.get_parameter(key).value
        if not get('port'):
            raise RuntimeError('Serial port is empty; check config/opencr_live.yaml')
        transport = PosixSerial(get('port'), get('baud'))
        try:
            if get('csv_path'):
                self.file = open(get('csv_path'), 'x', newline='', encoding='utf-8')
                self.writer = csv.writer(self.file, lineterminator='\n')
                self.writer.writerow(['monotonic_sec', 'direction', 'line'])
            self.link = SerialBridge(transport, log=self.record, command_timeout_sec=float(get('command_timeout_sec')))
            if self.link.reason:
                raise RuntimeError(self.link.reason)
            self.status = self.create_publisher(String, '/opencr/bridge_status', 1)
            self.sub = self.create_subscription(PanTiltCommand, '/control/pan_tilt_cmd', self.command, 1)
            self.timer = self.create_timer(0.01, self.tick)
            self.get_logger().info(f"OpenCR connected: {get('port')} baud={get('baud')}; command timeout={get('command_timeout_sec')} s")
        except Exception:
            if self.link:
                self.link.close()
            else:
                transport.close()
            if self.file:
                self.file.close()
            raise

    def record(self, now, direction, line):
        if self.writer:
            self.writer.writerow([now, direction, line])
            self.file.flush()

    def command(self, msg):
        stamp = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
        self.link.receive_command(msg.stop, float(msg.pan_velocity_rad_s), float(msg.tilt_velocity_rad_s),
                                  stamp, self.get_clock().now().nanoseconds)
        if self.link.reason:
            raise RuntimeError(self.link.reason)

    def tick(self):
        self.link.tick()
        if self.link.reason:
            raise RuntimeError(self.link.reason)
        msg = String()
        msg.data = json.dumps(self.link.snapshot())
        self.status.publish(msg)

    def destroy_node(self):
        if self.link:
            self.link.close()  # best-effort STOP; 자동 reconnect 없음
        if self.file:
            self.file.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = SerialNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception as exc:
        rclpy.logging.get_logger('opencr_node').error(f'OpenCR ERROR: {exc}; exiting, no reconnect')
        raise SystemExit(1)
    finally:
        if node:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
