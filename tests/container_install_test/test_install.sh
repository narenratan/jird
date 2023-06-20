#!/bin/bash

# Test installing jird and packages in a container

set -eux

podman rm -f install_tester
podman run -dt --device /dev/snd --name install_tester docker.io/library/$1
podman cp $(dirname $0) install_tester:/test
podman cp $(dirname $(dirname $(dirname $0)))/build/jird install_tester:/test
podman exec install_tester /test/run_tests.sh
