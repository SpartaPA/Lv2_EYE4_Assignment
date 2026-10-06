# zero 시험 재시도 기록

zero.log는 같은 파일명으로 여러 번 실행하여 최종 성공 실행만 보존됐다.
아래 내용은 담당자가 보존한 터미널 출력에 근거한다.

1. 최초 시도:
   STATE FAULT, GOAL=0,0, POS=3082,10, VEL=6,0,
   TORQUE=1,1, AGE_MS=75735.
   실행기는 초기 상태 검사에서 중단되어 ARM/VEL을 전송하지 않았다.
   원래 FAULT 발생 이벤트는 이 출력에 없어 원인은 미확정이다.
   위치·속도·토크는 오래된 캐시이며 당시 실제 상태를 확정하지 않는다.

2. 재시작 후 시도:
   STATE BOOT에서 초기 상태 검사 실패.
   CHECK/HOLD 이전이므로 실행기가 ARM/VEL을 전송하지 않았다.

3. CHECK/HOLD 완료 후 최종 시도:
   ACK ARM 및 ACK VEL 확인.
   TIMEOUT DISARMED 및 STOPPED TORQUE_RETAINED 확인.
   최종 GOAL=0,0, VEL=0,0, TORQUE=1,1.
   zero.log는 이 성공 실행의 원본 기록이다.

최종 zero 시험 성공과 이전 원인 미확정 FAULT를 구분하여 기록한다.
