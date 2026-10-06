"""인지 노드 (담당: 인지) — 컬러(+깊이) 영상에서 파란색 목표를 찾아 /target 발행

구독 (토픽 이름은 코드에 적지 않고 config/camera.yaml에서 읽음 — 파일 경로는 파라미터 camera_config)
  color_topic           sensor_msgs/Image  (bgr8 또는 rgb8)
  aligned_depth_topic   sensor_msgs/Image  (16UC1 또는 32FC1, 컬러에 정렬된 깊이) — use_depth: true일 때만
  (camera_info_topic은 이 노드에서 쓰지 않음 — 확인·기록용)
발행
  /target                   geometry_msgs/PointStamped  (발제문 지정 — 이름·형식 임의 변경 금지)
      point.x = ex  화면 중심 기준 가로 어긋남 (−1 ~ +1, 오른쪽이 +)
      point.y = ey  화면 중심 기준 세로 어긋남 (−1 ~ +1, 아래쪽이 +)
      point.z = z   목표 넓이 ÷ 화면 넓이 (검출되면 항상 0보다 큼)
      미검출이면 x = y = z = 0  → 제어는 z == 0 이면 미검출로 판단
      header = 입력 컬러 영상의 시각·좌표계
  /perception/debug_image   sensor_msgs/Image (bgr8) — publish_debug_image: true일 때만 (확인용 화면)

파라미터: config/tracker.yaml 의 perception_node 항목 (기본값은 detector.PARAM_DEFAULTS)
실행 예 (lv2_module5 폴더에서):
  ros2 run realsense_tracker perception_node --ros-args \\
    --params-file ros2_ws/src/realsense_tracker/config/tracker.yaml -p camera_config:=$PWD/config/camera.yaml
"""
import numpy as np
import rclpy
import yaml
from geometry_msgs.msg import PointStamped
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image

from .detector import PARAM_DEFAULTS, cfg_from_params, detect, draw

# 인지 파라미터 외에 노드에서만 쓰는 파라미터
NODE_PARAM_DEFAULTS = {
    "camera_config": "",            # config/camera.yaml 경로 — 카메라 토픽 이름을 여기서 읽음 (launch에서 지정)
    "use_depth": False,             # true면 깊이 영상도 받아 거리(dist_cm)를 확인 화면·로그에 표시
    "depth_unit_m": 0.001,          # 16UC1 깊이 값 1이 몇 m인지 (RealSense 기본: 1mm)
    "publish_debug_image": False,   # true면 /perception/debug_image 발행 (rqt_image_view 등으로 확인)
    # 영상 구독 방식. true = reliable (전달 보장), false = best effort (센서용, 손실 허용)
    # 실측(노트북, Fast DDS 기본 설정): 640x480 영상은 다른 프로세스에서 받을 때 reliable일 때만 전달됨
    # ※ RealSense wrapper의 발행 방식과 맞아야 함 (reliable 구독 + best effort 발행 → 연결 안 됨)
    "image_reliable": True,
}
CAMERA_TOPIC_KEYS = ("color_topic", "aligned_depth_topic", "camera_info_topic")


class ConfigError(Exception):
    """설정이 없거나 비어 있어 노드를 시작할 수 없음"""


def load_camera_topics(path):
    """camera.yaml에서 카메라 토픽 이름을 읽는다. 반환: {color_topic, aligned_depth_topic, camera_info_topic}"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {key: str(data.get(key) or "").strip() for key in CAMERA_TOPIC_KEYS}


def image_to_numpy(msg):
    """sensor_msgs/Image → numpy 배열 (cv_bridge 없이 변환)

    컬러: bgr8 / rgb8 → BGR (H, W, 3) uint8
    깊이: 16UC1 / mono16 → (H, W) uint16,  32FC1 → (H, W) float32 (m)
    """
    enc = msg.encoding.lower()
    rows = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.step)  # 줄 끝 여분(step)까지 포함
    if enc in ("bgr8", "rgb8"):
        img = rows[:, : msg.width * 3].reshape(msg.height, msg.width, 3)
        return np.ascontiguousarray(img[..., ::-1] if enc == "rgb8" else img)
    if enc in ("16uc1", "mono16"):
        dtype = np.dtype(">u2" if msg.is_bigendian else "<u2")
        return rows[:, : msg.width * 2].copy().view(dtype).reshape(msg.height, msg.width).astype(np.uint16)
    if enc == "32fc1":
        dtype = np.dtype(">f4" if msg.is_bigendian else "<f4")
        return rows[:, : msg.width * 4].copy().view(dtype).reshape(msg.height, msg.width).astype(np.float32)
    raise ValueError(f"지원하지 않는 영상 형식: {msg.encoding}")


def numpy_to_image(bgr, header):
    """BGR numpy 배열 → sensor_msgs/Image (bgr8)"""
    msg = Image()
    msg.header = header
    msg.height, msg.width = bgr.shape[:2]
    msg.encoding = "bgr8"
    msg.is_bigendian = 0
    msg.step = msg.width * 3
    msg.data = np.ascontiguousarray(bgr).tobytes()
    return msg


class PerceptionNode(Node):
    def __init__(self):
        super().__init__("perception_node")
        params = {name: self.declare_parameter(name, default).value
                  for name, default in {**PARAM_DEFAULTS, **NODE_PARAM_DEFAULTS}.items()}
        self.cfg = cfg_from_params(params)
        self.use_depth = bool(params["use_depth"])
        self.depth_unit_m = float(params["depth_unit_m"])
        self.last_found = None          # 검출 상태가 바뀔 때만 로그를 남기기 위함
        self.warned_size = False

        # 카메라 토픽 이름: config/camera.yaml (가이드: 코드에 하드코딩하지 않음)
        cam_path = params["camera_config"]
        if not cam_path:
            raise ConfigError("camera_config 파라미터가 비어 있음 → "
                              "-p camera_config:=<lv2_module5/config/camera.yaml 경로> 로 지정하세요")
        try:
            topics = load_camera_topics(cam_path)
        except OSError as e:
            raise ConfigError(f"camera_config 파일을 읽을 수 없음: {e}")
        needed = ["color_topic"] + (["aligned_depth_topic"] if self.use_depth else [])
        missing = [key for key in needed if not topics[key]]
        if missing:
            raise ConfigError(f"{cam_path}의 {', '.join(missing)} 값이 비어 있음 → RealSense wrapper 실행 후 "
                              "`ros2 topic list`로 실제 이름을 확인해 기록하세요")

        self.pub = self.create_publisher(PointStamped, "/target", 10)
        self.debug_pub = (self.create_publisher(Image, "/perception/debug_image", 1)
                          if params["publish_debug_image"] else None)

        # 영상 구독 QoS: 최신 영상만 처리하도록 큐는 짧게 (reliable이어도 밀린 영상을 쌓아 두지 않음)
        qos = (QoSProfile(depth=2, reliability=ReliabilityPolicy.RELIABLE)
               if params["image_reliable"] else qos_profile_sensor_data)
        if self.use_depth:
            color = Subscriber(self, Image, topics["color_topic"], qos_profile=qos)
            depth = Subscriber(self, Image, topics["aligned_depth_topic"], qos_profile=qos)
            self.sync = ApproximateTimeSynchronizer([color, depth], queue_size=10, slop=0.05)  # 시각 차 50ms 이내끼리 묶음
            self.sync.registerCallback(self.on_images)
        else:
            self.create_subscription(Image, topics["color_topic"], self.on_images, qos)

        r = self.cfg["hsv"]["ranges"][0]
        self.get_logger().info(
            f"인지 노드 시작: 컬러 {topics['color_topic']}"
            + (f", 깊이 {topics['aligned_depth_topic']}" if self.use_depth else "")
            + f", HSV {r['lower']}~{r['upper']}, min_area_ratio={self.cfg['min_area_ratio']}, "
            f"영상 구독={'reliable' if params['image_reliable'] else 'best effort'}, "
            f"확인 화면 발행={self.debug_pub is not None}")

    def on_images(self, color_msg, depth_msg=None):
        try:
            frame = image_to_numpy(color_msg)
            depth, scale = None, self.depth_unit_m
            if depth_msg is not None:
                depth = image_to_numpy(depth_msg)
                if depth_msg.encoding.lower() == "32fc1":
                    scale = 1.0                        # 32FC1은 이미 m 단위
                if depth.shape != frame.shape[:2]:     # 컬러에 정렬되지 않은 깊이는 쓸 수 없음
                    if not self.warned_size:
                        self.get_logger().warn(
                            f"깊이 {depth.shape}와 컬러 {frame.shape[:2]} 크기가 달라 거리 계산을 건너뜀 "
                            "(깊이를 컬러에 정렬해서 발행해야 함)")
                        self.warned_size = True
                    depth = None
        except ValueError as e:
            self.get_logger().error(str(e), throttle_duration_sec=5.0)
            return

        res = detect(frame, self.cfg, depth, scale)

        out = PointStamped()
        out.header = color_msg.header
        out.point.x = float(res["ex"])  # 미검출이면 detect()가 ex = ey = z = 0 을 돌려줌
        out.point.y = float(res["ey"])
        out.point.z = float(res["z"])
        self.pub.publish(out)

        if self.debug_pub is not None:
            self.debug_pub.publish(numpy_to_image(draw(frame, res), color_msg.header))

        if res["found"] != self.last_found:     # 검출 ↔ 미검출이 바뀔 때만 기록
            dist = "--" if res["dist_cm"] is None else f"{res['dist_cm']:.1f} cm"
            if res["found"]:
                self.get_logger().info(f"목표 검출: ex={res['ex']:+.3f} ey={res['ey']:+.3f} "
                                       f"z={res['z']:.4f} dist={dist} 후보={res['n_candidates']}")
            else:
                self.get_logger().info("목표 미검출 → x = y = z = 0 발행")
            self.last_found = res["found"]


def main(args=None):
    rclpy.init(args=args)
    try:
        node = PerceptionNode()
    except ConfigError as e:  # 설정 문제는 긴 오류 대신 해야 할 일을 알려주고 종료
        rclpy.logging.get_logger("perception_node").fatal(str(e))
        rclpy.try_shutdown()
        raise SystemExit(1)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):  # Ctrl+C·종료 신호는 정상 종료로 처리
        pass
    except Exception:
        if rclpy.ok():  # 실행 중에 난 오류는 그대로 알리고, 종료 신호와 겹쳐 난 오류(context 무효)만 무시
            raise
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
