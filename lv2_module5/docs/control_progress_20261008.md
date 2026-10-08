# 제어 개발 진행 기록 — 2026-10-08

## 1. 현재 상태

Raspberry Pi의 ROS 2 인지·제어 노드와 OpenCR을 연결하여
실제 Pan/Tilt 추적 시험을 수행했다.

현재 작업 설정은 Pan Kp 0.10 / Tilt Kp 0.10으로 선정한다.
이는 팀 공유 및 후속 검증에 사용할 설정이며,
과제의 모든 성능·안전 검증이 완료되었다는 의미는 아니다.

## 2. 선정한 제어 설정

설정 파일:
`ros2_ws/src/realsense_tracker/config/control.yaml`

| 항목 | 값 |
|---|---:|
| Pan Kp | 0.10 |
| Tilt Kp | 0.10 |
| Pan 속도 상한 | 0.05 rad/s |
| Tilt 속도 상한 | 0.05 rad/s |
| Pan deadband | 0.03 |
| Tilt deadband | 0.03 |
| Target timeout | 0.5 s |
| 추적 복귀 조건 | 신선한 목표 3프레임 연속 검출 |
| Bridge command age limit | 0.20 s |

Kp는 정규화된 중심 오차 1.0당 속도 명령(rad/s)의 크기이다.
Bridge command age limit는 별도 bridge 설정이다.

이번 선택에서는 Pan Kp만 비교했으며,
Tilt Kp와 속도 상한, deadband는 유지했다.

## 3. Kp 선정 근거

비교한 설정:

- 설정 A: Pan Kp 0.05 / Tilt Kp 0.10
- 설정 B: Pan Kp 0.10 / Tilt Kp 0.10

운전자 관찰:

- 설정 A는 Pan 추종이 느렸으며 목표 근처에서 다소 느려지거나
  멈추는 구간이 있었다.
- 설정 B는 Pan 추종 속도가 적절했고 반복 진동이나 오버슈트는
  관찰되지 않았다.
- 두 시험에서 Tilt 처짐이나 진동은 관찰되지 않았다.

따라서 후속 시험 및 팀 공유를 위한 작업 설정으로 설정 B를 선택한다.

단, 동일 비교 구간의 정량 분석과 설정별 3회 반복 조건은
아직 검증 완료되지 않았다. 최적 Kp 또는 최종 성능 검증 완료로
해석하지 않는다.

## 4. 최근 검토한 시험

### 설정 A

Run ID:
`kp_pan005_manual_20261008_181352_CE77Ft`

Archive:
`kp_pan005_manual_20261008_181352_CE77Ft_evidence_20261008_183249.tar.gz`

### 설정 B

Run ID:
`kp_pan010_manual_20261008_183415_CwS5pX`

Archive:
`kp_pan010_manual_20261008_183415_CwS5pX_evidence_20261008_184518.tar.gz`

### 기록 결과

| 항목 | 설정 A | 설정 B |
|---|---:|---:|
| Serial accepted / written | 14049 / 14049 | 6469 / 6469 |
| Serial dropped | 0 | 0 |
| Logger error | 없음 | 없음 |
| 검토 로그의 bridge FAULT / serial timeout | 발견되지 않음 | 발견되지 않음 |
| ARM TX → DISARM TX | 105.35 s | 45.72 s |
| DISARM TX → ACK RX | 약 62 ms | 약 54 ms |
| DISARM TX → 최초 정지 상태 보고 | 약 164 ms | 약 161 ms |

정지 상태 보고는 DISARMED, goal=0,0, vel=0,0을 의미한다.

DISARM 시간은 bridge의 serial 전송 기록부터 측정했다.
키보드 Enter 입력부터의 시간이나 실제 물리적 정지 순간을
측정한 값이 아니다.

두 시험은 수동 ARM/DISARM 방식으로 수행했다.
자동 cue client의 CLIENT READY 및 BOARD STOP CONFIRMED 항목은
이번 수동 시험에 해당하지 않는다.

## 5. 확인된 예외 및 해석 제한

- 설정 B에서 ARM TX 후 약 2.02초에 LOST가 기록되었고,
  약 2.99초에 TRACKING으로 복귀했다.
- 해당 구간에서 controller는 stop=true 명령 20개를 발행했다.
- 목표 소실 원인과 실제 영상 구간의 대응은 추가 확인이 필요하다.
- 이 사건만으로 Kp가 소실의 원인이라고 판단하지 않는다.
- 두 시험의 전체 ARMED 시간이 다르므로 전체 구간 평균을
  그대로 Kp 비교 결과로 사용하지 않는다.
- LEFT → CENTRE → RIGHT → CENTRE의 대응 구간을 먼저 식별한다.
- SUPPORTED_OFF 및 torque=0,0은 운전자가 확인했다.
  해당 serial 교환은 이번 archive에 포함되어 있지 않다.
- 과거 시험을 포함한 설정별 3회 비교 가능 여부는 아직 검토 중이다.


## 6. 증거 연결

### 설정 A — Pan Kp 0.05 / Tilt Kp 0.10

- Run ID: `kp_pan005_manual_20261008_181352_CE77Ft`
- Archive: `kp_pan005_manual_20261008_181352_CE77Ft_evidence_20261008_183249.tar.gz`
- Archive 다운로드: [설정 A 원본 기록](https://drive.google.com/file/d/1lla32U1u735MWSsd2OhCmlPHiZjmapPS/view?usp=sharing)
- Archive SHA-256: 'f025839c3e030d31ccb997e429c9f0e5a8eb9c68a5749828fd5d52225ebf4382'
- 영상 파일명: '20261008_161939_kp005.mp4'
- 영상 링크: [설정 A 추적 영상](https://drive.google.com/file/d/1REeAhNgEehgu9pnbofsCcOhR3siJY3Lk/view?usp=drive_link)

### 설정 B — Pan Kp 0.10 / Tilt Kp 0.10

- Run ID: `kp_pan010_manual_20261008_183415_CwS5pX`
- Archive: `kp_pan010_manual_20261008_183415_CwS5pX_evidence_20261008_184518.tar.gz`
- Archive 다운로드: [설정 B 원본 기록](https://drive.google.com/file/d/19J1ZxYnpnN_kPketWNs_vwTe8DfW5dM-/view?usp=drive_link)
- Archive SHA-256: 'fe500fc00dc9921771a65e0752d80e5c8674a5824dc25a9ecb7f9055e17a7f84'
- 영상 파일명: '20261008_164436_kp010.mp4'
- 영상 링크: [설정 B 추적 영상](https://drive.google.com/file/d/1VglOKOegU9RWukwfchgXF3M38RZ_DiKB/view?usp=drive_link)

### Source 식별

- 각 시험의 source commit 및 미커밋 변경 사항: 확인 필요
- 현재 checkout의 commit을 과거 시험의 commit으로 소급하여 기록하지 않는다.

## 7. 남은 작업

- [ ] 각 영상과 Run ID 연결
- [ ] 이전 시험을 포함한 전체 시험 목록 작성
- [ ] 동일 조건의 Kp 설정별 3회 비교 가능 여부 확인
- [ ] 비교 구간의 오차·명령·상태 그래프 작성
- [ ] 정상 추적 30초 시험 및 성능 지표 정리
- [ ] 약 2초 가림 후 재등장 시험 5회 검증
- [ ] /target 발행 중단에 따른 정지 검증
- [ ] 제어 통신 중단 시 보드 측 timeout 정지 검증
- [ ] Pan/Tilt 방향·회전 범위 제한 증거 정리
- [ ] 대표 성공 및 소실·복귀 bag 기록·재현
- [ ] 다른 팀원의 실행 재현 확인
- [ ] PR 리뷰 및 팀 문서 연결

## 8. 팀 공유 범위

이번 PR에서는 현재 제어 구현, 작업 설정과 시험 근거를 공유한다.
미완료 검증은 후속 작업으로 명시하고,
전체 과제 검증 완료로 표시하지 않는다.
