"""정렬 깊이 영상을 거리별 색으로 바꿔 RViz에서 보는 확인용 도구 (/target·인지 노드와 무관)

구독: camera.yaml의 aligned_depth_topic (16UC1, 1 = 1 mm) — reliable (wrapper 영상은 best effort로 거의 전달되지 않음)
발행: /perception/depth_colormap  sensor_msgs/Image bgr8 (입력 깊이 영상과 같은 header)
색:   거리 범위 안 = 가까울수록 빨강 → 멀수록 파랑,  범위 밖 = 회색,  깊이 측정 실패(0) = 검정,  아래쪽에 범례
      기본 범위 = tracker.yaml의 depth_min_distance_cm ~ depth_max_distance_cm (유효 추적 거리)

실행 (lv2_module5 폴더에서, RealSense wrapper 실행 중, ROS 환경):
  python3 tools/depth_view.py                          # 범위 = tracker.yaml (13~100 cm)
  python3 tools/depth_view.py --min-cm 20 --max-cm 300 # 범위 직접 지정
RViz: Image 디스플레이의 Topic을 /perception/depth_colormap 으로 (rviz/tracking_view.rviz의 "Depth (color)")
"""
import argparse

import cv2
import numpy as np

from common import load_camera, load_params

TOPIC_OUT = "/perception/depth_colormap"
FONT = cv2.FONT_HERSHEY_SIMPLEX


def colorize(depth_mm, min_mm, max_mm):
    """깊이(mm) → BGR. 범위 안은 가까울수록 빨강(JET 역순), 범위 밖 회색, 측정 실패(0) 검정"""
    t = np.clip((depth_mm.astype(np.float32) - min_mm) / (max_mm - min_mm), 0, 1)
    out = cv2.applyColorMap(((1.0 - t) * 255).astype(np.uint8), cv2.COLORMAP_JET)
    out[(depth_mm > 0) & ((depth_mm < min_mm) | (depth_mm > max_mm))] = (90, 90, 90)
    out[depth_mm == 0] = 0
    return out


def draw_legend(img, min_cm, max_cm):
    """아래쪽에 색 막대와 거리 표시"""
    h, w = img.shape[:2]
    x0, x1, y0, y1 = 10, w - 10, h - 40, h - 26
    img[h - 46:] = 0  # 글자가 영상 색에 묻히지 않게 범례 뒤를 어둡게
    ramp = (255 - np.linspace(0, 255, x1 - x0)).astype(np.uint8).reshape(1, -1)
    img[y0:y1, x0:x1] = np.repeat(cv2.applyColorMap(ramp, cv2.COLORMAP_JET), y1 - y0, axis=0)
    right = f"{max_cm:g} cm"
    (tw, _), _ = cv2.getTextSize(right, FONT, 0.5, 1)
    for text, x in ((f"{min_cm:g} cm", x0), (right, x1 - tw)):
        cv2.putText(img, text, (x, h - 8), FONT, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, "gray: out of range  black: no depth", (w // 2 - 140, h - 8), FONT, 0.45,
                (200, 200, 200), 1, cv2.LINE_AA)


def main():
    params = load_params()
    ap = argparse.ArgumentParser(description="정렬 깊이 → 거리별 색 영상 (RViz 확인용)")
    ap.add_argument("--min-cm", type=float, default=float(params["depth_min_distance_cm"]))
    ap.add_argument("--max-cm", type=float, default=float(params["depth_max_distance_cm"]))
    args = ap.parse_args()
    if not 0 <= args.min_cm < args.max_cm:
        raise SystemExit("--min-cm은 0 이상, --max-cm보다 작아야 함")
    topic = load_camera().get("aligned_depth_topic")
    if not topic:
        raise SystemExit("camera.yaml의 aligned_depth_topic이 비어 있음")

    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import Image

    from realsense_tracker.perception_node import image_to_numpy

    rclpy.init()
    node = rclpy.create_node("depth_view")
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
    pub = node.create_publisher(Image, TOPIC_OUT, qos)
    min_mm, max_mm = args.min_cm * 10, args.max_cm * 10

    def on_depth(msg):
        try:
            depth = image_to_numpy(msg)
        except ValueError as e:
            node.get_logger().error(str(e), throttle_duration_sec=5.0)
            return
        if msg.encoding.lower() == "32fc1":  # m 단위 → mm
            depth = np.nan_to_num(depth * 1000.0)
        out = colorize(depth, min_mm, max_mm)
        draw_legend(out, args.min_cm, args.max_cm)
        img = Image()
        img.header = msg.header
        img.height, img.width = out.shape[:2]
        img.encoding, img.is_bigendian, img.step = "bgr8", 0, out.shape[1] * 3
        img.data = out.tobytes()
        pub.publish(img)

    node.create_subscription(Image, topic, on_depth, qos)
    node.get_logger().info(f"{topic} → {TOPIC_OUT}  색 범위 {args.min_cm:g}~{args.max_cm:g} cm "
                           "(가까움 빨강 → 멀리 파랑, 범위 밖 회색, 측정 실패 검정)")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
