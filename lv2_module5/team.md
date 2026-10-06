# Team EYE4 (아이뻐)

## 1. 팀 정보

- 팀명: EYE4 (아이뻐)
- 프로젝트: Vision Object Tracking System
- 수행 인원: 4명
- 팀장: 전승혜 (SeungHye-J)
- 팀원: 김상화, 한상준, 조민혁
- 저장소: `Lv2_EYE4_Assignment`

---

## 2. 팀원 및 역할

| 이름 | GitHub ID | 역할 | 담당 Issue | 병합된 본인 PR | 다른 PR 리뷰 | 구현·검증 내용 |
| --- | --- | --- | --- | --- | --- | --- |
| 전승혜 | SeungHye-J | 팀장 + 검증·문서화 | TODO | [#1](https://github.com/SpartaPA/Lv2_EYE4_Assignment/pull/1), [#2](https://github.com/SpartaPA/Lv2_EYE4_Assignment/pull/2), [#4](https://github.com/SpartaPA/Lv2_EYE4_Assignment/pull/4), [#8](https://github.com/SpartaPA/Lv2_EYE4_Assignment/pull/8) | TODO | 저장소·문서 구조, 시험 조건(test.yaml), 통합본 감사·요구사항 추적, LIVE bridge 모드·지표 도구·문서 (dev/test1, 리뷰 전) |
| 김상화 | SangHwaKim09 | 인지 | TODO | 미기록 (main 병합 PR 없음 — dev/sanghwa) | TODO | detector·perception_node, HSV 튜닝·캡처·평가 도구, 세 장면·30/10 평가 프레임, D435 wrapper·QoS 실측 |
| 한상준 | WindForce08 | 통합 | TODO | [#3](https://github.com/SpartaPA/Lv2_EYE4_Assignment/pull/3), [#5](https://github.com/SpartaPA/Lv2_EYE4_Assignment/pull/5) | TODO | ROS 2 작업 환경·패키지 구성, tracker.launch.py, recordings 문서, 제어 파라미터 초안 |
| 조민혁 | eiioitsMin | 제어 | TODO | [#6](https://github.com/SpartaPA/Lv2_EYE4_Assignment/pull/6) | TODO | control·serial bridge, 2축 펌웨어, DYNAMIXEL 식별·commissioning, DRY/PTY/USB 시험 기록 |

> 역할은 인지·제어·통합·검증·문서화 영역을 기준으로 분담하며,
> 공동 작업을 수행하더라도 각자의 구현·검토·시험 기여를 구분하여 기록한다.
>
> PR 열은 main의 squash 병합 커밋 작성자 기준으로 확인한 링크다 (2026-10-07). Issue·리뷰 링크는 저장소 기록에서 확인하지 못해 TODO로 둔다 — 실제 링크만 적는다.
> 구현·검증 내용은 각자의 작업 브랜치 커밋(dev/sanghwa, dev/minhyeok, dev/sangjun) 기준이며, 장비 시험 여부는 report.md를 따른다.

---

## 3. 역할별 책임

### 팀장·테크리드

- 프로젝트 필수 범위와 시험 조건을 팀원과 합의한다.
- Issue별 담당자와 완료 조건을 정한다.
- 공통 인터페이스와 실행 규칙을 관리한다.
- 팀원의 PR과 실행 결과를 확인한다.
- 리뷰와 수정 사항을 확인한 뒤 최종 병합한다.
- 최종 `main` 상태와 제출 자료를 확인한다.
- 제출 태그 생성 및 팀 대표 제출을 담당한다.

### 인지 담당

- RealSense D435 Color 영상 입력 확인
- HSV 기반 색상 검출
- Mask 및 Contour 처리
- 목표 중심 좌표 계산
- 정규화 오차 `ex`, `ey` 계산
- 미검출 처리
- `/target` 메시지 발행
- 정상·미검출·가림 상황의 검출 결과 기록

### 제어 담당

- Dynamixel ID, baud rate, 방향 및 실제 장비 설정 확인
- ex → Pan, ey → Tilt의 2축 P 제어 구현
- Kp 설정 및 비교
- 속도 제한 및 각도 제한 적용
- 데드밴드 적용
- 미검출 및 통신 중단 시 안전 정지 확인
- OpenCR 및 Dynamixel 동작 검증

### 통합 담당

- RealSense ROS 2 wrapper 실행·Launch 구성 및 실제 Topic 확인
- wrapper Topic을 perception_node가 직접 구독하도록 연결
- opencr_node의 ROS 2 ↔ Serial 연결을 제어 담당과 공동 확인
- 인지 노드와 제어 노드 연결
- `/target` 메시지 형식·단위·부호 확인
- QoS 및 실행 순서 정리
- PC(SSH) → Raspberry Pi 접속, Pi 내부 ROS 2 노드 간 Topic 연결 확인 (모든 노드는 Pi에서 실행)
- Raspberry Pi에서 OpenCR 빌드·업로드·시리얼 확인
- 전체 시스템 실행 절차 정리
- ROS2 bag 기록 및 재생
- 다른 팀원이 README만으로 재현 가능한지 확인

### 검증·문서화 담당

- 시험 조건과 반복 횟수를 사전에 정리
- 정상 추적 30초 시험
- 약 2초 가림 후 재등장 5회 시험
- 인지 입력 중단 시험
- 제어 통신 중단 시험
- 처리 FPS, 검출률, 배경 오검출, 수평/수직 RMSE, 복구 성공률, 복구 시간 계산
- 결과 CSV 및 그래프 정리
- report.md 및 presentation.md 결과 연결
- 실패 결과 및 한계 기록

---

## 4. Git 협업 규칙

### 기본 작업 흐름

```text
Issue
→ 작업 브랜치 생성
→ 구현 및 시험
→ Commit / Push
→ Pull Request
→ 다른 팀원 Review
→ 수정 반영
→ Approval
→ 팀장 Merge
→ 최신 main 동기화
```

- 최신 `main`에서 `dev/<이름>` 브랜치로 작업한다. `main` 직접 변경과 강제 push를 하지 않는다.
- Issue에는 담당자·완료 조건·검증 방법을 기록한다. 개인별 clone을 사용하고 장비 시험은 한 사람씩 수행한다.
- `ros2_ws/build/`, `install/`, `log/` 등 생성물은 커밋하지 않는다.

### 담당 Issue 범위

| 담당 | Issue 범위 | 실제 Issue 링크 |
| --- | --- | --- |
| 전승혜 | 시험 조건 확정, 문서 정리, 정량 검증 및 제출 증빙 | TODO |
| 김상화 | wrapper 입력 유효성, HSV·Contour, `/target` 발행 | TODO |
| 한상준 | wrapper·Launch·패키지, Raspberry Pi 단일 runtime 연결, Serial 연결, bag 재현 | TODO |
| 조민혁 | Pan/Tilt P 제어·제한, 상태·복구, OpenCR firmware·watchdog | TODO |

### PR 규칙

- base는 `main`, compare는 본인 작업 브랜치로 지정한다.
- 본문에 Issue, 변경 이유, 인터페이스 영향, 실제 실행 명령·조건·증거, 미확인 TODO를 적는다.
- 미실행 작업은 Draft 또는 미검증으로 표시한다. 네 명 모두 본인 PR 1건 이상 병합과 타인 PR 리뷰 1건 이상을 남긴다.
- 작성자가 아닌 팀원 1명 이상의 승인, 리뷰 대화 해결, 충돌 해결과 검증 확인 후 팀장이 최종 병합한다.
- 팀장 PR도 타인이 승인한다. 승인 후 변경이 있으면 재검토한다.
- 팀장 부재 시 대행자·기간·권한을 사전에 기록한다: TODO (대행 필요 시).

### Review 규칙

리뷰에 다음 정보를 남긴다.

- 확인한 파일과 기준 commit
- 확인 조건: Issue 완료 조건, 메시지·단위·부호·시간·QoS, 축별 제한 및 실패 처리
- 실행/검증 결과: 명령·설정·로그 링크, 실행 여부와 장비 미확인 범위
- `Approve` 또는 `Request changes`의 구체적 근거

`/target`의 PointStamped·면적비 규약, 미검출·0.5초 입력 timeout의 양축 정지, 보드 측 watchdog, 신선한 3프레임 복귀를 확인한다. 문서 PR은 문서 검토 결과를 기록하고 하드웨어 검증과 구분한다.

## 5. Repository 보호 설정 확인

아래 항목은 실제 GitHub 설정 확인 전이며 체크하지 않는다.

- [ ] 팀원 초대 수락 및 작업 브랜치 push 권한 확인
- [ ] `main` 변경은 PR로만 반영
- [ ] 작성자 외 승인 1개 이상 요구
- [ ] 새 commit 이후 기존 승인 무효화 및 재검토
- [ ] 미해결 리뷰 대화 해결 요구
- [ ] `main` 갱신 권한을 팀장으로 제한하고 팀장도 우회 금지
- [ ] `main` force push·삭제 금지
- [ ] 문서 PR로 승인 전 병합 차단 → 타인 승인 → 팀장 병합 확인

설정 증거·확인자·확인일·시험 PR: TODO.
적용 불가 항목·사유: TODO. 기능을 적용할 수 없으면 팀장만 병합하는 운영 규칙을 기록하며 기술적 차단으로 보고하지 않는다.

## 6. 최종 통합 및 제출 체크리스트

- [ ]  팀 저장소에 팀명·팀장·팀원 3명의 이름과 계정이 있습니다.
- [ ]  main 보호 설정 또는 적용 불가 사유·운영 규칙을 기록했습니다.
- [ ]  4인 모두 본인 PR 병합 1건 이상과 다른 PR 리뷰 1건 이상을 남겼습니다.
- [ ]  팀장 본인의 PR도 다른 팀원이 승인했습니다.
- [ ]  목표 존재·부재·가림 장면과 실제 추적을 확인했습니다.
- [ ]  인지 입력 중단과 제어 통신 중단 모두 정지합니다.
- [ ]  Kp 두 설정을 동일 조건에서 반복했습니다.
- [ ]  소실·복귀 5회의 성공·실패를 모두 남겼습니다.
- [ ]  지표 정의와 원본 로그·평가 프레임이 일치합니다.
- [ ]  실제 모터 출력 없이 bag을 재현했습니다.
- [ ]  다른 팀원이 README로 실행한 기록이 있습니다.
- [ ]  팀 보고서와 4인 기여, 자료 접근 권한을 확인했습니다.
- [ ]  팀장이 최종 main에 제출 태그를 만들고 팀 대표로 제출합니다.
- [ ] Pan/Tilt 두 축 방향·속도·각도 제한·deadband 확인
- [ ] 실제 wrapper Topic과 encoding·frame_id·stamp 확인
- [ ] 모터 비활성 상태에서 중심, Pan ±오차, Tilt ±오차, 미검출, 입력 중단의 7개 모의 입력 검증
- [ ] 재등장 후 3초 이내 복귀 판정과 신선한 목표 3프레임 연속 검출 확인
- [ ] 목표 존재 최소 30프레임, 목표 없음 최소 10프레임 평가

최종 통합 확인자·날짜·기준 commit·실행 조건·결과·미완료 사항: TODO.
통합 작업 브랜치: `dev/test1` (통합본 감사·수정, 2026-10-07). 실제 장비 검증 전이며 main 병합은 PR 리뷰 후 팀장이 수행한다.
제출 태그 `lv2-module5-submit` 및 증빙 링크: TODO (최종 검증 후 생성).
