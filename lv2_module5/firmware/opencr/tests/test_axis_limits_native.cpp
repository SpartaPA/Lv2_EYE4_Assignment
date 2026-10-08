// Software-only register stub tests: never connects to motors.
#define main existing_regression_main
#include "test_integrated_native.cpp"
#undef main

bool contains(const std::string &s) {
 for(const auto &m:messages) if(m.find(s)!=std::string::npos)return true;
 return false;
}
void atOffset(int axis,int offset) {
 int p=origin[axis]+offset;
 dxl.regs[{IDS[axis],"Present_Position"}]=p;
 previous[axis]=holdAnchor[axis]=p;
}
int main() {
#if !ENABLE_MOTOR_OUTPUT
#error Build_this_test_with_ENABLE_MOTOR_OUTPUT_1
#endif
 assert(NEUTRAL_TOLERANCE_COUNTS==50);
 assert(OUTER_COUNTS[0]==1365 && OUTER_COUNTS[1]==682);
 assert(STOP_COUNTS[0]==1345 && STOP_COUNTS[1]==662);
 for(int axis=0;axis<2;++axis)for(int sign:{-1,1}) {
  reset();dxl.regs[{IDS[axis],"Present_Position"}]=(axis==0?3078:4096)+sign*50;
  prepared();assert(!faulted); // CHECK and HOLD accept inclusive +/-50.
  send("ARM\n");assert(armed); // Existing ARM window still permits startup tolerance.
  reset();dxl.regs[{IDS[axis],"Present_Position"}]=(axis==0?3078:4096)+sign*51;
  send("CHECK\n");assert(faulted && contains("SUPPORT_AT_NEUTRAL"));
  reset();send("CHECK\n");atOffset(axis,sign*51);send("HOLD\n");
  assert(faulted && contains("HOLD_POSE"));
  for(bool periodic:{false,true}) {
   reset();prepared();send("ARM\n");
   const std::string cmd=axis==0?(sign>0?"VEL .048 0\n":"VEL -.048 0\n"):
                                    (sign>0?"VEL 0 .048\n":"VEL 0 -.048\n");
   atOffset(axis,sign*(STOP_COUNTS[axis]-1));send(cmd);
   assert(armed && !faulted && goal[axis]*sign>0);
   atOffset(axis,sign*STOP_COUNTS[axis]);
   if(periodic)advance(25);else send(cmd);
   assert(!armed && !faulted && goal[0]==0 && goal[1]==0);
   assert(contains("EVENT LIMIT"));
  }
  reset();prepared();send("ARM\n");atOffset(axis,sign*STOP_COUNTS[axis]);
  send(axis==0?(sign>0?"VEL -.048 0\n":"VEL .048 0\n"):
               (sign>0?"VEL 0 -.048\n":"VEL 0 .048\n"));
  assert(armed && !faulted && goal[axis]*sign<0); // Inward is permitted before a limit trip.
  reset();prepared();atOffset(axis,sign*(OUTER_COUNTS[axis]-1));
  assert(feedback() && !faulted);
  atOffset(axis,sign*OUTER_COUNTS[axis]);assert(!feedback() && faulted);
  assert(contains("OUTER_BOUND"));
  reset();prepared();
  dxl.regs[{IDS[axis],"Present_Position"}]=holdAnchor[axis]+sign*21;
  assert(!feedback() && faulted && contains("HOLD_DRIFT")); // Not relaxed to 50.
 }
 for(int tilt:{-50,0,50,4046,4096,4146}) {
  reset();dxl.regs[{12,"Present_Position"}]=tilt;prepared();
  assert(origin[1]==tilt-neutralOffset(tilt));
 }
 reset();prepared();atOffset(0,800);assert(feedback()&&!faulted);
 reset();prepared();atOffset(1,800);assert(!feedback()&&faulted);
 std::cout<<"PASS axis-specific limits, neutral +/-50, wrap and retained drift protection\n";
 return 0;
}
