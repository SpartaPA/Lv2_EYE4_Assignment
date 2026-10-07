"""Pan/Tilt 2축 P 제어 로직 (담당: 제어) — ROS·시리얼·모터 접근 없음

역할
  /target 한 프레임(ex, ey, area_ratio, 원본 영상 시각)을 받아 상태(IDLE/TRACKING/LOST)를
  갱신하고, 현재 상태에서 내보낼 두 축 속도 명령(rad/s)을 계산한다.
  control_node.py가 ROS 입출력을, 이 파일이 판단을 담당하므로 ROS 없이 단위 시험할 수 있다.

입력 규약 (발제문 /target, geometry_msgs/PointStamped)
  x = ex = (cx - W/2)/(W/2)   오른쪽 +   [-1, 1]
  y = ey = (cy - H/2)/(H/2)   아래쪽 +   [-1, 1]
  z = area_ratio              검출되면 (0, 1], 미검출이면 정확히 0
  z == 0 이면 x, y는 의미가 없으므로 제어에 쓰지 않는다.

출력 (stop, pan_rad_s, tilt_rad_s)
  pan  = clamp(pan_direction  * kp_pan  * ex, ±pan_speed_limit)    (|ex| <= pan_deadband 이면 0)
  tilt = clamp(tilt_direction * kp_tilt * ey, ±tilt_speed_limit)   (|ey| <= tilt_deadband 이면 0)
  direction(+1/-1)은 "영상 오차 부호 → 모터 원시 속도 부호" 변환이며 **이 파일에서 한 번만** 적용한다.
  opencr_node와 OpenCR 펌웨어는 부호를 다시 곱하지 않는다.

안전 규칙
  - 미검출(z=0), 값 이상, 오래된/중복/역순 시각 → 즉시 LOST, 두 축 0 (이전 속도 유지 금지)
  - 마지막 신선한 입력 후 timeout(기본 0.5초) → LOST, 두 축 0
  - LOST/IDLE → TRACKING 복귀는 신선한 검출 프레임 recovery_frames(기본 3)개 연속일 때만
  - set_enabled(False) → IDLE (명시적 중지). 다시 켜도 3프레임 조건을 거쳐야 TRACKING
  - 실제 엔코더 각도 제한은 위치를 아는 OpenCR 펌웨어가 담당한다. 여기서 위치를 적분해
    가짜 각도 제한을 만들지 않는다.
"""
import math

# 펌웨어 tracking_controller_2axis.ino 의 MAX_RAD_S 와 같은 값 (펌웨어가 이보다 큰 VEL을 거부).
# control의 축별 속도 상한은 이 값 이하여야 하며, opencr_node도 같은 상한으로 명령을 검사한다.
MAX_VELOCITY_RAD_S = 0.3


class Controller:
    def __init__(self, kp_pan=0.1, kp_tilt=0.1,
                 pan_speed_limit=0.05, tilt_speed_limit=0.05,
                 pan_deadband=0.03, tilt_deadband=0.03,
                 timeout=0.5, recovery_frames=3, pan_direction=-1, tilt_direction=1):
        """파라미터가 하나라도 잘못되면 ValueError — 잘못된 설정으로 노드가 시작되지 않게 한다."""
        values = (kp_pan, kp_tilt, pan_speed_limit, tilt_speed_limit,
                  pan_deadband, tilt_deadband, timeout)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Parameters must be finite')
        if min(kp_pan, kp_tilt) < 0 or timeout <= 0 or recovery_frames < 1:
            raise ValueError('Invalid control parameters')
        for limit in (pan_speed_limit, tilt_speed_limit):
            if not 0 < limit <= MAX_VELOCITY_RAD_S:
                raise ValueError(f'Speed limit must be in (0, {MAX_VELOCITY_RAD_S}] rad/s')
        for deadband in (pan_deadband, tilt_deadband):
            if not 0 <= deadband < 1:
                raise ValueError('Deadband must be in [0, 1)')
        if pan_direction not in (-1, 1) or tilt_direction not in (-1, 1):
            raise ValueError('Directions must be -1 or +1')
        self.kp_pan, self.kp_tilt = kp_pan, kp_tilt
        self.pan_speed_limit, self.tilt_speed_limit = pan_speed_limit, tilt_speed_limit
        self.pan_deadband, self.tilt_deadband = pan_deadband, tilt_deadband
        self.timeout, self.recovery_frames = timeout, recovery_frames
        self.pan_direction, self.tilt_direction = pan_direction, tilt_direction
        self.enabled = True
        self.state = 'IDLE'
        self.count = 0              # 복귀용 연속 신선 검출 프레임 수 (타이머 호출이 아니라 새 영상 기준)
        self.last_received = None   # 마지막 신선한 입력의 수신 단조 시각 (초)
        self.last_stamp = None      # 마지막으로 받아들인 원본 영상 시각 (ns) — 중복·역순 차단
        self.frame_stamp = None
        self.xy = (0.0, 0.0)

    def lose(self):
        """LOST로 전환: 복귀 카운트와 마지막 오차를 버린다 (이전 좌표 재사용 금지)."""
        self.state = 'LOST'
        self.count = 0
        self.xy = (0.0, 0.0)

    def set_enabled(self, enabled):
        """명시적 추적 중지/재개. 중지하면 IDLE + 정지, 재개해도 3프레임 복귀 조건을 다시 거친다."""
        self.enabled = bool(enabled)
        self.state = 'IDLE'
        self.count = 0
        self.xy = (0.0, 0.0)

    def receive(self, x, y, z, stamp_ns, ros_now_ns, mono_now):
        """/target 한 프레임 처리.

        stamp_ns   : 원본 Color 영상 시각 (header.stamp)
        ros_now_ns : 노드 ROS 시각 — bag 재생(use_sim_time)에서도 같은 시계로 비교된다
        mono_now   : 수신 단조 시각 — 시스템 시각이 바뀌어도 timeout이 늘어나지 않게 함
        """
        # timeout을 먼저 평가: 발행이 끊겼다 재개된 첫 프레임이 옛 TRACKING을 이어받지 못하게 한다.
        self.output(mono_now, ros_now_ns)
        if not self.enabled:
            return
        age = (ros_now_ns - stamp_ns) / 1e9
        valid = (all(math.isfinite(v) for v in (x, y, z))
                 and abs(x) <= 1 and abs(y) <= 1 and 0 <= z <= 1)
        # 신선도: 영상 시각이 현재보다 미래가 아니고 timeout 이내. 멈춘 카메라의 옛 영상을
        # 새 입력으로 취급하지 않는다.
        fresh = stamp_ns > 0 and 0 <= age <= self.timeout
        ordered = self.last_stamp is None or stamp_ns > self.last_stamp
        if not valid or not fresh or not ordered:
            self.lose()
            return
        self.last_stamp = stamp_ns
        self.frame_stamp = stamp_ns
        self.last_received = mono_now
        if z == 0:  # 정상 영상의 미검출: 입력은 신선하지만 목표가 없음 → 즉시 정지
            self.lose()
            return
        self.xy = (x, y)
        if self.state != 'TRACKING':
            self.count += 1
            if self.count >= self.recovery_frames:
                self.state = 'TRACKING'

    def output(self, mono_now, ros_now_ns):
        """현재 내보낼 명령 (stop, pan_rad_s, tilt_rad_s). 20 Hz 타이머와 receive()가 호출한다."""
        if not self.enabled:  # 명시적 중지: IDLE 유지, 새 추적 명령 없음
            return True, 0.0, 0.0
        if self.last_received is not None:
            age = (ros_now_ns - self.frame_stamp) / 1e9
            # 입력 침묵(수신 단조 시각) 또는 영상 시각 노화 중 하나라도 timeout이면 LOST
            if mono_now - self.last_received >= self.timeout or not 0 <= age <= self.timeout:
                self.lose()
        if self.state != 'TRACKING':
            return True, 0.0, 0.0
        x, y = self.xy

        def clamp(value, limit):
            return max(-limit, min(limit, value))

        pan = 0.0 if abs(x) <= self.pan_deadband else clamp(
            self.pan_direction * self.kp_pan * x, self.pan_speed_limit)
        tilt = 0.0 if abs(y) <= self.tilt_deadband else clamp(
            self.tilt_direction * self.kp_tilt * y, self.tilt_speed_limit)
        return False, pan, tilt
