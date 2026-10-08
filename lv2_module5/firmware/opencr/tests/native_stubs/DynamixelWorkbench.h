#pragma once
#include <stdint.h>
#include <map>
#include <string>
#include <vector>
struct Write {uint8_t id;std::string key;int32_t value;};
class DynamixelWorkbench {
public:
 std::map<std::pair<int,std::string>,int32_t> regs;
 std::vector<Write> writes;
 int reads=0, inits=0, badRead=0, badWrite=0;
 std::string badKey;
 DynamixelWorkbench(){for(int id:{11,12}) {
   regs[{id,"Firmware_Version"}]=42; regs[{id,"Operating_Mode"}]=1;
   regs[{id,"Status_Return_Level"}]=2;
   regs[{id,"Present_Position"}]=id==11?3078:4096;
 }}
 bool init(const char*,uint32_t,const char**){++inits;return true;}
 bool ping(uint8_t,uint16_t *m,const char**){*m=1020;return true;}
 float getProtocolVersion(){return 2.0f;}
 bool itemRead(uint8_t id,const char*key,int32_t*v,const char**) {
   ++reads;if(badRead==id)return false;*v=regs[{id,key}];return true;
 }
 bool itemWrite(uint8_t id,const char*key,int32_t v,const char**) {
   writes.push_back({id,key,v});
   if(badWrite==id && badKey==key && v!=0)return false;
   regs[{id,key}]=v;
   if(std::string(key)=="Goal_Velocity")regs[{id,"Present_Velocity"}]=v;
   return true;
 }
};
