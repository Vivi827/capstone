# TTS response improvement

Active integration branch: `gsd/phase-2-tts-latency`, based on latest main
`edacb8b`. Worktree: `C:\Users\eunheay\AppData\Local\Temp\pally-tts-main-20260915`.
The original checkout and its user edits are preserved.

## Contract

- Keep natural corrections in Pally's spoken reply.
- Return reply, audio and review feedback together. No delayed inline cards,
  background feedback delivery, or streaming UI changes.
- End conversation on Home. History navigation is user initiated; a session's
  Feedback view displays saved corrections. Do not change navigation.
- Review feedback must describe corrections actually expressed by Pally.

## Rollback checkpoint

- Starting commit: `b192751e80b687ee19278b3481d821a912d00dbd`.
- Exact pre-edit copies and SHA-256 manifest:
  `C:\Users\eunheay\AppData\Local\Temp\pally-tts-rollback-_noe71pv`.
- Existing user edits in `ai/generate_feedback.py` and both scoring workbooks
  are backed up. Do not overwrite them with files from HEAD.
- Voice-only rollback: set `PALLY_TTS_VOICE=en-US-Journey-F` and restart.
- Full rollback: restore only changed existing files from this checkpoint and
  remove only newly added files listed in its manifest, after checking that no
  later edits would be overwritten. Do not reset the repository.

## Pre-implementation validation

- TTS currently creates a new HTTP client for every synthesis request.
- The turn endpoint already runs TTS and feedback concurrently and waits for
  both; lowering TTS latency does not guarantee lower total turn latency.
- The original checkout was stale. Latest main uses `httpPallyApi`, including
  `/api/conversations/{id}/turns` and History APIs. Home completion dispatches
  `session/end` without navigation. No frontend changes are needed for this patch.
- Local Cloud TTS credentials are absent. Tested the existing deployed `/api/tts`
  endpoint using three identical texts with both voices, alternating order.
  All six calls returned HTTP 200 with MP3 audio.

| Characters | Journey ms | Leda ms |
|---|---:|---:|
| 52 | 1550 | 921 |
| 63 | 2285 | 794 |
| 93 | 3670 | 1441 |

These are small-sample end-to-end API timings from this machine, not production
p95 measurements or a voice-quality assessment. Samples and raw measurements
are stored with the checkpoint.

## Implementation plan

1. Default to configurable Leda; keep explicit voice overrides and Journey rollback.
2. Reuse a lifespan-owned HTTP client for TTS, keeping idle connections for up
   to 60 seconds between conversational turns and closing it on app shutdown.
3. Preserve the single-response turn contract and MP3 output.
4. Change review extraction instructions and validate original/corrected spans
   against the utterance/reply. Preserve pre-existing feedback edits.
5. Test API behavior, resource cleanup, error handling, grounding and regression;
   run real provider checks where credentials are available.

## Scope limits

The user authorized production deployment after verifying the Railway target.
No database migration, frontend navigation change, asynchronous feedback delivery
or speech-rate acceleration. Quality listening and mobile production E2E must
be reported separately from automated checks.

## Validation results

- Latest-main regression checks: 33 passed (TTS defaults/override/rollback,
  connection lifecycle, provider error recovery, grounded feedback, app smoke,
  reply shaping and complete-turn/history contract). The contract test uses
  controlled provider/DB substitutes and proves that ready audio does not cause
  early response, and that the returned card matches saved History feedback.
  These checks are now included in CI. `git diff --check` passed.
- TTS comparison: mean Journey 2502 ms vs Leda 1052 ms across the three texts
  above (about 58% lower). This compares voices through the deployed API, not
  a deployed version of this patch or full conversation latency.
- Real Gemini checks after prompt changes: spoken correction recorded;
  an error not corrected by Pally omitted; correct speech omitted; a tense
  correction involving a perspective change recorded. All four completed
  successfully. One earlier ungrounded response was rejected by validation;
  explicit examples were added before the final check.
- Natural-recast chat prompt, turn response/save ordering and frontend files
  are unchanged. No automatic navigation or delayed feedback attachment added.
- Both pre-existing scoring workbooks match checkpoint hashes.
- Cloud TTS credentials are not configured locally. Direct local-to-Google
  TTS E2E, mobile playback/voice quality, production connection-pooling impact
  and full turn latency have not been verified. No deployment performed.

## Release preflight

- User authorized deployment after checking project ownership.
- Authenticated as BEAK EUNHEAY with access to Kim Minju's workspace.
- Confirmed target: workspace `6d007f5d-ab0a-4c91-871f-357fe3681d8d`, project
  `f9d8024f-96aa-4f83-b052-ed7c7fc1da4a` (powerful-laughter), production
  `6d62476b-31dd-4d7a-8e50-b3e9e839f8bf`, web
  `5f36d5be-259f-4d72-8b6b-91c5d5938f20`.
- Previous successful deployment: `ae2457ca-30c0-400d-bbb0-bcdd00c798df`,
  source `edacb8bfbf111cf64ff21f63d21df954651e14b0`.
- Railway source is puter8/capstone main, repository root, with start command
  `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- No PALLY_TTS_VOICE override is configured. Existing Cloud TTS credentials
  successfully synthesized audio using the changed local API and pooled client:
  Journey 1405 ms; Leda 704 ms and 671 ms. Credentials were held only in memory.
- Release through feature PR, passing CI, main merge, automatic Railway deploy.
- Voice rollback: set PALLY_TTS_VOICE=en-US-Journey-F and redeploy/restart.
  Full code rollback: revert this release through a new PR, or use Railway's
  previous successful deployment if an immediate operational rollback is needed.
- Verify the deployed commit, health and returned default TTS voice after release.
  The small TTS benchmark is not a whole-turn performance measurement.
