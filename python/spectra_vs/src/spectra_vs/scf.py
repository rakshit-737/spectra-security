"""SCF-lite: the one JSON serialiser every slice artifact is written through.

The global encoding law in the operative specification's `data_contracts` section is not
a style preference. Two runs of the pipeline must produce byte-identical files, and a
serialiser that sorts keys sometimes, emits a float occasionally, or writes `null` for an
absent member is the single cheapest way to lose that property. Routing every artifact
through one function makes the law checkable in one place instead of at every call site.

FOUR THINGS ARE REJECTED RATHER THAN COERCED.

`float` in any position, because the specification's E-CANON-FLOAT exists precisely so
that a rounded value can never reach a hash preimage. There is no float anywhere in the
slice and there is no path that would produce one silently.

`None` in a value position, because optionality on the wire is member absence. A `null`
would make "the generator had no value" and "the generator had the value null" the same
bytes, and a later stage could not tell them apart.

An object key outside `[a-z0-9_]+`, because the key set is the wire contract and an
accidental camelCase or hyphenated key would be a new contract member nobody declared.

A bare JSON integer outside the unsigned 32-bit range, because the contract permits JSON
integers only where the field table says u8/u16/u32. Everything wider - i64 nanoseconds,
u64 masks and seeds - is a string, and this guard is what turns "I forgot to stringify a
timestamp" into an error at the serialiser rather than a silently narrowed value in an
archived certificate.

WHAT THIS MODULE DOES NOT DO. It does not hash. Hashing goes through `spectra_core.canon`,
which owns the domain-separated digest and the algorithm substitution note.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

from spectra_core import canon
from spectra_core.errors import CanonError, SchemaError

__all__ = [
    "U32_MAX",
    "file_hash_ref",
    "hash_ref_of",
    "render_jsonl",
    "scf_bytes",
    "scf_dumps",
    "scf_line",
    "validate_scf",
    "write_bytes",
    "write_jsonl",
    "write_scf",
]

#: The widest value the contract permits as a bare JSON integer.
U32_MAX: Final[int] = (1 << 32) - 1

_KEY: Final = re.compile(r"\A[a-z0-9_]+\Z")


def validate_scf(value: object, *, where: str = "scf") -> None:
    """Walk `value` and raise on anything the encoding law forbids.

    Called before every serialisation rather than trusting the caller, because the cost of
    the walk is nothing next to the cost of discovering a float inside an archived
    artifact whose hash is already quoted in a certificate.
    """
    if value is None:
        raise SchemaError(f"{where}: null is never a value; express absence by omitting the member")
    if isinstance(value, bool):
        return
    if isinstance(value, float) or isinstance(value, complex):
        raise CanonError(f"{where}: float in a number position", code="E-CANON-FLOAT")
    if isinstance(value, int):
        if not 0 <= value <= U32_MAX:
            raise SchemaError(
                f"{where}: {value} is not a bare JSON integer position; i64 nanoseconds, "
                "u64 masks and u64 seeds are strings",
                code="E-CANON-WIDTH",
            )
        return
    if isinstance(value, str):
        return
    if isinstance(value, dict):
        for key, member in value.items():
            if not isinstance(key, str) or _KEY.match(key) is None:
                raise SchemaError(f"{where}: object key {key!r} is not ASCII [a-z0-9_]+")
            validate_scf(member, where=f"{where}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, member in enumerate(value):
            validate_scf(member, where=f"{where}[{index}]")
        return
    raise SchemaError(f"{where}: {type(value).__name__} has no SCF-lite encoding")


def scf_dumps(value: Any, *, where: str = "scf") -> str:
    """The canonical text of one object. Keys sorted by byte value, no insignificant space."""
    validate_scf(value, where=where)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def scf_line(value: Any, *, where: str = "scf") -> str:
    """One JSONL line: the canonical text and exactly one LF."""
    return scf_dumps(value, where=where) + "\n"


def scf_bytes(value: Any, *, where: str = "scf") -> bytes:
    """The canonical UTF-8 octets of a whole-file object, with exactly one trailing LF."""
    return scf_line(value, where=where).encode("utf-8")


def render_jsonl(values: object, *, where: str = "scf") -> bytes:
    """The canonical octets of a JSONL file: one line per element, in the order given.

    Order is the caller's responsibility and is never sorted here, so that an emitter that
    produced its records in hash-map order goes red against its own ordering test instead
    of being tidied up on the way out.
    """
    parts: list[str] = []
    for index, value in enumerate(values):  # type: ignore[union-attr]
        parts.append(scf_line(value, where=f"{where}[{index}]"))
    return "".join(parts).encode("utf-8")


def hash_ref_of(kind: str, payload: bytes) -> str:
    """A `"b2b256:<64hex>"` reference over exact file octets, domain-separated by `kind`."""
    return canon.hash_ref(kind, payload)


def write_bytes(path: Path, payload: bytes) -> Path:
    """Write exact octets with no BOM and no newline translation.

    Binary mode on purpose: text mode on Windows would translate LF to CRLF and a CR byte
    is a hard encoding-law violation that would change every downstream hash.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(payload)
    return path


def write_scf(path: Path, value: Any, *, where: str = "scf") -> bytes:
    """Serialise one whole-file object and write it. Returns the octets that were written."""
    payload = scf_bytes(value, where=where)
    write_bytes(path, payload)
    return payload


def write_jsonl(path: Path, values: object, *, where: str = "scf") -> bytes:
    """Serialise a sequence as JSONL and write it. Returns the octets that were written."""
    payload = render_jsonl(values, where=where)
    write_bytes(path, payload)
    return payload


def file_hash_ref(kind: str, path: Path) -> str:
    """Hash a file's exact octets, which is what every `*_hash` member in the slice covers."""
    return canon.hash_ref(kind, path.read_bytes())
