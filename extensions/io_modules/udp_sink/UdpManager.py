"""
Class to handle a receiving udp socket.
"""

import struct
import socket
from typing import Optional, Tuple
import threading
import json
from vif.logger.logger import LoggerMixin
from vif.flatten.flatten import flatten
from enum import Enum


class ErrorCode(Enum):
    OK = 0,
    RECOVERABLE = 1,
    CRITICAL = 2


class UdpManager(LoggerMixin):
    def __init__(self):
        """
        Initialized default values and most objects as None.
        """
        super().__init__()
        self.address: Optional[str] = None
        self.port: Optional[int] = None
        self.socket: Optional[socket.socket] = None
        self.stop_event: Optional[threading.Event] = None  # Used to create cancelable loops

        self.big_endian = False
        self.struct_size = 0
        self.struct_format = None
        self.struct_names = None

        self.default_msg_length = 20000
        self.timeout_sec = 1.0

        self.use_length_bytes: bool = False
        self.number_length_bytes: int = 4
        self.data_format: str = "json"

    def config(self, config_dict: dict, stop_event) -> ErrorCode:
        """
        Configures the UdpManager by applying the config dictionary directly.
        :param config_dict: The dictionary containing the config values.
        :param stop_event: The stop event to listen to. This allows for externally cancelable loops in the whole class.
        :return: The error code to indicate if the operation was successful.
        """
        try:
            self.logger.info("Configuring udp socket.")
            self.address = config_dict["udp_address"]
            self.use_length_bytes = config_dict["use_length_bytes"]
            self.number_length_bytes = config_dict["number_length_bytes"]
            self.data_format = config_dict["data_format"]
            self.port = config_dict["udp_port"]
            self.big_endian = config_dict["big_endian"]
            self.stop_event = stop_event
            return ErrorCode.OK
        except Exception as e:
            self.logger.error(f"Cannot configure UDP socket. {e}")
            return ErrorCode.CRITICAL

    def setup(self) -> ErrorCode:
        """
        Sets up the UdpManager class by binding to the port.
        :return: The error code to indicate if the operation was successful.
        """
        self.logger.info("Setting up udp socket.")
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.address, self.port))
            self.socket.settimeout(self.timeout_sec)
            return ErrorCode.OK
        except Exception as e:
            self.logger.error(f"Could not set up UDP server socket. {e}")
            return ErrorCode.CRITICAL

    def receive(self) -> Tuple[ErrorCode, dict]:
        """
        Receives a data packet and returns it as a dictionary.
        :return: A tuple with an error code and the populated dictionary, if receiving was successful.
        """
        byte_data = self._receive_internal(self.socket)

        if len(byte_data) == 0:
            return ErrorCode.RECOVERABLE, {}

        if self.data_format == "json":
            return self._parse_json_data(byte_data)
        elif self.data_format == "struct":
            return self._parse_struct_data(byte_data)
        else:
            self.logger.error("Invalid data format provided for UDP parsing. Only use json or struct.")
            return ErrorCode.RECOVERABLE, {}

    def close(self) -> ErrorCode:
        """
        Closes the socket.
        :return: The error code to indicate if the operation was successful.
        """
        self.logger.info("Closing down udp socket.")
        try:
            if self.socket is not None:
                self.socket.close()
                self.socket = None
            return ErrorCode.OK
        except Exception as e:
            self.logger.warning(f"Could not close UDP client socket. {e}")
            return ErrorCode.RECOVERABLE

    def _receive_internal(self, recv_socket) -> bytes:
        """
        Receives data from a variable socket.
        :param recv_socket: The socket to receive with.
        :return: The bytes received by the operation. Is empty if it failed.
        """
        try:
            if self.use_length_bytes:
                raw_length = recv_socket.recvfrom(self.number_length_bytes)[0]
                if len(raw_length) == 0:
                    return b""
                if self.big_endian:
                    length = int.from_bytes(raw_length, byteorder="big", signed=False)
                else:
                    length = int.from_bytes(raw_length, byteorder="little", signed=False)
                return recv_socket.recvfrom(length)[0]
            else:
                return recv_socket.recvfrom(self.default_msg_length)[0]
        except TimeoutError:
            return b""

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
            return ErrorCode.RECOVERABLE, {}

        except Exception as e:
            self.logger.error(f'Exception: {e}')
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
            self.logger.error(f"Cannot parse struct data. {e}")
            return ErrorCode.CRITICAL, {}
