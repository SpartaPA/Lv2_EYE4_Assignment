# 카메라 부하 조건 USB DRY 60초 재확인 결과

## 시험 식별 및 판정

- 실행 ID: `camera_timing_20261008_114736_6d9W5s`
- 시험일: 2026-10-08 (KST)
- 원시 증거: `camera_timing_20261008_114736_6d9W5s_evidence.tar.gz`
- SHA-256: `5bce8e57847fdb4c114eb1c045e6ac9d74b6aeb8ac71a893f3c9406482c7e146`
- 기준 커밋: `0ffe9d089db26df9ea65d7ddb17d3552926e366b`
- 적용 변경: `opencr_node.py` 일반 상태 발행 최소 간격 100 ms, phase/reason 변경 및 서비스 처리 후 추가 상태 발행. 기존 시리얼 처리 타이머 10 ms 유지.
- 변경 소스 SHA-256: `a644d43c52e90fea2093420bc7288e886c24f897d6784e600ab764d9258b3fba`
- 이전 비교 실행: `camera_timing_20261008_111439_bRT2Q9` (51.8초 후 DISARM)

**판정: 계획한 60초 이상의 연속 ARMED 유지 및 FAULT 미발생 조건을 충족했다. ARMED 확인부터 첫 DISARM 송신까지 82.330658763초였다. 실제 모터 추종 성능 또는 LIVE 안전 검증의 통과를 의미하지 않는다.**

## 조건 및 절차

Pan/Tilt 2축을 유지했다. ROS_DOMAIN_ID=87, Pan/Tilt Kp=0.1/0.1, deadband=0.03/0.03, 속도 제한=0.05/0.05 rad/s, 방향=-1/+1, target timeout=0.5 s, recovery_frames=3, command_max_age_sec=0.15, USB=115200 baud이다. DRY 모드 및 enable_live_hardware=false로 실행했다.

실험 계획에 따라 모터 전원 분리와 카메라 기계적 지지를 유지하고 기존 관측기 및 비동기 CSV 로깅을 사용했다. 이는 작업자가 정한 실행 조건이며, 소프트웨어 로그만으로 실제 배선/지지 상태를 독립 검증한 것은 아니다. 실제 엔코더 중립 검사는 수행하지 않았다.

카메라/인지, 제어기, 브리지, 관측기를 실행하고 BOOT에서 PREPARE를 요청하여 READY에 도달한 뒤 ARM했다. 이후 명시적 DISARM 요청, 프로세스 종료, 리셋하지 않은 상태의 직접 STATUS 확인 순으로 종료했다.

## 시간 및 관측 결과

| 사건 | 결과 |
|---|---|
| 브리지 ARMED 확인 | 약 11:51:12.701 KST |
| 첫 DISARM 송신 | 약 11:52:35.031 KST |
| 분석 구간 | monotonic 12678.409287898 ~ 12760.739946661 |
| ARMED 유지 시간 | 82.330658763 s |
| 브리지 FAULT | 기록 없음 |
| 종료 phase | READY |

지속시간은 단조 시계 차이로 계산했고 KST는 기록된 wall/monotonic 기준으로 환산했다. 관측기는 monotonic 12678.432175245에 ARMED를 수신했다. 12738.498657010의 ARMED 상태 수신 시 60초 안내 조건이 충족된다. 표준출력 원문은 별도 저장되지 않아 안내 문구가 터미널에 실제 표시되었는지는 직접 인용하지 않는다. 지속시간 자체는 원시 이벤트로 확인된다.

## ARMED 구간 성능

| 지표 | 이번 실행 | 이전 51.8초 실행 |
|---|---:|---:|
| 제어기 명령 발행률 | 20.02 Hz | 20.04 Hz |
| 최대 명령 발행 간격 | 66.4 ms | 65.6 ms |
| 최대 브리지 명령 수신 콜백 간격 | 88.9 ms | 84.6 ms |
| 수신 시 명령 최대 나이 | 48.0 ms | 37.3 ms |
| 시리얼 타이머 콜백 실행률 | 99.33 Hz | 98.88 Hz |
| 최대 시리얼 타이머 콜백 간격 | 37.3 ms | 48.3 ms |
| 관측기 상태 메시지 수신률 | 9.40 Hz | 9.43 Hz |
| FAULT | 기록 없음 | 기록 없음 |

측정 방법: 분석 구간 내부의 `command_publish_begin`, `bridge_command_begin`, `bridge_tick_begin`, `observer_bridge_status` 이벤트를 사용했다. 이벤트율은 (N-1)/(마지막 시각-첫 시각), 최대 간격은 인접 이벤트 시각 차이의 최댓값이다. 수신 명령 나이는 `(ros_ns-stamp_ns)/10^6` ms이다. 수신 나이는 순수 네트워크 지연 또는 watchdog 전체 여유와 동일하지 않다. 상태 수신률은 관측기 기준이며, 정확한 발행률 측정과 구분한다.

기존 `timing_summary.txt`의 무FAULT 요약은 첫 프로세스 종료 직전 약 20초를 대상으로 한다. 이번에는 ARMED 전체 구간을 대표하지 않으므로 위 표는 JSONL을 별도 구간 추출하여 계산했다. 이전 값은 이전 실행 분석 결과를 인용했다.

## 추적 상태

관측기에 기록된 첫 LOST 전환은 ARM 이후 약 74.490초로, 첫 60초 안에는 LOST가 기록되지 않았다. 이후 아래 두 구간이 관측되었다.

| 전환 | ARM 이후 경과 시간 |
|---|---:|
| LOST → TRACKING | 74.490 → 74.685 s |
| LOST → TRACKING | 75.739 → 76.857 s |

제어 명령 발행 1,649개 중 stop=false 1,621개, stop=true 28개였다. 관측기 추적 상태 수신은 TRACKING 1,619개, LOST 26개였다. 서로 다른 이벤트 스트림의 개수 차이를 손실량으로 단정하지 않는다. 이는 의도적으로 계획한 가림 시험이 아니며 물체 재등장 시각도 별도로 확인하지 않았으므로 요구된 가림/복귀 반복시험을 대신하지 않는다.

## 로그 무결성 및 최종 상태

- CSV accepted=7,939, written=7,939, dropped=0, error 없음, 최종 대조 PASS.
- 제어기/브리지/관측기 버퍼 덮어쓰기 모두 0.
- 정리 오류 모두 0, 기록된 runtime_error 없음.

직접 확인한 종료 보드 응답:

```text
STATE DISARMED MODE=DRY ARMED=0 GOAL=0,0 POS=3078,4096 VEL=0,0 TORQUE=1,1 AGE_MS=4 T_MS=287077
```

DRY 보드의 DISARMED 및 영속도 상태를 확인했다. POS와 TORQUE는 시뮬레이션 값이므로 실제 엔코더 위치, 실제 토크 유지, 실제 모터 정지의 증거로 해석하지 않는다.

## 결론 및 다음 단계

상태 발행 주기를 낮춘 동일 소스에서 두 실행이 각각 약 51.8초와 82.3초 동안 FAULT 없이 유지되었고, 이번 실행으로 계획한 60초 DRY 확인을 완료했다. 150 ms 명령 신선도 제한과 2축 설정은 유지되었다. 상태 발행 부하 감소가 이전 실패의 유일한 원인 해결이었다는 인과관계나 모든 부하에서의 안정성을 입증하지는 않는다.

다음 단계는 추가 동일 DRY 반복이 아니라 LIVE 준비이다. 별도 읽기 전용 검사 스케치로 실제 엔코더 중립 및 Torque_Enable/오류 상태를 확인하고, 검토된 LIVE 펌웨어를 복원한 뒤 해당 시작 절차를 수행한다. 실제 모터 전원과 엔코더 검사는 LIVE 준비 단계에서만 다룬다. 이후 2축을 유지하면서 Pan Kp 비교, 정상 추종, 가림/복귀 및 입력·통신 중단 시험의 증거를 수집한다.

근거 파일: `bridge_timing.jsonl`, `controller_timing.jsonl`, `observer_timing.jsonl`, 각 `.meta.json`, `probe.py`, `arm.log`, `disarm.log`, `board_final_status.log`, `serial_usb.csv`, `timing_summary.txt`, `controller_params.yaml`, `bridge_params.yaml`, `source_head.txt`, `source_hashes.json`, `source_snapshot.tar.gz`, `experiment_note_ko.md`.
