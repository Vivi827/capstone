# -*- coding: utf-8 -*-
r"""Extract speaker turns from the Santa Barbara Corpus of Spoken American
English (SBCSAE) `.trn` transcripts.

Format notes (verified against the actual 60 files in
`data/external_raw/santa_barbara/extracted/TRN/`, not assumed from generic
SBC documentation):

- Every file starts directly with a timestamped line; none of the 60 files
  in this release have a header/metadata preamble to skip.
- Three concrete line layouts are mixed across files (and even within one
  file in a few places):
    A. `start end\tSPEAKER:\ttext`   (one tab-field holds "start end",
       space-separated) -- SBC001-SBC013.
    B. `start\tend\tSPEAKER:\ttext`  (start/end are separate tab fields)
       -- SBC015-SBC060.
    C. `start end SPEAKER:\ttext`    (start/end/speaker all space-separated,
       only the text is tab-separated) -- SBC014, and scattered lines
       elsewhere (e.g. SBC013's birthday-card scene).
  Rather than branch on file-level format, `LINE_RE` captures the two
  leading numbers with `\s+`/`\s*` (matches both tab and space) and hands
  everything after them to `split_speaker_and_text`, which does its own
  greedy whitespace consumption. This makes the parser format-agnostic and
  also tolerant of one-off malformed lines (stray leading tabs, doubled
  whitespace, a birthday-card scene in SBC013 that abandons tabs almost
  entirely for ~80 lines).
- Speaker label only appears on the first line of a turn; continuation
  lines have a blank/whitespace speaker field and belong to the same
  speaker until a new `LABEL:` token appears at the start of the
  post-timestamp remainder. Labels observed include ordinary names
  (`LENORE:`), disambiguated duplicates (`TOM_1:`), and non-person sources
  (`>ENV:` for environmental sound, `AUD:`/`AUD1:` for audience,
  `MANY:` for simultaneous crowd sound, `X:` for an unidentified speaker,
  `#FOSTER:` for an uncertain speaker identification). All are kept as-is
  (colon stripped) rather than filtered, since some still carry real words
  (e.g. `AUD5: [#Walt],`); turns whose only content is a bracketed sound
  event (`((APPLAUSE))`) clean to an empty string and are dropped by the
  same empty-utterance rule the AMI/ICSI extractors use.
- A small number of lines are transcriber editorial comments injected at
  the text position, not speech, e.g. `0.00 0.00\t$ INDETERMINATE BETWEEN
  "TOO" AND "TWO"`. Any post-timestamp remainder starting with `$` is
  dropped outright (does not become a continuation line).
- Two files (`SBC037.trn`, `SBC060.trn`) contain non-UTF-8 bytes (cp1252
  apostrophes/quotes, one Latin word). Decoding tries UTF-8 first and
  falls back to cp1252.
- Six lines across five files contain a literal NUL byte standing in for a
  lowercase "c" (`\x00hurch` -> `church`, `\x00ouple` -> `couple`, etc. --
  verified by inspecting every occurrence; all six are missing exactly
  "c"). This is fixed at the raw-byte level before decoding. A handful of
  files also have a stray trailing `\x7f` (DEL) byte right before a
  newline with no adjacent content; it is dropped.

Cleaning conventions applied to the joined turn text, verified against
this release (not the generic literature description) by grepping for
every distinct marker family actually present:

- `...`, `..`, `.` as a standalone pause token (whitespace/start/end on
  both sides, not directly attached to a preceding letter) -> removed.
  Sentence-final `.`/`,`/`?` attached directly to a word (no preceding
  space) is real punctuation and is left untouched -- these are
  intonation-contour marks in the Du Bois system (falling/continuing/
  appeal), not pauses, and the two are reliably distinguishable by
  whether there is a space before the dot(s).
- `=` vowel-elongation marker attached to a word -> the `=` is deleted,
  the word is kept (e.g. `ti=red` -> `tired`... actually kept as `tired`
  only after concatenation; script keeps the surrounding letters as-is
  and just removes the `=` character, so `ti=red` -> `tired`).
- `@` laughter token: bursts of bare `@` (e.g. `@@@`, `@ @ @`) are
  converted to one `laughter` annotation event per run and removed from
  the text. `<@ ... @>` (speech produced while laughing) is treated as an
  ordinary paired paralinguistic wrapper -- the `@` delimiters are
  stripped and the spoken words inside are kept in the running text (the
  "laughing quality" nuance itself is not preserved as a separate event;
  documented limitation).
- `(H)`, `(Hx)`, `(TSK)`, `(SNIFF)`, `(COUGH)`, and every other bracketed
  bare-word non-lexical marker actually observed in this release (see the
  full list found by grepping `\([A-Za-z_]+\)` across all 60 files: H, Hx,
  TSK, SNIFF, THROAT, COUGH, LAUGHTER, SWALLOW, GASP, SIGH, YAWN, and
  dozens of one-off environmental/vocal codes) -> removed from text,
  recorded as a lowercase annotation event.
- `((WORD_WORD))` double-parenthesis environmental event descriptions
  (`((APPLAUSE))`, `((DOOR_OPENING))`, ...) -> removed from text, recorded
  as a lowercase annotation event (underscores kept, e.g. `door_opening`).
- `%` glottal stop marker -> deleted (attached to a word or standalone,
  both occur in this release).
- `<X ... X>`, `<@ ... @>`, `<YWN ... YWN>`, `<<WRITING ... WRITING>>`,
  and every other `<CODE ... CODE>` / `<<CODE ... CODE>>` paralinguistic
  quality wrapper actually observed (grepped: X, ACC, BR, CRY, F, FF, HI,
  L, MRC, P, PAR, PP, Q, READ, SHOUT, SIGH, SING, SM, SMOKING, VOX, WRITING
  plus many environmental-noise codes reused as wrappers) -> code tags
  stripped, inner text kept. Applied with a paired regex first (handles
  the common same-turn case), then a fallback pass strips any leftover
  unpaired `<...` / `...>` fragment, because a handful of wrappers in this
  corpus open in one speaker's turn and close in a later, non-adjacent
  turn by the same speaker (an interleaved second speaker's turns sit
  between the open and the close) -- with turns built strictly from
  *consecutive* same-speaker lines, such wrappers cannot be paired across
  the intervening turn, so the lone delimiters are stripped instead of
  matched. This is a deliberate, documented simplification, not a bug.
- `[...]`, `[2...2]`, `[3...3]`, up to `[9...9]` overlap brackets ->
  brackets and the paired digit stripped, inner text kept (paired regex
  plus the same kind of unmatched-fallback strip).
- `~word` anonymized/truncated name marker -> `~` deleted, word kept.
- `!word` pitch/stress marker (observed heavily, e.g. `!Kevin`, `!Sue`) ->
  `!` deleted, word kept. Not in the task's original convention list but
  present throughout this release; documented here rather than left in
  the output as stray punctuation.
- `#word` uncertain-transcription marker (observed heavily, e.g.
  `#Walter`, `#Windham`) -> `#` deleted, word kept, EXCEPT when `#` opens
  a speaker label (`#FOSTER:`), which is a different convention (uncertain
  *speaker identity*) and is left on the speaker field as typed.
  `& word` / `word &` continuation-across-a-pause marker (observed, e.g.
  `another &` / `& brat`) -> `&` deleted like a pause token; in every
  sampled case the two sides are already separate whole words, so plain
  deletion (not word-splicing) produces correct running text.
- `(1.2)`-style bare numeric timed-pause parens -> not found anywhere in
  this release (grepped for it explicitly), but still stripped
  defensively in case a rare instance was missed.
- `--` word-cutoff marker, and a bare trailing `-` directly on a truncated
  word (`wait-`, `b=-`) which is the same convention at a different
  granularity -- both are KEPT as-is. Decision, not an oversight: cutoffs
  are potentially meaningful for downstream humor/disfluency judgment
  (self-correction, interruption) and stripping them risks silently
  fusing two different words together with no separator.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.conversation_context import add_adjacent_turn_context
except ModuleNotFoundError:
    from conversation_context import add_adjacent_turn_context


SOURCE_NAME = "santa_barbara_real"
DEFAULT_INPUT = Path("data/external_raw/santa_barbara/extracted/TRN")
DEFAULT_OUTPUT = Path("data/fixtures/santa_barbara_utterances.jsonl")

# Two leading numeric fields (start, end), separated from each other and
# from the remainder by any run of tabs/spaces. See module docstring for
# why this single pattern covers all three on-disk layouts.
LINE_RE = re.compile(r"^\s*([\d.]+)\s+([\d.]+)\s*(.*)$")
SPEAKER_RE = re.compile(r"^([A-Za-z0-9_>#]+):\s*(.*)$")

DOUBLE_PAREN_EVENT_RE = re.compile(r"\(\(([^()]+)\)\)")
BARE_PAREN_MARKER_RE = re.compile(r"\(([A-Za-z_]+)\)")
BARE_PAREN_TIMED_PAUSE_RE = re.compile(r"\(\d+(?:\.\d+)?\)")
PAIRED_ANGLE_TAG_RE = re.compile(r"<{1,2}([A-Za-z@][A-Za-z0-9_]*)\s+(.*?)\s*\1>{1,2}")
LONE_ANGLE_OPEN_RE = re.compile(r"<{1,2}[A-Za-z@][A-Za-z0-9_]*\s*")
LONE_ANGLE_CLOSE_RE = re.compile(r"\s*[A-Za-z0-9_@]*>{1,2}")
STRAY_ANGLE_RE = re.compile(r"[<>]")
PAIRED_OVERLAP_BRACKET_RE = re.compile(r"\[([0-9]*)(.*?)\1\]")
LONE_BRACKET_RE = re.compile(r"[\[\]]")
LAUGH_RUN_RE = re.compile(r"@+")
STANDALONE_PAUSE_RE = re.compile(r"(?<![A-Za-z0-9])\.{1,3}(?=\s|$)")
TILDE_RE = re.compile(r"~(?=\w)")
BANG_RE = re.compile(r"!(?=\w)")
HASH_RE = re.compile(r"#(?=\w)")
AMPERSAND_RE = re.compile(r"&")
WHITESPACE_RE = re.compile(r"\s+")
SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.?!:;])")

# Files known (by inspection) to need a cp1252 fallback for a handful of
# non-UTF-8 bytes (cp1252 right-single-quote / accented Latin letter).
NUL_TO_C_FIX = b"\x00"


def read_text(path: Path) -> str:
    data = path.read_bytes()
    data = data.replace(NUL_TO_C_FIX, b"c").replace(b"\x7f", b"")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def split_speaker_and_text(remainder: str) -> tuple[str | None, str | None]:
    """Split the post-timestamp remainder of one line into (speaker, text).

    Returns (None, None) for transcriber editorial comment lines (they
    start with "$" and carry no speech), (None, text) for a continuation
    line with no speaker label, or (speaker, text) for a line that opens
    a new turn.
    """
    remainder = remainder.strip()
    if not remainder or remainder.startswith("$"):
        return None, None
    match = SPEAKER_RE.match(remainder)
    if match:
        return match.group(1), match.group(2).strip()
    return None, remainder


def strip_double_paren_events(text: str, events: list[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        events.append(match.group(1).strip().lower().replace(" ", "_"))
        return " "

    return DOUBLE_PAREN_EVENT_RE.sub(replace, text)


def strip_bare_paren_markers(text: str, events: list[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        events.append(match.group(1).strip().lower())
        return " "

    return BARE_PAREN_MARKER_RE.sub(replace, text)


def strip_angle_tags(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = PAIRED_ANGLE_TAG_RE.sub(lambda m: f" {m.group(2)} ", text)
    text = LONE_ANGLE_OPEN_RE.sub(" ", text)
    text = LONE_ANGLE_CLOSE_RE.sub(" ", text)
    text = STRAY_ANGLE_RE.sub(" ", text)
    return text


def strip_overlap_brackets(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = PAIRED_OVERLAP_BRACKET_RE.sub(lambda m: f" {m.group(2)} ", text)
    text = LONE_BRACKET_RE.sub(" ", text)
    return text


def strip_laughter(text: str, events: list[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        events.append("laughter")
        return " "

    return LAUGH_RUN_RE.sub(replace, text)


def clean_text(raw_text: str) -> tuple[str, list[str]]:
    events: list[str] = []
    text = raw_text
    text = strip_double_paren_events(text, events)
    text = strip_angle_tags(text)
    text = strip_overlap_brackets(text)
    text = text.replace("%", " ")
    text = text.replace("=", "")
    text = AMPERSAND_RE.sub(" ", text)
    text = TILDE_RE.sub("", text)
    text = BANG_RE.sub("", text)
    text = HASH_RE.sub("", text)
    text = BARE_PAREN_TIMED_PAUSE_RE.sub(" ", text)
    text = strip_bare_paren_markers(text, events)
    text = strip_laughter(text, events)
    text = STANDALONE_PAUSE_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    text = SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = text.strip(" -,:;")
    return text, events


def parse_lines(path: Path) -> list[tuple[str, str, str | None, str | None]]:
    """Return (start, end, speaker_or_None, text_or_None) for every real line.

    A None text means the line was a dropped editorial comment.
    """
    parsed: list[tuple[str, str, str | None, str | None]] = []
    text = read_text(path)
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if not line.strip():
            continue
        match = LINE_RE.match(line)
        if not match:
            continue
        start, end, remainder = match.groups()
        speaker, line_text = split_speaker_and_text(remainder)
        parsed.append((start, end, speaker, line_text))
    return parsed


def build_turns(
    lines: list[tuple[str, str, str | None, str | None]],
) -> list[dict[str, Any]]:
    """Group consecutive same-speaker lines into raw turns.

    Turn numbering counts every raw turn (including ones later dropped
    for having no surviving text after cleaning), so `source_record_id`
    stays traceable to a stable position in the original transcript.
    """
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for start, end, speaker, line_text in lines:
        if line_text is None:
            continue
        if speaker is not None:
            current = {
                "speaker": speaker,
                "start_time": start,
                "end_time": end,
                "raw_parts": [line_text] if line_text else [],
            }
            turns.append(current)
        else:
            if current is None:
                # Continuation line with no preceding speaker in this file;
                # keep it rather than silently drop real speech.
                current = {
                    "speaker": "UNKNOWN",
                    "start_time": start,
                    "end_time": end,
                    "raw_parts": [],
                }
                turns.append(current)
            current["end_time"] = end
            if line_text:
                current["raw_parts"].append(line_text)
    return turns


def extract_file(path: Path) -> tuple[list[dict[str, Any]], int, int]:
    file_id = path.stem
    lines = parse_lines(path)
    raw_turns = build_turns(lines)
    rows: list[dict[str, Any]] = []
    skipped_empty = 0
    for turn_number, turn in enumerate(raw_turns, start=1):
        raw_text = " ".join(turn["raw_parts"])
        utterance, events = clean_text(raw_text)
        if not utterance:
            skipped_empty += 1
            continue
        rows.append(
            {
                "utterance": utterance,
                "source": SOURCE_NAME,
                "axes": None,
                "source_record_id": f"{file_id}.turn{turn_number}",
                "source_group": file_id,
                "meeting_id": file_id,
                "speaker": turn["speaker"],
                "speaker_id": turn["speaker"],
                "start_time": turn["start_time"],
                "end_time": turn["end_time"],
                "annotation_events": events,
            }
        )
    return rows, len(raw_turns), skipped_empty


def extract_corpus(input_dir: Path) -> tuple[int, int, int, list[dict[str, Any]]]:
    files = sorted(input_dir.glob("SBC*.trn"))
    rows: list[dict[str, Any]] = []
    total_raw_turns = 0
    total_skipped_empty = 0
    for path in files:
        file_rows, raw_turn_count, skipped_empty = extract_file(path)
        rows.extend(file_rows)
        total_raw_turns += raw_turn_count
        total_skipped_empty += skipped_empty
    return (
        len(files),
        total_raw_turns,
        total_skipped_empty,
        add_adjacent_turn_context(rows, "meeting_id", "start_time"),
    )


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
    file_count, raw_turns, skipped_empty, rows = extract_corpus(args.input)
    count = write_jsonl(rows, args.output)
    speakers = Counter(str(row["speaker"]) for row in rows)
    print(f"trn_files={file_count}")
    print(f"raw_turns={raw_turns}")
    print(f"skipped_empty_after_cleaning={skipped_empty}")
    print(f"utterances={count}")
    print(f"distinct_speakers={len(speakers)}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
