import logging
import time
from enum import Enum
from threading import Thread
from typing import NewType

import _thread
from robot.board import Board

Zone = NewType('Zone', int)

LOGGER = logging.getLogger(__name__)


def kill_after_delay(timeout_seconds, exit_message):
    """
    Interrupts main process after the given delay.
    """

    end_time = time.time() + timeout_seconds

    def worker():
        while time.time() < end_time:
            remaining = end_time - time.time()
            time.sleep(max(remaining, 0.01))

        LOGGER.info("Timeout %rs expired: %s", timeout_seconds, exit_message)

        # Interrupt the main thread to kill the user code
        _thread.interrupt_main()  # type: ignore

    worker_thread = Thread(target=worker, daemon=True)
    worker_thread.start()
    return worker_thread


class GameMode(Enum):
    """Possible modes the robot can be in."""

    COMPETITION = 'competition'
    DEVELOPMENT = 'development'


class GameState(Board):
    """A description of the initial game state the robot is operating under."""

    @property
    def zone(self) -> Zone:
        """
        The zone in which the robot starts the match.

        This is configured by inserting a competition zone USB stick into the
        robot.

        :return: zone ID the robot started in (0-3)
        """
        return self._send_and_receive({})['zone']

    @property
    def mode(self) -> GameMode:
        """
        :return: The ``GameMode`` that the robot is currently in.
        """
        value = self._send_and_receive({})['mode']
        return GameMode(value)
