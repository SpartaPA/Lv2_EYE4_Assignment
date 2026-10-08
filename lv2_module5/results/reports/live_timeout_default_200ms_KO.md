# LIVE 명령 신선도 기본 설정 200 ms 채택

- 적용 파일: realsense_tracker/config/opencr_live.yaml
- 변경: command_max_age_sec 0.15 → 0.20.
- 근거: 150 ms 실행에서 약 152.6 ms 제어기 발행 간격과 명령 만료가 관측되었다.
- 후속 200 ms LIVE 실행은 약 146.7초 동안 FAULT 없이 동작했다.
- 작업자는 양축 추종 방향이 올바르고 처짐·진동이 없었다고 보고했다.
- 이 결과가 timeout 변경의 인과적 효과나 모든 부하에서의 안정성을 입증하지는 않는다.
- 별도 DISARM 검증 시험은 작업자 결정으로 당분간 보류한다.
- 보류는 정상 시험 종료 시 DISARM 절차를 생략한다는 의미가 아니다.
- 200 ms 설정에서 통제된 명령 중단 정지 검증은 미완료이다.
- 펌웨어 timeout 300 ms, 모터 watchdog, 속도 제한 및 축별 경계는 유지한다.
- generic bridge fallback 및 기존 DRY 진단 설정은 변경하지 않는다.
