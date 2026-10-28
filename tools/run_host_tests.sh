#!/bin/sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_root="$project_root/firmware"
test_tmp=$(mktemp -d)
trap 'rm -rf "$test_tmp"' EXIT HUP INT TERM
compiler=${CXX:-clang++}
"$compiler" -std=c++17 -Wall -Wextra -Werror -Wno-unused-private-field -pthread \
 -I"$source_root/tests/host/stubs" -I"$source_root/lib/GemilaiMateController/src/peripherals" \
 "$source_root/tests/host/test_control.cpp" \
 "$source_root/lib/GemilaiMateController/src/peripherals/PumpPSM.cpp" \
 "$source_root/lib/GemilaiMateController/src/peripherals/DigitalInput.cpp" -o "$test_tmp/control"
"$test_tmp/control"
"$compiler" -std=c++17 -Wall -Wextra -Werror -I"$source_root/lib/GemilaiMateController/src" \
 "$source_root/tests/host/test_ping_watchdog.cpp" -o "$test_tmp/ping"
"$test_tmp/ping"
