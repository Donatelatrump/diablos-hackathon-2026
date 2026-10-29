// Geometry only. These amplified educational paths never feed model inference.
const METRES_PER_INCH = 0.0254;
const METRES_PER_SECOND_PER_MPH = 0.44704;
export const MOVEMENT_AMPLIFICATION = 2.5;

export function flightSeconds(data, release) {
  return (release.z - 0.1) / (data.RelSpeed * METRES_PER_SECOND_PER_MPH);
}

export function pitchPoint(t, data, release) {
  const fraction = Math.max(0, Math.min(1, t));
  const time = flightSeconds(data, release) * fraction;
  // Every pitch has the same sight line, NOT a forced common arrival point.
  // Gravity depends on flight time; signed induced break accumulates toward home.
  // No per-pitch normalization or clipping: preserve differences between profiles.
  return [
    release.x * (1 - fraction) + data.HorzBreak * METRES_PER_INCH * MOVEMENT_AMPLIFICATION * fraction ** 2,
    release.y + (2.1 - release.y) * fraction - 0.5 * 9.80665 * time ** 2
      + data.InducedVertBreak * METRES_PER_INCH * MOVEMENT_AMPLIFICATION * fraction ** 2,
    release.z + (0.1 - release.z) * fraction,
  ];
}

export function groundContactFraction(data, release) {
  if (pitchPoint(1, data, release)[1] >= 0.15) return 1;
  let low = 0, high = 1;
  for (let i = 0; i < 40; i++) {
    const mid = (low + high) / 2;
    if (pitchPoint(mid, data, release)[1] > 0.15) low = mid;
    else high = mid;
  }
  return high;
}
