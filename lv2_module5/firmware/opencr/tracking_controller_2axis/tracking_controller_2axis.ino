// Pi runtime: VEL <pan_rad_s> <tilt_rad_s> / STOP / STATUS. 수동 ARM/모드 handshake 없음.
// setup에서 모터 확인과 영속도 토크 유지가 자동 실행된다. 초기 설치 때 중립 자세 필요.
// ENABLE_MOTOR_OUTPUT=0은 native/bench 시험 전용 컴파일 옵션. 정상 펌웨어 기본은 실제 출력.
// 새 유효 VEL/STOP마다 500 ms watchdog 갱신. STATUS/invalid 입력은 갱신하지 않는다.
// 통신 timeout은 STOP하고 새 fresh 명령으로 복구. 실제 하드웨어 오류는 FAULT 후 점검 필요.
// 속도/엔코더 경계는 기존 bench 값(0.05 rad/s, ±80/±100 counts)을 유지: 기구 최대값 아님.
// STOP은 토크를 유지한다. Tilt 카메라를 지지한 뒤에만 SUPPORTED_OFF로 토크 해제.
#include <Arduino.h>
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif
#include <DynamixelWorkbench.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <errno.h>
extern "C" {
#include "usbd_cdc_interface.h"
}
#ifndef ENABLE_MOTOR_OUTPUT
#define ENABLE_MOTOR_OUTPUT 1
#endif
#if ENABLE_MOTOR_OUTPUT != 0 && ENABLE_MOTOR_OUTPUT != 1
#error ENABLE_MOTOR_OUTPUT_must_be_0_or_1
#endif

// Commissioning option: accept the mechanically assembled, stationary pose as
// the runtime origin. Hardware identity, zero velocity, and all runtime limits
// remain enforced. Set to 0 after the physical neutral encoder values are
// confirmed and restore the fixed neutral check below.
#ifndef ACCEPT_STATIONARY_POSE_AS_ORIGIN
#define ACCEPT_STATIONARY_POSE_AS_ORIGIN 1
#endif

DynamixelWorkbench dxl;
const uint8_t IDS[2] = {11, 12};  // {Pan, Tilt} — dxl_discovery 스캔으로 확인
const uint32_t COMMAND_MS = 500, POLL_MS = 20, BUS_TICKS = 25;  // 명령 timeout, 피드백 주기, 모터 watchdog(×20 ms)
const float MAX_RAD_S = 0.05f;
const float RAD_S_PER_UNIT = 0.229f * 6.28318530718f / 60.0f;
// Velocity input is already motor-native sign: positive pan left, tilt up (2026-10-07 control.yaml 기록; 폐루프 확인 필요).
// Reference pose: manually verified pan=3078, tilt=0 modulo 4096.
const int32_t STOP_COUNTS = 80, OUTER_COUNTS = 100;

bool ready = false, holding = false, faulted = false;
bool stopping = false, baseline = false, commandActive = false;
bool known[2] = {false, false};
int32_t pos[2] = {0, 0}, vel[2] = {0, 0}, torque[2] = {0, 0};
int32_t origin[2] = {3078, 0}, previous[2] = {0, 0}, goal[2] = {0, 0};
int32_t holdAnchor[2] = {0, 0};
uint32_t lastCommand = 0, lastPoll = 0, sampleAt = 0, stopAt = 0;
uint8_t quiet = 0;
char line[64];
size_t used = 0;
bool discardLine = false;

void service();
void stopBoth(const char *event);

void reply(const char *s) {
  uint8_t packet[256];
  size_t n = strlen(s);
  if (n > sizeof(packet)-2) return;
  memcpy(packet, s, n); packet[n++]='\n';
  (void)CDC_Itf_Write(packet, (uint32_t)n);
}
bool readItem(uint8_t axis, const char *key, int32_t &v) {
  const char *log = nullptr;
  return dxl.itemRead(IDS[axis], key, &v, &log);
}
bool eq(uint8_t axis, const char *key, int32_t v) {
  int32_t actual=0;
  return readItem(axis,key,actual) && actual==v;
}
bool writeItem(uint8_t axis, const char *key, int32_t v) {
  const char *log=nullptr;
  return dxl.itemWrite(IDS[axis],key,v,&log);
}
bool verified(uint8_t axis, const char *key, int32_t v) {
  return writeItem(axis,key,v) && eq(axis,key,v);
}
// Try BOTH zero writes even if the first fails. No other automatic bus traffic
// after fault: this permits each configured motor watchdog to expire.
void fail(const char *why) {
  if (faulted) return;
  faulted=true; commandActive=false; stopping=false;
  goal[0]=goal[1]=0;
#if ENABLE_MOTOR_OUTPUT
  for (uint8_t i=0;i<2;++i) if (known[i]) (void)writeItem(i,"Goal_Velocity",0);
#endif
  char out[160]; snprintf(out,sizeof(out),"FAULT %s SUPPORT_CAMERA; NO_AUTO_RECOVERY",why);
  reply(out);
}
bool goals(int32_t p, int32_t t) {
#if ENABLE_MOTOR_OUTPUT
  const bool a=verified(0,"Goal_Velocity",p);
  // If first write failed, do not initiate a nonzero second-axis movement.
  if (!a) { fail("PAN_WRITE"); return false; }
  if (!verified(1,"Goal_Velocity",t)) { fail("TILT_WRITE"); return false; }
#endif
  goal[0]=p; goal[1]=t;
  return true;
}
int32_t neutralOffset(int32_t p) {
  int32_t x=p%4096; if(x<0)x+=4096; if(x>=2048)x-=4096; return x;
}
bool feedback() {
#if ENABLE_MOTOR_OUTPUT
  for(uint8_t i=0;i<2;++i) {
    int32_t error=0;
    if(!readItem(i,"Present_Position",pos[i]) ||
       !readItem(i,"Present_Velocity",vel[i]) ||
       !readItem(i,"Torque_Enable",torque[i]) ||
       !readItem(i,"Hardware_Error_Status",error)) { fail("READ"); return false; }
    if(error) { fail("HARDWARE_ERROR"); return false; }
    if(holding && (torque[i]!=1 || !eq(i,"Bus_Watchdog",BUS_TICKS))) {
      fail("TORQUE_OR_BUS_WATCHDOG"); return false;
    }
    if(baseline) {
      const int64_t d=(int64_t)pos[i]-origin[i];
      const int64_t step=(int64_t)pos[i]-previous[i];
      if(d<=-OUTER_COUNTS || d>=OUTER_COUNTS) { fail("OUTER_BOUND"); return false; }
      if(step>30 || step< -30) { fail("POSITION_DISCONTINUITY"); return false; }
      if(vel[i]>5 || vel[i]< -5) { fail("UNEXPECTED_SPEED"); return false; }
      if(holding && !stopping && goal[i]==0) {
        const int64_t h=(int64_t)pos[i]-holdAnchor[i];
        if(h>20 || h< -20) { fail("HOLD_DRIFT"); return false; }
      }
    }
    previous[i]=pos[i];
  }
#else
  torque[0]=torque[1]=holding?1:0; // native 시험 전용: 실제 모터 호출 없음.
  vel[0]=goal[0]; vel[1]=goal[1];
#endif
  sampleAt=millis(); return true;
}
void status() {
  char out[250];
  const char *state=faulted?"FAULT":!ready?"BOOT":!holding?"READY":
                    stopping?"STOPPING":"READY";
  snprintf(out,sizeof(out),
    "STATE %s GOAL=%ld,%ld POS=%ld,%ld VEL=%ld,%ld TORQUE=%ld,%ld AGE_MS=%lu T_MS=%lu",
    state,
    (long)goal[0],(long)goal[1],(long)pos[0],(long)pos[1],
    (long)vel[0],(long)vel[1],(long)torque[0],(long)torque[1],
    (unsigned long)(millis()-sampleAt),(unsigned long)millis());
  reply(out); // Cached data: STATUS never touches the motor bus or command timer.
}
void check() {
  if(ready || faulted) {reply("ERR CHECK_STATE");return;}
#if ENABLE_MOTOR_OUTPUT
  const char *log=nullptr;
  if(!dxl.init("",1000000,&log)) {fail("INIT");return;}
  for(uint8_t i=0;i<2;++i) {
    uint16_t model=0;
    if(!dxl.ping(IDS[i],&model,&log) || model!=1020 || dxl.getProtocolVersion()!=2.0f) {
      fail("IDENTITY");return;
    }
    known[i]=true;
    int32_t fw=0;
    if(!readItem(i,"Firmware_Version",fw) || fw<38 ||
       !eq(i,"Operating_Mode",1) || !eq(i,"Drive_Mode",0) ||
       !eq(i,"Homing_Offset",0) || !eq(i,"Torque_Enable",0) ||
       !eq(i,"Status_Return_Level",2) || !eq(i,"Bus_Watchdog",0)) {
      fail("PRECHECK");return;
    }
  }
#else
  pos[0]=3078;pos[1]=4096;
#endif
  if(!feedback())return;
  if(vel[0]!=0 || vel[1]!=0) {
    fail("SUPPORT_AT_NEUTRAL");return;
  }
#if ACCEPT_STATIONARY_POSE_AS_ORIGIN
  // The current stationary pose is accepted for commissioning. This avoids
  // assuming the old hard-coded assembly reference before it is measured.
  origin[0]=pos[0];
  origin[1]=pos[1]-neutralOffset(pos[1]);
#else
  if(labs(pos[0]-3078)>20 || labs(neutralOffset(pos[1]))>20) {
    fail("SUPPORT_AT_NEUTRAL");return;
  }
  origin[0]=3078; origin[1]=pos[1]-neutralOffset(pos[1]);
#endif
  for(uint8_t i=0;i<2;++i) {previous[i]=pos[i];holdAnchor[i]=pos[i];}
  baseline=true;ready=true;
  // 초기 점검 완료. runtime 서비스/handshake로 노출하지 않음.
}
void hold() {
  if(!ready || holding || faulted) {reply("ERR HOLD_STATE");return;}
  // Still physically supported. Refuse a changed pose after initial check.
  if(!feedback())return;
  if(labs(pos[0]-origin[0])>20 || labs(pos[1]-origin[1])>20 || vel[0]!=0 || vel[1]!=0) {
    fail("HOLD_POSE");return;
  }
#if ENABLE_MOTOR_OUTPUT
  // Verify both are off before clearing either watchdog or enabling either axis.
  if(!eq(0,"Torque_Enable",0)||!eq(1,"Torque_Enable",0) ||
     !eq(0,"Bus_Watchdog",0)||!eq(1,"Bus_Watchdog",0)) {fail("HOLD_PRECHECK");return;}
  if(!goals(0,0))return;
  for(uint8_t i=0;i<2;++i) {
    if(!verified(i,"Profile_Acceleration",1) || !verified(i,"Bus_Watchdog",BUS_TICKS)) {
      fail("HOLD_CONFIG");return;
    }
  }
  // Partial success is possible: on fault support before SUPPORTED_OFF.
  for(uint8_t i=0;i<2;++i) if(!verified(i,"Torque_Enable",1)) {fail("TORQUE_ENABLE");return;}
#endif
  holding=true;
  for(uint8_t i=0;i<2;++i)holdAnchor[i]=pos[i];
  lastPoll=millis();
  stopBoth("READY ZERO_REQUESTED");
}
void stopBoth(const char *event) {
  if(faulted)return;
  if(!holding) {goal[0]=goal[1]=0;reply(event);return;}
  if(!stopping) {stopAt=millis();quiet=0;stopping=true;}
  if(!goals(0,0))return;
  reply(event);
}
void off() {
  if(!ready && !faulted) {reply("ERR CHECK_FIRST");return;}
  // Explicit physical-support assertion. Can also release after a latched fault.
  bool ok=true;
#if ENABLE_MOTOR_OUTPUT
  for(uint8_t i=0;i<2;++i) {
    if(!known[i]) {ok=false;continue;}
    const bool one=verified(i,"Torque_Enable",0); ok=one&&ok;
  }
  if(!ok) {fail("OFF_UNCONFIRMED");reply("ERR OFF_UNCONFIRMED SUPPORT_AND_POWER_OFF");return;}
  for(uint8_t i=0;i<2;++i) {
    const bool one=verified(i,"Bus_Watchdog",0) && verified(i,"Goal_Velocity",0);
    ok=one&&ok;
  }
#endif
  commandActive=false;holding=false;stopping=false;goal[0]=goal[1]=0;torque[0]=torque[1]=0;
  // Require reset and a new startup after release. Do not reuse pose references.
  ready=false;baseline=false;faulted=true;
  reply(ok?"ACK SUPPORTED_OFF TORQUE_OFF_CONFIRMED RESET_REQUIRED":
           "ERR CLEANUP TORQUE_OFF_CONFIRMED POWER_OFF");
}
void timeout() {
  if(commandActive && (uint32_t)(millis()-lastCommand)>=COMMAND_MS) {
    commandActive=false;
    if(used>0)discardLine=true; // timeout 전에 수신한 미완성 VEL도 폐기: 늦은 LF로 되살리지 않음
    stopBoth("EVENT TIMEOUT ZERO_REQUESTED");
  }
}
void service() {
  if(faulted)return;
  timeout();
  if(!holding || faulted)return;
  uint32_t now=millis();
  if((uint32_t)(now-lastPoll)<POLL_MS)return;
  lastPoll=now;
  if(!feedback())return;
  timeout();
  if(faulted)return;
  if(!stopping) {
    for(uint8_t i=0;i<2;++i) {
      int64_t d=(int64_t)pos[i]-origin[i];
      if((d>=STOP_COUNTS && goal[i]>0)||(d<=-STOP_COUNTS && goal[i]<0)) {
        stopBoth("EVENT LIMIT ZERO_REQUESTED");break;
      }
    }
  }
  if(stopping) {
    if(vel[0]==0 && vel[1]==0) {if(quiet<3)++quiet;} else quiet=0;
    if((uint32_t)(millis()-stopAt)>=100 && quiet>=3) {
      stopping=false;for(uint8_t i=0;i<2;++i)holdAnchor[i]=pos[i];
      reply("EVENT STOPPED TORQUE_RETAINED");
    } else if((uint32_t)(millis()-stopAt)>=500)fail("STOP_NOT_CONFIRMED");
  }
}
bool parsePair(const char *s, float &p, float &t) {
  char *end=nullptr;errno=0;p=strtof(s,&end);
  if(end==s||errno==ERANGE||!isfinite(p)||*end!=' ')return false;
  s=end+1;while(*s==' ')++s;
  errno=0;t=strtof(s,&end);
  return end!=s && *end=='\0' && errno!=ERANGE && isfinite(t);
}
void command(const char *s) {
  service(); // Expiry is checked before accepting any next command.
  if(!strcmp(s,"STATUS")){status();return;}
#if !ENABLE_MOTOR_OUTPUT
  if(!strcmp(s,"TEST_STATUS")){reply("TEST_ONLY NO_MOTOR_OUTPUT");return;}
#endif
  if(!strcmp(s,"SUPPORTED_OFF")){off();return;}
  if(faulted){reply("ERR FAULT_RESET_REQUIRED");return;}
  if(!strcmp(s,"STOP")) {
    lastCommand=millis(); commandActive=true;
    stopBoth("ACK STOP ZERO_REQUESTED");return;
  }
  if(!strncmp(s,"VEL ",4)) {
    float p=0,t=0;
    if(!parsePair(s+4,p,t)){stopBoth("REJECT VALUE ZERO_REQUESTED");return;}
    // 최대속도는 firmware에서도 clamp. NaN/Inf는 위에서 거부.
    p=fmaxf(-MAX_RAD_S,fminf(MAX_RAD_S,p));t=fmaxf(-MAX_RAD_S,fminf(MAX_RAD_S,t));
    if(!holding){stopBoth("REJECT NOT_READY");return;}
    if(stopping){reply("ACK STOPPING");return;} // 정지 확인 중 명령은 저장하지 않음
    const int32_t a=(int32_t)lroundf(p/RAD_S_PER_UNIT);
    const int32_t b=(int32_t)lroundf(t/RAD_S_PER_UNIT);
    // Entire pair validated before either write. Hardware writes are sequential.
    // Freshly poll feedback, then re-check timeout before enabling movement.
    if(!feedback())return;
    timeout();if(faulted||stopping){reply("ACK STOPPING");return;}
    const int32_t next[2]={a,b};
    for(uint8_t i=0;i<2;++i) {
      const int64_t d=(int64_t)pos[i]-origin[i];
      if((d>=STOP_COUNTS && next[i]>0)||(d<=-STOP_COUNTS && next[i]<0)) {
        stopBoth("EVENT LIMIT ZERO_REQUESTED");return;
      }
    }
    lastCommand=millis(); commandActive=true; // 새 유효 명령마다 500 ms timer reset
    const bool goingZero=(a==0&&b==0&&(goal[0]!=0||goal[1]!=0));
    for(uint8_t i=0;i<2;++i)if(next[i]==0&&goal[i]!=0)holdAnchor[i]=pos[i];
    if(!goals(a,b))return;
    if(goingZero){stopping=true;stopAt=millis();quiet=0;}
    reply("ACK VEL");return;
  }
  stopBoth("REJECT COMMAND ZERO_REQUESTED");
}
void setup(){
  Serial.begin(115200);
  check();  // 기존 모델/설정/중립 엔코더 확인을 자동으로 수행
  if(!faulted)hold();  // 영속도 + 토크 유지 + Bus_Watchdog 설정
}
void loop(){
  service();
  for(uint8_t n=0;n<32&&Serial.available()>0;++n){
    service();int c=Serial.read();if(c<0)break;
    if(c=='\r')continue;
    if(c=='\n') {
      if(discardLine)stopBoth("REJECT LINE ZERO_REQUESTED");else if(used){line[used]=0;command(line);}
      used=0;discardLine=false;continue;
    }
    if(discardLine)continue;
    if(c<32||c>126||used>=sizeof(line)-1){discardLine=true;continue;}
    line[used++]=(char)c;
  }
  service();
}
