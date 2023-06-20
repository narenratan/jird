#!/bin/bash

# Run build script in Ubuntu container and copy build executable back to
# local machine.

# To be run in top level repo dir

set -ex

cd $(dirname $(dirname $0))
rm -rf build
mkdir build
podman rm -f jird_builder
podman run -dt --name jird_builder docker.io/library/ubuntu:18.04
podman cp . jird_builder:repo
podman exec jird_builder /repo/build_scripts/build.sh
podman cp jird_builder:/repo/cli.bin ./build/jird
podman cp jird_builder:/repo/cli.dist ./build
