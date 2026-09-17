"""scripts/parquet_codec.py
─────────────────────────
Minimal Apache Parquet reader/writer used by bosun-spec fixtures and tests.

Implements uncompressed PLAIN-encoded files for INT32, INT64, FLOAT, DOUBLE,
BYTE_ARRAY, and BOOLEAN columns so telemetry samples can be generated and
inspected without pyarrow. Schema metadata (names, physical types, logical
annotations, REQUIRED vs OPTIONAL) is round-tripped through the FileMetaData
footer using Thrift Compact Protocol.

This is not a general-purpose Parquet library.
"""

from __future__ import annotations

import struct
from typing import Any, Dict, List, Optional, Tuple

PARQUET_MAGIC = b"PAR1"

# parquet.thrift Type
TYPE_BOOLEAN = 0
TYPE_INT32 = 1
TYPE_INT64 = 2
TYPE_INT96 = 3
TYPE_FLOAT = 4
TYPE_DOUBLE = 5
TYPE_BYTE_ARRAY = 6
TYPE_FIXED_LEN_BYTE_ARRAY = 7

PHYSICAL_TYPE_NAMES = {
    TYPE_BOOLEAN: "BOOLEAN",
    TYPE_INT32: "INT32",
    TYPE_INT64: "INT64",
    TYPE_INT96: "INT96",
    TYPE_FLOAT: "FLOAT",
    TYPE_DOUBLE: "DOUBLE",
    TYPE_BYTE_ARRAY: "BYTE_ARRAY",
    TYPE_FIXED_LEN_BYTE_ARRAY: "FIXED_LEN_BYTE_ARRAY",
}
PHYSICAL_TYPE_IDS = {name: code for code, name in PHYSICAL_TYPE_NAMES.items()}

# parquet.thrift ConvertedType
CONVERTED_UTF8 = 0
CONVERTED_DATE = 6
CONVERTED_TIME_MICROS = 8
CONVERTED_TIMESTAMP_MILLIS = 9
CONVERTED_TIMESTAMP_MICROS = 10
CONVERTED_DECIMAL = 5

CONVERTED_TYPE_NAMES = {
    CONVERTED_UTF8: "UTF8",
    CONVERTED_DECIMAL: "DECIMAL",
    CONVERTED_DATE: "DATE",
    CONVERTED_TIME_MICROS: "TIME_MICROS",
    CONVERTED_TIMESTAMP_MILLIS: "TIMESTAMP_MILLIS",
    CONVERTED_TIMESTAMP_MICROS: "TIMESTAMP_MICROS",
}
CONVERTED_TYPE_IDS = {name: code for code, name in CONVERTED_TYPE_NAMES.items()}

REP_REQUIRED = 0
REP_OPTIONAL = 1
REP_REPEATED = 2

# parquet.thrift Encoding / CompressionCodec / PageType
ENCODING_PLAIN = 0
ENCODING_RLE = 3
COMPRESSION_UNCOMPRESSED = 0
PAGE_TYPE_DATA_PAGE = 0

# Thrift Compact Protocol type nibble
T_STOP = 0
T_BOOLEAN_TRUE = 1
T_BOOLEAN_FALSE = 2
T_BYTE = 3
T_I16 = 4
T_I32 = 5
T_I64 = 6
T_DOUBLE = 7
T_BINARY = 8
T_LIST = 9
T_SET = 10
T_MAP = 11
T_STRUCT = 12


# ---------------------------------------------------------------------------
# Contract vocabulary mapping
# ---------------------------------------------------------------------------

_CONTRACT_TYPE_CANON = {
    "INT64": "INT64",
    "int64": "INT64",
    "INT32": "INT32",
    "int32": "INT32",
    "FLOAT": "FLOAT",
    "float32": "FLOAT",
    "DOUBLE": "DOUBLE",
    "float64": "DOUBLE",
    "double": "DOUBLE",
    "BYTE_ARRAY": "BYTE_ARRAY",
    "STRING": "STRING",
    "string": "STRING",
    "utf8": "STRING",
    "BOOLEAN": "BOOLEAN",
}

_LOGICAL_CANON = {
    "TIMESTAMP_MICROS": "TIMESTAMP_MICROS",
    "TIMESTAMP_MILLIS": "TIMESTAMP_MILLIS",
    "TIMESTAMP_NANOS": "TIMESTAMP_NANOS",
    "UTF8": "UTF8",
    "STRING": "UTF8",
    "DECIMAL": "DECIMAL",
    "DATE": "DATE",
    "TIME_MICROS": "TIME_MICROS",
    "NONE": "NONE",
    None: "NONE",
}


def canonicalize_contract_type(type_name: str) -> str:
    """Map a contract type token onto the canonical comparison vocabulary."""
    try:
        return _CONTRACT_TYPE_CANON[type_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported parquet contract type: {type_name!r}") from exc


def canonicalize_logical_type(logical_type: Optional[str]) -> str:
    """Map a contract or parquet logical annotation onto a comparison token."""
    try:
        return _LOGICAL_CANON[logical_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported parquet logical type: {logical_type!r}") from exc


def contract_type_to_physical(type_name: str) -> Tuple[int, Optional[int]]:
    """Return (parquet Type, ConvertedType or None) for a contract column type."""
    canon = canonicalize_contract_type(type_name)
    if canon == "STRING":
        return TYPE_BYTE_ARRAY, CONVERTED_UTF8
    if canon == "BYTE_ARRAY":
        return TYPE_BYTE_ARRAY, None
    return PHYSICAL_TYPE_IDS[canon], None


def physical_to_contract_type(physical: str, converted: Optional[str]) -> str:
    """Map parquet physical + converted types onto the contract type enum."""
    if physical == "BYTE_ARRAY" and canonicalize_logical_type(converted) == "UTF8":
        return "STRING"
    return physical


_RECORD_DEF_BY_REALM = {
    "pratique": "pratiqueRecord",
    "13-pratique": "pratiqueRecord",
    "squadron": "squadronRecord",
    "16-squadron": "squadronRecord",
    "the-glass": "theGlassRecord",
    "the_glass": "theGlassRecord",
    "30-the-glass": "theGlassRecord",
}


def fields_from_record_contract(contract: Dict[str, Any], realm: str) -> List[Dict[str, Any]]:
    """Derive expected columns from parquet-contracts.schema.json record $defs."""
    def_name = _RECORD_DEF_BY_REALM.get(realm)
    if not def_name:
        raise ValueError(
            f"Realm {realm!r} has no record contract in parquet-contracts.schema.json"
        )
    record = contract["$defs"][def_name]
    required = list(record.get("required") or [])
    fields: List[Dict[str, Any]] = []
    for name, prop in (record.get("properties") or {}).items():
        ref = str(prop.get("$ref") or "")
        if ref.endswith("/int64"):
            parquet_type = "INT64"
            logical = "TIMESTAMP_MICROS" if name == "timestamp_utc" else "NONE"
        elif ref.endswith("/float64"):
            parquet_type = "DOUBLE"
            logical = "NONE"
        elif prop.get("type") == "string":
            parquet_type = "STRING"
            logical = "UTF8"
        else:
            raise ValueError(f"Cannot map contract property {name!r} to a Parquet type: {prop}")
        fields.append(
            {
                "name": name,
                "type": parquet_type,
                "logical_type": logical,
                "nullable": name not in required,
            }
        )
    return fields


# ---------------------------------------------------------------------------
# Thrift Compact Protocol
# ---------------------------------------------------------------------------

class CompactWriter:
    """Subset of Thrift Compact Protocol used by Parquet footers and page headers."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._last_fid: List[int] = [0]

    def dumps(self) -> bytes:
        return bytes(self._buf)

    def write_struct_begin(self) -> None:
        self._last_fid.append(0)

    def write_struct_end(self) -> None:
        self._buf.append(T_STOP)
        self._last_fid.pop()

    def write_field_begin(self, field_id: int, compact_type: int) -> None:
        last = self._last_fid[-1]
        delta = field_id - last
        if 0 < delta <= 15:
            self._buf.append((delta << 4) | compact_type)
        else:
            self._buf.append(compact_type)
            self._write_i16(field_id)
        self._last_fid[-1] = field_id

    def write_i32_field(self, field_id: int, value: int) -> None:
        self.write_field_begin(field_id, T_I32)
        self._write_zigzag_varint(value)

    def write_i64_field(self, field_id: int, value: int) -> None:
        self.write_field_begin(field_id, T_I64)
        self._write_zigzag_varint(value)

    def write_string_field(self, field_id: int, value: str) -> None:
        encoded = value.encode("utf-8")
        self.write_field_begin(field_id, T_BINARY)
        self._write_varint(len(encoded))
        self._buf.extend(encoded)

    def write_list_begin_field(self, field_id: int, elem_type: int, size: int) -> None:
        self.write_field_begin(field_id, T_LIST)
        if size <= 14:
            self._buf.append((size << 4) | elem_type)
        else:
            self._buf.append(0xF0 | elem_type)
            self._write_varint(size)

    def write_struct_field_begin(self, field_id: int) -> None:
        self.write_field_begin(field_id, T_STRUCT)
        self.write_struct_begin()

    def _write_i16(self, value: int) -> None:
        self._write_zigzag_varint(value)

    def _write_zigzag_varint(self, value: int) -> None:
        self._write_varint((value << 1) ^ (value >> 63))

    def _write_varint(self, value: int) -> None:
        if value < 0:
            value &= (1 << 64) - 1
        while value > 0x7F:
            self._buf.append((value & 0x7F) | 0x80)
            value >>= 7
        self._buf.append(value)


class CompactReader:
    """Subset of Thrift Compact Protocol sufficient to extract FileMetaData.schema."""

    def __init__(self, data: bytes, offset: int = 0) -> None:
        self._data = data
        self._pos = offset
        self._last_fid: List[int] = [0]

    def read_struct_begin(self) -> None:
        self._last_fid.append(0)

    def read_field_header(self) -> Tuple[int, int]:
        header = self._read_byte()
        if header == T_STOP:
            return 0, T_STOP
        compact_type = header & 0x0F
        delta = (header & 0xF0) >> 4
        if delta == 0:
            field_id = self._read_zigzag_int()
        else:
            field_id = self._last_fid[-1] + delta
        self._last_fid[-1] = field_id
        return field_id, compact_type

    def skip_field(self, compact_type: int) -> None:
        if compact_type in (T_BOOLEAN_TRUE, T_BOOLEAN_FALSE, T_STOP):
            return
        if compact_type == T_BYTE:
            self._pos += 1
            return
        if compact_type in (T_I16, T_I32, T_I64):
            self._read_varint()
            return
        if compact_type == T_DOUBLE:
            self._pos += 8
            return
        if compact_type == T_BINARY:
            length = self._read_varint()
            self._pos += length
            return
        if compact_type in (T_LIST, T_SET):
            size, elem_type = self._read_list_header()
            for _ in range(size):
                self.skip_field(elem_type)
            return
        if compact_type == T_MAP:
            header = self._read_byte()
            key_type = (header & 0xF0) >> 4
            val_type = header & 0x0F
            size = 0 if header == 0 else self._read_varint()
            for _ in range(size):
                self.skip_field(key_type)
                self.skip_field(val_type)
            return
        if compact_type == T_STRUCT:
            self.read_struct_begin()
            while True:
                _fid, ctype = self.read_field_header()
                if ctype == T_STOP:
                    break
                self.skip_field(ctype)
            self._last_fid.pop()
            return
        raise ValueError(f"Cannot skip compact type {compact_type}")

    def read_i32(self) -> int:
        return self._read_zigzag_int()

    def read_i64(self) -> int:
        return self._read_zigzag_int()

    def read_string(self) -> str:
        length = self._read_varint()
        raw = self._data[self._pos : self._pos + length]
        self._pos += length
        return raw.decode("utf-8")

    def read_list_header(self) -> Tuple[int, int]:
        return self._read_list_header()

    def _read_list_header(self) -> Tuple[int, int]:
        header = self._read_byte()
        elem_type = header & 0x0F
        size = (header & 0xF0) >> 4
        if size == 15:
            size = self._read_varint()
        return size, elem_type

    def _read_byte(self) -> int:
        value = self._data[self._pos]
        self._pos += 1
        return value

    def _read_varint(self) -> int:
        shift = 0
        result = 0
        while True:
            byte = self._read_byte()
            result |= (byte & 0x7F) << shift
            if byte & 0x80 == 0:
                return result
            shift += 7

    def _read_zigzag_int(self) -> int:
        encoded = self._read_varint()
        return (encoded >> 1) ^ -(encoded & 1)


# ---------------------------------------------------------------------------
# Schema encode / decode
# ---------------------------------------------------------------------------

def _write_schema_element(writer: CompactWriter, element: Dict[str, Any]) -> None:
    writer.write_struct_begin()
    if "type" in element and element["type"] is not None:
        writer.write_i32_field(1, int(element["type"]))
    if "type_length" in element:
        writer.write_i32_field(2, int(element["type_length"]))
    if "repetition_type" in element and element["repetition_type"] is not None:
        writer.write_i32_field(3, int(element["repetition_type"]))
    writer.write_string_field(4, str(element["name"]))
    if "num_children" in element and element["num_children"] is not None:
        writer.write_i32_field(5, int(element["num_children"]))
    if "converted_type" in element and element["converted_type"] is not None:
        writer.write_i32_field(6, int(element["converted_type"]))
    writer.write_struct_end()


def _read_schema_element(reader: CompactReader) -> Dict[str, Any]:
    reader.read_struct_begin()
    element: Dict[str, Any] = {}
    while True:
        field_id, compact_type = reader.read_field_header()
        if compact_type == T_STOP:
            break
        if field_id == 1 and compact_type == T_I32:
            element["type"] = reader.read_i32()
        elif field_id == 2 and compact_type == T_I32:
            element["type_length"] = reader.read_i32()
        elif field_id == 3 and compact_type == T_I32:
            element["repetition_type"] = reader.read_i32()
        elif field_id == 4 and compact_type == T_BINARY:
            element["name"] = reader.read_string()
        elif field_id == 5 and compact_type == T_I32:
            element["num_children"] = reader.read_i32()
        elif field_id == 6 and compact_type == T_I32:
            element["converted_type"] = reader.read_i32()
        else:
            reader.skip_field(compact_type)
    reader._last_fid.pop()
    return element


def _schema_elements_from_columns(columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    elements: List[Dict[str, Any]] = [
        {"name": "schema", "num_children": len(columns), "repetition_type": REP_REQUIRED}
    ]
    for column in columns:
        physical, converted_from_type = contract_type_to_physical(column["type"])
        logical = canonicalize_logical_type(column.get("logical_type"))
        converted = converted_from_type
        if logical == "UTF8":
            converted = CONVERTED_UTF8
        elif logical == "NONE":
            converted = converted_from_type
        elif logical in CONVERTED_TYPE_IDS:
            converted = CONVERTED_TYPE_IDS[logical]
        nullable = bool(column.get("nullable", False))
        elements.append(
            {
                "type": physical,
                "repetition_type": REP_OPTIONAL if nullable else REP_REQUIRED,
                "name": column["name"],
                "converted_type": converted,
            }
        )
    return elements


def _write_page_header(num_values: int, page_size: int) -> bytes:
    writer = CompactWriter()
    writer.write_struct_begin()
    writer.write_i32_field(1, PAGE_TYPE_DATA_PAGE)
    writer.write_i32_field(2, page_size)
    writer.write_i32_field(3, page_size)
    writer.write_struct_field_begin(5)
    writer.write_i32_field(1, num_values)
    writer.write_i32_field(2, ENCODING_PLAIN)
    writer.write_i32_field(3, ENCODING_RLE)
    writer.write_i32_field(4, ENCODING_RLE)
    writer.write_struct_end()
    writer.write_struct_end()
    return writer.dumps()


def _encode_plain_values(physical: int, values: List[Any]) -> bytes:
    if physical == TYPE_BOOLEAN:
        packed = bytearray()
        byte = 0
        bit = 0
        for value in values:
            if value:
                byte |= 1 << bit
            bit += 1
            if bit == 8:
                packed.append(byte)
                byte = 0
                bit = 0
        if bit:
            packed.append(byte)
        return bytes(packed)
    if physical == TYPE_INT32:
        return b"".join(struct.pack("<i", int(v)) for v in values)
    if physical == TYPE_INT64:
        return b"".join(struct.pack("<q", int(v)) for v in values)
    if physical == TYPE_FLOAT:
        return b"".join(struct.pack("<f", float(v)) for v in values)
    if physical == TYPE_DOUBLE:
        return b"".join(struct.pack("<d", float(v)) for v in values)
    if physical == TYPE_BYTE_ARRAY:
        chunks = []
        for value in values:
            encoded = value if isinstance(value, bytes) else str(value).encode("utf-8")
            chunks.append(struct.pack("<I", len(encoded)) + encoded)
        return b"".join(chunks)
    raise ValueError(f"Unsupported physical type for PLAIN encoding: {physical}")


def _write_file_metadata(
    schema_elements: List[Dict[str, Any]],
    row_count: int,
    column_chunks: List[Dict[str, Any]],
) -> bytes:
    writer = CompactWriter()
    writer.write_struct_begin()
    writer.write_i32_field(1, 1)
    writer.write_list_begin_field(2, T_STRUCT, len(schema_elements))
    for element in schema_elements:
        _write_schema_element(writer, element)

    writer.write_i64_field(3, row_count)
    writer.write_list_begin_field(4, T_STRUCT, 1)
    # RowGroup
    writer.write_struct_begin()
    writer.write_list_begin_field(1, T_STRUCT, len(column_chunks))
    total_bytes = 0
    for chunk in column_chunks:
        total_bytes += chunk["total_uncompressed_size"]
        writer.write_struct_begin()
        writer.write_i64_field(2, chunk["file_offset"])
        writer.write_struct_field_begin(3)
        writer.write_i32_field(1, chunk["type"])
        writer.write_list_begin_field(2, T_I32, 1)
        writer._write_zigzag_varint(ENCODING_PLAIN)
        writer.write_list_begin_field(3, T_BINARY, 1)
        encoded_path = chunk["name"].encode("utf-8")
        writer._write_varint(len(encoded_path))
        writer._buf.extend(encoded_path)
        writer.write_i32_field(4, COMPRESSION_UNCOMPRESSED)
        writer.write_i64_field(5, row_count)
        writer.write_i64_field(6, chunk["total_uncompressed_size"])
        writer.write_i64_field(7, chunk["total_compressed_size"])
        writer.write_i64_field(9, chunk["data_page_offset"])
        writer.write_struct_end()
        writer.write_struct_end()
    writer.write_i64_field(2, total_bytes)
    writer.write_i64_field(3, row_count)
    writer.write_struct_end()
    writer.write_string_field(6, "bosun-spec parquet_codec 1.0.0")
    writer.write_struct_end()
    return writer.dumps()


def write_parquet_table(path: Any, columns: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> None:
    """Write a single-row-group uncompressed Parquet file for ``columns`` / ``rows``."""
    from pathlib import Path

    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    schema_elements = _schema_elements_from_columns(columns)
    body = bytearray(PARQUET_MAGIC)
    column_chunks: List[Dict[str, Any]] = []
    for column in columns:
        physical, _converted = contract_type_to_physical(column["type"])
        logical = canonicalize_logical_type(column.get("logical_type"))
        if logical in CONVERTED_TYPE_IDS and logical != "NONE":
            # logical annotation does not change PLAIN physical layout
            pass
        values = [row[column["name"]] for row in rows]
        page_data = _encode_plain_values(physical, values)
        header = _write_page_header(len(rows), len(page_data))
        file_offset = len(body)
        body.extend(header)
        body.extend(page_data)
        total_size = len(header) + len(page_data)
        column_chunks.append(
            {
                "name": column["name"],
                "type": physical,
                "file_offset": file_offset,
                "data_page_offset": file_offset,
                "total_uncompressed_size": total_size,
                "total_compressed_size": total_size,
            }
        )
    metadata = _write_file_metadata(schema_elements, len(rows), column_chunks)
    with dest.open("wb") as fh:
        fh.write(body)
        fh.write(metadata)
        fh.write(struct.pack("<I", len(metadata)))
        fh.write(PARQUET_MAGIC)


def read_parquet_schema(path: Any) -> List[Dict[str, Any]]:
    """Read columnar schema metadata from a Parquet footer.

    Returns a list of contract-shaped field dicts: name, type, logical_type, nullable.
    """
    from pathlib import Path

    dest = Path(path)
    data = dest.read_bytes()
    if len(data) < 12 or data[:4] != PARQUET_MAGIC or data[-4:] != PARQUET_MAGIC:
        raise ValueError(f"{dest} is not a Parquet file (missing PAR1 magic)")
    metadata_length = struct.unpack("<I", data[-8:-4])[0]
    metadata_start = len(data) - 8 - metadata_length
    if metadata_start < 4 or metadata_length <= 0:
        raise ValueError(f"{dest} has an invalid Parquet footer length {metadata_length}")
    reader = CompactReader(data[metadata_start : metadata_start + metadata_length])
    reader.read_struct_begin()
    schema_elements: List[Dict[str, Any]] = []
    while True:
        field_id, compact_type = reader.read_field_header()
        if compact_type == T_STOP:
            break
        if field_id == 2 and compact_type == T_LIST:
            size, elem_type = reader.read_list_header()
            if elem_type != T_STRUCT:
                raise ValueError(f"{dest}: FileMetaData.schema is not a list of structs")
            schema_elements = [_read_schema_element(reader) for _ in range(size)]
        else:
            reader.skip_field(compact_type)

    if not schema_elements:
        raise ValueError(f"{dest}: Parquet FileMetaData is missing a schema")

    fields: List[Dict[str, Any]] = []
    for element in schema_elements[1:]:
        if element.get("num_children"):
            continue
        physical_id = element.get("type")
        if physical_id is None:
            continue
        physical_name = PHYSICAL_TYPE_NAMES[physical_id]
        converted_id = element.get("converted_type")
        converted_name = CONVERTED_TYPE_NAMES.get(converted_id)
        repetition = element.get("repetition_type", REP_OPTIONAL)
        fields.append(
            {
                "name": element["name"],
                "type": physical_to_contract_type(physical_name, converted_name),
                "logical_type": canonicalize_logical_type(converted_name),
                "nullable": repetition != REP_REQUIRED,
            }
        )
    return fields
