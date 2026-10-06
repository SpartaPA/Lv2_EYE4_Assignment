"""tools 공통 부분: 경로, 설정 읽기, 검출기 불러오기, 카메라 입력 2종

카메라 입력
  RealSenseCamera: ROS 없이 RealSense를 직접 엶 (pyrealsense2, 도구용 .venv) — wrapper가 켜져 있으면 못 씀
  RosCamera      : RealSense ROS wrapper가 발행하는 토픽에서 받음 (ROS 환경의 시스템 파이썬) — 실제 파이프라인과 같은 입력
검출 알고리즘은 ROS 패키지의 detector.py를 그대로 불러와 쓴다 (알고리즘 코드는 한 곳에만 둠).
"""
import sys
import time
from pathlib import Path

import numpy as np
import yaml

LV2 = Path(__file__).resolve().parents[1]                  # lv2_module5/
PKG = LV2 / "ros2_ws" / "src" / "realsense_tracker"        # ROS 2 패키지 폴더
PARAMS_PATH = PKG / "config" / "tracker.yaml"              # 인지 파라미터 (perception_node 항목)
CAMERA_PATH = LV2 / "config" / "camera.yaml"               # 카메라 해상도·fps
RESULTS = LV2 / "results"

sys.path.insert(0, str(PKG))  # ROS 빌드 없이 detector.py를 바로 불러오기 위함
from realsense_tracker.detector import PARAM_DEFAULTS, cfg_from_params, detect, draw  # noqa: E402,F401


def load_params(path=PARAMS_PATH):
    """tracker.yaml의 perception_node 파라미터 (파일에 없는 값은 detector.PARAM_DEFAULTS 사용)"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    params = (data.get("perception_node") or {}).get("ros__parameters") or {}
    return {**PARAM_DEFAULTS, **params}


def load_camera(path=CAMERA_PATH):
    """camera.yaml 전체 (width, height, fps, profile, 토픽 이름) — 도구는 width, height, fps만 사용"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class RealSenseCamera:
    """RealSense에서 컬러 영상과 (컬러 좌표에 맞춰 정렬된) 깊이 영상을 읽는다.

    cam_cfg: camera.yaml 내용 (width, height, fps 사용)
    """

    def __init__(self, cam_cfg):
        import pyrealsense2 as rs  # 카메라를 쓸 때만 필요

        w, h, fps = cam_cfg["width"], cam_cfg["height"], cam_cfg.get("fps", 30)
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, w, h, rs.format.bgr8, fps)
        config.enable_stream(rs.stream.depth, w, h, rs.format.z16, fps)
        try:
            profile = self.pipeline.start(config)
        except RuntimeError as e:  # 연결 안 됨, 다른 프로그램(RealSense ROS wrapper 등)이 사용 중, 지원하지 않는 해상도 등
            raise SystemExit(f"RealSense를 열 수 없습니다: {e}")
        self.depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()  # 깊이 값 → 미터
        self.align = rs.align(rs.stream.color)  # 깊이를 컬러 좌표에 맞춤 (같은 픽셀 = 같은 지점)

    def read(self):
        """반환: (ok, color(BGR), depth(z16)). 실패하면 (False, None, None)"""
        try:
            frames = self.align.process(self.pipeline.wait_for_frames())
        except RuntimeError:  # 일정 시간 동안 프레임이 안 들어옴
            return False, None, None
        color, depth = frames.get_color_frame(), frames.get_depth_frame()
        if not color or not depth:
            return False, None, None
        return True, np.asanyarray(color.get_data()).copy(), np.asanyarray(depth.get_data()).copy()

    def flush(self, n=5):
        """쌓여 있던 오래된 프레임 버리기 (headless에서 입력을 기다린 뒤 사용)"""
        for _ in range(n):
            self.read()

    def release(self):
        self.pipeline.stop()


class RosCamera:
    """RealSense ROS wrapper 토픽에서 컬러와 (컬러에 정렬된) 깊이를 읽는다 — RealSenseCamera와 사용법 같음

    cam_cfg: camera.yaml 내용 (color_topic, aligned_depth_topic 사용)
    ROS 2 환경(source /opt/ros/lyrical/setup.bash)의 시스템 파이썬에서 실행해야 함
    """

    def __init__(self, cam_cfg):
        import rclpy
        from message_filters import ApproximateTimeSynchronizer, Subscriber
        from rclpy.qos import QoSProfile, ReliabilityPolicy
        from sensor_msgs.msg import Image

        from realsense_tracker.perception_node import image_to_numpy

        if not cam_cfg.get("color_topic") or not cam_cfg.get("aligned_depth_topic"):
            raise SystemExit("camera.yaml의 color_topic / aligned_depth_topic이 비어 있음")
        self.rclpy, self.to_numpy = rclpy, image_to_numpy
        rclpy.init()
        self.node = rclpy.create_node("tools_camera")
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)  # wrapper 영상은 reliable로만 제대로 받아짐
        self.sync = ApproximateTimeSynchronizer(
            [Subscriber(self.node, Image, cam_cfg["color_topic"], qos_profile=qos),
             Subscriber(self.node, Image, cam_cfg["aligned_depth_topic"], qos_profile=qos)],
            queue_size=10, slop=0.05)
        self.sync.registerCallback(self._on_images)
        self.latest = None
        self.depth_scale = 0.001  # 16UC1 = 1mm 단위 (32FC1이면 read()에서 1.0으로 바뀜)

    def _on_images(self, color, depth):
        self.latest = (color, depth)

    def read(self, timeout_sec=5.0):
        """호출한 뒤에 들어온 새 영상을 기다려 반환: (ok, color(BGR), depth). 시간 안에 안 오면 (False, None, None)"""
        self.latest = None
        end = time.monotonic() + timeout_sec
        while self.latest is None and time.monotonic() < end:
            self.rclpy.spin_once(self.node, timeout_sec=0.05)
        if self.latest is None:
            return False, None, None
        color, depth = self.latest
        self.depth_scale = 1.0 if depth.encoding.lower() == "32fc1" else 0.001
        return True, self.to_numpy(color), self.to_numpy(depth)

    def flush(self, n=5):
        """read()가 항상 호출 이후의 새 영상을 기다리므로 버릴 프레임이 없음 (RealSenseCamera와 사용법을 맞추기 위함)"""

    def release(self):
        self.node.destroy_node()
        self.rclpy.try_shutdown()
