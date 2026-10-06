#include <cassert>
#include <iostream>
#include <string>
#include <vector>
#include "../tracking_controller_2axis/tracking_controller_2axis.ino"
std::vector<std::string> messages;
extern "C" int CDC_Itf_Write(uint8_t*p,uint32_t n){messages.emplace_back((char*)p,n);return n;}
void reset(){
 dxl=DynamixelWorkbench();fakeNow=0;Serial.input.clear();messages.clear();
 ready=holding=armed=faulted=stopping=baseline=false;known[0]=known[1]=false;
 for(int i=0;i<2;++i){pos[i]=vel[i]=torque[i]=goal[i]=previous[i]=holdAnchor[i]=0;}
 origin[0]=3078;origin[1]=0;lastCommand=lastPoll=sampleAt=stopAt=0;
 quiet=0;used=0;discardLine=false;setup();
}
void send(const std::string&s){for(unsigned char c:s)Serial.input.push_back(c);while(Serial.available())loop();}
void advance(uint32_t ms){for(uint32_t i=0;i<ms;++i){++fakeNow;loop();}}
void prepared(){send("CHECK\nHOLD\n");advance(150);assert(ready&&holding&&!armed&&!stopping&&!faulted);}
int main(){
 reset();send("VEL 0.02 0\n");assert(!armed&&goal[0]==0);prepared();send("ARM\nVEL 0.048 -0.048\n");assert(armed&&goal[0]==2&&goal[1]==-2);
 auto writes=dxl.writes.size();auto stamp=lastCommand;
 for(auto s:{"VEL 0.01 nan\n","VEL 0.01 1\n","VEL 0.01\n","VEL 0.01 0 junk\n","VEL 0.01 inf\n"})send(s);
 assert(dxl.writes.size()==writes&&lastCommand==stamp&&goal[0]==2&&goal[1]==-2);
 for(int i=0;i<7;++i){send("STATUS\nHELLO\nARM\n");advance(50);}
 assert(!armed&&goal[0]==0&&goal[1]==0);advance(150);assert(!stopping&&holding);
 send("VEL .048 .048\n");assert(!armed&&goal[0]==0);
 send("ARM\nVEL .048 .048");advance(350);send("\n");assert(!armed&&goal[0]==0);advance(150);
 send("ARM\n");send(std::string(100,'x'));advance(350);send("\nSTATUS\n");assert(!armed&&!discardLine&&used==0);
 advance(150);send("ARM\nVEL .048 0\nSTOP\n");advance(150);assert(armed&&!stopping&&goal[0]==0);
 send("DISARM\n");advance(150);assert(!armed&&holding);send("SUPPORTED_OFF\n");assert(!holding&&faulted);
 // Unsigned millisecond rollover must still expire correctly.
 reset();prepared();fakeNow=UINT32_MAX-100;lastPoll=fakeNow;send("ARM\nVEL .048 0\n");advance(350);assert(!armed&&goal[0]==0);
#if ENABLE_MOTOR_OUTPUT
 // Validation is atomic, physical writes are not: recover from second-axis failure.
 reset();prepared();send("ARM\n");dxl.badWrite=12;dxl.badKey="Goal_Velocity";
 send("VEL .048 .048\n");assert(faulted&&!armed);
 assert(dxl.regs[std::make_pair(11,std::string("Goal_Velocity"))]==0);
 assert(dxl.regs[std::make_pair(12,std::string("Goal_Velocity"))]==0);
 auto count=dxl.reads;auto wc=dxl.writes.size();advance(500);send("STATUS\nARM\n");assert(dxl.reads==count&&dxl.writes.size()==wc);
 reset();prepared();send("ARM\nVEL .048 0\n");dxl.badRead=12;advance(25);assert(faulted&&!armed&&goal[0]==0);
 reset();prepared();send("ARM\nVEL .048 0\n");
 for(int p:{3100,3120,3140,3158}){dxl.regs[{11,"Present_Position"}]=p;advance(25);}
 assert(!armed&&!faulted&&goal[0]==0);advance(150);assert(!stopping);
 // Initial tilt pose may be represented as 0 or 4096 after reboot.
 reset();dxl.regs[{12,"Present_Position"}]=0;prepared();assert(origin[1]==0);
 // A reset during holding is a fault, not a silently wrapped reading.
 dxl.regs[{12,"Present_Position"}]=4096;advance(25);assert(faulted);
#else
 assert(dxl.inits==0&&dxl.reads==0&&dxl.writes.empty());
#endif
 std::cout<<"PASS native controller scenarios MODE="<<(ENABLE_MOTOR_OUTPUT?"LIVE_STUB":"DRY")<<"\n";
}
