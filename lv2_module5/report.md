### 제어: 비동기 CSV 로깅 개선 및 USB DRY 비교 시험

기존 Serial CSV 동기 기록 구간에서 약 138.72 ms의 지연이 관찰되어,
파일 쓰기를 bounded queue와 별도 worker thread로 분리했다.
제어기, 펌웨어 및 bridge의 150 ms 명령 신선도 제한은 유지했다.

Raspberry Pi에서 기존 core 시험 20개와 logger 시험 3개가 통과했으며,
로깅을 활성화한 상태로 중앙 30초 → 오른쪽 120초 →
목표 발행 중단 1200초 → 복구 20초의 전체 DRY 시퀀스를 완료했다.
Serial CSV에 FAULT 레코드는 없었고, 계획된 disarm 및 최종
DISARMED MODE=DRY, GOAL=0,0, VEL=0,0을 확인했다.

최종 CSV는 211201개 데이터 행을 포함한다.
저장된 로깅 상태에서 dropped=0 및 error=""를 확인했으며,
보존된 마지막 Serial 이벤트 12305개의 내용과 순서는 CSV와 일치했다.
다만 CSV_FINAL 종료 보고 누락으로 최종 카운터와 전체 행 수의 대조는 미완료다.

또한 disarm 이후 READY 상태에서 약 338 ms의 명령 수신 콜백 간격이 관찰되었다.
따라서 이번 결과는 해당 DRY 시퀀스의 성공으로 평가하며,
전체 타이밍 문제 해결이나 실제 모터 운용 검증 완료로 해석하지 않는다.

- 상세 기록: [시험 기록](results/logs/ros2/serial_timing_async_csv_20261007_123117/progress_record_ko.md)
- 후속 작업: 종료 통계 저장 보완, 수신 지연 확인, 팀 브랜치 통합 후 회귀 시험,
  카메라·인지 동시 실행 DRY 시험
