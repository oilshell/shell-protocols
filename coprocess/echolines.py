#!/usr/bin/python
"""
echolines.py
"""
from __future__ import print_function

import optparse
import os
import random
import sys
import time

import fcli_server_lib
import util
log = util.log

# 300 ms sleep.  This is the startup time we want to save.
time.sleep(0.3)


def Options():
  """Returns an option parser instance."""

  p = optparse.OptionParser('fcli_driver.py [OPTION] ARG...')
  p.add_option(
      '--prefix', dest='prefix', default='',
      help='Print a prefix on every line')
  p.add_option(
      '--delay-ms', dest='delay_ms', default=0,
      help='Wait this number of milliseconds between every line.')
  p.add_option(
      '--status', dest='status', type=int, default=0,
      help='Exit with this status')

  # Blow up the input or reduce it. For testing the event loop.
  p.add_option(
      '--ratio', dest='ratio', type=float, default=1.0,
      help='Output lines with this probability (can be > 1.0)')
  return p


def main(argv):
  p = Options()
  (opts, argv) = p.parse_args(argv[1:])

  for arg in argv:
    log('arg = %r', arg)

  start_time = time.time()
  seconds = float(opts.delay_ms) / 1000.0

  i = 0
  while True:  # PATCH: for line in sys.stdin doesn't work?
    line = sys.stdin.readline()
    if not line:
      break
    prob = opts.ratio
    while random.random() < prob:
      if opts.prefix:
        time.sleep(seconds)
        sys.stdout.write(opts.prefix)

      time.sleep(seconds)
      sys.stdout.write(line)
      sys.stdout.flush()  # PATCH

      prob -= 1.0
      i += 1

  log('Wrote %d lines in %.3f seconds', i, time.time() - start_time)

  return opts.status


if __name__ == '__main__':
  if os.getenv('FCLI_VERSION'):
    util.HackyLogRedirect()
    sys.exit(fcli_server_lib.MainLoop(main))
  else:
    sys.exit(main(sys.argv))
