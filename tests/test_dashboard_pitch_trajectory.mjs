import test from 'node:test';
import assert from 'node:assert/strict';
import { pitchPoint, flightSeconds, groundContactFraction } from '../assets/visualizacion/dashboard_pitch_trajectory.mjs';

const release = { x: .3, y: 1.9, z: 17.5 };
// Medians of the trained hand-specific profiles, in their original units.
const fastball = { RelSpeed: 92.13, HorzBreak: 8.51, InducedVertBreak: 15.09 };
const curveball = { RelSpeed: 78.53, HorzBreak: -8.13, InducedVertBreak: -7.45 };

test('curve and fastball no longer share a forced arrival point', () => {
  const fast = pitchPoint(1, fastball, release), curve = pitchPoint(1, curveball, release);
  assert.ok(fast[0] > 0 && curve[0] < 0, 'lateral break must reach opposite sides');
  assert.ok(fast[1] - curve[1] > 1.4, 'vertical difference must remain visible');
  assert.equal(fast[2], curve[2]);
  assert.ok(flightSeconds(curveball, release) > flightSeconds(fastball, release));
});

test('same release and sight line let the measured movement create differences', () => {
  assert.deepEqual(pitchPoint(0, fastball, release), [release.x, release.y, release.z]);
  assert.deepEqual(pitchPoint(0, curveball, release), [release.x, release.y, release.z]);
  const t = .00001;
  const fast = pitchPoint(t, fastball, release), curve = pitchPoint(t, curveball, release);
  assert.ok(Math.abs(fast[0] - curve[0]) < 1e-8);
  assert.ok(Math.abs(fast[1] - curve[1]) < 1e-8);
});

test('signed hand-specific break is preserved without a second mirror', () => {
  const leftFast = { RelSpeed: 90.53, HorzBreak: -8.23, InducedVertBreak: 15.38 };
  const leftCurve = { RelSpeed: 76.85, HorzBreak: 8.27, InducedVertBreak: -6.01 };
  assert.ok(pitchPoint(1, leftFast, release)[0] < 0);
  assert.ok(pitchPoint(1, leftCurve, release)[0] > 0);
  assert.ok(pitchPoint(1, leftFast, release)[1] > pitchPoint(1, leftCurve, release)[1]);
});

test('custom measurements change the actual arrival, not just the label', () => {
  const changed = pitchPoint(1, { ...fastball, HorzBreak: 0, InducedVertBreak: 0 }, release);
  const original = pitchPoint(1, fastball, release);
  assert.equal(changed[0], 0);
  assert.notEqual(changed[1], original[1]);
});

test('large illustrated drops stop at ground contact rather than disappearing under turf', () => {
  const slowPitch = { RelSpeed: 63.84, HorzBreak: -11.74, InducedVertBreak: -10.97 };
  const end = groundContactFraction(slowPitch, release);
  assert.ok(end > 0 && end < 1);
  assert.ok(Math.abs(pitchPoint(end, slowPitch, release)[1] - .15) < 1e-8);
  assert.equal(groundContactFraction(fastball, release), 1);
});
