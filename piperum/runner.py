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

import copy
import os
import signal
from subprocess import CalledProcessError, PIPE, Popen
from typing import LiteralString, Self

from piperum import utils
from piperum.background import Task, TaskPoller


class Piperum:
    """
    Handy subprocess pipelines runner with pipelines support.

    :param task_poller: background.TaskPoller; polls background tasks completion
    """

    def __init__(self, task_poller: TaskPoller) -> Self:
        self._env: dict[LiteralString, LiteralString] = {}
        self._cwd: str | os.PathLike | None = None
        self._task_poller: TaskPoller = task_poller

    def __call__(
        self,
        cwd: os.PathLike | None = None,
        **env: LiteralString,
    ) -> Self:
        """
        Change.

        :param cwd:   pipelines working directory
        :param **env: environment variables
        """

        if not all(map(lambda x: type(x) is str, env.values())):
            raise TypeError("env variable value should be of type str.")

        new_piperum = copy.copy(self)

        new_piperum._cwd = cwd if cwd is not None else self._cwd

        new_piperum._env = self._env
        new_piperum._env.update(env)

        return new_piperum

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_) -> None:
        pass

    def _kill(self, prcs: list[Popen]) -> None:
        """
        Send signal to process group.

        :param prcs: list of pipeline processes
        """

        try:
            os.killpg(prcs[0].pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        map(lambda prc: prc.wait(), prcs)

    def run(
        self,
        *cmds: str,
        inptxt: str | None = None,
        inpfl: str | os.PathLike | None = None,
        outfl: str | os.PathLike | None = None,
        errfl: str | os.PathLike | None = None,
        err2out: bool = False,
        timeout: int | None = None,
    ) -> None:
        """
        Run pipeline in foreground.

        :param *cmds:                           pipeline commands
        :param inptxt:                          text to be written to pipeline stdin; exclusive mutual with inpfl
        :param inpfl:                           file name to connect to stdin; exclusive mutual with inptxt
        :param outfl:                           file name to redirect stdout to
        :param errfl:                           file name to redirect stderr to; exclusive mutual with err2out
        :param err2out:                         redirect stderr to stdout; exclusive mutual with errfl
        :param timeout:                         pipeline completion wait timeout
        :raises subprocess.CalledProcessError:  any process of pipeline return code != 0
        """

        prc_inp: str | os.PathLike | None = inptxt or inpfl
        retcode: int = 0

        with (
            utils.wrap_tty() as tty_fd,
            utils.prepare_std(inptxt=inptxt, inpfl=inpfl, outfl=outfl, errfl=errfl, err2out=err2out) as std,
        ):
            prcs: list[Popen] = utils.construct_pipeline(
                *cmds, cwd=self._cwd, env=self._env, stdin=std[0], stdout=std[1], stderr=std[2]
            )

            os.tcsetpgrp(tty_fd, prcs[0].pid)

            try:
                for prc in prcs:
                    if prc_inp is None:
                        prc.wait(timeout)
                    else:
                        prc.communicate(input=prc_inp, timeout=timeout)
                        prc_inp = None

                    retcode = prc.returncode

                    if retcode:
                        raise CalledProcessError(retcode, prc.args)
            finally:
                self._kill(prcs)

    def cap(
        self,
        *cmds: str,
        inptxt: str | None = None,
        inpfl: str | os.PathLike | None = None,
        errfl: str | os.PathLike | None = None,
        err2out: bool = False,
        timeout: int | None = None,
    ) -> str | None:
        """
        Run pipeline in foreground and capture stdout.

        :param *cmds:                           pipeline commands
        :param inptxt:                          text to be written to pipeline stdin; exclusive mutual with inpfl
        :param inpfl:                           file name to connect to stdin; exclusive mutual with inptxt
        :param errfl:                           file name to redirect stderr to; exclusive mutual with err2out
        :param err2out:                         redirect stderr to stdout; exclusive mutual with errfl
        :param timeout:                         pipeline completion wait timeout
        :returns:                               captured text
        :raises subprocess.CalledProcessError:  any process of pipeline return code != 0
        """

        prc_inp: str | None = inptxt or inpfl
        res_out: str = None
        retcode: int = 0

        with (
            utils.wrap_tty() as tty_fd,
            utils.prepare_std(inptxt=inptxt, inpfl=inpfl, outfl=None, errfl=errfl, err2out=err2out) as std,
        ):
            prcs: list[Popen] = utils.construct_pipeline(
                *cmds, cwd=self._cwd, env=self._env, stdin=std[0], stdout=PIPE, stderr=std[2]
            )

            os.tcsetpgrp(tty_fd, prcs[0].pid)

            try:
                prcs_len: int = len(prcs)
                res_out: str | bytes = ""
                for i, prc in enumerate(prcs):
                    if prcs_len == 1:
                        res_out, _ = prc.communicate(input=prc_inp, timeout=timeout)
                    elif prc_inp is not None:
                        prc.communicate(input=prc_inp, timeout=timeout)
                        prc_inp = None
                    elif i == prcs_len - 1:
                        res_out, _ = prc.communicate(timeout=timeout)
                    else:
                        prc.wait(timeout)

                    retcode = prc.returncode

                    if retcode:
                        raise CalledProcessError(retcode, prc.args)
            finally:
                self._kill(prcs)

        return res_out

    def run_bg(
        self,
        *cmds: str,
        inpfl: str | os.PathLike | None = None,
        outfl: str | os.PathLike | None = None,
        errfl: str | os.PathLike | None = None,
        err2out: bool = False,
    ) -> Task | None:
        """
        Run pipeline in background.

        :param *cmds:   pipeline commands
        :param inpfl:   file name to connect to stdin
        :param outfl:   file name to redirect stdout to
        :param errfl:   file name to redirect stderr to; exclusive mutual with err2out
        :param err2out: redirect stderr to stdout; mutual exclusive with errfl
        :returns:       background.Task
        """

        with utils.prepare_std(inpfl=inpfl, outfl=outfl, errfl=errfl, err2out=err2out) as std:
            prcs: list[Popen] = utils.construct_pipeline(
                *cmds, cwd=self._cwd, env=self._env, stdin=std[0], stdout=std[1], stderr=std[2]
            )

        return self._task_poller.add(Task(prcs))
