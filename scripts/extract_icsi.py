# -*- coding: utf-8 -*-
"""Extract attributed dialogue-act turns from the ICSI Meeting Corpus.

ICSI stores orthographic words and dialogue acts in separate NXT XML files,
the same general format as AMI (see scripts/extract_ami.py, which this
script mirrors closely). A dialogue-act references one contiguous range of
word IDs, which makes it the closest available unit to a natural spoken
utterance. This extractor keeps the dialogue-act label (MRDA tag string) and
a best-effort human gloss as provenance; none of those annotations are
converted into Pally axis scores.

Differences from AMI, documented here rather than silently papered over:

- ICSI's dialogue-act "type" is a plain attribute on <dialogueact> (an
  MRDA/SWBD-DAMSL tag string such as "s^bk|s"), not a pointer into a
  separate ontology file the way AMI's da-type is. There is no da-types.xml
  equivalent to resolve, so `dialogue_act` stores the raw tag string
  directly and `dialogue_act_gloss` is produced from a hardcoded MRDA
  glossary (see MRDA_GLOSS below). That glossary is a best-effort mapping
  built from general knowledge of the published MRDA coding manual, not
  parsed from any file shipped in this corpus release -- treat it as
  approximate, especially for rare specific tags.
- ICSI has no AMI-style PM/ME/UI meeting roles. The `participant` attribute
  (e.g. "mn017") is a flat per-corpus speaker code with no meeting role
  semantics, so `speaker_role` is always None here.
- ICSI's Words files use several non-"w" element kinds as nite:child href
  *endpoints* -- most importantly <disfmarker>, which AMI's own words files
  also contain but never as a range endpoint. AMI's parse_word_entries only
  indexes "w" and "vocalsound" elements, so an href ending on a disfmarker
  id would fail the word_indexes lookup and the whole dialogue-act would be
  silently dropped. Measured against the actual ICSI release, disfmarker
  endpoints occur ~11k times (out of ~230k endpoints), so this extractor
  additionally indexes disfmarker/nonvocalsound/pause/comment elements (as
  event-only entries with no text) so those dialogue-acts are not lost.
  This is a deliberate, minor widening of AMI's element-kind coverage, not
  a change to the core algorithm (href-range -> word-index resolution,
  text vs. event rendering).
- Word IDs occasionally contain a literal comma inside the numeric suffix,
  e.g. nite:id="Bdb001.w.1,251". This looks unusual but requires no special
  parsing: HREF_RANGE_RE only excludes ")" from the captured id, and the
  same literal (comma-containing) string appears both in the href and in
  the words file's nite:id attribute, so plain string-keyed dict lookups
  match correctly with no numeric interpretation needed.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.conversation_context import add_adjacent_turn_context
except ModuleNotFoundError:
    from conversation_context import add_adjacent_turn_context


SOURCE_NAME = "icsi_real"
DEFAULT_INPUT = Path("data/external_raw/icsi_manual_zip/core/ICSI")
DEFAULT_OUTPUT = Path("data/fixtures/icsi_utterances.jsonl")
HREF_RANGE_RE = re.compile(r"#id\(([^)]+)\)(?:\.\.id\(([^)]+)\))?")
WHITESPACE_RE = re.compile(r"\s+")
TOKEN_SPLIT_RE = re.compile(r"[\^.:|]+")

# ICSI's <w c="..."> attribute classifies token type. Unlike AMI's boolean
# punc="true", ICSI uses named codes. These are the codes observed in this
# release that should attach to the preceding token with no leading space
# (sentence punctuation, comma, possessive/contraction 's, mid-word hyphen,
# truncation-boundary marker, closing quote). LQUOTE/W/TRUNCW/LET/ABBR/CD
# are treated as ordinary space-separated tokens -- a known simplification
# (an opening quote ideally attaches to the *following* word instead, but
# that requires lookahead state this simple renderer does not track).
PUNCTUATION_CODES = {".", "CM", "APOSS", "HYPH", "SYM", "RQUOTE", "QUOTE"}

# Best-effort MRDA tag -> human gloss map. Built from general knowledge of
# the published MRDA coding manual (Shriberg et al. 2004 / Dhillon, Bhagat,
# Carvey & Shriberg's ICSI-MRDA tagging guide), NOT parsed from a file in
# this release (no such gloss file was found under data/external_raw/
# icsi_manual_zip). Covers the tokens that actually occur most frequently
# in this release's dialogueact "type" strings; rarer/unrecognized tokens
# fall back to the raw token text in build_dialogue_act_gloss.
MRDA_GLOSS: dict[str, str] = {
    "s": "Statement",
    "b": "Backchannel/Continuer",
    "%": "Interrupted/Abandoned/Uninterpretable",
    "%-": "Interrupted/Abandoned (partial)",
    "%--": "Interrupted/Abandoned (further truncated)",
    "fh": "Floor Holder",
    "fg": "Floor Grabber",
    "bk": "Acknowledge-answer",
    "ba": "Assessment/Appreciation",
    "bu": "Understanding-check",
    "bh": "Rhetorical-question Backchannel",
    "aa": "Accept",
    "ar": "Reject",
    "arp": "Partial-Reject",
    "aap": "Partial-Accept",
    "am": "Maybe",
    "qy": "Yes-No Question",
    "qw": "Wh-Question",
    "qr": "Or-Question",
    "qrr": "Or-Clause (after Yes-No Question)",
    "qo": "Open-ended Question",
    "qh": "Rhetorical Question",
    "d": "Declarative-Question marker",
    "g": "Tag-Question marker",
    "rt": "Rising Tone (intonation marker)",
    "e": "Exclamation",
    "df": "Defending/Explanation",
    "cs": "Offer",
    "co": "Action-directive",
    "na": "Affirmative non-yes Answer",
    "no": "Other Answer",
    "ng": "Negative non-no Answer",
    "nd": "Dispreferred Answer",
    "ny": "Yes Answer",
    "j": "Joke",
    "h": "Hold Before Answer/Agreement",
    "2": "Collaborative Completion",
    "cc": "Commit",
    "t": "About-task",
    "t1": "Self-talk",
    "t3": "Third-party-talk",
    "m": "Mimic-other",
    "f": "Follow-me",
    "fe": "Exclamation (reading/expressive)",
    "fa": "Apology",
    "fw": "Welcome",
    "by": "Sympathy",
    "bc": "Correct-misspeaking",
    "bd": "Downplayer",
    "r": "Repeat/Rephrase-request",
    "tc": "Topic-change",
    "z": "Non-labeled/uncertain (approximate)",
}


def local_name(name: str) -> str:
    """Return an XML element or attribute name without its namespace prefix."""
    return name.rsplit("}", maxsplit=1)[-1].rsplit(":", maxsplit=1)[-1]


def attribute(element: ET.Element, name: str, default: str = "") -> str:
    for key, value in element.attrib.items():
        if local_name(key) == name:
            return value
    return default


def clean_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip(" -,:;")


def build_dialogue_act_gloss(type_code: str) -> str | None:
    if not type_code:
        return None
    tokens = [token.strip("+-") for token in TOKEN_SPLIT_RE.split(type_code)]
    glosses = [MRDA_GLOSS.get(token, token) for token in tokens if token]
    return " + ".join(glosses) if glosses else None


def parse_speaker_metadata(speakers_path: Path) -> dict[str, dict[str, str | None]]:
    """Parse ICSI's flat, corpus-wide speakers.xml (keyed by participant tag).

    Unlike AMI's per-meeting participants.xml + meetings.xml pairing, ICSI
    speaker metadata is not scoped to a meeting, and there is no meeting
    role (PM/ME/UI) annotation at all -- speaker_role is left to the caller
    to set to None. Native language is read from the nested
    <native><language> element when present; if a speaker has no <native>
    block their native_language is left as None (this corpus release does
    not state an explicit "native English" default).
    """
    root = ET.parse(speakers_path).getroot()
    metadata: dict[str, dict[str, str | None]] = {}
    for speaker in root:
        if local_name(speaker.tag) != "speaker":
            continue
        tag = attribute(speaker, "tag")
        if not tag:
            continue
        native_language: str | None = None
        for native in speaker.iter():
            if local_name(native.tag) != "native":
                continue
            for child in native:
                if local_name(child.tag) == "language":
                    native_language = (child.text or "").strip() or None
                    break
            break
        metadata[tag] = {
            "speaker_native_language": native_language,
            "speaker_gender": attribute(speaker, "gender") or None,
        }
    return metadata


def parse_word_entries(path: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Parse an ICSI Words file into ordered entries plus an id->index map.

    Widened relative to AMI's parse_word_entries: also indexes disfmarker,
    nonvocalsound, pause, and comment elements as event-only entries (no
    text) so that dialogue-act href ranges ending on one of those ids can
    still be resolved. See the module docstring for why this matters for
    ICSI specifically.
    """
    root = ET.parse(path).getroot()
    entries: list[dict[str, str]] = []
    for element in root:
        kind = local_name(element.tag)
        entry_id = attribute(element, "id")
        if not entry_id:
            continue
        if kind == "w":
            entries.append(
                {
                    "id": entry_id,
                    "text": (element.text or "").strip(),
                    "punctuation": attribute(element, "c") in PUNCTUATION_CODES,
                    "event": "",
                    "start_time": attribute(element, "starttime"),
                    "end_time": attribute(element, "endtime"),
                }
            )
        elif kind in {"vocalsound", "nonvocalsound", "comment"}:
            entries.append(
                {
                    "id": entry_id,
                    "text": "",
                    "punctuation": False,
                    "event": attribute(element, "description", kind),
                    "start_time": attribute(element, "starttime"),
                    "end_time": attribute(element, "endtime"),
                }
            )
        elif kind in {"disfmarker", "pause"}:
            entries.append(
                {
                    "id": entry_id,
                    "text": "",
                    "punctuation": False,
                    "event": kind,
                    "start_time": attribute(element, "starttime"),
                    "end_time": attribute(element, "endtime"),
                }
            )
    return entries, {entry["id"]: index for index, entry in enumerate(entries)}


def render_entries(entries: list[dict[str, str]]) -> tuple[str, list[str]]:
    tokens: list[str] = []
    events: list[str] = []
    for entry in entries:
        if entry["event"]:
            events.append(entry["event"])
            continue
        token = entry["text"]
        if not token:
            continue
        if entry["punctuation"] and tokens:
            tokens[-1] += token
        else:
            tokens.append(token)
    return clean_text(" ".join(tokens)), events


def parse_href_range(href: str) -> tuple[str, str] | None:
    match = HREF_RANGE_RE.search(href)
    if not match:
        return None
    start_id, end_id = match.groups()
    return start_id, end_id or start_id


def extract_file(
    dialogue_path: Path,
    words_dir: Path,
    speaker_metadata: dict[str, dict[str, str | None]],
) -> list[dict[str, Any]]:
    stem = dialogue_path.name.removesuffix(".dialogue-acts.xml")
    meeting_id, speaker = stem.rsplit(".", maxsplit=1)
    word_path = words_dir / f"{stem}.words.xml"
    if not word_path.exists():
        return []
    entries, word_indexes = parse_word_entries(word_path)
    root = ET.parse(dialogue_path).getroot()
    return extract_dialogue_act_rows(
        root,
        entries,
        word_indexes,
        meeting_id,
        speaker,
        speaker_metadata,
    )


def extract_dialogue_act_rows(
    root: ET.Element,
    entries: list[dict[str, str]],
    word_indexes: dict[str, int],
    meeting_id: str,
    speaker: str,
    speaker_metadata: dict[str, dict[str, str | None]],
) -> list[dict[str, Any]]:
    """Render one ICSI speaker file after its XML and word entries are parsed."""
    rows: list[dict[str, Any]] = []

    for act in root:
        if local_name(act.tag) != "dialogueact":
            continue
        act_id = attribute(act, "id")
        word_range: tuple[str, str] | None = None
        for child in act:
            if local_name(child.tag) == "child":
                word_range = parse_href_range(attribute(child, "href"))
        if not act_id or not word_range:
            continue
        start_id, end_id = word_range
        if start_id not in word_indexes or end_id not in word_indexes:
            continue
        start_index, end_index = word_indexes[start_id], word_indexes[end_id]
        if end_index < start_index:
            start_index, end_index = end_index, start_index
        utterance, events = render_entries(entries[start_index : end_index + 1])
        if not utterance:
            continue
        type_code = attribute(act, "type")
        participant = attribute(act, "participant")
        participant_metadata = speaker_metadata.get(participant, {})
        rows.append(
            {
                "utterance": utterance,
                "source": SOURCE_NAME,
                "axes": None,
                "source_record_id": act_id,
                "source_group": meeting_id,
                "meeting_id": meeting_id,
                "speaker": speaker,
                "speaker_id": participant or None,
                "speaker_native_language": participant_metadata.get("speaker_native_language"),
                "speaker_role": None,
                "dialogue_act": type_code or None,
                "dialogue_act_gloss": build_dialogue_act_gloss(type_code),
                "start_time": entries[start_index].get("start_time"),
                "end_time": entries[end_index].get("end_time"),
                "annotation_events": events,
            }
        )
    return rows


def extract_corpus(input_dir: Path) -> tuple[int, int, list[dict[str, Any]]]:
    dialogue_dir = input_dir / "DialogueActs"
    words_dir = input_dir / "Words"
    speaker_metadata = parse_speaker_metadata(input_dir / "speakers.xml")
    files = sorted(dialogue_dir.glob("*.dialogue-acts.xml"))
    rows: list[dict[str, Any]] = []
    skipped = 0
    for path in files:
        extracted = extract_file(path, words_dir, speaker_metadata)
        stem = path.name.removesuffix(".dialogue-acts.xml")
        if not extracted and not (words_dir / f"{stem}.words.xml").exists():
            skipped += 1
        rows.extend(extracted)
    return len(files), skipped, add_adjacent_turn_context(rows, "meeting_id", "start_time")


def write_jsonl(rows: Iterable[dict[str, Any]], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    file_count, skipped, rows = extract_corpus(args.input)
    count = write_jsonl(rows, args.output)
    acts = Counter(str(row["dialogue_act"] or "unknown") for row in rows)
    languages = Counter(str(row["speaker_native_language"] or "unknown") for row in rows)
    print(f"dialogue_act_files={file_count}")
    print(f"skipped_missing_word_files={skipped}")
    print(f"utterances={count}")
    print(f"distinct_dialogue_act_types={len(acts)}")
    print("top_dialogue_acts=" + ", ".join(f"{name}:{acts[name]}" for name, _ in acts.most_common(20)))
    print("native_languages=" + ", ".join(f"{name}:{languages[name]}" for name in sorted(languages)))
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
