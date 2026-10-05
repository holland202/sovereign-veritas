# OBS-1 interface: frozen baseline for round one

**Frozen:** commit `04bca2dfbb014d66566a38f9068a07a2e9c86947` on `experiment/obs1-interface`.
`docs/OBS1_INTERFACE.md` at that commit: sha256 `dff9af54ed649546f8251072fc630a73da09563e627c6c9120741210009a8f4e`.

Recorded 2026-10-04 after Amos Tipton (Founder & Chief Architect, HYBRID WAYSS; OBS-1 design lead) confirmed by
private message that he is comfortable freezing that version for the agreed round-one experiment. His message is
not published here. What he confirmed:

- Checkpoint B stays as written: releasing the held write in the synthetic sandbox shows the consequence of a missing
  fence, and `LATE_WRITE_UNFENCED` records that failure explicitly.
- The checkpoint ordering, the separate fence permission, the successful read after fencing, and the reported
  timeout behaviour address the points discussed.
- The stated limits stay, including leaving revocation during execution, and late-write release at other
  positions, to later rounds.

**What this freeze means.** Agreement on the test interface only. Whether an implementation satisfies it is for the
tests to establish. Amos's agreement is not an endorsement of sovereign-veritas or of any implementation.

## Order from here (no OBS-1 implementation code exists at this commit)

1. Amos writes the four core cases from this interface, including the delayed-write recovery variant, each with
   expected reports, effects, classes and mismatches.
2. They are committed **unedited** under `docs/external/`, with their sha256, before any implementation is written
   or shared.
3. Only then is the implementation written and run against them. Any later change to `OBS1_INTERFACE.md` is a new
   version with its own hash, not an edit to this baseline.

Recorded by Claude (Opus 5.5) at Chad Holland's direction from Amos Tipton's message; the hash and checksum were
checked against the repository before writing.
