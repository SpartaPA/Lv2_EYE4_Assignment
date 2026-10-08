#include <cassert>
#include <iostream>
#include <string>
#include <vector>
#include "../tracking_controller_2axis/tracking_controller_2axis.ino"
std::vector<std::string> messages;
extern "C" int CDC_Itf_Write(uint8_t*p,uint32_t n){messages.emplace_back((char*)p,n);return n;}
void reset(){
 dxl=DynamixelWorkbench();fakeNow=0;Serial.input.clear();messages.clear();
 ready=holding=faulted=stopping=baseline=commandActive=false;known[0]=known[1]=false;
 for(int i=0;i<2;++i){pos[i]=vel[i]=torque[i]=goal[i]=previous[i]=holdAnchor[i]=0;}
 origin[0]=3078;origin[1]=0;lastCommand=lastPoll=sampleAt=stopAt=0;
 quiet=0;used=0;discardLine=false;setup();
}
void send(const std::string&s){for(unsigned char c:s)Serial.input.push_back(c);while(Serial.available())loop();}
void advance(uint32_t ms){for(uint32_t i=0;i<ms;++i){++fakeNow;loop();}}
void prepared(){advance(150);assert(ready&&holding&&!stopping&&!faulted);}
int main(){
 reset();prepared();send("VEL .048 -.048\n");assert(goal[0]==2&&goal[1]==-2);
 // A valid pair feeds the watchdog, invalid input stops without feeding it.
 auto stamp=lastCommand;send("VEL .01 nan\n");assert(goal[0]==0&&goal[1]==0&&lastCommand==stamp);
 advance(150);send("VEL 1 -1\n");assert(goal[0]==2&&goal[1]==-2); // clamp at .05
 for(int i=0;i<40;++i){advance(50);send("VEL .048 -.048\n");assert(goal[0]==2&&goal[1]==-2);}
 advance(499);assert(goal[0]==2);advance(1);assert(goal[0]==0&&goal[1]==0&&!commandActive&&!faulted);
 advance(150);assert(goal[0]==0);send("VEL -.024 .024\n");assert(goal[0]==-1&&goal[1]==1);
 send("STOP\n");assert(goal[0]==0&&goal[1]==0);advance(150);
 // STATUS, bad values, incomplete/oversized lines must not keep velocity alive.
 send("VEL .048 0\n");stamp=lastCommand;
 for(int i=0;i<11;++i){send("STATUS\n");advance(50);}
 assert(goal[0]==0&&lastCommand==stamp&&!commandActive);
 advance(150);send("VEL .048 0\nVEL .02 0");advance(1000);
 assert(goal[0]==0);send("\n");assert(goal[0]==0);advance(150);
 send("VEL .048 0\n");send(std::string(100,'x'));advance(550);send("\nSTATUS\n");
 assert(goal[0]==0&&!discardLine&&used==0);advance(150);
 send("VEL .048 0\n");send("VEL .01 inf\n");assert(goal[0]==0);advance(150);
 send("VEL .048 0 junk\n");assert(goal[0]==0);advance(150);
 // No automatic restoration of the old goal; fresh VEL is required after timeout.
 advance(1000);assert(goal[0]==0);send("VEL -.048 0\n");assert(goal[0]==-2);
 reset();prepared();fakeNow=UINT32_MAX-100;lastPoll=fakeNow;
 send("VEL .048 0\n");advance(500);assert(goal[0]==0);advance(150);
#if ENABLE_MOTOR_OUTPUT
 reset();prepared();dxl.badWrite=12;dxl.badKey="Goal_Velocity";
 send("VEL .048 .048\n");assert(faulted&&goal[0]==0&&goal[1]==0);
 assert(dxl.regs[std::make_pair(11,std::string("Goal_Velocity"))]==0);
 assert(dxl.regs[std::make_pair(12,std::string("Goal_Velocity"))]==0);
 auto count=dxl.reads;auto wc=dxl.writes.size();advance(600);send("STATUS\nVEL .048 0\n");
 assert(dxl.reads==count&&dxl.writes.size()==wc);
 reset();prepared();send("VEL .048 0\n");dxl.badRead=12;advance(25);assert(faulted&&goal[0]==0);
 reset();prepared();send("VEL .048 0\n");
 for(int p:{3100,3120,3140,3158}){dxl.regs[{11,"Present_Position"}]=p;advance(25);}
 assert(!faulted&&goal[0]==0);advance(150);send("VEL .048 0\n");assert(goal[0]==0);
 advance(150);send("VEL -.048 0\n");assert(goal[0]==-2); // inward allowed
 reset();prepared();send("VEL 0 .048\n");
 for(int p:{4116,4136,4156,4176}){dxl.regs[{12,"Present_Position"}]=p;advance(25);}
 assert(!faulted&&goal[1]==0);advance(150);send("VEL 0 -.048\n");assert(goal[1]==-2);
 reset();prepared();send("VEL .048 0\n");
 for(int p:{3100,3120,3140,3160,3178}){dxl.regs[{11,"Present_Position"}]=p;advance(25);}
 assert(faulted&&goal[0]==0); // outer boundary
 reset();prepared();assert(dxl.regs[std::make_pair(11,std::string("Bus_Watchdog"))]==25);
 dxl.regs[{12,"Present_Position"}]=0;advance(25);assert(faulted); // encoder discontinuity
#else
 assert(dxl.inits==0&&dxl.reads==0&&dxl.writes.empty());
#endif
 reset();prepared();send("SUPPORTED_OFF\n");assert(!holding&&faulted&&goal[0]==0);
 std::cout<<"PASS native controller safety scenarios "<<(ENABLE_MOTOR_OUTPUT?"HARDWARE_STUB":"NO_MOTOR_OUTPUT")<<"\n";
}
