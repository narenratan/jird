sr = 44100
ksmps = 64
nchnls = 2
0dbfs = 5

instr 1
  iAmp = p4
  iFreq = p5
  aVco vco2 iAmp, iFreq
  kEnv madsr 0.1, 0.4, 0.6, 0.7
  aLp moogladder aVco, 5000, 0.4
  outall aLp*kEnv
endin
