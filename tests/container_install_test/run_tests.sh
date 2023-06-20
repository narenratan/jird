#!/bin/bash

# Install dependencies and test running jird

set -eux

apt-get update

cd /test

apt-get install alsa-utils -y
./jird -v -c sconfig.json test_music

apt-get install fluidsynth -y
./jird -v test_music

apt-get install zynaddsubfx -y
./jird -v -c zconfig.json test_music

echo PASSED
