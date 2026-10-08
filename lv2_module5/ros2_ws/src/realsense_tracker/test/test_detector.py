"""detector.py 단위 시험 — 합성 영상으로 ex/ey/area_ratio 산식, 미검출 z=0, 선택적 거리 gate 확인 (ROS 불필요)"""
import unittest

import numpy as np

from realsense_tracker.detector import PARAM_DEFAULTS, cfg_from_params, detect

W, H = 640, 480
BLUE = (200, 60, 20)  # BGR, HSV H≈110 → 기본 범위 [93, 130] 안


def frame_with_square(cx, cy, half=20):
    img = np.full((H, W, 3), 255, np.uint8)
    img[cy - half:cy + half, cx - half:cx + half] = BLUE
    return img


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.cfg = cfg_from_params(PARAM_DEFAULTS)

    def test_normalized_error_and_area_ratio(self):
        res = detect(frame_with_square(480, 120), self.cfg)
        self.assertTrue(res['found'])
        self.assertAlmostEqual(res['ex'], (res['cx'] - W / 2) / (W / 2))
        self.assertAlmostEqual(res['ey'], (res['cy'] - H / 2) / (H / 2))
        self.assertGreater(res['ex'], 0.45)   # 오른쪽 +
        self.assertLess(res['ey'], -0.45)     # 위쪽 -
        self.assertAlmostEqual(res['z'], 40 * 40 / (W * H), delta=0.0005)

    def test_no_target_publishes_zero(self):
        res = detect(np.full((H, W, 3), 255, np.uint8), self.cfg)
        self.assertEqual((res['found'], res['ex'], res['ey'], res['z']), (False, 0.0, 0.0, 0.0))

    def test_depth_is_record_only_by_default(self):
        far = np.full((H, W), 3000, np.uint16)  # 300 cm — 13~100 cm 밖
        res = detect(frame_with_square(320, 240), self.cfg, far, 0.001)
        self.assertTrue(res['found'])
        self.assertAlmostEqual(res['dist_cm'], 300.0)
        res = detect(frame_with_square(320, 240), self.cfg, np.zeros((H, W), np.uint16), 0.001)
        self.assertTrue(res['found'])          # 깊이 측정 실패여도 Color 검출 유지
        self.assertIsNone(res['dist_cm'])

    def test_optional_depth_gate(self):
        cfg = cfg_from_params({**PARAM_DEFAULTS, 'enforce_depth_range': True})
        far = np.full((H, W), 3000, np.uint16)
        res = detect(frame_with_square(320, 240), cfg, far, 0.001)
        self.assertEqual((res['found'], res['z']), (False, 0.0))
        near = np.full((H, W), 500, np.uint16)
        self.assertTrue(detect(frame_with_square(320, 240), cfg, near, 0.001)['found'])


if __name__ == '__main__':
    unittest.main()
