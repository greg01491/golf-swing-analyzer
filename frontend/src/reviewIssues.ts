import type { MarkerReviewAnnotation, ReviewIssue, SessionReviewIssues } from './api.ts'

export function queuedReviewIssues(
  evidence: Pick<SessionReviewIssues, 'issues' | 'tolerance_issues'> | null,
  showAllSupport = false,
): ReviewIssue[] {
  return (showAllSupport ? evidence?.issues : evidence?.tolerance_issues) ?? []
}

export interface ReviewIssueGroup extends Omit<ReviewIssue, 'metric'> {
  key: string
  metrics: string[]
  worst_frame_index?: number
  peak_error_px?: number
}

export function groupReviewIssues(issues: ReviewIssue[]): ReviewIssueGroup[] {
  const groups = new Map<string, ReviewIssueGroup>()
  for (const issue of issues) {
    const { metric, ...evidence } = issue
    const key = JSON.stringify(evidence)
    const group = groups.get(key)
    if (group) {
      if (!group.metrics.includes(metric)) group.metrics.push(metric)
    } else {
      groups.set(key, { ...evidence, key, metrics: [metric] })
    }
  }
  for (const group of groups.values()) {
    for (const frame of group.frame_indices) {
      const measurement = group.measurements?.[frame]
      if (
        measurement?.unit === 'px' &&
        Number.isFinite(measurement.value) &&
        (group.peak_error_px === undefined || measurement.value > group.peak_error_px)
      ) {
        group.peak_error_px = measurement.value
        group.worst_frame_index = frame
      }
    }
  }
  return [...groups.values()].sort((left, right) => {
    const leftPeak = left.peak_error_px ?? Number.NEGATIVE_INFINITY
    const rightPeak = right.peak_error_px ?? Number.NEGATIVE_INFINITY
    return leftPeak === rightPeak ? 0 : rightPeak - leftPeak
  })
}

export function observationReview(
  annotations: MarkerReviewAnnotation[],
  camera: string | null,
  marker: string | null,
  frame: number,
): MarkerReviewAnnotation | undefined {
  return annotations.find(
    (annotation) =>
      annotation.camera === camera &&
      annotation.marker === marker &&
      annotation.frame_index === frame,
  )
}

export function reviewIssueTarget(issue: ReviewIssueGroup, frame: number) {
  if (
    !issue.camera ||
    !issue.marker ||
    !issue.fps ||
    !Number.isFinite(issue.fps) ||
    issue.fps <= 0 ||
    !issue.frame_indices.includes(frame)
  ) {
    return null
  }
  return { camera: issue.camera, marker: issue.marker, frame, time: (frame + 0.25) / issue.fps }
}

export function counterpartReviewTarget(
  issue: ReviewIssueGroup,
  frame: number,
  cameras: Record<string, { fps?: number }>,
) {
  const source = reviewIssueTarget(issue, frame)
  if (!source || !issue.fps) return null
  const camera = source.camera === 'camera_1' ? 'camera_2' as const : 'camera_1' as const
  const fps = cameras[camera]?.fps
  if (!fps || !Number.isFinite(fps) || fps <= 0) return null
  const nativeFrame = Math.round((frame / issue.fps) * fps)
  return { camera, marker: source.marker, frame: nativeFrame, time: (nativeFrame + 0.25) / fps }
}
