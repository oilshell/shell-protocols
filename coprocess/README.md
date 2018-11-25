### Demo of the FCLI Coprocess Protocol

Here's a simple Unix filter that prepends a string to each line:

```
$ time seq 3 | ./echolines.py --prefix /
/1
/2
/3
Wrote 3 lines

real    0m0.220s
```

I inserted a **200 ms** delay at the beginning to simulate loading many
dependencies before `main()`.  You pay this cost every time the shell invokes a
new `echolines.py` process.

-----

Here's a way to drastically reduce startup time.

I wrapped `main()` with `fcli_server_lib.py`, so it runs as a **coprocess**
when `FCLI_VERSION` is in the environment.

Try this:

```
$ ./demo.sh start-coproc
```

It starts the coprocess/server and then invokes it via `fcli_invoke.py`.  The
driver and the coprocess communicate using named pipes in `_tmp`.

The first time, you have to pay the 200 ms startup time, but you save it on
every other invocation.

Source the `echolines-fcli` function:

```
source interactive.sh
```

And try the same command:

```
$ time seq 3 | echolines-fcli --prefix /
/1
/2
/3
Wrote 3 lines

real    0m0.017s
```

It's now **faster**.  Try these commands as well:

```sh
# stdout and stderr work
$ time seq 10 | echolines-fcli --prefix / >out.txt 2>err.txt
$ head out.txt err.txt

# status works
$ time seq 10 | echolines-fcli --prefix / --status 42
$ echo $?
42

# Add a delay before each line
$ time seq 10 | echolines-fcli --prefix / --delay-ms 50

# Blow up the input, testing the event loop
$ time seq 50 | echolines-fcli --prefix / --ratio 1000.0 | wc -l

# Contract the input.  TODO: Bug here because it hangs?
$ time seq 50000 | echolines-fcli --prefix / --ratio 0.001 | wc -l

# List the current dir.
$ time seq 1 | echolines-fcli  --prefix / --ls

# The listing changes after you cd!  The coprocess takes on the current #
directory of the driver fcli_invoke.py.
$ cd /
$ time seq 1 | echolines-fcli  --prefix / --ls
```

Other commands:

```
./demo.sh list-coproc
./demo.sh stop-coproc
```

### Required Patches

In addition to the expected wrapping `main()` with `fcli_server_lib`:

- `for line in sys.stdin` had to be `while True: line = sys.stdin.readline()` for some reason
- Add `sys.stdout.flush()` after each print()

### Notes

- `fcli_invoke.py` is a short, generic program that can be built into shells
  like [Oil](https://www.oilshell.org).  Instead of a `fork(); exec()` on every
  coprocess invocation, there will just be a `fork()`.

### Protocol Sketch

- Control pipes: `_tmp/fcli-in` and `_tmp/fcli-out`
- Data pipes: `_tmp/{stdin,stdout,stderr}`.  (NOTE: There should probably be new ones for each invocation.)
- Request/response format: netstrings where the payload is an array of
  `NUL`-terminated strings.
  - This format is easy to use from both Python and C.
  - We use `getopt()` to parse the protocol!  We are **not** using it to parse
    the command line.  This is so that every process doesn't need a new JSON
    dependency.  It can just use `libc` or the equivalent.

### TODO

- Process management and concurrency: imagine `echolines-fcli |
  echolines-fcli`.
  - Need to manage the named pipes.  (Yes, named pipes are pain.  Unix domain
    sockets would also work, although the server should not be concurrent.)
- Signals (Ctrl-C)
- Handle unexpected server exit.
- Check protocol errors on both the client and server.  This already exists in
  the protocol, but error cases need to be polished.

### Links

- [Coprocess Protocol
  V2](https://github.com/oilshell/oil/wiki/Coprocess-Protocol-V2) -- The main
  design motivation is that **existing tools** can be converted to coprocesses
  as easily as possible.  We don't want to modify every print statement in the
  program.
- [joblimate](https://github.com/apenwarr/joblimate)
