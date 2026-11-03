#!/usr/bin/env python3
"""Compile both hardware maps; sharing ID=3 must never remap the old boards."""
from pathlib import Path
import os,shutil,subprocess,tempfile
R=Path(__file__).resolve().parents[1]
source='''#include <cstdint>
#include <cassert>
#include "ControllerConfig.h"
int main() {
 const auto& c=GEMILAI_3007Z;
 assert(c.autodetectValue==3);
 assert(c.heaterPin==14 && c.pumpPin==9 && c.pumpSensePin==21 && c.valvePin==10 && c.altPin==47);
 assert(c.pumpOn==1 && c.valveOn==1 && c.altOn==1);
 assert(c.pressureScl==41 && c.pressureSda==42);
 assert(c.maxSckPin==6 && c.maxCsPin==7 && c.maxMisoPin==4);
 assert(c.brewButtonPin==38 && c.steamButtonPin==48);
 assert(c.scaleSclPin==17 && c.scaleSdaPin==18 && c.scaleSda1Pin==39);
 assert(c.ext1Pin==1 && c.ext2Pin==2 && c.ext3Pin==8 && c.ext4Pin==12 && c.ext5Pin==13);
#ifdef GEMILAIMATE_COMPACT
 assert(c.sunriseSdaPin==43 && c.sunriseSclPin==44);
#else
 assert(c.sunriseSdaPin==15 && c.sunriseSclPin==16);
#endif
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'profile.cpp').write_text(source)
 for target in ['legacy','compact']:
  cmd=[os.environ.get('CXX',shutil.which('c++')),'-std=c++17','-I'+str(R/'firmware/lib/GemilaiMateController/src'),str(p/'profile.cpp'),'-o',str(p/target)]
  if target=='compact':cmd+=['-DGEMILAIMATE_COMPACT=1']
  subprocess.run(cmd,check=True);subprocess.run([str(p/target)],check=True)
print('PASS compiled legacy 15/16 and compact 43/44 maps; Pro LEGO GPIO/polarities preserved')
