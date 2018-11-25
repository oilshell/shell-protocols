#!/bin/bash
#
# Usage:
#   source interactive.sh

echolines-fcli() {
  # note: argv[0] is unused
  ./fcli_invoke.py --fcli-in _tmp/fcli-in --fcli-out _tmp/fcli-out -- \
    echolines "$@"
}

