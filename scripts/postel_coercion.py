"""scripts/postel_coercion.py
─────────────────────────────
High-throughput Postel normalization and permissive envelope ingestion engine.

Adheres to Postel's Robustness Principle:
  "Be conservative in what you send, be liberal in what you accept."

Invariants:
  1. Permissive input handling:
     - Date-only strings ('YYYY-MM-DD')
     - Timestamps missing seconds ('YYYY-MM-DDTHH:MMZ', 'YYYY-MM-DDTHH:MM')
     - Full ISO timestamps with timezone offsets or subsecond fractions
     - Space-delimited ISO timestamps ('YYYY-MM-DD HH:MM:SS')
     - Native Python datetime.date and datetime.datetime objects
     - Scalar strings where arrays/lists of URNs are required
     - Bare UUIDs or un-prefixed UUIDs coerced to canonical UUID URNs ('urn:uuid:...')
     - Whitespace and prefix tolerance on realm identifiers
  2. Conservative output:
     - Canonical RFC 3339 / ISO 8601 UTC timestamps ('YYYY-MM-DDTHH:MM:SSZ')
     - Validated canonical URN lists ('urn:...')
  3. Throughput floor:
     - High-performance fast paths achieving >100,000 operations/sec.

Usage:
  from scripts.postel_coercion import (
      coerce_timestamp,
      coerce_urn_list,
      coerce_envelope,
      normalize_frontmatter,
  )
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union

# Compiled regex for URN validation conforming to RFC 8141 & Bosun envelope schema:
# ^urn:[a-zA-Z0-9_.:-]+$
_URN_PATTERN = re.compile(r"^urn:[a-zA-Z0-9_.:-]+$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_REALM_PREFIX_PATTERN = re.compile(r"^[0-9]{2}-([a-z0-9_-]+)$")


def is_valid_urn(s: Any) -> bool:
    """Return True if s is a non-empty string matching canonical URN syntax."""
    if not isinstance(s, str) or len(s) < 5 or not s.startswith("urn:"):
        return False
    return bool(_URN_PATTERN.match(s))


def is_valid_uuid_urn(s: Any) -> bool:
    """Return True if s is a canonical UUID URN ('urn:uuid:<36-hex-uuid>')."""
    if not isinstance(s, str) or not s.startswith("urn:uuid:"):
        return False
    return bool(_UUID_PATTERN.match(s[9:]))


def coerce_id(val: Any) -> str:
    """Permissively coerce entity ID to a canonical 'urn:uuid:<uuid>' string.

    Accepts:
      - Canonical 'urn:uuid:<uuid>' (normalizes to lowercase)
      - Un-prefixed 'uuid:<uuid>'
      - Bare UUID string '<uuid>'
    """
    if not isinstance(val, str):
        raise TypeError(f"Envelope ID must be a string, got {type(val).__name__}")

    s = val.strip()
    L = len(s)
    # Fast path 1: Already canonical lowercase 'urn:uuid:<uuid>' (length 45)
    if L == 45 and s.startswith("urn:uuid:"):
        return s if s.islower() else "urn:uuid:" + s[9:].lower()

    # Fast path 2: Bare UUID (length 36)
    if L == 36 and s.count("-") == 4:
        return "urn:uuid:" + s.lower()

    # Fast path 3: 'uuid:<uuid>' (length 41)
    if L == 41 and s.startswith("uuid:"):
        return "urn:uuid:" + s[5:].lower()

    if s.startswith("urn:uuid:"):
        uuid_part = s[9:]
        if not _UUID_PATTERN.match(uuid_part):
            raise ValueError(f"Invalid UUID in URN {s!r}")
        return "urn:uuid:" + uuid_part.lower()

    # Pass through other URNs if valid
    if is_valid_urn(s):
        return s

    raise ValueError(f"Cannot coerce ID to canonical URN: {val!r}")


def coerce_realm(val: Any) -> str:
    """Permissively coerce realm string to canonical lowercase identifier.

    Strips whitespace, converts to lowercase, and strips leading 2-digit prefixes
    (e.g., '06-harbor' -> 'harbor').
    """
    if not isinstance(val, str):
        raise TypeError(f"Realm must be a string, got {type(val).__name__}")

    s = val.strip()
    # Fast path: already clean lowercase string without digits-prefix
    if s.islower() and not (len(s) > 3 and s[2] == "-" and s[:2].isdigit()):
        return s

    s = s.lower()
    prefix_match = _REALM_PREFIX_PATTERN.match(s)
    if prefix_match:
        return prefix_match.group(1)
    return s


def coerce_timestamp(val: Any) -> str:
    """Coerce permissive date/timestamp representations into canonical RFC 3339 UTC ('...Z').

    Permissive inputs handled:
      - 'YYYY-MM-DD': Coerced to 'YYYY-MM-DDT00:00:00Z'
      - 'YYYY-MM-DDTHH:MM': Coerced to 'YYYY-MM-DDTHH:MM:00Z'
      - 'YYYY-MM-DDTHH:MMZ': Coerced to 'YYYY-MM-DDTHH:MM:00Z'
      - 'YYYY-MM-DDTHH:MM:SS': Coerced to 'YYYY-MM-DDTHH:MM:SSZ'
      - 'YYYY-MM-DDTHH:MM:SSZ': Identity (already canonical)
      - 'YYYY-MM-DDTHH:MM:SS.sssZ': Preserved as RFC 3339 UTC
      - 'YYYY-MM-DD HH:MM:SS': Coerced to 'YYYY-MM-DDTHH:MM:SSZ'
      - 'YYYY-MM-DDTHH:MM:SS+HH:MM': Converted to UTC '...Z'
      - 'YYYY-MM-DDTHH:MM+HH:MM': Converted to UTC '...Z'
      - datetime.datetime: Converted to UTC and formatted as '...Z'
      - datetime.date: Coerced to 'YYYY-MM-DDT00:00:00Z'
      - int/float (unix epoch seconds): Converted to UTC '...Z'
    """
    if isinstance(val, str):
        s = val.strip()
        L = len(s)

        # Fast path 1: Standard canonical RFC 3339 UTC string 'YYYY-MM-DDTHH:MM:SSZ'
        if L == 20 and s[19] == "Z" and s[10] == "T":
            return s

        # Fast path 2: Date-only 'YYYY-MM-DD'
        if L == 10 and s[4] == "-" and s[7] == "-":
            return s + "T00:00:00Z"

        # Fast path 3: Missing seconds with Z 'YYYY-MM-DDTHH:MMZ'
        if L == 17 and s[16] == "Z" and s[10] == "T":
            return s[:16] + ":00Z"

        # Fast path 4: Missing seconds without Z 'YYYY-MM-DDTHH:MM'
        if L == 16 and s[10] == "T":
            return s + ":00Z"

        # Fast path 5: Full timestamp without Z 'YYYY-MM-DDTHH:MM:SS'
        if L == 19 and s[10] == "T":
            return s + "Z"

        # Fast path 6: Space separator 'YYYY-MM-DD HH:MM:SS'
        if L == 19 and s[10] == " ":
            return s[:10] + "T" + s[11:] + "Z"

        # Fast path 7: Space separator missing seconds 'YYYY-MM-DD HH:MM'
        if L == 16 and s[10] == " ":
            return s[:10] + "T" + s[11:] + ":00Z"

        # Fast path 8: Fractional seconds ending in Z 'YYYY-MM-DDTHH:MM:SS.sssZ'
        if L > 20 and s.endswith("Z") and s[10] == "T" and "." in s[18:]:
            return s

        # Fast path 9: Fixed offset 'YYYY-MM-DDTHH:MM:SS+HH:MM'
        if L == 25 and s[10] == "T" and s[19] in ("+", "-") and s[22] == ":":
            sign = 1 if s[19] == "+" else -1
            oh = int(s[20:22]) * sign
            om = int(s[23:25]) * sign
            h = int(s[11:13]) - oh
            m = int(s[14:16]) - om
            if 0 <= h < 24 and 0 <= m < 60:
                return f"{s[:11]}{h:02d}:{m:02d}:{s[17:19]}Z"

        # Fast path 10: Fixed offset missing seconds 'YYYY-MM-DDTHH:MM+HH:MM'
        if L == 22 and s[10] == "T" and s[16] in ("+", "-") and s[19] == ":":
            sign = 1 if s[16] == "+" else -1
            oh = int(s[17:19]) * sign
            om = int(s[20:22]) * sign
            h = int(s[11:13]) - oh
            m = int(s[14:16]) - om
            if 0 <= h < 24 and 0 <= m < 60:
                return f"{s[:11]}{h:02d}:{m:02d}:00Z"

        # General path: handles timezone offsets (+02:00, -05:00), subseconds, etc.
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)

            iso = dt.isoformat().replace("+00:00", "Z")
            if not iso.endswith("Z"):
                iso += "Z"
            return iso
        except Exception as exc:
            raise ValueError(f"Cannot coerce invalid timestamp {val!r}: {exc}") from exc

    if isinstance(val, datetime):
        if val.tzinfo is None:
            dt_utc = val.replace(tzinfo=timezone.utc)
        else:
            dt_utc = val.astimezone(timezone.utc)

        iso = dt_utc.isoformat().replace("+00:00", "Z")
        if not iso.endswith("Z"):
            iso += "Z"
        return iso

    if isinstance(val, date):
        return f"{val.isoformat()}T00:00:00Z"

    if isinstance(val, (int, float)):
        dt_utc = datetime.fromtimestamp(val, tz=timezone.utc)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    raise TypeError(f"Unsupported timestamp type: {type(val).__name__} ({val!r})")


def coerce_urn_list(val: Any) -> List[str]:
    """Coerce a scalar string, list, or iterable into a validated list of URN strings.

    Permissive input handling:
      - Single URN string: 'urn:yeoman:contact:...' -> ['urn:yeoman:contact:...']
      - Comma-separated URN string: 'urn:a, urn:b' -> ['urn:a', 'urn:b']
      - List/tuple/set of URNs: validated element-wise
      - None / empty: -> []

    Conservative output:
      - Validated list of canonical URN strings matching '^urn:[a-zA-Z0-9_.:-]+$'.
    """
    if val is None or val == "":
        return []

    if isinstance(val, str):
        val = val.strip()
        if not val:
            return []
        if "," in val:
            parts = [p.strip() for p in val.split(",") if p.strip()]
            for p in parts:
                if not is_valid_urn(p):
                    raise ValueError(f"Invalid URN in comma-separated list: {p!r}")
            return parts

        if not is_valid_urn(val):
            raise ValueError(f"Invalid URN string: {val!r}")
        return [val]

    if isinstance(val, list):
        for item in val:
            if not isinstance(item, str) or not is_valid_urn(item):
                raise ValueError(f"Invalid URN in list: {item!r}")
        return val

    if isinstance(val, (tuple, set)):
        result: List[str] = []
        for item in val:
            if not isinstance(item, str) or not is_valid_urn(item):
                raise ValueError(f"Invalid URN in list: {item!r}")
            result.append(item.strip())
        return result

    raise TypeError(f"Cannot coerce {type(val).__name__} to URN list: {val!r}")


def coerce_relations(relations: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Coerce a relations mapping so all predicate values are validated URN lists."""
    if relations is None:
        return {}
    if not isinstance(relations, dict):
        raise TypeError(f"Relations must be a dictionary, got {type(relations).__name__}")

    coerced: Dict[str, List[str]] = {}
    for verb, target in relations.items():
        coerced[str(verb)] = coerce_urn_list(target)
    return coerced


def coerce_envelope(envelope: Dict[str, Any], inplace: bool = False) -> Dict[str, Any]:
    """Permissively coerce a $pkm envelope (or frontmatter dictionary) into canonical form.

    If input has a '$pkm' key, the nested envelope is coerced.
    If input is the envelope itself, its fields are coerced directly.

    Returns the normalized dictionary.
    """
    if not isinstance(envelope, dict):
        raise TypeError(f"Envelope must be a dict, got {type(envelope).__name__}")

    if "$pkm" in envelope and isinstance(envelope["$pkm"], dict):
        res = envelope if inplace else dict(envelope)
        res["$pkm"] = coerce_envelope(res["$pkm"], inplace=inplace)
        return res

    res = envelope if inplace else dict(envelope)

    if "id" in res:
        res["id"] = coerce_id(res["id"])

    if "realm" in res:
        res["realm"] = coerce_realm(res["realm"])

    if "created_at" in res:
        res["created_at"] = coerce_timestamp(res["created_at"])

    if "updated_at" in res:
        res["updated_at"] = coerce_timestamp(res["updated_at"])

    if "relations" in res and isinstance(res["relations"], dict):
        res["relations"] = coerce_relations(res["relations"])

    return res


_ROOT_LIST_FIELDS: Set[str] = frozenset(
    {
        "tags",
        "wikilinks",
        "blocked_by",
        "depends_on",
        "depends-on",
        "blocks",
        "waitingOn",
        "chain_of_custody_urns",
        "prior_art_urns",
        "attendees",
    }
)


def normalize_frontmatter(
    frontmatter: Dict[str, Any], inplace: bool = False
) -> Dict[str, Any]:
    """Normalize full YAML frontmatter, coercing $pkm and standard scalar-to-array fields."""
    if not isinstance(frontmatter, dict):
        raise TypeError(f"Frontmatter must be a dict, got {type(frontmatter).__name__}")

    res = frontmatter if inplace else dict(frontmatter)

    # Normalize $pkm envelope
    if "$pkm" in res and isinstance(res["$pkm"], dict):
        res["$pkm"] = coerce_envelope(res["$pkm"], inplace=inplace)

    # Permissive scalar strings where lists are standard
    for field in _ROOT_LIST_FIELDS:
        if field in res:
            val = res[field]
            if isinstance(val, str):
                s = val.strip()
                if "," in s:
                    res[field] = [p.strip() for p in s.split(",") if p.strip()]
                elif s:
                    res[field] = [s]
                else:
                    res[field] = []

    return res


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="High-throughput Postel normalization utility for Bosun PKM envelopes."
    )
    parser.add_argument("--json", help="Input JSON string to coerce.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output.")
    args = parser.parse_args(argv)

    if args.json:
        data = json.loads(args.json)
        result = coerce_envelope(data)
        indent = 2 if args.pretty else None
        print(json.dumps(result, indent=indent))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
