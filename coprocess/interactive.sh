#!/bin/bash
#
# Usage:
#   source interactive.sh

# Make sure you source this from its own directory!
THIS_DIR=$PWD

echolines-fcli() {
  # note: argv[0] is unused
  $THIS_DIR/fcli_invoke.py \
    --fcli-in $THIS_DIR/_tmp/fcli-in --fcli-out $THIS_DIR/_tmp/fcli-out -- \
    echolines "$@"
}

