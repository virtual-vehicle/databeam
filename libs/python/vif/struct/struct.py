import dataclasses
import struct

from typing import ClassVar, TypeVar, Type


T = TypeVar('T', bound='Struct')


@dataclasses.dataclass
class Struct:
    """
    Base type for a C like struct representation
    To implement a specific struct, derive class, override _STRUCT with a struct.Struct object, type as typing.ClassVar
    add all required members
    """
    _STRUCT: ClassVar[struct.Struct]

    @classmethod
    def size(cls: Type[T]) -> int:
        """
        Size of the _Struct in packed (i.e. binary) form
        :return: size of the packed package
        """
        return cls._STRUCT.size

    @classmethod
    def from_bytes(cls: Type[T], b: bytes) -> T:
        """
        Create _Struct from binary data
        :param b: binary data input
        :return: resulting _Struct
        """
        # noinspection PyArgumentList
        return cls(*cls._STRUCT.unpack_from(b))

    def __bytes__(self) -> bytes:
        """
        serialize _Struct to binary data
        :return: the serialized _Struct
        """
        return self._STRUCT.pack(*dataclasses.astuple(self))
