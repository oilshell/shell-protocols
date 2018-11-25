#!/usr/bin/python
"""
fcli_server_lib.py
"""
from __future__ import print_function

import getopt
import os
import sys

from util import log, netstring_readfd, netstring_encode


def ParseRequest(fcli_req_args):
  opts, args = getopt.getopt(fcli_req_args, "d:r:w:i:o:e:")

  fds = []

  # TODO:
  # -k or -s or -h to stop/halt the process?
  # -s for stats?

  for name, value in opts:
    log('flag %s = %s', name, value)

    if name == '-d':
      #log('chdir %s', value)
      os.chdir(value)  # TODO: error handling

    elif name == '-r':
      # The -r must come BEFORE -i -o -e

      # BLOCKS unless someone opened for writing.
      fd = os.open(value, os.O_RDONLY)
      fds.append(fd)

    elif name == '-w':
      # The -w must come BEFORE -i -o -e
      fd = os.open(value, os.O_WRONLY)
      fds.append(fd)

    elif name == '-i':  # redir stdin
      log('stdin %r', value)
      index = int(value)
      # TODO: IndexError is protocol error
      fd = fds[index]
      os.dup2(fd, 0)
      os.close(fd)
      log('dup stdin %d done', fd)

    elif name == '-o':  # redir stdout
      log('stdout %r', value)
      index = int(value)
      fd = fds[index]
      os.dup2(fd, 1)
      os.close(fd)
      log('dup stdout %d done', fd)

    elif name == '-e':  # redir stderr
      log('stderr %r', value)
      index = int(value)
      fd = fds[index]
      os.dup2(fd, 2)
      os.close(fd)
      log('dup stderr %d done', fd)

    else:
      raise AssertionError()  # shouldn't get here

  log('ParseRequest done')

  # close stdout and stderr afterward?
  to_close = [1, 2]
  return args, to_close


def _MainLoop(main_func, in_f, out_f):
  while True:
    log('MainLoop top')
    try:
      request = netstring_readfd(in_f)
    except EOFError:
      break

    # remove last one since NUL-terminated
    fcli_req_args = request.split('\0')[:-1]

    log('MainLoop got request %r', fcli_req_args)
    try:
      argv, to_close = ParseRequest(fcli_req_args)
    except getopt.GetoptError as err:
      # TODO: Write -e protocol error
      raise RuntimeError(str(err))

    log('argv = %r', argv)

    try:
      status = main_func(argv)
    except Exception as e:
      # TODO: catch it and return status=1?
      raise

    for fd in to_close:
      log('worker closing fd %d', fd)
      os.close(fd)

    # -s for status, for symmetry
    # Other info could be put here?  Like the number of requests server or
    # something?

    response = ['-s', status]
    response_str = ''.join('%s\0' % s for s in response)
    t = netstring_encode(response_str)
    log('writing back %r', t)
    os.write(out_f, t)

  return 0


def MainLoop(main_func):
  # TODO: Remove this as an env variable so we don't confuse other processes.
  # Also remove FCLI_VERSION.

  fcli_in = os.getenv('FCLI_IN')
  fcli_out = os.getenv('FCLI_OUT')

  in_f = os.open(fcli_in, os.O_RDWR)
  out_f = os.open(fcli_out, os.O_RDWR)

  _MainLoop(main_func, in_f, out_f)

  # NOTE: It doesn't return?  We just kill it?  Or we can process the '-k'
  # command.  To shutdown.

  os.close(in_f)
  os.close(out_f)
