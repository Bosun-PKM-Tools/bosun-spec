"""
tests/test_codec_fixtures.py
────────────────────────────
Integrity checks for canonical ingestion codec fixtures under
``fixtures/codecs/``.  These files are golden samples of upstream export
formats (vCard, iCalendar, Todoist, Things, Goodreads, Kindle clippings)
that importers must parse.  This suite does not implement the codecs;
it asserts the fixtures themselves are well-formed on disk.

  1. Every required fixture exists and is non-empty.
  2. Every fixture decodes as UTF-8 (UTF-8 BOM permitted; stripped via
     ``utf-8-sig``).
  3. RFC 2426 / RFC 5545 documents use CRLF and fold at the 75-octet
     physical-line boundary.
  4. Kindle ``My Clippings.txt`` starts with a 3-byte UTF-8 BOM and uses
     CRLF record separators.
  5. Structural markers required by the batch (custom vCard labels,
     embedded vs URI photos, RRULE/EXDATE, RSVP attendees, task
     hierarchy, mixed ISBNs) are present.

Usage
  python tests/test_codec_fixtures.py   # standalone
  python -m pytest tests/test_codec_fixtures.py -v
"""

from __future__ import annotations

import csv
import io
import json
import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_CODECS = _REPO_ROOT / "fixtures" / "codecs"

UTF8_BOM = b"\xef\xbb\xbf"
UTF16LE_BOM = b"\xff\xfe"
UTF16BE_BOM = b"\xfe\xff"
CRLF = b"\r\n"
RFC_LINE_LIMIT = 75

_REQUIRED_FIXTURES = (
    "vcard/contacts-v3.vcf",
    "vcard/contacts-v4.vcf",
    "ical/agenda-complex.ics",
    "tasks/todoist-export.json",
    "tasks/things-export.json",
    "media/goodreads-sample.csv",
    "media/kindle-clippings.txt",
)

_RFC_FOLDED = (
    "vcard/contacts-v3.vcf",
    "vcard/contacts-v4.vcf",
    "ical/agenda-complex.ics",
)


def _path(relative: str) -> pathlib.Path:
    return _CODECS / relative


def _read_bytes(relative: str) -> bytes:
    path = _path(relative)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_bytes()


def _decode_utf8(data: bytes) -> str:
    return data.decode("utf-8-sig")


def _physical_lines(data: bytes) -> list[bytes]:
    """Split an RFC document into physical lines, retaining empty lines."""
    if data.endswith(CRLF):
        body = data[: -len(CRLF)]
    else:
        body = data
    return body.split(CRLF)


def _unfold(data: bytes) -> str:
    """Unfold RFC 2426 / RFC 5545 physical lines into logical lines."""
    text = _decode_utf8(data).replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n ", "").replace("\n\t", "")


class TestCodecFixtureIntegrity(unittest.TestCase):
    """UTF-8, CRLF, and byte-boundary checks for ingestion fixtures."""

    def test_required_fixture_files_exist(self):
        missing = [name for name in _REQUIRED_FIXTURES if not _path(name).is_file()]
        self.assertEqual(
            missing,
            [],
            f"Required codec fixtures missing under fixtures/codecs/: {missing}",
        )

    def test_required_fixture_files_are_nonempty(self):
        for name in _REQUIRED_FIXTURES:
            with self.subTest(fixture=name):
                data = _read_bytes(name)
                self.assertGreater(
                    len(data),
                    0,
                    f"{name}: fixture is empty",
                )

    def test_all_fixtures_decode_as_utf8(self):
        """Every fixture must be valid UTF-8 (BOM stripped via utf-8-sig)."""
        for name in _REQUIRED_FIXTURES:
            with self.subTest(fixture=name):
                data = _read_bytes(name)
                try:
                    text = _decode_utf8(data)
                except UnicodeDecodeError as exc:
                    self.fail(f"{name}: not valid UTF-8: {exc}")
                self.assertIsInstance(text, str)
                self.assertGreater(len(text), 0, f"{name}: decoded to empty text")

    def test_rfc_documents_use_crlf_exclusively(self):
        """vCard and iCalendar are RFC text: CR LF, never a bare LF."""
        for name in _RFC_FOLDED:
            with self.subTest(fixture=name):
                data = _read_bytes(name)
                self.assertTrue(
                    data.endswith(CRLF),
                    f"{name}: RFC document must end with CRLF",
                )
                self.assertNotIn(
                    b"\n",
                    data.replace(CRLF, b""),
                    f"{name}: contains bare LF; RFC 2426/5545 require CRLF",
                )
                self.assertNotIn(
                    b"\r",
                    data.replace(CRLF, b""),
                    f"{name}: contains bare CR; RFC 2426/5545 require CRLF",
                )

    def test_rfc_physical_lines_respect_75_octet_fold(self):
        """No physical line may exceed 75 octets excluding the CRLF."""
        for name in _RFC_FOLDED:
            with self.subTest(fixture=name):
                lines = _physical_lines(_read_bytes(name))
                over = [
                    (index, len(line), line[:40])
                    for index, line in enumerate(lines)
                    if len(line) > RFC_LINE_LIMIT
                ]
                self.assertEqual(
                    over,
                    [],
                    f"{name}: physical lines exceed {RFC_LINE_LIMIT} octets: {over}",
                )

    def test_rfc_documents_hit_the_75_octet_streaming_boundary(self):
        """At least one physical line is exactly 75 octets (fold was exercised)."""
        for name in _RFC_FOLDED:
            with self.subTest(fixture=name):
                lengths = [len(line) for line in _physical_lines(_read_bytes(name)) if line]
                self.assertIn(
                    RFC_LINE_LIMIT,
                    lengths,
                    f"{name}: expected at least one physical line of exactly "
                    f"{RFC_LINE_LIMIT} octets to exercise streaming fold limits; "
                    f"max={max(lengths) if lengths else 0}",
                )

    def test_rfc_continuation_lines_begin_with_space(self):
        """Folded continuations are a single leading SPACE (RFC 5545 section 3.1)."""
        for name in _RFC_FOLDED:
            with self.subTest(fixture=name):
                continuations = [
                    line
                    for line in _physical_lines(_read_bytes(name))
                    if line[:1] in (b" ", b"\t")
                ]
                self.assertGreater(
                    len(continuations),
                    0,
                    f"{name}: expected folded continuation lines",
                )
                for line in continuations:
                    self.assertTrue(
                        line.startswith(b" "),
                        f"{name}: continuation must start with SPACE, got {line[:8]!r}",
                    )

    def test_vcard3_has_apple_custom_label_and_embedded_jpeg(self):
        text = _unfold(_read_bytes("vcard/contacts-v3.vcf"))
        self.assertIn("VERSION:3.0", text)
        self.assertIn("item1.X-ABLabel:CustomPhone", text)
        self.assertIn("PHOTO;ENCODING=b;TYPE=JPEG:", text)
        self.assertIn("/9j/", text)
        self.assertGreaterEqual(text.count("BEGIN:VCARD"), 2)
        self.assertEqual(
            text.count("BEGIN:VCARD"),
            text.count("END:VCARD"),
        )

    def test_vcard4_uses_uri_photos(self):
        text = _unfold(_read_bytes("vcard/contacts-v4.vcf"))
        self.assertIn("VERSION:4.0", text)
        self.assertNotIn("ENCODING=b", text)
        self.assertIn("https://archive.example/avatars/", text)
        self.assertRegex(text, r"PHOTO[;:].*https://")
        self.assertGreaterEqual(text.count("BEGIN:VCARD"), 2)

    def test_ical_has_rrule_exdate_multiday_rsvp_and_journal(self):
        text = _unfold(_read_bytes("ical/agenda-complex.ics"))
        self.assertIn("BEGIN:VCALENDAR", text)
        self.assertIn("RRULE:FREQ=DAILY", text)
        self.assertIn("RRULE:FREQ=WEEKLY", text)
        self.assertIn("EXDATE;", text)
        self.assertIn("DTSTART;VALUE=DATE:20260918", text)
        self.assertIn("DTEND;VALUE=DATE:20260921", text)
        self.assertIn("RSVP=TRUE", text)
        self.assertIn("ATTENDEE;", text)
        self.assertIn("BEGIN:VJOURNAL", text)
        self.assertIn("END:VJOURNAL", text)
        self.assertNotIn("BEGIN:VJOURNAL\nATTENDEE", text)

    def test_todoist_export_hierarchy_priority_and_recurrence(self):
        payload = json.loads(_decode_utf8(_read_bytes("tasks/todoist-export.json")))
        items = payload["items"]
        priorities = {item["priority"] for item in items}
        self.assertEqual(priorities, {1, 2, 3, 4})
        children = [item for item in items if item.get("parent_id")]
        self.assertGreaterEqual(len(children), 1)
        parent_ids = {item["id"] for item in items}
        for child in children:
            self.assertIn(child["parent_id"], parent_ids)
        recurring = [
            item
            for item in items
            if item.get("due") and item["due"].get("is_recurring") is True
        ]
        self.assertGreaterEqual(len(recurring), 1)
        project_ids = {project["id"] for project in payload["projects"]}
        for item in items:
            self.assertIn(item["project_id"], project_ids)

    def test_things_export_checklists_headings_deadlines_and_projects(self):
        payload = json.loads(_decode_utf8(_read_bytes("tasks/things-export.json")))
        self.assertGreaterEqual(len(payload["projects"]), 1)
        self.assertGreaterEqual(len(payload["headings"]), 1)
        self.assertGreaterEqual(len(payload["todos"]), 1)
        project_ids = {project["uuid"] for project in payload["projects"]}
        heading_ids = {heading["uuid"] for heading in payload["headings"]}
        for heading in payload["headings"]:
            self.assertIn(heading["project_uuid"], project_ids)
        todos_with_deadline = [todo for todo in payload["todos"] if todo.get("deadline")]
        todos_with_checklist = [todo for todo in payload["todos"] if todo.get("checklist")]
        todos_under_heading = [todo for todo in payload["todos"] if todo.get("heading_uuid")]
        self.assertGreaterEqual(len(todos_with_deadline), 1)
        self.assertGreaterEqual(len(todos_with_checklist), 1)
        self.assertGreaterEqual(len(todos_under_heading), 1)
        for todo in todos_under_heading:
            self.assertIn(todo["heading_uuid"], heading_ids)
            self.assertIn(todo["project_uuid"], project_ids)
        checklist_titles = [
            item["title"]
            for todo in todos_with_checklist
            for item in todo["checklist"]
        ]
        self.assertGreaterEqual(len(checklist_titles), 2)

    def test_goodreads_csv_mixes_isbn10_isbn13_ratings_and_shelves(self):
        text = _decode_utf8(_read_bytes("media/goodreads-sample.csv"))
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        self.assertGreaterEqual(len(rows), 3)
        self.assertIn("ISBN", reader.fieldnames)
        self.assertIn("ISBN13", reader.fieldnames)
        self.assertIn("My Rating", reader.fieldnames)
        self.assertIn("Bookshelves", reader.fieldnames)
        self.assertIn("Date Read", reader.fieldnames)

        def _unwrap(value: str) -> str:
            value = (value or "").strip()
            if value.startswith('="') and value.endswith('"'):
                return value[2:-1]
            return value.strip('"')

        isbn10_rows = [row for row in rows if len(_unwrap(row["ISBN"])) == 10]
        isbn13_rows = [row for row in rows if len(_unwrap(row["ISBN13"])) == 13]
        self.assertGreaterEqual(len(isbn10_rows), 1, "expected at least one ISBN-10")
        self.assertGreaterEqual(len(isbn13_rows), 1, "expected at least one ISBN-13")
        ratings = {int(row["My Rating"]) for row in rows if row["My Rating"] != ""}
        self.assertTrue(ratings & {1, 2, 3, 4, 5}, f"expected a star rating 1-5, got {ratings}")
        shelves = [row["Bookshelves"] for row in rows if row["Bookshelves"].strip()]
        self.assertTrue(
            any("," in shelf for shelf in shelves),
            "expected at least one custom multi-shelf value",
        )
        self.assertTrue(
            any(row["Date Read"].strip() for row in rows),
            "expected at least one Date Read",
        )

    def test_kindle_clippings_bom_crlf_and_location_offsets(self):
        data = _read_bytes("media/kindle-clippings.txt")
        self.assertTrue(
            data.startswith(UTF8_BOM),
            f"kindle-clippings.txt must start with UTF-8 BOM ef bb bf, got {data[:4]!r}",
        )
        self.assertFalse(
            data.startswith(UTF16LE_BOM) or data.startswith(UTF16BE_BOM),
            "kindle-clippings.txt must not be UTF-16",
        )
        payload = data[len(UTF8_BOM) :]
        payload.decode("utf-8")
        self.assertTrue(
            payload.endswith(CRLF),
            "kindle-clippings.txt payload must end with CRLF",
        )
        self.assertNotIn(
            b"\n",
            payload.replace(CRLF, b""),
            "kindle-clippings.txt contains bare LF; Kindle writes CRLF",
        )
        text = _decode_utf8(data)
        self.assertGreaterEqual(text.count("=========="), 3)
        self.assertIn("Location ", text)
        self.assertIn("location ", text)
        self.assertIn(" on page ", text)
        self.assertIn("Your Highlight Location ", text)
        self.assertGreaterEqual(text.count("Added on "), 3)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCodecFixtureIntegrity)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
