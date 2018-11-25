#!/bin/bash
#
# Usage:
#   ./demo.sh <function name>

set -o nounset
set -o pipefail
set -o errexit

source interactive.sh

echolines-batch() {
  seq 5 | ./echolines.py --prefix '-- '
}

start-coproc() {
  mkdir -p _tmp

  rm _tmp/* || true

  mkfifo _tmp/fcli-in || true
  mkfifo _tmp/fcli-out || true

  set -x

  # NOTE: This process stays alive, and we have to kill it.
  # TODO: Start this wtih </dev/null >/dev/null 2>/dev/null ?
  if true; then
    FCLI_VERSION=1 FCLI_IN=_tmp/fcli-in FCLI_OUT=_tmp/fcli-out \
      ./echolines.py "$@" &
  fi

  seq 10 | echolines-fcli --prefix '-- '
}

# TODO: do we need PID files then?
stop-coproc() {
  killall echolines.py
}

list-coproc() {
  ps aux | grep echolines
}

"$@"
