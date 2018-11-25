#!/usr/bin/python
"""
util.py
"""
from __future__ import print_function

import os
import sys

PID = os.getpid()

# HACK TO SAVE TERMINAL
def HackyLogRedirect():
  os.dup2(2, 99)


DEBUG = os.getenv('DEBUG')

def log(msg, *args):
  if not DEBUG:
    return

  if args:
    msg = msg % args
  #print('[%d] %s' % (PID, msg), file=sys.stderr)
  os.write(99, '[%d] %s\n' % (PID, msg))


def read_length(read_func):
  # TODO: We should also prevent the loop from going too many times?
  buf = ''
  while True:
    c = read_func(1)
    if not c:  # EOF
      raise EOFError
    if not c.isdigit():
      if buf:
        if c != ':':
          raise ValueError("Expected ':', got %r" % c)
      else:  # didn't get a number
        raise ValueError("Expected chunk length, got %r" % c)
      break
    buf += c
  return buf


def _netstring_read(read_func, max_length):
  """Helper for netstring_read and netstring_readfd."""
  length_str = read_length(read_func)
  length = int(length_str)
  if max_length and length > max_length:
    raise ValueError("Payload is too large: %s" % length)
  payload = read_func(length)
  tag_byte = read_func(1)

  # dump_line can emit a newline.
  if tag_byte != ',' and tag_byte != '\n':
    raise ValueError('Got tag %r, expected comma or newline' % tag_byte)
  return payload


def netstring_read(f, max_length=0):
  """Read a byte string.

  Returns:
    The bytes

  Raises:
    ValueError: if the value is not a byte string (comma or newline)
  """
  read_func = f.read
  return _netstring_read(read_func, max_length)


def netstring_readfd(fd, max_length=0):
  """Read a byte string from a file descriptor.

  Raises:
    ValueError: if the value is not a byte string (comma or newline)
  """
  read_func = lambda length: os.read(fd, length)
  return _netstring_read(read_func, max_length)


def netstring_encode(s):
  """
  Args:
    s: A byte string to encode
  """
  return '%d:%s,' % (len(s), s)
