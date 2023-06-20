#!/bin/bash

set -eux

for x in ubuntu:20.04 ubuntu:22.04 ubuntu:23.04 debian:buster-slim debian:bullseye-slim debian:bookworm-slim; do
  $(dirname $0)/test_install.sh $x
done

echo ALL PASSED
