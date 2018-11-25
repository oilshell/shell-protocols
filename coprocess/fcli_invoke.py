#!/usr/bin/python -S
"""
fcli_invoke.py

Invoke a coprocess that supports the FCLI protocol.

Uses the cwd, stdin/stdout/stderr, and maybe env of THIS process.  Exits with
the exit code.
"""
from __future__ import print_function

import getopt  # for parsing the response
import os
import optparse  # Richer command line interface
import sys
import select
import stat

from util import log, netstring_readfd, netstring_encode


PIPE_SIZE = 4096

def Options():
  """Returns an option parser instance."""

  p = optparse.OptionParser('fcli_driver.py [OPTION] ARG...')

  # TODO: Could this be a unix socket?  Or a pair?  Or even environment
  # variable?  No but then that "pollutes" the current env.
  p.add_option(
      '--fcli-in', dest='fcli_in',
      help='Connect to an existing FCLI control input')
  p.add_option(
      '--fcli-out', dest='fcli_out',
      help='Connect to an existing FCLI control output')
  return p


def ParseResponse(fcli_reply_args):
  try:
    opts, args = getopt.getopt(fcli_reply_args, "s:e:")
  except getopt.GetoptError as err:
    # TODO: protocol error
    raise RuntimeError(str(err))

  status = None
  error_str = None
  for name, value in opts:
    if name == '-s':
      status = value
    elif name == '-e':
      error_str = value
      log('stdin %r', value)
    else:
      raise AssertionError  # shouldn't get here

  try:
    status = int(status)  # None if missing
  except ValueError:
    raise RuntimeError('protocol error')

  return status, error_str


THIS_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))


def main(argv):
  p = Options()
  (opts, argv) = p.parse_args(argv[1:])

  # Create private named pipes for this instance.  Anonymous pipes don't work,
  # because they can't be inherited.

  fifo_stdin = os.path.join(THIS_DIR, '_tmp/stdin')
  fifo_stdout = os.path.join(THIS_DIR, '_tmp/stdout')
  fifo_stderr = os.path.join(THIS_DIR, '_tmp/stderr')

  try:
    os.mkfifo(fifo_stdin)
    os.mkfifo(fifo_stdout)
    os.mkfifo(fifo_stderr)
  except OSError as e:
    log('error making fifos: %s', e)

  # Yes this works, you can tell if stdout/stderr are going to the same file
  # descriptor!
  ids = []
  for fd in [0, 1, 2]:
    st = os.fstat(fd)
    ids.append((st.st_dev, st.st_ino))
  log('IDs = %s', ids)
  # Now find all the unique ones?

  request = [
      '-d', os.getcwd(),

      # TODO: Don't always open 3!
      '-r', fifo_stdin,  # open for reading
      '-w', fifo_stdout,  # for writing
      '-w', fifo_stderr,  # for writing

      # NOTE: These are INDICES and not fds!!!
      '-i', '0',
      '-o', '1',
      '-e', '2',
  ] + argv

  # These have to be opened in a specific order.  Can't use "with".

  in_f = os.open(opts.fcli_in, os.O_RDWR)
  out_f = os.open(opts.fcli_out, os.O_RDWR)

  request_str = ''.join('%s\0' % s for s in request)
  t = netstring_encode(request_str)
  log('writing %r', t)
  os.write(in_f, t)
  #os.flush(in_f)

  # Named pipes are weird in that open() blocks.  Now we've sent the request,
  # which instructs the worker to open files.  So now we can open and unblock
  # the worker.
  # NOTE: Does this cause 3 separate context switches because of the blocking?

  log('open stdin')
  #their_stdin_fd = os.open(fifo_stdin, os.O_RDWR)  # write
  their_stdin_fd = os.open(fifo_stdin, os.O_WRONLY)  # write
  log('open stdout')
  their_stdout_fd = os.open(fifo_stdout, os.O_RDONLY)  # read, no block
  log('open stderr')
  their_stderr_fd = os.open(fifo_stderr, os.O_RDONLY)  # read, no block
  log('done opening')

  log('their_stdin_fd = %d, their_stdout_fd = %d, their_stderr_fd = %d',
      their_stdin_fd, their_stdout_fd, their_stderr_fd)

  # to read -> to write
  # We select on ALL of these descriptors.  And then only if BOTH are ready,
  # then we do a read and a write.

  r_all = [0, their_stdout_fd, their_stderr_fd]
  w_all = [their_stdin_fd, 1, 2]

  rw_lookup = {}
  wr_lookup = {}
  for r, w in zip(r_all, w_all):
    rw_lookup[r] = w
    wr_lookup[w] = r

  # Modified in the loop
  r_wait = set(r_all)
  w_wait = None  # will be initialized
  to_write = {}  # fd -> bytes
  r_eof = set()

  # TODO: Test case:
  # stdin is really fast, while outputs 1% of it with sleeps in between.
  # we should have a limited buffer here.

  # Now enter an event loop for stdin/stdout/stderr.
  while True:
    # PROBLEM: 1 and 2 will always be ready for write?
    # how do we tell if we're done?
    # Do we need two selects?

    if not r_wait:
      break

    log('r_wait = %r', r_wait)
    r_ready, _, _ = select.select(r_wait, [], [])
    log('r_ready = %r', r_ready)

    if not r_ready:
      break

    # read at least one?
    for r in r_ready:
      w = rw_lookup[r]
      b = os.read(r, PIPE_SIZE)
      if not b:
        log('EOF reading from descriptor %d', r)
        r_eof.add(r)
      to_write[w] = b  # could be empty

    r_not_ready = set(r_wait) - set(r_ready)

    # Wait for ones with data
    w_wait = [rw_lookup[r] for r in r_ready]

    log('w_wait = %r', w_wait)
    try:
      _, w_ready, _ = select.select([], w_wait, [])
    except select.error as e:
      log('error: [%s] [%s]', e.args, e.message)
      raise
    log('w_ready = %r', w_ready)

    for w in w_ready:
      try:
        b = to_write.pop(w)
      except KeyError:
        continue  # nothing to write

      if not b:  # EOF
        # don't need to close stdout/stderr?
        if w not in (1,2):
          log('close %d', w)
          os.close(w)
          continue

      os.write(w, b)

    w_not_ready = set(w_wait) - set(w_ready)
    r_no_wait = set([wr_lookup[w] for w in w_not_ready])
    # Apply backpressure by not reading from descriptors that we still have
    # pending data for.
    r_wait = set(r_all) - r_no_wait - r_eof

  log('DONE I/O loop')

  # Now read the exit code.
  #
  # TODO: Handle the case that the server crashed

  response = netstring_readfd(out_f)
  # remove last one since NUL-terminated
  fcli_reply_args = response.split('\0')[:-1]
  status, error_str = ParseResponse(fcli_reply_args)

  if error_str:
    # TODO: Send errors and surface them here.  Always exit 1 on error?
    pass

  log('status = %d, error_str = %r', status, error_str)

  # skip -s.  Should we parse debug info here too?
  return status


if __name__ == '__main__':
  try:
    sys.exit(main(sys.argv))
  except RuntimeError as e:
    print('FATAL: %s' % e, file=sys.stderr)
    sys.exit(1)
