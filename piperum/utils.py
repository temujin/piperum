# Copyright (c) 2025 Oleg Anufriev
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import re
import shlex
import signal
import sys
from collections.abc import Generator
from contextlib import contextmanager
from subprocess import PIPE, Popen, STDOUT
from typing import IO


DO_APPEND_RE = re.compile(r"^\+")


def open_stream_w(path: str | os.PathLike | None) -> IO | None:
    """
    Open/create file for write/append.

    :param path: file name
    """

    if path is None:
        return None
    else:
        mode: str = "a" if DO_APPEND_RE.match(str(path)) is not None else "w"
        return open(re.sub(r"^\+", "", str(path)).strip(), mode)


def open_stream_r(path: str | os.PathLike | None) -> IO | None:
    """
    Open file for reading.

    :param path: file name
    """

    if path is None:
        return None
    else:
        return open(re.sub(r"^\+", "", str(path)).strip())


@contextmanager
def prepare_std(
    inptxt: str = None,
    inpfl: str | os.PathLike = None,
    outfl: str | os.PathLike = None,
    errfl: str | os.PathLike = None,
    err2out: bool = False,
) -> Generator:
    """
    Prepare pipeline std streams.

    :param inptxt:  text to be written to pipeline stdin
    :param inpfl:   file name to connect to stdin; exclusive mutual with inptxt
    :param outfl:   file name to redirect stdout to
    :param errfl:   file name to redirect stderr to; exclusive mutual with err2out
    :param err2out: redirect stderr to stdout; exclusive mutual with errfl
    :yields:        tuple of std streams
    """

    stdout: IO = open_stream_w(outfl)

    if inptxt is not None and inpfl is not None:
        raise Exception("Arguments conflict: ['inptxt', 'inpfl']")

    if inptxt is not None:
        stdin: int = PIPE
    else:
        stdin = open_stream_r(inpfl)

    if err2out:
        stderr: int = STDOUT
        if errfl is not None:
            raise Exception("Arguments conflict: ['errfl', 'err2out']")
    else:
        stderr: IO = open_stream_w(errfl)

    try:
        yield (stdin, stdout, stderr)
    finally:
        map(lambda stream: stream.close(), filter(lambda stream: stream is not None, [stdin, stdout, stderr]))


@contextmanager
def wrap_tty() -> Generator:
    """
    Deal with process group to control terminal association

    * memorize current process group associated to control terminal
    * inhibit SIGTTOU handling
    * roll back things afterwards

    :yields: control tty file descriptor
    """
    tty_path: str = os.ttyname(sys.stdin.fileno())
    tty_fd: IO = os.open(tty_path, os.O_RDONLY)

    orig_tcpgrp: int = os.tcgetpgrp(tty_fd)
    orig_sigttou_handler = signal.getsignal(signal.SIGTTOU)
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    try:
        yield tty_fd
    finally:
        os.tcsetpgrp(tty_fd, orig_tcpgrp)
        signal.signal(signal.SIGTTOU, orig_sigttou_handler)
        os.close(tty_fd)


def construct_pipeline(
    *cmds: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    stdin: PIPE | None = None,
    stdout: PIPE | None = None,
    stderr: PIPE | None = None,
) -> list[Popen]:
    """
    Spawn processes, connect them by pipes, connect std streams.

    :param *cmds:  pipeline commands
    :param cwd:    pipeline working directory
    :param env:    extra envrionment variables to set for pipeline
    :param stdin:  input stream
    :param stdout: output stream
    :param stderr: error stream
    :returns: list of pipeline Popen objects
    """

    prcs: list[Popen] = []
    pipeline_size: int = len(cmds)
    pgid: int = 0

    prcs_env: dict = os.environ.copy()
    if env is not dict:
        prcs_env.update(env)

    for i, cmd in enumerate(cmds):
        cmd_as_list: list[str] = shlex.split(cmd)

        prc_stdin: IO | int | None = None
        prc_stdout: IO | int | None = None
        prc_stderr: IO | int | None = stderr

        if i == 0:
            prc_stdin = stdin
        if i > 0:
            prc_stdin = prcs[i - 1].stdout

        if i < pipeline_size - 1:
            prc_stdout = PIPE
        if i == pipeline_size - 1:
            prc_stdout = stdout

        prc = Popen(
            cmd_as_list,
            stdin=prc_stdin,
            stdout=prc_stdout,
            stderr=prc_stderr,
            env=env,
            bufsize=1,
            encoding="utf-8",
            text=True,
            process_group=pgid,
            cwd=cwd,
        )
        if pgid == 0:
            pgid = prc.pid

        prcs.append(prc)

    return prcs
