"""Canonical byte encoding, domain-separated hashing, and the ordering helpers.

THE DIGEST SUBSTITUTION, STATED LOUDLY.

The specification names BLAKE3 everywhere it names a digest: section 57.3 defines
`DIGEST(kind, payload) = BLAKE3-256("spectra/v1/" || kind || 0x1F || payload)`, and the
slice's encoding law renders hash strings as `"blake3:<64 hex>"` and says a run must
abort rather than substitute another digest silently.

THIS REFERENCE IMPLEMENTATION DOES NOT HAVE BLAKE3. The environment is Python 3.14 with
the standard library only: no pip, no network, no third-party packages. `hashlib` offers
no BLAKE3 and there is no way to add one. The substitution made here is
`hashlib.blake2b(digest_size=32)`, and it is declared rather than hidden:

  * `HASH_ALGORITHM` names what is actually computed, `"blake2b-256"`.
  * `SPEC_HASH_ALGORITHM` names what the specification asks for, `"blake3"`.
  * `HASH_REF_PREFIX` is `"b2b256:"`, NOT `"blake3:"`. Nothing in this package ever
    writes a blake2b digest behind a blake3 label. A verifier reading `b2b256:` knows
    exactly what it is looking at and knows it is not the specified artifact.
  * `HASH_ALGORITHM` is carried into every certificate: `model.Certificate` requires it
    as a member and rejects a certificate built with any other value.

What this costs, honestly: no digest produced here is comparable with a digest produced
by a BLAKE3 implementation, so no fixture, golden hash or certificate from this package
is the artifact the specification describes. Swapping the algorithm back is a one-line
change to `_raw_digest` plus a constant, and every digest in the repository changes
value, which is the intended consequence of the digest name being part of what the scope
commits to.

ENCODING LAW IMPLEMENTED HERE (section 57.3 rules 3 and 4, and the slice's global
encoding law): fixed field order; unsigned integers big-endian at a fixed width;
sequences length-prefixed; set-valued sequences sorted bytewise before hashing; no
floats in any position; no JSON in any hash preimage; text normalised to NFC before it
is encoded. No wall clock is read anywhere in this module.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from typing import Final

from spectra_core.errors import CanonError, DeterminismError, LimitError

__all__ = [
    "DOMAIN_PREFIX",
    "HASH_ALGORITHM",
    "HASH_REF_PREFIX",
    "HASH_SUBSTITUTION_NOTE",
    "SPEC_HASH_ALGORITHM",
    "UNIT_SEPARATOR",
    "ascii_text",
    "blob",
    "boolean",
    "byte_order_key",
    "check_strictly_ascending",
    "digest",
    "digest_hex",
    "hash_ref",
    "i64",
    "leb128",
    "leb128_seq",
    "mask_hex",
    "nfc",
    "ordered_seq",
    "pairs",
    "parse_hash_ref",
    "reject_float",
    "sorted_by_bytes",
    "sorted_set",
    "sorted_unique",
    "u16",
    "u32",
    "u64",
    "u8",
    "utf8_text",
]


# ---------------------------------------------------------------------------
# Algorithm declaration
# ---------------------------------------------------------------------------

#: The digest actually computed by this reference implementation.
HASH_ALGORITHM: Final[str] = "blake2b-256"

#: The digest the specification names. Not available here; see the module docstring.
SPEC_HASH_ALGORITHM: Final[str] = "blake3"

#: The wire prefix for a hash reference. Deliberately not `"blake3:"`.
HASH_REF_PREFIX: Final[str] = "b2b256:"

#: One sentence that travels with the substitution wherever it is reported.
HASH_SUBSTITUTION_NOTE: Final[str] = (
    "The specification names blake3. This Python reference implementation computes "
    "blake2b-256 because the standard library has no blake3 and no package may be "
    "installed. Digests here are not comparable with specified digests."
)

#: Section 57.3 rule 1. `0x1F` is the ASCII unit separator and never appears in `kind`.
DOMAIN_PREFIX: Final[bytes] = b"spectra/v1/"
UNIT_SEPARATOR: Final[int] = 0x1F

_DIGEST_OCTETS: Final[int] = 32
_MAX_SEQ: Final[int] = 0xFFFFFFFF


def _raw_digest(data: bytes) -> bytes:
    """The single place the digest algorithm is chosen.

    Swapping blake2b for blake3 is this function plus the four constants above. Keeping
    it to one function is what makes the substitution auditable rather than scattered.
    """
    return hashlib.blake2b(data, digest_size=_DIGEST_OCTETS).digest()


def digest(kind: str, payload: bytes) -> bytes:
    """`DIGEST(kind, payload)` of section 57.3 rule 1, with the declared substitution.

    Domain separation by `kind` is not decoration: without it a fact payload and a rule
    instance payload that happened to encode to the same bytes would collide across
    concepts, and a collision across concepts is a forged identity rather than a clash.
    """
    if not isinstance(kind, str) or not kind:
        raise CanonError("digest: kind must be a non-empty ASCII string")
    try:
        kind_bytes = kind.encode("ascii")
    except UnicodeEncodeError:
        raise CanonError(f"digest: kind must be ASCII, got {kind!r}") from None
    if UNIT_SEPARATOR in kind_bytes:
        raise CanonError("digest: the unit separator may never appear inside kind")
    if not isinstance(payload, (bytes, bytearray)):
        raise CanonError(f"digest: payload must be bytes, got {type(payload).__name__}")
    return _raw_digest(DOMAIN_PREFIX + kind_bytes + bytes([UNIT_SEPARATOR]) + bytes(payload))


def digest_hex(kind: str, payload: bytes, octets: int = _DIGEST_OCTETS) -> str:
    """Lowercase hex of `digest`, truncated to the first `octets` bytes.

    Section 57.3 rule 2: truncation is a prefix, never a fold and never an XOR, so an
    h128 id is literally the opening half of the h256 digest of the same payload.
    """
    if octets not in (16, _DIGEST_OCTETS):
        raise CanonError(f"digest_hex: octets must be 16 or {_DIGEST_OCTETS}, got {octets}")
    return digest(kind, payload)[:octets].hex()


def hash_ref(kind: str, payload: bytes) -> str:
    """A full-width hash reference string, `"b2b256:<64 lowercase hex>"`."""
    return HASH_REF_PREFIX + digest_hex(kind, payload, _DIGEST_OCTETS)


def parse_hash_ref(value: str) -> bytes:
    """Return the 32 raw octets of a hash reference, rejecting any other algorithm label.

    A `"blake3:"` string reaching this function is an error rather than a fallback: this
    implementation cannot produce or check one, and accepting it would let an artifact
    claim a digest nothing here computed.
    """
    if not isinstance(value, str):
        raise CanonError(f"parse_hash_ref: expected str, got {type(value).__name__}")
    if not value.startswith(HASH_REF_PREFIX):
        raise CanonError(
            f"parse_hash_ref: expected the {HASH_REF_PREFIX!r} prefix of {HASH_ALGORITHM}, "
            f"got {value!r}"
        )
    body = value[len(HASH_REF_PREFIX) :]
    if len(body) != _DIGEST_OCTETS * 2 or any(c not in "0123456789abcdef" for c in body):
        raise CanonError(f"parse_hash_ref: body is not 64 lowercase hex digits: {value!r}")
    return bytes.fromhex(body)


# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------


def reject_float(value: object, *, where: str) -> None:
    """Raise if `value` is a float or a complex. Called from every integer encoder.

    Floats are banned outright rather than rounded, because a rounded float is a value
    whose bytes depend on a platform's formatting and on the order of the arithmetic that
    produced it, and both of those break byte-identical replay.
    """
    if isinstance(value, (float, complex)):
        raise CanonError(f"{where}: floats are forbidden, got {value!r}", code="E-CANON-FLOAT")


def _uint(value: int, width: int, *, where: str) -> bytes:
    reject_float(value, where=where)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CanonError(f"{where}: expected int, got {type(value).__name__}")
    if not 0 <= value < (1 << (width * 8)):
        raise CanonError(
            f"{where}: {value} does not fit an unsigned {width * 8}-bit field",
            code="E-CANON-WIDTH",
        )
    return value.to_bytes(width, "big", signed=False)


def u8(value: int) -> bytes:
    """One octet, big-endian."""
    return _uint(value, 1, where="u8")


def u16(value: int) -> bytes:
    """Two octets, big-endian."""
    return _uint(value, 2, where="u16")


def u32(value: int) -> bytes:
    """Four octets, big-endian."""
    return _uint(value, 4, where="u32")


def u64(value: int) -> bytes:
    """Eight octets, big-endian. Bytewise order of the encoding is numeric order."""
    return _uint(value, 8, where="u64")


def i64(value: int) -> bytes:
    """Eight octets, big-endian, two's complement.

    Used only for nanosecond instants, which may in principle precede the Unix epoch.
    Bytewise order of this encoding is NOT numeric order across the sign boundary, so it
    is never used as a sort key; sort on the integer, then encode.
    """
    reject_float(value, where="i64")
    if isinstance(value, bool) or not isinstance(value, int):
        raise CanonError(f"i64: expected int, got {type(value).__name__}")
    if not -(1 << 63) <= value < (1 << 63):
        raise CanonError(f"i64: {value} does not fit a signed 64-bit field", code="E-CANON-WIDTH")
    return value.to_bytes(8, "big", signed=True)


def boolean(value: bool) -> bytes:
    """One octet, `0x00` or `0x01`. Rejects truthy non-bools so `1` cannot pass for True."""
    if not isinstance(value, bool):
        raise CanonError(f"boolean: expected bool, got {type(value).__name__}")
    return b"\x01" if value else b"\x00"


def leb128(value: int) -> bytes:
    """Unsigned LEB128, no padding, minimal length.

    The CAE encoding, the corridor digest and the gap digest all specify LEB128. A
    non-minimal encoding would give two byte strings for one number, so the loop below
    stops as soon as the remainder is zero and never emits a trailing `0x80`.
    """
    reject_float(value, where="leb128")
    if isinstance(value, bool) or not isinstance(value, int):
        raise CanonError(f"leb128: expected int, got {type(value).__name__}")
    if value < 0:
        raise CanonError(f"leb128: unsigned only, got {value}")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def nfc(value: str) -> str:
    """Normalise to NFC and reject control characters.

    Two visually identical strings in different normal forms hash differently, so
    normalisation happens once, here, rather than at each call site where it would be
    forgotten in one of them.
    """
    if not isinstance(value, str):
        raise CanonError(f"nfc: expected str, got {type(value).__name__}")
    normalised = unicodedata.normalize("NFC", value)
    for ch in normalised:
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            raise CanonError(
                f"nfc: control character U+{ord(ch):04X} in {value!r}", code="E-CANON-NFC"
            )
    return normalised


def ascii_text(value: str) -> bytes:
    """`u32` length prefix then the US-ASCII octets. For identifiers and enum tokens."""
    if not isinstance(value, str):
        raise CanonError(f"ascii_text: expected str, got {type(value).__name__}")
    try:
        raw = value.encode("ascii")
    except UnicodeEncodeError:
        raise CanonError(f"ascii_text: value is not US-ASCII: {value!r}") from None
    return blob(raw)


def utf8_text(value: str) -> bytes:
    """`u32` length prefix then the NFC UTF-8 octets. For free text such as a reason."""
    return blob(nfc(value).encode("utf-8"))


def blob(value: bytes) -> bytes:
    """`u32` octet-count prefix then the octets themselves.

    Length-prefixing rather than delimiting is what stops two adjacent fields from being
    re-cut at a different boundary and producing a second preimage for the same bytes.
    """
    if not isinstance(value, (bytes, bytearray)):
        raise CanonError(f"blob: expected bytes, got {type(value).__name__}")
    if len(value) > _MAX_SEQ:
        raise LimitError(f"blob: {len(value)} octets exceeds the u32 length prefix")
    return u32(len(value)) + bytes(value)


def mask_hex(value: int) -> str:
    """Render a 64-bit blocker mask as `"0x%016x"`.

    A mask is rendered, never compared: the numeric value of a mask is never a tie-break
    and never enters a sort key that feeds an output path.
    """
    reject_float(value, where="mask_hex")
    if isinstance(value, bool) or not isinstance(value, int):
        raise CanonError(f"mask_hex: expected int, got {type(value).__name__}")
    if not 0 <= value < (1 << 64):
        raise CanonError(f"mask_hex: {value} does not fit 64 bits", code="E-CANON-WIDTH")
    return f"0x{value:016x}"


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------


def ordered_seq(items: Iterable[bytes]) -> bytes:
    """`u32` count then each element's canonical bytes, in the order given.

    Use where the declared order IS the content: a rule's body in its declared order, a
    cut's literals in rank order, a witness node's children.
    """
    materialised = [_as_bytes(item, where="ordered_seq") for item in items]
    if len(materialised) > _MAX_SEQ:
        raise LimitError(f"ordered_seq: {len(materialised)} elements exceeds the u32 count")
    return u32(len(materialised)) + b"".join(materialised)


def sorted_set(items: Iterable[bytes]) -> bytes:
    """`u32` count then each element sorted bytewise ascending, duplicates rejected.

    Section 57.3 rule 4. Use where the collection is a set: the sources of a rule, the
    licence ids of a silent instance, the entity ids of a fact's arguments when the
    predicate is symmetric. Rejecting duplicates rather than collapsing them keeps a
    caller's double-add visible instead of silently canonicalised away.
    """
    materialised = sorted(_as_bytes(item, where="sorted_set") for item in items)
    for left, right in zip(materialised, materialised[1:]):
        if left == right:
            raise CanonError("sorted_set: duplicate element", code="E-CANON-DUPKEY")
    if len(materialised) > _MAX_SEQ:
        raise LimitError(f"sorted_set: {len(materialised)} elements exceeds the u32 count")
    return u32(len(materialised)) + b"".join(materialised)


def pairs(items: Iterable[tuple[str, str]]) -> bytes:
    """A string map encoded as a bytewise-sorted sequence of key/value pairs.

    There is no JSON object in any hash preimage, so a map is a sorted sequence and the
    sort is on the encoded key bytes. Duplicate keys are an error, not a last-write-wins.
    """
    encoded: list[tuple[bytes, bytes]] = []
    for key, value in items:
        encoded.append((ascii_text(key) if key.isascii() else utf8_text(key), utf8_text(value)))
    encoded.sort(key=lambda kv: kv[0])
    for left, right in zip(encoded, encoded[1:]):
        if left[0] == right[0]:
            raise CanonError("pairs: duplicate key", code="E-CANON-DUPKEY")
    return u32(len(encoded)) + b"".join(k + v for k, v in encoded)


def leb128_seq(values: Sequence[int]) -> bytes:
    """`LEB128(len)` then `LEB128(v)` for each value, in the order given.

    This is the corridor-id and gap-digest preimage shape. It is order-preserving: the
    caller sorts first where the contract says the vector is ascending.
    """
    return leb128(len(values)) + b"".join(leb128(v) for v in values)


def _as_bytes(item: object, *, where: str) -> bytes:
    if not isinstance(item, (bytes, bytearray)):
        raise CanonError(f"{where}: elements must already be canonical bytes, got {type(item).__name__}")
    return bytes(item)


# ---------------------------------------------------------------------------
# Ordering helpers: the determinism surface other modules must use
# ---------------------------------------------------------------------------


def byte_order_key(value: str) -> bytes:
    """The one permitted sort key for a string.

    Python's default string comparison is by code point, which agrees with UTF-8 bytewise
    order for every string; using this key anyway states the intent at the call site, so
    a later edit cannot quietly introduce a locale-aware or case-folded comparison.
    """
    if not isinstance(value, str):
        raise DeterminismError(f"byte_order_key: expected str, got {type(value).__name__}")
    return nfc(value).encode("utf-8")


def sorted_by_bytes[T](items: Iterable[T], key: Callable[[T], str]) -> list[T]:
    """Sort by the UTF-8 bytes of `key`, ascending. Never by locale collation."""
    return sorted(items, key=lambda item: byte_order_key(key(item)))


def sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    """Sort bytewise ascending and reject duplicates.

    Every array the data contracts declare sorted is STRICTLY ascending, so a duplicate
    is a contract violation rather than something to deduplicate on the way out.
    """
    ordered = sorted(values, key=byte_order_key)
    for left, right in zip(ordered, ordered[1:]):
        if left == right:
            raise CanonError(f"sorted_unique: duplicate value {left!r}", code="E-CANON-DUPKEY")
    return tuple(ordered)


def check_strictly_ascending[T](
    items: Sequence[T], key: Callable[[T], object], *, where: str
) -> Sequence[T]:
    """Verify in one scan that `items` is strictly ascending under `key`, and return it.

    It verifies rather than sorts on purpose. Sorting here would mask an emitter that
    produced its output in hash-map order, which is the determinism defect this whole
    layer exists to prevent; the checker never sorts either, for the same reason.
    """
    previous: object = None
    for index, item in enumerate(items):
        current = key(item)
        if index and not previous < current:  # type: ignore[operator]
            raise CanonError(
                f"{where}: element {index} is not strictly greater than its predecessor",
                code="E-CANON-ORDER",
            )
        previous = current
    return items
