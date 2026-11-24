import assert from 'node:assert/strict'
import test from 'node:test'
import type { ReviewIssue, MarkerReviewAnnotation } from '../src/api.ts'
import {
  groupReviewIssues,
  counterpartReviewTarget,
  observationReview,
  queuedReviewIssues,
  reviewIssueTarget,
} from '../src/reviewIssues.ts'

const issue = (changes: Partial<ReviewIssue> = {}): ReviewIssue => ({
  metric: 'hip_turn_deg',
  marker: 'RHip',
  camera: 'camera_1',
  frame_indices: [136, 137, 138],
  fps: 120,
  start_time_s: 136 / 120,
  end_time_s: 138 / 120,
  reason: 'Observation or reconstruction support rejected',
  camera_attribution: 'not_isolated',
  mapping_reason: null,
  ...changes,
})

test('review queue groups identical support spans without merging cameras or different frames', () => {
  const groups = groupReviewIssues([
    issue(),
    issue({ metric: 'x_factor_deg' }),
    issue({ camera: 'camera_2', fps: 60 }),
    issue({ frame_indices: [172] }),
  ])
  assert.equal(groups.length, 3)
  assert.deepEqual(groups[0].metrics, ['hip_turn_deg', 'x_factor_deg'])
})

test('review navigation uses native camera fps and never guesses an unmapped observation', () => {
  const [first, second, unmapped, geometry] = groupReviewIssues([
    issue(),
    issue({ camera: 'camera_2', fps: 60 }),
    issue({
      fps: null,
      frame_indices: [],
      mapping_reason: 'Saved camera frame mapping unavailable',
    }),
    issue({ marker: null, camera: null, frame_indices: [], fps: null }),
  ])
  assert.equal(reviewIssueTarget(first, 137)?.time, 137.25 / 120)
  assert.equal(reviewIssueTarget(second, 137)?.time, 137.25 / 60)
  assert.equal(Math.floor(reviewIssueTarget(first, 137)!.time * 120), 137)
  assert.equal(Math.round(reviewIssueTarget(first, 137)!.time * 120), 137)
  assert.equal(reviewIssueTarget(first, 355), null)
  assert.equal(reviewIssueTarget(unmapped, 137), null)
  assert.equal(reviewIssueTarget(geometry, 137), null)
})

test('existing judgments match exact camera, marker and native frame only', () => {
  const annotation: MarkerReviewAnnotation = {
    camera: 'camera_1',
    frame_index: 137,
    marker: 'RHip',
    label: 'occluded',
    note: 'Hidden',
  }
  assert.equal(observationReview([annotation], 'camera_1', 'RHip', 137), annotation)
  assert.equal(observationReview([annotation], 'camera_2', 'RHip', 137), undefined)
  assert.equal(observationReview([annotation], 'camera_1', 'RHip', 136), undefined)
  assert.equal(observationReview([annotation], 'camera_1', 'LHip', 137), undefined)
})

test('default queue excludes passing views and unresolved support and preserves measured values', () => {
  const rejected = issue()
  const failing = issue({
    camera: 'camera_2',
    frame_indices: [137],
    camera_attribution: 'camera_check_failed',
    measurements: {
      '137': {
        reason: 'Reprojection error exceeds tolerance',
        value: 28,
        threshold: 15,
        unit: 'px',
      },
    },
  })
  const evidence = {
    issues: [rejected, issue({ camera: 'camera_2' })],
    tolerance_issues: [failing],
  }
  assert.deepEqual(queuedReviewIssues(evidence), [failing])
  assert.deepEqual(queuedReviewIssues(evidence, true), evidence.issues)
  assert.deepEqual(queuedReviewIssues({ issues: [rejected] }), [])
  assert.deepEqual(queuedReviewIssues(null), [])
  assert.equal(groupReviewIssues(queuedReviewIssues(evidence))[0].measurements?.['137'].value, 28)
})

test('pixel-error groups sort largest first and select the worst frame without reordering native spans', () => {
  const measured = (value: number) => ({
    reason: 'Reprojection error exceeds tolerance', value, threshold: 15, unit: 'px' as const,
  })
  const groups = groupReviewIssues([
    issue({ marker: 'Head', measurements: { '136': measured(18), '138': measured(32) } }),
    issue({ marker: 'LHip', measurements: { '137': measured(80) } }),
    issue({ marker: 'RHip', measurements: { '136': measured(45) } }),
    issue({ marker: 'Neck' }),
    issue({ marker: 'LWrist', measurements: {
      '136': { reason: 'Low confidence', value: 0.1, threshold: 0.3, unit: 'score' },
    } }),
  ])
  assert.deepEqual(groups.map((group) => group.marker), ['LHip', 'RHip', 'Head', 'Neck', 'LWrist'])
  assert.deepEqual(groups.slice(0, 3).map((group) => group.peak_error_px), [80, 45, 32])
  assert.equal(groups[2].worst_frame_index, 138)
  assert.deepEqual(groups[2].frame_indices, [136, 137, 138])
})

test('counterpart is accessible even without a tolerance failure and uses its own camera rate', () => {
  const [group] = groupReviewIssues([issue({ marker: 'Head' })])
  const sameRate = counterpartReviewTarget(group, 136, { camera_2: { fps: 120 } })
  assert.deepEqual(sameRate, {
    camera: 'camera_2', marker: 'Head', frame: 136, time: 136.25 / 120,
  })
  const differentRate = counterpartReviewTarget(group, 136, { camera_2: { fps: 60 } })
  assert.equal(differentRate?.frame, 68)
  assert.equal(differentRate?.time, 68.25 / 60)
  assert.equal(counterpartReviewTarget(group, 136, {}), null)
  assert.equal(counterpartReviewTarget(group, 136, { camera_2: { fps: 0 } }), null)
  assert.equal(counterpartReviewTarget(group, 355, { camera_2: { fps: 120 } }), null)
})
