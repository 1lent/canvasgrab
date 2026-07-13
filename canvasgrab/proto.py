from typing import Optional, Tuple


def _varint_encode(value: int) -> bytes:
    buf = bytearray()
    while value > 0x7F:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.append(value & 0x7F)
    return bytes(buf)


def _varint_decode(data: bytes, offset: int = 0) -> Tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return value, offset


_WIRE_VARINT = 0
_WIRE_LEN = 2


def _tag(field_number: int, wire_type: int) -> int:
    return (field_number << 3) | wire_type


def encode_canvas_request(track_uri: str) -> bytes:
    v = track_uri.encode()
    entity = (
        _varint_encode(_tag(1, _WIRE_LEN))
        + _varint_encode(len(v))
        + v
    )
    return (
        _varint_encode(_tag(1, _WIRE_LEN))
        + _varint_encode(len(entity))
        + entity
    )


class _ProtoReader:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def done(self) -> bool:
        return self._pos >= len(self._data)

    def next_tag(self) -> Optional[Tuple[int, int]]:
        if self.done():
            return None
        tag, self._pos = _varint_decode(self._data, self._pos)
        return tag >> 3, tag & 7

    def read_varint(self) -> int:
        value, self._pos = _varint_decode(self._data, self._pos)
        return value

    def read_bytes(self) -> bytes:
        length = self.read_varint()
        value = self._data[self._pos:self._pos + length]
        self._pos += length
        return value

    def skip(self, wire_type: int) -> None:
        if wire_type == _WIRE_VARINT:
            self.read_varint()
        elif wire_type == _WIRE_LEN:
            length = self.read_varint()
            self._pos += length
        elif wire_type in (1, 5):
            self._pos += 8 if wire_type == 1 else 4


def _parse_canvaz(data: bytes) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    reader = _ProtoReader(data)
    url = None
    canvas_type = None
    artist_name = None
    while not reader.done():
        tag = reader.next_tag()
        if tag is None:
            break
        field_number, wire_type = tag
        if field_number == 2 and wire_type == _WIRE_LEN:
            if url is None:
                url = reader.read_bytes().decode()
            else:
                reader.skip(wire_type)
        elif field_number == 4 and wire_type == _WIRE_VARINT:
            canvas_type = reader.read_varint()
        elif field_number == 6 and wire_type == _WIRE_LEN:
            artist_bytes = reader.read_bytes()
            artist_name = _parse_artist_name(artist_bytes)
        elif field_number == 5 and wire_type == _WIRE_LEN:
            reader.skip(wire_type)
        else:
            reader.skip(wire_type)
    return url, canvas_type, artist_name


def _parse_artist_name(data: bytes) -> Optional[str]:
    reader = _ProtoReader(data)
    while not reader.done():
        tag = reader.next_tag()
        if tag is None:
            break
        field_number, wire_type = tag
        if field_number == 2 and wire_type == _WIRE_LEN:
            return reader.read_bytes().decode()
        else:
            reader.skip(wire_type)
    return None


def decode_canvas_url(data: bytes) -> Tuple[Optional[str], Optional[str]]:
    reader = _ProtoReader(data)
    best_url = None
    best_artist = None
    best_prio = -1
    while not reader.done():
        tag = reader.next_tag()
        if tag is None:
            break
        field_number, wire_type = tag
        if field_number == 1 and wire_type == _WIRE_LEN:
            url, canvas_type, artist_name = _parse_canvaz(reader.read_bytes())
            if url:
                priority = 2 if canvas_type == 2 else (0 if canvas_type is not None else 1)
                if priority > best_prio:
                    best_url = url
                    best_artist = artist_name
                    best_prio = priority
        else:
            reader.skip(wire_type)
    return best_url, best_artist
