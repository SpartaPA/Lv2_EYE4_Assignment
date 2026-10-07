"""추적 시험 CSV 기록기 (담당: 검증·통합) — 문제 3·4 실시간 기록과 문제 5 bag 결과 재분석에 같은 코드 사용

구독 (모두 읽기만 함 — 명령을 발행하지 않으므로 모터에 영향 없음)
  /target                 geometry_msgs/PointStamped (best effort)   → 행 1개 = /target 1프레임
  /tracking_status        std_msgs/String                            → 그 시점의 최신 상태
  /control/pan_tilt_cmd   realsense_tracker_interfaces/PanTiltCommand → 그 시점의 최신 명령
CSV 열
  run_id, time_s(첫 /target 영상 시각 기준 초), stamp_ns(원본 영상 시각), receive_time_s(노드 시계),
  detected(z>0), ex, ey, area_ratio, state, stop, pan_command, tilt_command, command_unit(rad/s)
  state·명령은 /target 수신 순간의 "최신 값"이다. control_node가 20 Hz로 발행하므로 최대 약 50 ms 늦을 수 있다.

실행 (ROS 환경 + 워크스페이스 install/setup.bash source 후, lv2_module5 폴더에서)
  실시간:  python3 tools/tracking_logger.py --run-id kpA_01
  bag 재분석: python3 tools/tracking_logger.py --run-id success_01_reanalysis --ros-args -p use_sim_time:=true
           (다른 터미널에서 ros2 bag play <bag> --clock — README 문제 5)
  Ctrl+C로 종료하면 저장한 행 수를 출력한다. 출력: results/logs/verification/<run_id>.csv (이미 있으면 거부)
"""
import argparse
import csv
import sys
from pathlib import Path

import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.executors import ExternalShutdownException
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rclpy.utilities import remove_ros_args
from std_msgs.msg import String

from realsense_tracker_interfaces.msg import PanTiltCommand

LV2 = Path(__file__).resolve().parents[1]
FIELDS = ["run_id", "time_s", "stamp_ns", "receive_time_s", "detected", "ex", "ey", "area_ratio",
          "state", "stop", "pan_command", "tilt_command", "command_unit"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True, help="bag·시리얼 로그와 같은 실행 ID")
    ap.add_argument("--output-dir", default=str(LV2 / "results" / "logs" / "verification"))
    ap.add_argument("--target-topic", default="/target", help="입력 재처리 결과를 기록하려면 /target_replay")
    args = ap.parse_args(remove_ros_args(sys.argv)[1:])

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{args.run_id}.csv"
    f = open(path, "x", newline="", encoding="utf-8")  # 'x': 기존 시험 기록을 덮어쓰지 않음
    writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()

    rclpy.init(args=sys.argv)
    node = rclpy.create_node("tracking_logger")
    latest = {"state": "", "stop": "", "pan": "", "tilt": ""}
    first = {"stamp": None}
    rows = {"n": 0}

    def on_status(msg):
        latest["state"] = msg.data

    def on_command(msg):
        latest.update(stop=int(msg.stop), pan=f"{msg.pan_velocity_rad_s:.6f}", tilt=f"{msg.tilt_velocity_rad_s:.6f}")

    def on_target(msg):
        stamp = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
        if first["stamp"] is None:
            first["stamp"] = stamp
        writer.writerow({
            "run_id": args.run_id,
            "time_s": f"{(stamp - first['stamp']) / 1e9:.4f}",
            "stamp_ns": stamp,
            "receive_time_s": f"{node.get_clock().now().nanoseconds / 1e9:.4f}",
            "detected": int(msg.point.z > 0),
            "ex": f"{msg.point.x:.5f}", "ey": f"{msg.point.y:.5f}", "area_ratio": f"{msg.point.z:.6f}",
            "state": latest["state"], "stop": latest["stop"],
            "pan_command": latest["pan"], "tilt_command": latest["tilt"], "command_unit": "rad/s",
        })
        rows["n"] += 1
        if rows["n"] % 30 == 0:
            f.flush()

    best_effort = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)  # /target 발행 QoS와 호환
    node.create_subscription(PointStamped, args.target_topic, on_target, best_effort)
    node.create_subscription(String, "/tracking_status", on_status, 10)
    node.create_subscription(PanTiltCommand, "/control/pan_tilt_cmd", on_command, 10)
    node.get_logger().info(f"기록 시작: {path} (Ctrl+C로 종료)")
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        f.close()
        print(f"{rows['n']}행 저장: {path}")
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
