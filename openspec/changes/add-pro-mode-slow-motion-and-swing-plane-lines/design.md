## Context

`SessionView.tsx` already renders Pro Mode's synced dual-camera grid (`pro-playback-grid`)
with `videoRefs` (a `Record<string, HTMLVideoElement | null>>`) and `syncProVideos()`,
which mirrors the primary camera's `play`/`pause`/`currentTime`/`playbackRate` onto the
other camera(s) via native `<video>` events. The single-camera view already has a working
0-100% slow-motion slider (`speed` state) that sets `playbackRate` on whichever videos are
currently mounted. See proposal.md for why this needs extending to Pro Mode.

The app has no backend involvement in video overlays today: the existing "ball marker"
and pose-overlay skeleton are the only annotations, and both are either server-rendered
(pose overlay, baked into the video by Pose2Sim) or positioned via absolute CSS from
known pixel coordinates (ball marker). There is no club/shaft tracking anywhere in the
pipeline (analysis explicitly notes "no club tracking").

## Goals / Non-Goals

**Goals:**
- Reuse the existing `speed` state and slow-motion slider UI/behavior for Pro Mode,
  rather than introducing a second mechanism.
- Keep the reference line purely a client-side visual aid: no server round-trip, no
  dependency on pose/landmark data.
- Make the line trivial to reposition per camera, since the useful angle differs between
  the down-the-line and face-on views.

**Non-Goals:**
- No automatic detection or suggestion of the "correct" swing plane angle.
- No club/shaft tracking (would require new CV work; out of scope per proposal).
- No multi-line-at-once UI in this change (one line per camera view is enough to start).

## Decisions

**Slow motion shared across Pro Mode videos: reuse `speed` state, not a new prop.**
The existing `useEffect` that applies `speed / 100` to every ref in `videoRefs.current`
already iterates all mounted videos, so exposing the existing slider inside the Pro Mode
block (instead of only the single-camera block) is sufficient — no new state or sync
logic needed. `syncProVideos('rate')` (triggered by the primary video's `onRateChange`)
remains as a secondary safety net if a browser fires that event independently.
Alternative considered: give Pro Mode its own independent speed state — rejected, since
the two views must move at the same rate by definition (it's the same swing).

**Reference line as an absolutely-positioned SVG overlay per camera, not baked into
video pixels.**
Mirrors the existing ball-marker pattern (`position: absolute` element sized against
`videoSize`), but using an SVG `<line>` with draggable circle handles at each endpoint,
layered over the `<video>` in the same wrapping container. Positions are stored as
fractions (0-1) of video width/height (like the ball marker's percentage-based
`left`/`top`), so the line stays aligned if the video element is resized.
Alternatives considered:
- *Canvas overlay*: more manual hit-testing for drag handles; SVG gets pointer events
  and hover/drag affordances for free.
- *Backend-rendered line burned into the overlay video*: rejected — would require
  re-encoding on every color/position change and couples a purely cosmetic aid to the
  processing pipeline for no benefit.

**Persistence via `localStorage`, keyed per camera role, matching the existing
`pro-mode` preference pattern.**
`camera_1`/`camera_2` are stable role identifiers already used as dict keys throughout
the frontend (`videoSources`, `videoRefs`). Storing
`swing-plane-line:<camera>` -> `{ x1, y1, x2, y2, color, visible }` as JSON keeps the
same low-ceremony approach as `pro-mode` and needs no backend schema or API change.
Alternative considered: persist per-session (would let different swings show different
lines, but the proposal's "no re-drawing every session" framing plus the added state
management complexity make the simpler global-per-camera choice preferable for this
first pass).

## Risks / Trade-offs

- [Risk] SVG overlay must stay pixel-aligned with the `<video>` element across the
  `max-height: 68vh` responsive sizing already in `App.css`. -> Mitigation: reuse the
  same `videoSize`-based percentage positioning already proven by the ball marker, which
  faces an identical constraint.
- [Risk] A fixed screen-space line is a rough visual aid, not a measurement — a golfer
  could misread it as more precise than it is. -> Mitigation: this is inherent to the
  proposal's explicit choice (no tracking); no measurement or angle readout is shown.
- [Risk] `localStorage` persistence is global to the browser profile, not per-user or
  per-rig. -> Mitigation: acceptable for a single-golfer desktop app (matches existing
  `pro-mode`/`theme`/`voice-feedback` precedent).
