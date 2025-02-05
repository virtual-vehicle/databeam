"""
Class to handle a receiving TCP socket as a client or as a server.
"""

import struct
import socket
import traceback
from typing import Optional, Tuple
import threading
import json
from enum import Enum

from vif.logger.logger import LoggerMixin
from vif.flatten.flatten import flatten


class ErrorCode(Enum):
    OK = 0,
    RECOVERABLE = 1,
    CRITICAL = 2


class Connection:
    def __init__(self, connection: socket.socket, address: str):
        self.socket = connection
        self.address = address


class TcpManager(LoggerMixin):
    def __init__(self):
        """
        Initialized default values and most objects as None.
        """
        super().__init__()
        self.address: Optional[str] = None
        self.port: Optional[int] = None
        self.socket: Optional[socket.socket] = None
        self.conn: Optional[Connection] = None
        self.stop_event: Optional[threading.Event] = None  # Used to create cancelable loops

        self.big_endian = False
        self.struct_size = 0
        self.struct_format = None
        self.struct_names = None

        self.default_msg_length = 20000
        self.timeout_sec = 1.0
        self.as_client: bool = False

        self.use_length_bytes: bool = False
        self.number_length_bytes: int = 4
        self.data_format: str = "json"

    def config(self, config_dict: dict, stop_event) -> ErrorCode:
        """
        Configures the TcpManager by applying the config dictionary directly.
        :param config_dict: The dictionary containing the config values.
        :param stop_event: The stop event to listen to. This allows for externally cancelable loops in the whole class.
        :return: The error code to indicate if the operation was successful.
        """
        try:
            self.logger.info("Configuring tcp socket.")
            self.address = config_dict["tcp_address"]
            self.as_client = config_dict["client_mode"]
            self.use_length_bytes = config_dict["use_length_bytes"]
            self.number_length_bytes = config_dict["number_length_bytes"]
            self.data_format = config_dict["data_format"]
            self.port = config_dict["tcp_port"]
            self.big_endian = config_dict["big_endian"]
            self.stop_event = stop_event
            return ErrorCode.OK
        except Exception as e:
            self.logger.error(f"Cannot configure TCP socket. {e}")
            return ErrorCode.CRITICAL

    def setup(self) -> ErrorCode:
        """
        Sets up the TcpManager class by preparing potential connections.
        :return: The error code to indicate if the operation was successful.
        """
        if self.as_client:
            self.logger.info("Setting up tcp client.")
            return self._setup_as_client()
        else:
            self.logger.info("Setting up tcp server.")
            return self._setup_as_server()

    def connect(self) -> ErrorCode:
        """
        Either accepts a conenction or connects to a server based on configuration.
        :return: The error code to indicate if the operation was successful.
        """
        if self.as_client:
            return self._connect_as_client()
        else:
            return self._connect_as_server()

    def receive(self) -> Tuple[ErrorCode, dict]:
        """
        Receives a data packet and returns it as a dictionary.
        :return: A tuple with an error code and the populated dictionary, if receiving was successful.
        """
        if self.as_client:
            byte_data = self._receive_internal(self.socket)
        else:
            byte_data = self._receive_internal(self.conn.socket)

        if len(byte_data) == 0:
            # Something broke probably in the connection
            return ErrorCode.CRITICAL, {}

        if self.data_format == "json":
            return self._parse_json_data(byte_data)
        elif self.data_format == "struct":
            return self._parse_struct_data(byte_data)
        else:
            self.logger.error("Invalid data format provided for TCP parsing. Only use json or struct.")
            return ErrorCode.RECOVERABLE, {}

    def close(self) -> ErrorCode:
        """
        Closes the socket.
        :return: The error code to indicate if the operation was successful.
        """
        if self.as_client:
            self.logger.info("Closing tcp client.")
            return self._close_as_client()
        else:
            self.logger.info("Closing tcp server.")
            return self._close_as_server()

    def _setup_as_server(self) -> ErrorCode:
        """
        Sets up the socket if configured as a server.
        :return: The error code to indicate if the operation was successful.
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.address, self.port))
            self.socket.settimeout(self.timeout_sec)
            self.socket.listen(1)
            return ErrorCode.OK
        except Exception as e:
            self.logger.error(f"EX _setup_as_server ({type(e).__name__}): {e}")
            return ErrorCode.CRITICAL

    def _setup_as_client(self) -> ErrorCode:
        """
        Sets up the socket if configured as a client.
        :return: The error code to indicate if the operation was successful.
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            return ErrorCode.OK
        except Exception as e:
            self.logger.error(f"EX _setup_as_client ({type(e).__name__}): {e}")
            return ErrorCode.CRITICAL

    def _connect_as_server(self) -> ErrorCode:
        """
        Accepts a connection if configured as a server.
        :return: The error code to indicate if the operation was successful.
        """
        try:
            if self.conn is None:
                conn_socket, addr = self.socket.accept()
                self.conn = Connection(conn_socket, addr)
                self.logger.debug(f"Client at address {self.conn.socket.getsockname()} Connected.")
            return ErrorCode.OK
        except Exception as e:
            self.logger.error(f"EX _connect_as_server ({type(e).__name__}): {e}")
            return ErrorCode.CRITICAL

    def _connect_as_client(self) -> ErrorCode:
        """
        Establishes a connection if configured as a client.
        :return: The error code to indicate if the operation was successful.
        """
        try:
            self.socket.connect((self.address, self.port))
            return ErrorCode.OK
        except Exception as e:
            self.logger.error(f"EX _connect_as_client ({type(e).__name__}): {e}")
            return ErrorCode.CRITICAL

    def _receive_internal(self, recv_socket) -> bytes:
        """
        Receives data from a variable socket.
        :param recv_socket: The socket to receive with.
        :return: The bytes received by the operation. Is empty if it failed.
        """
        if self.use_length_bytes:
            raw_length = self._receive_blocking(recv_socket, self.number_length_bytes, True)
            if len(raw_length) == 0:
                return b""
            if self.big_endian:
                length = int.from_bytes(raw_length, byteorder="big", signed=False)
            else:
                length = int.from_bytes(raw_length, byteorder="little", signed=False)
            return self._receive_blocking(recv_socket, length, True)
        else:
            return self._receive_blocking(recv_socket, self.default_msg_length, False)

    def _parse_json_data(self, byte_data: bytes) -> Tuple[ErrorCode, dict]:
        """
        Parses a json-byte packet into a dictionary.
        :param byte_data: The data to parse.
        :return: A tuple with an error code and the populated dictionary if successful.
        """
        try:
            json_data = json.loads(byte_data.decode("utf-8").replace("'", '"'))

        except json.JSONDecodeError:
            self.logger.warning(f"Malformed JSON: {byte_data.decode('utf-8')}")
            self.logger.info("Going to recover from malformation")
            c = None
            while c != b"}":
                if self.as_client:
                    c = self._receive_blocking(self.socket, 1, True)
                else:
                    c = self._receive_blocking(self.conn.socket, 1, True)

                if len(c) == 0:
                    break
            self.logger.info("Recovered from malformation.")
            return ErrorCode.RECOVERABLE, {}

        except Exception as e:
            self.logger.error(f'EX _parse_json_data ({type(e).__name__}): {e}')
            return ErrorCode.CRITICAL, {}

        json_data = flatten(json_data)

        # store all json numbers as floats
        for key, value in json_data.items():
            if isinstance(value, int):
                json_data[key] = float(value)

        return ErrorCode.OK, json_data

    def _parse_struct_data(self, byte_data: bytes) -> Tuple[ErrorCode, dict]:
        """
        Parses a struct-byte packet into a dictionary.
        :param byte_data: The data to parse.
        :return: A tuple with an error code and the populated dictionary if successful.
        """
        # parse and store data if packet has correct length
        try:
            if len(byte_data) == self.struct_size:
                unpacked = struct.unpack(self.struct_format, byte_data)
                data_dict = {}
                for idx, name in enumerate(self.struct_names):
                    if isinstance(unpacked[idx], bytes):
                        data_dict[name] = unpacked[idx].decode()  # convert bytes to string
                    else:
                        data_dict[name] = unpacked[idx]
                return ErrorCode.OK, data_dict
            else:
                self.logger.warning("Packet size mismatch: is %d, should be %d",
                                    len(byte_data), self.struct_size)
                return ErrorCode.CRITICAL, {}
        except Exception as e:
            self.logger.error(f'EX _parse_struct_data ({type(e).__name__}): {e}')
            return ErrorCode.CRITICAL, {}

    def _close_as_server(self) -> ErrorCode:
        """
        Closes the socket if configured as a server.
        :return: The error code to indicate if the operation was successful.
        """
        try:
            if self.conn is not None:
                self.conn.socket.close()
                self.conn = None
            if self.socket is not None:
                self.socket.close()
                self.socket = None
            return ErrorCode.OK
        except Exception as e:
            self.logger.warning(f'EX _close_as_server ({type(e).__name__}): {e}')
            return ErrorCode.RECOVERABLE

    def _close_as_client(self) -> ErrorCode:
        """
        Closes the socket if configured as a client.
        :return: The error code to indicate if the operation was successful.
        """
        try:
            if self.socket is not None:
                self.socket.close()
                self.socket = None
            return ErrorCode.OK
        except Exception as e:
            self.logger.warning(f'EX _close_as_client ({type(e).__name__}): {e}')
            return ErrorCode.RECOVERABLE

    def _receive_blocking(self, conn: socket.socket, num_bytes: int, force_num_bytes: bool) -> bytes:
        """
        Receives a single packet of data in a blocking manner. Can be cancelled by setting the stop event of the
        module.
        :param conn: The socket to receive with.
        :param num_bytes: The number of bytes to receive.
        :param force_num_bytes: If set to True, it will guarantee the number of bytes provided. If False, it is
                                allowed to receive fewer bytes.
        :return: The bytes received. Empty if not successful.
        """
        data = b""

        while not self.stop_event.is_set():
            try:
                if force_num_bytes:
                    while num_bytes > 0 and not self.stop_event.is_set():
                        received = conn.recv(num_bytes)

                        if len(received) == 0:
                            return b""

                        num_bytes -= len(received)
                        data = b"".join([data, received])
                else:
                    data = conn.recv(num_bytes)

                if self.stop_event.is_set():
                    return b""
                return data
            except Exception as e:
                self.logger.error(f'EX _receive_blocking ({type(e).__name__}): {e}\n{traceback.format_exc()}')
                return b""

        return b""
