// Run the actual DRY firmware logic over a PTY; no physical-device emulation.
#include <chrono>
#include <fcntl.h>
#include <unistd.h>
#include "../tracking_controller_2axis/tracking_controller_2axis.ino"
int channel=-1;
extern "C" int CDC_Itf_Write(uint8_t*p,uint32_t n){return (int)write(channel,p,n);}
int main(int argc,char**argv){
 if(argc!=2)return 2;
 channel=atoi(argv[1]);
 fcntl(channel,F_SETFL,O_NONBLOCK);
 auto start=std::chrono::steady_clock::now();setup();
 for(;;){
  fakeNow=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
  char b[256];ssize_t n=read(channel,b,sizeof(b));
  for(ssize_t i=0;i<n;++i)Serial.input.push_back((unsigned char)b[i]);
  loop();usleep(1000);
 }
}
