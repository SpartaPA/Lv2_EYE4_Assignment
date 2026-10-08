# 검증 기록 — 2026-10-08

[report.md](../../../report.md)에 검증 결론·참고 이미지·미완료 회고를 통합했다. [verification_results.csv](verification_results.csv)는 실제 시험값을 발명하지 않고 이번 제출 자료의 증거 상태를 기록한다.

## 파일 구분

| 파일 | 의미 |
|---|---|
| verification_results.csv | 요구 시험·판정·증거·부족한 자료·검증 방해 원인 |
| recovery_trials.csv | 기존 실측 양식. 원본에 회차가 없어 헤더만 유지 |
| interruption_trials.csv | 기존 실측 양식. 원본에 회차가 없어 헤더만 유지 |
| ../perception/ | 이전 노트북 인지 평가 원본 |
| ../control/ | 이전 Pi DRY/PTY/USB 통신 원본 |
| ../opencr/ | 이전 commissioning·펌웨어 단독 LIVE 원본 |
| ../../verification_sources/ | 제출 회고·실행 스크립트·팀 PR 설명 요약 |

회고에서 역산한 시각을 실측 양식에 넣지 않았다. 복구 실패를 0초로 쓰지 않는다. latest LIVE 원본이 없는 상태는 실패율 100% 또는 성공률 0%와 다르다.

`tracking_logger.py`는 /target 수신 때만 행을 기록한다. /target 중단 후 정지 판단은 추적 CSV 하나로 입증할 수 없다. bridge를 강제 종료한 뒤 보드가 정지했는지도 종료된 bridge CSV만으로 확인할 수 없다. 영상·보드 상태·시각이 연결된 별도 근거가 필요하다.

이번 문서 작성 과정에서 신규 하드웨어 시험을 수행하지 않았다. 원본 파일의 수치·판정 칸은 수정하지 않았다.
