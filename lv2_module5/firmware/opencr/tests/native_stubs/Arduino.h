#pragma once
#include <stdint.h>
#include <stddef.h>
#include <deque>
inline uint32_t fakeNow=0;
inline uint32_t millis(){return fakeNow;}
struct SerialFake { std::deque<int> input; void begin(int){} int available(){return input.size();} int read(){int x=input.front();input.pop_front();return x;} };
inline SerialFake Serial;
