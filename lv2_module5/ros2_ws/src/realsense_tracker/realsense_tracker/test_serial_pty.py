"""시리얼 bridge 명령 경로를 실제 DRY 펌웨어 코드(native PTY 실행 파일)와 Linux PTY로 연결해 시험한다.

모터·OpenCR 없이 실행. 펌웨어는 firmware/opencr/tests/native_pty.cpp를 ENABLE_MOTOR_OUTPUT=0으로 컴파일한 것.
  기본:            준비/2축 VEL/STOP/0.5초 침묵 STOP/새 명령 복구 확인
  --cycles N:      STOP → 복귀를 N회 반복 (serial_stop_race_fix 회귀 시험, 이전 test_stop_recovery_pty 통합)
  --tick-sec 0.01: 실제 opencr_node와 같은 10 ms tick으로 실행 (반복 시험 권장값)
"""
import argparse
import csv
import os
from pathlib import Path
import pty
import subprocess
import time
from .serial_core import PosixSerial,SerialBridge


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--firmware-executable',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--cycles',type=int,default=0,help='repeated STOP/recovery cycles (0-100)')
    parser.add_argument('--tick-sec',type=float,default=.002,help='bridge tick sleep; opencr_node uses 0.01')
    args=parser.parse_args()
    assert 0<=args.cycles<=100,'cycles must be between 0 and 100'
    out=Path(args.output_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    executable=str(Path(args.firmware_executable).resolve())
    logfile=open(out/'serial_pty.csv','x',newline='');writer=csv.writer(logfile,lineterminator='\n')
    writer.writerow(['monotonic_sec','direction','line'])
    def record(*row):writer.writerow(row);logfile.flush()
    master,slave=pty.openpty();transport=None;process=None;bridge=None
    try:
        transport=PosixSerial(os.ttyname(slave));os.close(slave);slave=None
        process=subprocess.Popen([executable,str(master)],pass_fds=(master,))
        os.close(master);master=None
        bridge=SerialBridge(transport,record)
        last_feed=0.0
        def pump(seconds,command=None):
            nonlocal last_feed
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                if command and time.monotonic()-last_feed>=.04:
                    stamp=time.time_ns();stop,pan,tilt=command
                    bridge.receive_command(stop,pan,tilt,stamp,stamp);last_feed=time.monotonic()
                bridge.tick();time.sleep(args.tick_sec)
        def wait(predicate,command=None,seconds=2):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                pump(.005,command)
                if predicate():return
                assert not bridge.reason,bridge.snapshot()
            raise AssertionError('Timeout: '+str(bridge.snapshot()))
        wait(lambda:bridge.board and bridge.board['state']=='READY')
        print('PASS automatic firmware initialization; no prepare/arm',flush=True)
        for label,pan,tilt,goal in [('center',0,0,(0,0)),('pan-right',-.04,0,(-2,0)),
                                 ('pan-left',.04,0,(2,0)),('tilt-down',0,.04,(0,2)),
                                 ('tilt-up',0,-.04,(0,-2)),('both',-.04,.04,(-2,2))]:
            wait(lambda:bridge.board and bridge.board['goal']==goal,(False,pan,tilt))
            assert not bridge.reason;print('PASS serial '+label,flush=True)
        wait(lambda:bridge.board['goal']==(0,0) and bridge.board['vel']==(0,0),
             (True,0,0))
        pump(.25,(True,0,0));assert not bridge.reason,bridge.snapshot()
        print('PASS stop=true keeps watchdog STOP for normal target recovery',flush=True)
        wait(lambda:bridge.board['goal']==(-2,0),(False,-.04,0))
        print('PASS fresh target command resumes after STOP without manual service',flush=True)
        for cycle in range(args.cycles):
            pump(.55+(cycle%5)*.013,(True,0,0))
            assert not bridge.reason,bridge.snapshot()
            wait(lambda:bridge.board['goal']==(-2,0),(False,-.04,0))
            assert not bridge.reason,bridge.snapshot()
        if args.cycles:
            print(f'PASS {args.cycles} repeated STOP/recovery cycles at {args.tick_sec*1000:g} ms bridge ticks',flush=True)
        pump(.65)
        assert bridge.timed_out and not bridge.reason,bridge.snapshot()
        assert bridge.board['goal']==(0,0),bridge.snapshot()
        wait(lambda:bridge.board['goal']==(-2,0),(False,-.04,0))
        print('PASS timeout STOP and fresh command recovery; no cached velocity',flush=True)
        bridge.close();bridge=None
        process.terminate();process.wait(timeout=5);process=None
        print('ALL SERIAL PTY CORE CHECKS PASSED; FIRMWARE_MODE=DRY',flush=True)
    finally:
        if bridge:bridge.close()
        elif transport:transport.close()
        if process and process.poll() is None:
            process.terminate();process.wait(timeout=5)
        if slave is not None:os.close(slave)
        if master is not None:os.close(master)
        logfile.close()

if __name__=='__main__':main()
