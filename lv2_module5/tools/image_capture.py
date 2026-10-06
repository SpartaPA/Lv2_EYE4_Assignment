"""3종 장면(정상/미검출/가림) 검출 결과 저장 (RealSense 컬러 + 깊이)

키:  n = 정상(normal)   e = 목표 없음(empty)   o = 일부 가림(occluded)   q = 종료
저장:
  results/images/detection/<장면>_<시각>_{raw,mask,det}.png   원본 / 색 마스크 / 검출 결과 그림
  results/logs/perception/log.csv                             저장할 때마다 한 줄씩 기록

실행 (lv2_module5 폴더에서):
  python3 tools/image_capture.py --source ros   # RealSense ROS wrapper 토픽에서 받음 (실제 파이프라인과 같은 입력, ROS 환경)
  python tools/image_capture.py                 # RealSense를 직접 엶 (도구용 .venv, wrapper가 꺼져 있어야 함)
  ... --headless                                # 화면 없이: 터미널에 n/e/o/q 입력 후 Enter
설정: ros2_ws/src/realsense_tracker/config/tracker.yaml (perception_node), config/camera.yaml
"""
import argparse
import csv
import os
import sys
import time

import cv2

from common import (PARAMS_PATH, RESULTS, RealSenseCamera, RosCamera, cfg_from_params, detect, draw,
                    load_camera, load_params)

OUT_IMG = str(RESULTS / "images" / "detection")
OUT_LOG = str(RESULTS / "logs" / "perception" / "log.csv")
SCENES = {"n": "normal", "e": "empty", "o": "occluded"}


def save(frame, res, scene, cfg):
    os.makedirs(OUT_IMG, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_LOG), exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    ts, n = stamp, 2
    while os.path.exists(f"{OUT_IMG}/{scene}_{ts}_raw.png"):  # 같은 초에 또 저장하면 _2, _3 …을 붙여 덮어쓰기 방지
        ts, n = f"{stamp}_{n}", n + 1
    base = f"{OUT_IMG}/{scene}_{ts}"
    cv2.imwrite(f"{base}_raw.png", frame)
    cv2.imwrite(f"{base}_mask.png", res["mask"])
    cv2.imwrite(f"{base}_det.png", draw(frame, res))

    new = not os.path.exists(OUT_LOG)
    with open(OUT_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "scene", "found", "ex", "ey", "z", "dist_cm", "n_candidates",
                        "width", "height", "hsv_ranges", "min_area_ratio"])
        H, W = frame.shape[:2]
        dist = "" if res["dist_cm"] is None else f"{res['dist_cm']:.1f}"  # 측정 실패·믿을 수 없으면 빈칸
        w.writerow([ts, scene, res["found"], f"{res['ex']:.4f}", f"{res['ey']:.4f}",
                    f"{res['z']:.5f}", dist, res["n_candidates"], W, H,
                    cfg["hsv"]["ranges"], cfg["min_area_ratio"]])
    print(f"[{scene}] found={res['found']} ex={res['ex']:+.3f} z={res['z']:.4f} "
          f"dist={dist or '--'} cm → {base}_*.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=str(PARAMS_PATH), help="perception_node 파라미터 파일 (tracker.yaml)")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--source", choices=["realsense", "ros"], default="realsense",
                    help="realsense = 카메라 직접 (기본), ros = RealSense ROS wrapper 토픽")
    args = ap.parse_args()

    cfg = cfg_from_params(load_params(args.params))
    cam = (RosCamera if args.source == "ros" else RealSenseCamera)(load_camera())
    print(f"입력: {'RealSense ROS wrapper 토픽' if args.source == 'ros' else 'RealSense 직접 (pyrealsense2)'}")

    while True:
        if args.headless:
            key = input("n/e/o 저장, q 종료 > ").strip()[:1]
            cam.flush()                 # 입력을 기다리는 동안 쌓인 오래된 프레임 버리기
        ok, frame, depth = cam.read()
        if not ok:
            print("카메라 프레임을 못 읽음")
            cam.release()
            sys.exit(1)
        res = detect(frame, cfg, depth, cam.depth_scale)

        if not args.headless:
            mask_bgr = cv2.cvtColor(res["mask"], cv2.COLOR_GRAY2BGR)
            cv2.imshow("capture (n/e/o 저장, q 종료)", cv2.hconcat([draw(frame, res), mask_bgr]))
            key = chr(cv2.waitKey(1) & 0xFF)

        if key in SCENES:
            save(frame, res, SCENES[key], cfg)
        elif key == "q":
            break

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
