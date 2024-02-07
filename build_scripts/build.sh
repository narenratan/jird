#!/bin/bash

# Build single-file jird executable including surgepy

set -ex

# Install prerequisites
apt-get update
apt-get upgrade -y
apt-get install python3.8 python3.8-dev python3-venv python3.8-venv git gcc g++-8 patchelf -y
python3.8 -m venv .venv
source .venv/bin/activate
python3.8 -m pip install --upgrade pip
python3.8 -m pip install nuitka ordered-set zstandard

# Set up repo (assumed to be in container in /repo)
cd /repo
# git checkout .
git clean -dfx
git submodule update --init --recursive

export CXX=g++-8
# Build surgepy
python3.8 -m pip install libs/surge/src/surge-python
unset CXX

# Build jird executable with nuitka
export PYTHONPATH=src
python3.8 -m nuitka \
  --onefile \
  --include-data-dir=src/jird/data/=jird/data/ \
  --no-deployment-flag=self-execution \
  src/jird/cli.py
