import json
import socket
import time
from collections import Mapping
from pathlib import Path
from typing import Union


class BoardList(Mapping):
    """A mapping of ``Board``s allowing access by index or identity."""

    def __init__(self, *args, **kwargs):
        self._store = dict(*args, **kwargs)
        self._store_list = sorted(self._store.values(), key=lambda board: board.serial)

    def __getitem__(self, attr):
        if type(attr) is int:
            return self._store_list[attr]
        return self._store[attr]

    def __iter__(self):
        return iter(self._store_list)

    def __len__(self):
        return len(self._store_list)


class Board:
    """Base class for connections to ``robotd`` board sockets."""

    SEND_TIMEOUT_SECS = 6
    RECV_BUFFER_BYTES = 2048

    def __init__(self, socket_path: Union[Path, str]):
        self.socket_path = Path(socket_path)
        self.socket = None
        self.data = b''

        self._connect()

    @property
    def serial(self):
        """Serial number for the board."""
        return self.socket_path.stem

    def _greeting_response(self, data):
        """
        Handle the response to the greeting command.

        NOTE: This is called on reconnect in addition to first connection
        """
        pass

    def _connect(self):
        """
        Connect or reconnect to a socket.

        :param socket_path: Path for the unix socket
        """
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(self.SEND_TIMEOUT_SECS)

        try:
            self.socket.connect(str(self.socket_path))
        except ConnectionRefusedError as e:
            print('Error connecting to: ', self.socket_path)
            raise e

        greeting = self.receive()
        self._greeting_response(greeting)

    def _get_lc_error(self):
        """
        Describe a lost connection error.

        :return: The text for a lost connection error
        """
        return "Lost Connection to {conn} at {path}".format(
            conn=str(self.__class__.__name__),
            path=self.socket_path,
        )

    def _socket_with_single_retry(self, handler):
        retryable_errors = (
            socket.timeout,
            BrokenPipeError,
            OSError,
            ConnectionResetError,
        )

        backoffs = [
            0.1,
            0.5,
            1.0,
            2.0,
            3.0,
        ]

        try:
            return handler()
        except retryable_errors as e:
            original_exception = e

        for backoff in backoffs:
            time.sleep(backoff)

            try:
                self._connect()
            except (ConnectionRefusedError, FileNotFoundError):
                continue

            try:
                return handler()
            except retryable_errors:
                pass

        raise original_exception

    def send(self, message, should_retry=True):
        """
        Send a message to robotd.

        :param retry: used internally
        :param message: message to send
        """

        data = (json.dumps(message) + '\n').encode('utf-8')

        def sendall():
            print('Sent:', data.strip())
            self.socket.sendall(data)

        if should_retry:
            return self._socket_with_single_retry(sendall)
        else:
            return sendall()

    def _recv_from_socket(self, size):
        data = self.socket.recv(size)
        if data == b'':
            raise BrokenPipeError()
        return data

    def receive(self, should_retry=True):
        """
        Receive a message from robotd.
        """
        while b'\n' not in self.data:
            if should_retry:
                message = self._socket_with_single_retry(
                    lambda: self._recv_from_socket(4096),
                )
            else:
                message = self._recv_from_socket(4096)

            self.data += message

        line = self.data.split(b'\n', 1)[0]
        self.data = self.data[len(line) + 1:]

        print('Received:', line.strip())

        return json.loads(line.decode('utf-8'))

    def send_and_receive(self, message, should_retry=True):
        """
        Send a message to robotd and wait for a response.
        """
        self.send(message, should_retry)
        return self.receive(should_retry)

    def close(self):
        """
        Close the the connection to the underlying robotd board.
        """
        self.socket.detach()

    __del__ = close
