# Pan 단독 초기 구동 시험

- 시험일: 2026-10-06
- 대상: Pan ID 11
- Tilt ID 12: 토크 비활성화 및 기계적 지지 유지
- 원본 로그: [commission.log](commission.log)
- 방향 기준: 카메라 뒤에서 정면을 바라보는 방향

## 확인 결과

| 항목 | 결과 |
|---|---|
| 초기 검사 | CHECK_OK |
| 명시적 STOP | STOPPED DISARMED 확인 |
| ARM 대기 시간 초과 | ARM_IDLE_TIMEOUT 이후 DISARMED 확인 |
| JOG + | 실제 좌측 회전, 위치 3070 → 3074 |
| JOG - | 실제 우측 회전, 위치 3074 → 3067 |
| 두 JOG의 시간 제한 | JOG_TIMEOUT 이후 STOPPED DISARMED 확인 |
| 최종 상태 | DISARMED, 위치 3067, 속도 0 |

## 해석 및 제한

- Pan의 양의 원시 속도 명령은 좌측, 음의 명령은 우측 회전에 대응한다.
- ERR LINE이 한 차례 발생했으며 원인 입력은 기록되지 않았다.
  이후 STATUS 응답으로 파서 복구를 확인했다.
- 본 시험은 방향 및 기본 정지 동작 확인이다.
- 실제 정지 지연, 위치 경계 정지, 통신 단절 시 모터 버스 watchdog,
  피드백 실패 처리는 아직 실측 검증하지 않았다.
- Tilt의 구동 및 중력 부하 유지 성능은 아직 미검증이다.
