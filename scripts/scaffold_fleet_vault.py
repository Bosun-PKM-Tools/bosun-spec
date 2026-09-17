"""scripts/scaffold_fleet_vault.py
──────────────────────────────────
Scaffolds a valid 50-realm Bosun PKM fleet vault directory layout:
  01-bosun/
  02-yeoman/
  ...
  50-relay/

For each realm, populates:
  1. `<realm_dir>/.bosun/state.json`: Initialized manifest with $pkm envelope.
  2. `<realm_dir>/starter.md`: Initial starter note rendered from templates/realms/<realm>.template.md.

Usage:
  python scripts/scaffold_fleet_vault.py [target_dir]
  python scripts/scaffold_fleet_vault.py /path/to/vault --starter-filename starter.md
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import pathlib
import re
import sys
import time
import uuid

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_DEFAULT_TEMPLATES_DIR = _REPO_ROOT / "templates" / "realms"

REALM_KEYS: tuple[str, ...] = (
    "01-bosun",
    "02-yeoman",
    "03-trice",
    "04-logbook",
    "05-quartermaster",
    "06-harbor",
    "07-press",
    "08-embers",
    "09-careen",
    "10-primer",
    "11-passage",
    "12-galley",
    "13-pratique",
    "14-tactician",
    "15-drydock",
    "16-squadron",
    "17-supercargo",
    "18-commonplace",
    "19-chantey",
    "20-marquee",
    "21-scrimshaw",
    "22-traverse",
    "23-docent",
    "24-proctor",
    "25-ropewalk",
    "26-gavel",
    "27-lineage",
    "28-legacy",
    "29-arbor",
    "30-the-glass",
    "31-dispatch",
    "32-registry",
    "33-purser",
    "34-cadence",
    "35-reckoning",
    "36-strongbox",
    "37-trajectory",
    "38-binnacle",
    "39-claim",
    "40-tribute",
    "41-weft",
    "42-reverie",
    "43-provenance",
    "44-menagerie",
    "45-muster",
    "46-breadboard",
    "47-pavilion",
    "48-charthouse",
    "49-commonwealth",
    "50-relay",
)


def generate_uuidv7() -> str:
    """Generate an RFC 9562-compliant UUIDv7 string.

    Combines 48-bit millisecond timestamp, 4-bit version 7,
    12-bit random data, 2-bit variant 10, and 62-bit random data.
    """
    ts_ms = int(time.time() * 1000)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF
    uuid_int = (ts_ms << 80) | (7 << 76) | (rand_a << 64) | (2 << 62) | rand_b
    return str(uuid.UUID(int=uuid_int))


def get_canonical_realm(realm_key: str) -> str:
    """Extract canonical lowercase realm name from prefix-name key (e.g. '01-bosun' -> 'bosun')."""
    return realm_key.split("-", 1)[1]


def render_template_content(
    template_str: str,
    note_uuid: str,
    date_utc: str,
    title: str,
) -> str:
    """Substitute template variables {{ uuidv7 }}, {{ date_utc }}, {{ title }}."""
    replacements = {
        "uuidv7": note_uuid,
        "date_utc": date_utc,
        "title": title,
    }
    rendered = template_str
    for key, val in replacements.items():
        pattern = r"\{\{\s*" + re.escape(key) + r"\s*\}\}"
        rendered = re.sub(pattern, val, rendered)
    return rendered


def scaffold_realm(
    realm_key: str,
    vault_dir: pathlib.Path,
    templates_dir: pathlib.Path,
    starter_filename: str = "starter.md",
    timestamp: str | None = None,
    force: bool = False,
) -> pathlib.Path:
    """Scaffold a single realm directory layout with state manifest and starter note."""
    canonical_realm = get_canonical_realm(realm_key)
    realm_dir = vault_dir / realm_key
    bosun_dir = realm_dir / ".bosun"

    realm_dir.mkdir(parents=True, exist_ok=True)
    bosun_dir.mkdir(parents=True, exist_ok=True)

    iso_now = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Author <realm_dir>/.bosun/state.json initialized manifest
    state_path = bosun_dir / "state.json"
    if not state_path.exists() or force:
        manifest_uuid = generate_uuidv7()
        state_manifest = {
            "$schema": "https://bosunpkm.com/schemas/v1/meta/envelope.schema.json",
            "realm": canonical_realm,
            "realm_key": realm_key,
            "status": "initialized",
            "schema_version": "1.0.0",
            "initialized_at": iso_now,
            "updated_at": iso_now,
            "starter_note": starter_filename,
            "note_count": 1,
            "$pkm": {
                "id": f"urn:uuid:{manifest_uuid}",
                "realm": canonical_realm,
                "created_at": iso_now,
                "updated_at": iso_now,
                "relations": {},
            },
        }
        state_path.write_text(json.dumps(state_manifest, indent=2) + "\n", encoding="utf-8")

    # 2. Author initial starter note based on templates/realms/<realm_key>.template.md
    starter_note_path = realm_dir / starter_filename
    if not starter_note_path.exists() or force:
        template_file = templates_dir / f"{realm_key}.template.md"
        if not template_file.exists():
            raise FileNotFoundError(f"Template not found: {template_file}")

        template_text = template_file.read_text(encoding="utf-8")
        note_uuid = generate_uuidv7()
        title = f"{canonical_realm.replace('-', ' ').title()} Starter Note"

        rendered_content = render_template_content(
            template_str=template_text,
            note_uuid=note_uuid,
            date_utc=iso_now,
            title=title,
        )
        starter_note_path.write_text(rendered_content, encoding="utf-8")

    return realm_dir


def scaffold_fleet_vault(
    target_dir: str | pathlib.Path,
    templates_dir: str | pathlib.Path | None = None,
    starter_filename: str = "starter.md",
    timestamp: str | None = None,
    force: bool = False,
) -> dict[str, pathlib.Path]:
    """Scaffold all 50 realm directories under target_dir."""
    vault_path = pathlib.Path(target_dir).resolve()
    tpl_path = pathlib.Path(templates_dir).resolve() if templates_dir else _DEFAULT_TEMPLATES_DIR

    if not tpl_path.exists():
        raise FileNotFoundError(f"Templates directory does not exist: {tpl_path}")

    vault_path.mkdir(parents=True, exist_ok=True)
    created_realms: dict[str, pathlib.Path] = {}

    for realm_key in REALM_KEYS:
        r_path = scaffold_realm(
            realm_key=realm_key,
            vault_dir=vault_path,
            templates_dir=tpl_path,
            starter_filename=starter_filename,
            timestamp=timestamp,
            force=force,
        )
        created_realms[realm_key] = r_path

    return created_realms


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a valid 50-realm Bosun PKM fleet vault layout."
    )
    parser.add_argument(
        "target_dir",
        nargs="?",
        default="./vault",
        help="Target vault directory path (default: ./vault)",
    )
    parser.add_argument(
        "--templates-dir",
        "-t",
        default=None,
        help="Path to realm templates directory (default: templates/realms/)",
    )
    parser.add_argument(
        "--starter-filename",
        "-s",
        default="starter.md",
        help="Starter note filename within each realm directory (default: starter.md)",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing state.json and starter notes",
    )

    args = parser.parse_args(argv)

    try:
        created = scaffold_fleet_vault(
            target_dir=args.target_dir,
            templates_dir=args.templates_dir,
            starter_filename=args.starter_filename,
            force=args.force,
        )
        print(f"Successfully scaffolded {len(created)} realms in {pathlib.Path(args.target_dir).resolve()}")
        for key in REALM_KEYS:
            print(f"  + {key}/ (.bosun/state.json, {args.starter_filename})")
        return 0
    except Exception as exc:
        print(f"Error scaffolding fleet vault: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
