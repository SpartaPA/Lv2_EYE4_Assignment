# 비동기 CSV 로깅 적용 및 USB DRY 비교 시험

## 1. 시험 목적

기존 USB DRY 시험에서는 Serial CSV 기록 콜백의 실행 구간이 약
138.72 ms까지 길어지면서 bridge의 150 ms 명령 신선도 제한을 초과하는
ROS_COMMAND_TIMEOUT이 발생했다.

CSV 기록을 비활성화한 비교 시험에서는 전체 입력 시퀀스가 완료되었으며,
이후 제어 노드를 수동 종료했을 때 예상된 watchdog timeout이 발생했다.

이번 시험은 CSV 파일 쓰기를 bridge 제어 콜백에서 분리한 뒤,
로깅을 활성화한 상태에서도 동일한 입력 시퀀스를 완료하는지 확인하기 위해 수행했다.

기존 지연 구간에는 파일 쓰기뿐 아니라 프로세스 스케줄링 지연도 포함될 수 있으므로,
저장장치가 유일한 원인이라고 단정하지 않는다.

## 2. 구현 변경

- 기준 브랜치: dev/minhyeok
- 기준 커밋: d489b99c1754b1146868a3057095585b55dc105c
- 기준 커밋에 opencr_async_csv_d489b99.patch를 적용한 작업 트리에서 시험
- opencr_node.py의 record()에서 직접 수행하던 CSV 쓰기 및 flush 제거
- 최대 4,096개 레코드를 보관하는 bounded queue 도입
- 별도 worker thread에서 CSV 일괄 기록 및 주기적 flush 수행
- queue 포화 시 제어 콜백을 대기시키지 않고 dropped 수 증가
- bridge_status에 accepted, written, dropped, error 및 worker 상태 추가
- 종료 시 Serial DISARM/close를 먼저 수행한 뒤 logger 종료를 제한된 시간 동안 대기
- 제어기, 펌웨어 및 150 ms 명령 신선도 제한은 변경하지 않음

## 3. 사전 검증

Raspberry Pi에서 다음 항목을 확인했다.

- 기존 제어/Serial core 단위 시험: 20개 통과
- 비동기 CSV logger 시험: 3개 통과
- realsense_tracker_interfaces 및 realsense_tracker 빌드 성공
- 실행 환경에서 AsyncCsv 모듈 import 확인
- SerialNode.record()가 비동기 logger에 레코드를 전달하는 구현인지 확인

## 4. 시험 조건

- 실행 장비: Raspberry Pi
- ROS 2 배포판: Lyrical
- OpenCR 모드: DRY
- 실제 모터 연결: 해제
- Serial CSV 기록: 활성화
- bridge 명령 신선도 제한: 0.15초
- observer: ARM 이전 실행
- 시험 디렉터리: serial_timing_async_csv_20261007_123117

ARM 이후 자동 입력:
1. 중앙 목표 30초
2. 오른쪽 목표 120초
3. /target 발행 중단 1,200초
4. 오른쪽 목표 재발행 20초

목표 발행 중단 중에도 제어 노드는 계속 실행하며 STOP 명령을 발행했다.

## 5. 시험 결과

- 전체 자동 입력 시퀀스 완료
- 저장된 Serial CSV에서 FAULT 레코드 0건
- 시퀀스 완료 후 bridge 상태 ARMED, fault reason 없음
- 이후 목표가 다시 소실된 상태에서 두 축 목표 속도 및 모의 속도 0 확인
- /opencr/disarm 요청 성공
- bridge READY 및 보드 DISARMED, ARMED=0 확인
- 제어 노드를 유지한 상태에서 계획된 disarm 수행
- Terminal A를 Ctrl+C로 종료
- 최종 직접 STATUS 조회에서도 DISARMED MODE=DRY, GOAL=0,0, VEL=0,0 확인
- TORQUE=1,1은 DRY 모드의 모의 토크 유지 상태이며 실제 모터 검증 결과가 아님

로깅 상태:
- 시퀀스 완료 후 저장한 상태: accepted=199540, written=199540,
  dropped=0, error=""
- disarm 확인 상태: accepted=208736, written=208736,
  dropped=0, error=""
- 최종 CSV 데이터 행 수: 211201개, 헤더 제외
- 보존된 bridge 진단의 마지막 Serial 이벤트 12305개는
  CSV 마지막 12305개 행의 direction/line과 순서대로 일치

## 6. 타이밍 분석과 해석 범위

보존된 bridge 진단 구간 약 147.49초에서:
- Serial 기록 콜백 최대 실행 시간: 약 0.439 ms
- bridge timer 콜백 최대 실행 시간: 약 2.976 ms
- bridge timer 시작 간 최대 간격: 약 13.016 ms

비동기 변경 후 Serial 기록 콜백 시간은 큐에 전달하는 시간이며,
worker의 실제 파일 쓰기 완료 시간을 의미하지 않는다.

진단은 최근 60000개 이벤트를 보관하는 순환 버퍼 방식이므로,
위 최대값을 전체 시험 시간의 최대값으로 해석하지 않는다.

추가로 disarm 완료 후 READY 상태에서 bridge 명령 수신 콜백 간
약 338.16 ms의 간격과 약 239.93 ms의 명령 원본 시각 지연이 관찰되었다.
이는 ARMED 상태에서 발생한 fault는 아니지만,
모든 메시지 전달·스케줄링 지연이 해소되었다고 판단할 수 없는 근거다.

## 7. 한계 및 미확인 항목

- CSV_FINAL 종료 보고가 bridge.log에 남지 않음
- 최종 accepted/written 카운터와 전체 211201행의 완전 대조는 미확인
- 저장된 상태와 마지막 Serial 이벤트 대조는 로깅 정상 동작을 뒷받침하지만,
  전체 기록의 무손실을 최종 카운터로 입증한 것은 아님
- status topic echo에서 메시지 유실 알림 1건이 있었음
- 해당 알림은 CSV dropped와 구분하며 원인은 아직 확정하지 않음
- 실제 카메라/인지 처리 부하가 없는 DRY 시험 결과임
- 실제 모터 추적 성능, 장시간 신뢰성 및 전체 시스템 부하 조건은 별도 검증 필요

## 8. 결론

비동기 CSV 기록을 활성화한 상태에서 20분 목표 소실과 복구를 포함한
전체 DRY 입력 시퀀스를 완료했으며, 예상하지 않은 bridge fault는 기록되지 않았다.
계획된 disarm과 최종 보드 정지 상태도 확인했다.

이번 결과는 제어 콜백에서 동기 파일 쓰기를 분리한 변경의 유효성을 뒷받침한다.
다만 종료 카운터 누락 및 READY 상태의 명령 수신 지연이 남아 있으므로,
전체 타이밍 문제의 완전 해결 또는 LIVE 운용 검증 완료로 기록하지 않는다.

## 9. 다음 작업

1. 진단 wrapper와 프로세스 종료 경로를 확인하고 최종 logger 통계 저장을 보완한다.
2. READY 상태에서 관찰된 명령 수신 지연을 보존하고 원인을 추가 확인한다.
3. 팀 통합 브랜치 dev/test1의 최신 변경을 검토하고 제어 변경을 통합한다.
4. 통합 후 7개 모의 입력, STOP/복구 및 watchdog 회귀 시험을 수행한다.
5. Raspberry Pi에서 카메라·인지 노드를 함께 실행한 DRY 부하 시험을 수행한다.
6. 이후 실제 Pan/Tilt 추적 및 과제 필수 정량 시험을 진행한다.
