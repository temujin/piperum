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
from signal import SIGKILL, SIGTERM
from subprocess import TimeoutExpired, Popen
import time
from threading import Thread
from typing import Self, List, Set


class Task:
    """
    Representer of pipeline running in background.

    :param prcs: list of pipeline Popen objects
    """

    def __init__(self, prcs: List[Popen]) -> Self:
        self._prcs: List[Popen] = prcs
        self.pid: int = prcs[0].pid

    @property
    def returncode(self) -> int | None:
        """
        Pipeline retirncode.

        :returns: pipeline returncode if one is complete, else None
        """
        return self._prcs[-1].poll()

    @property
    def is_alive(self) -> bool:
        """
        Is pipeline still running.
        """

        rc: int | None = self._prcs[-1].poll()
        if rc is None:
            return True

        return False

    def __repr__(self) -> str:
        cmds: List[str] = []
        for prc in self._prcs:
            cmds.append(" ".join(prc.args))
        return f"""Task(cmd="{" | ".join(cmds)}", alive={self.is_alive}, pid={self.pid})"""

    def kill(self, signal: int = SIGTERM) -> None:
        """
        Send signal to pipeline.
        """
        try:
            os.killpg(self.pid, signal or SIGKILL)
        except ProcessLookupError:
            pass

    def wait(self, timeout: int = None) -> int:
        """
        Wait for pipeline to complete.

        :timeout:                         pipeline completion wait timeout
        :returns:                         pipeline return code
        :raise subprocess.TimeoutExpired: on waiting timeout expired
        """

        for prc in self._prcs:
            try:
                return prc.wait(timeout)
            except TimeoutExpired:
                self.kill(signal=SIGKILL)
                raise


class TaskPoller:
    def __init__(self) -> Self:
        self.tasks: Set = set()
        self._poll_th: Thread | None = None

    def _poll_func(self) -> None:
        while True:
            finished_tasks: Set = set()
            time.sleep(0.1)
            if not self.tasks:
                break
            for task in self.tasks:
                rc: int | None = task.returncode
                if rc is not None:
                    finished_tasks.add(task)

            self.tasks.difference_update(finished_tasks)

    def add(self, task: Task) -> Task:
        """
        Add task for polling.
        """

        self.tasks.add(task)
        if self._poll_th is None or not self._poll_th.is_alive():
            self._poll_th = Thread(target=self._poll_func)
            self._poll_th.start()

        return task

    def __del__(self) -> None:
        for task in self.tasks:
            task.kill(signal=SIGKILL)
