// Human-friendly metadata for each swing metric: a readable label, which
// camera view the metric is best understood from, a plain-language
// description, and what "good" looks like. Keyed by the backend metric name.

export type MetricView = 'down-the-line' | 'front-on'

export interface MetricInfo {
  label: string
  view: MetricView
  description: string
  good: string
}

export const METRIC_INFO: Record<string, MetricInfo> = {
  shoulder_turn_deg: {
    label: 'Peak Shoulder Turn',
    view: 'down-the-line',
    description:
      'Peak horizontal shoulder rotation from address during the backswing, measured around the supported vertical reference. This is not rotation around the spine.',
    good: 'A full turn of about 85–95° stores power. Under ~80° usually means a short, arms-only backswing.',
  },
  hip_turn_deg: {
    label: 'Peak Hip Turn',
    view: 'down-the-line',
    description:
      'Peak horizontal hip rotation from address during the backswing, not necessarily the rotation at the top frame.',
    good: 'Around 40–55°. The hips should turn roughly half as much as the shoulders — that difference creates coil.',
  },
  x_factor_deg: {
    label: 'Peak X-Factor',
    view: 'down-the-line',
    description:
      'Peak circular separation between simultaneous address-relative shoulder and hip turns during the backswing, not a subtraction of independently timed peaks.',
    good: 'About 35–50°. More separation stores more power, but too much can strain the back.',
  },
  spine_tilt_deg: {
    label: 'Spine Tilt',
    view: 'down-the-line',
    description:
      'Forward hip-to-neck bend at address in the ball-facing vertical plane, excluding lateral side-bend.',
    good: 'Roughly 25–40° of forward bend gives the arms room to swing and helps you stay on plane.',
  },
  tempo_ratio: {
    label: 'Tempo',
    view: 'front-on',
    description: 'The ratio of your backswing time to your downswing time.',
    good: 'A smooth 3:1 (backswing three times longer than the downswing) is the tour-average rhythm.',
  },
  hip_sway_top_pct: {
    label: 'Hip Sway (Top)',
    view: 'front-on',
    description:
      'How much your hips slide sideways instead of turning by the top of the backswing, as a percentage of your stance width.',
    good: 'Keep it low — under ~15%. Big lateral sway makes it hard to return to the ball consistently.',
  },
  hip_sway_impact_pct: {
    label: 'Hip Sway (Impact)',
    view: 'front-on',
    description:
      'How far your hips have slid sideways from their address position at impact, as a percentage of stance width.',
    good: 'A small shift toward the target is fine, but excessive sway (>20%) leaks power and strike consistency.',
  },
  hip_rotation_impact_deg: {
    label: 'Hip Rotation at Impact',
    view: 'down-the-line',
    description:
      'Horizontal hip rotation from address at impact. Positive is open toward the target; negative is closed.',
    good: 'Good players are about 30–45° open at impact — the hips lead the hands and clear the way for the club.',
  },
  shoulder_tilt_impact_deg: {
    label: 'Shoulder Tilt (Impact)',
    view: 'front-on',
    description:
      'Shoulder-line inclination to horizontal at impact. Positive means the trail shoulder is lower; negative means the lead shoulder is lower.',
    good: 'Around 25–45°. This tilt keeps you behind the ball and helps you hit up on the drive.',
  },
  backswing_time_s: {
    label: 'Backswing Time',
    view: 'front-on',
    description: 'How long your backswing takes, from address to the top.',
    good: 'Typically ~0.7–0.9s. Paired with the downswing time this is the raw version of your tempo ratio.',
  },
  downswing_time_s: {
    label: 'Downswing Time',
    view: 'front-on',
    description: 'How long your downswing takes, from the top to impact.',
    good: 'Usually ~0.2–0.3s — roughly a third of the backswing for tour-average 3:1 tempo.',
  },
  head_movement_cm: {
    label: 'Head Excursion',
    view: 'front-on',
    description:
      'Maximum 3D displacement of your head from its address position through impact, including movement followed by a return. Not total path length.',
    good: 'Under ~10cm. A little is natural, but big head movement makes consistent contact much harder.',
  },
  spine_angle_change_deg: {
    label: 'Spine-Angle Maintenance',
    view: 'down-the-line',
    description:
      'Absolute change in forward spine bend from address to impact, excluding lateral bend. The magnitude alone does not say whether you stood up or bent farther.',
    good: 'Keep it small — under ~10°. Standing up out of posture through impact causes thin and inconsistent strikes.',
  },
  early_extension_cm: {
    label: 'Early Extension',
    view: 'down-the-line',
    description:
      'Pelvis displacement from address to impact along the supported ball-facing direction. Positive is toward the ball; negative is retreat.',
    good: 'Under ~8cm. Staying in your posture (hips back, not toward the ball) keeps room for the arms to swing.',
  },
  reverse_spine_deg: {
    label: 'Reverse Spine',
    view: 'front-on',
    description:
      'Hip-to-neck lateral bend at the top. Positive is toward the target (reverse tilt); negative is away from the target.',
    good: 'Keep the side-bend modest (under ~12°) and tilted away from the target, not toward it.',
  },
  knee_flex_deg: {
    label: 'Knee Angle (Address)',
    view: 'down-the-line',
    description:
      'Mean included hip-knee-ankle angle at address across both supported legs. 180 degrees is straight, not 180 degrees of flexion.',
    good: 'Around 150–170° — an athletic amount of flex. Too straight or too deep both hurt balance and rotation.',
  },
  lead_arm_deg: {
    label: 'Lead-Arm Straightness',
    view: 'down-the-line',
    description: 'The angle of your lead arm (shoulder–elbow–wrist) at the top of the backswing.',
    good: 'Close to straight (160–180°) at the top gives a consistent swing radius and solid contact.',
  },
  hand_speed_impact_ms: {
    label: 'Peak Hand Speed Near Impact',
    view: 'front-on',
    description:
      'Peak supported individual-wrist speed in the configured time window around impact. Not speed at one exact frame or clubhead speed.',
    good: 'Higher is generally faster, but prioritise a repeatable strike over raw speed. Reported in metres per second.',
  },
  swing_plane_deg: {
    label: 'Hand-Path Inclination',
    view: 'down-the-line',
    description:
      'Inclination of the hand-midpoint displacement from address to the top. An endpoint body-pose proxy, not a fitted swing plane or club-shaft angle.',
    good: 'Varies by club and height; look for a consistent plane swing-to-swing rather than a single "right" number.',
  },
}

// Fallback for any metric without explicit metadata: turn snake_case into a
// Title Case label and drop the trailing unit hint (e.g. "_deg", "_pct").
export function formatMetricName(name: string): string {
  const info = METRIC_INFO[name]
  if (info) return info.label
  return name
    .replace(/_(deg|pct|ratio|cm|ms|m|s)$/i, '')
    .split('_')
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export const VIEW_LABELS: Record<MetricView, string> = {
  'down-the-line': 'Down the line',
  'front-on': 'Front on',
}
