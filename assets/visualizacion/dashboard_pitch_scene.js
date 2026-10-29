// Build instructions and third-party notices: dashboard_pitch_scene.README.md.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { pitchPoint, flightSeconds, groundContactFraction } from './dashboard_pitch_trajectory.mjs';

const data = window.pitchVisualData;
const canvas = document.getElementById('scene');
const stage = document.getElementById('stage');
document.getElementById('speed').textContent = `${data.RelSpeed.toFixed(1)} mph`;

function startScene() {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#edf1e6');
  scene.fog = new THREE.Fog('#edf1e6', 36, 100);
  const camera = new THREE.PerspectiveCamera(43, 1, 0.1, 160);
  const orbit = new OrbitControls(camera, canvas);
  // OrbitControls sets touch-action:none. Allow vertical page scrolling on phones;
  // horizontal dragging still rotates the scene and camera presets stay available.
  canvas.style.touchAction = 'pan-y';
  orbit.enableDamping = true; orbit.enablePan = false;
  orbit.minDistance = 8; orbit.maxDistance = 43;
  orbit.minPolarAngle = 0.25; orbit.maxPolarAngle = Math.PI / 2 - 0.04;
  orbit.target.set(0, 1.3, 11); camera.position.set(3, 3.4, -8); orbit.update();
  scene.add(new THREE.HemisphereLight('#d8ecff', '#355c35', 2.2));
  const key = new THREE.DirectionalLight('#ffecd1', 3.5);
  key.position.set(-14, 24, -8); key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  Object.assign(key.shadow.camera, { left: -25, right: 25, top: 30, bottom: -20, far: 80 });
  key.shadow.bias = -0.0006; scene.add(key);
  const rim = new THREE.DirectionalLight('#9bdaff', 2.2); rim.position.set(18, 12, 22); scene.add(rim);
  const mat = (color, roughness = 0.8) => new THREE.MeshStandardMaterial({ color, roughness });
  const turf = mat('#6d975d'), dirt = mat('#c7a17a'), chalk = mat('#fffdf4');
  const red = mat('#c12b43'), pants = mat('#ece6dc'), skin = mat('#cf9877'), dark = mat('#25313a');
  function mesh(geometry, material, x = 0, y = 0, z = 0, parent = scene) {
    const object = new THREE.Mesh(geometry, material);
    object.position.set(x, y, z); object.castShadow = true; object.receiveShadow = true;
    parent.add(object); return object;
  }
  function disk(radius, material, x, z, height = 0.018) {
    return mesh(new THREE.CylinderGeometry(radius, radius, height, 80), material, x, height / 2, z);
  }
  disk(39, turf, 0, 12, 0.08);
  const bands = [mat('#729d61'), mat('#648d54')];
  for (let i = 0; i < 12; i++) {
    const z = -22 + i * 6, halfWidth = Math.sqrt(Math.max(0, 37 ** 2 - (z - 12) ** 2));
    if (halfWidth > 0) mesh(new THREE.BoxGeometry(halfWidth * 2, 0.015, 5.9), bands[i % 2], 0, 0.05, z);
  }
  disk(3.1, dirt, 0, 0, 0.1); disk(1.95, dirt, 0, 18.1, 0.36);
  mesh(new THREE.BoxGeometry(0.65, 0.04, 0.15), chalk, 0, 0.4, 18.3);
  const plateShape = new THREE.Shape();
  plateShape.moveTo(-0.24, 0.24); plateShape.lineTo(0.24, 0.24); plateShape.lineTo(0.24, 0);
  plateShape.lineTo(0, -0.23); plateShape.lineTo(-0.24, 0); plateShape.closePath();
  const plate = mesh(new THREE.ShapeGeometry(plateShape), new THREE.MeshStandardMaterial({ color: '#fff9e8', side: THREE.DoubleSide }), 0, 0.115, 0);
  plate.rotation.x = -Math.PI / 2;
  function line(points, color, opacity = 1, parent = scene) {
    const object = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p => new THREE.Vector3(...p))), new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
    parent.add(object); return object;
  }
  line([[-28, 0.1, 28], [0, 0.1, 0], [28, 0.1, 28]], '#fff3d5', 0.7);
  for (const x of [-0.95, 0.95]) line([[x - .3, .12, -.3], [x + .3, .12, -.3], [x + .3, .12, 1], [x - .3, .12, 1], [x - .3, .12, -.3]], '#f5e6cc', .5);
  for (let tier = 0; tier < 4; tier++) {
    const seats = mesh(new THREE.TorusGeometry(34 + tier * 1.4, .65, 5, 100), mat(tier % 2 ? '#8f9b8a' : '#a4ad98'), 0, 1.2 + tier * .95, 12);
    seats.rotation.x = Math.PI / 2;
  }
  for (const x of [-25, 25]) for (const z of [-7, 32]) {
    mesh(new THREE.CylinderGeometry(.12, .2, 15, 8), mat('#647b85'), x, 7.5, z);
    const lamps = mesh(new THREE.BoxGeometry(3.5, 1.2, .3), mat('#566b7a'), x, 15, z);
    lamps.lookAt(0, 5, 10);
    for (let i = 0; i < 4; i++) {
      const bulb = mesh(new THREE.BoxGeometry(.55, .65, .1), new THREE.MeshStandardMaterial({ color: '#fff4d2', emissive: '#fff0ca', emissiveIntensity: 3 }), (i - 1.5) * .77, 0, .22, lamps);
      bulb.castShadow = false;
    }
  }
  mesh(new THREE.PlaneGeometry(.8, 1.1), new THREE.MeshBasicMaterial({ color: '#a2f4df', transparent: true, opacity: .055, side: THREE.DoubleSide, depthWrite: false }), 0, 1.05, .08);
  line([[-.4, .5, .08], [-.4, 1.6, .08], [.4, 1.6, .08], [.4, .5, .08], [-.4, .5, .08]], '#a2f4df', .7);

  // Articulated stylized pitcher. This gesture is independent of model scoring.
  const pitcher = new THREE.Group(); pitcher.position.set(0, .38, 18); scene.add(pitcher);
  const torso = new THREE.Group(); torso.position.y = 1.04; pitcher.add(torso);
  mesh(new THREE.CapsuleGeometry(.24, .36, 5, 12), red, 0, .22, 0, torso);
  mesh(new THREE.SphereGeometry(.19, 20, 16), skin, 0, .83, -.015, torso);
  mesh(new THREE.SphereGeometry(.2, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), red, 0, .85, -.015, torso);
  mesh(new THREE.BoxGeometry(.32, .035, .18), red, 0, .86, -.18, torso);
  mesh(new THREE.BoxGeometry(.035, .42, .015), chalk, 0, .24, -.232, torso);
  const handSign = data.hand === 'Left' ? -1 : 1;
  function limb(parent, x, y, material, length, radius) {
    const pivot = new THREE.Group(); pivot.position.set(x, y, 0); parent.add(pivot);
    mesh(new THREE.CapsuleGeometry(radius, length - 2 * radius, 4, 10), material, 0, -length / 2, 0, pivot);
    return pivot;
  }
  const arm = limb(torso, handSign * .3, .48, red, .58, .09);
  const throwingHand = mesh(new THREE.SphereGeometry(.09, 12, 10), skin, 0, -.66, 0, arm);
  const gloveArm = limb(torso, -handSign * .3, .48, red, .55, .09);
  mesh(new THREE.SphereGeometry(.16, 12, 10), mat('#9c6d43'), 0, -.59, -.01, gloveArm);
  const leftLeg = limb(pitcher, -.14, 1, pants, .78, .115), rightLeg = limb(pitcher, .14, 1, pants, .78, .115);
  for (const leg of [leftLeg, rightLeg]) mesh(new THREE.BoxGeometry(.22, .12, .36), dark, 0, -.8, -.08, leg);

  const ball = new THREE.Group(); scene.add(ball);
  mesh(new THREE.SphereGeometry(.115, 24, 16), mat('#fff8e6', .42), 0, 0, 0, ball);
  const seamMat = new THREE.LineBasicMaterial({ color: '#c52840' });
  for (const sign of [-1, 1]) {
    const points = [];
    for (let i = 0; i <= 64; i++) {
      const a = i / 64 * Math.PI * 2;
      points.push(new THREE.Vector3(sign * .05 + .027 * Math.cos(2 * a), .099 * Math.cos(a), .099 * Math.sin(a)));
    }
    ball.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), seamMat));
  }
  const halo = mesh(new THREE.SphereGeometry(.18, 16, 12), new THREE.MeshBasicMaterial({ color: '#ffbf8e', transparent: true, opacity: .12, depthWrite: false }), 0, 0, 0, ball);
  halo.castShadow = false;
  const start = new THREE.Vector3();
  let endFraction = 1;
  function curve(t) {
    return new THREE.Vector3(...pitchPoint(t * endFraction, data, start));
  }
  const trajectory = line(Array.from({ length: 101 }, () => [0, 0, 0]), '#c82c38', 1);
  const reference = data.comparison ?? { RelSpeed: 90, HorzBreak: 0, InducedVertBreak: 0 };
  const ghost = line(Array.from({ length: 101 }, () => [0, 0, 0]), '#2e6fa6', .55);
  ghost.material = new THREE.LineDashedMaterial({ color: '#2e6fa6', transparent: true, opacity: .55, dashSize: .25, gapSize: .2 });
  function setPath(object, fraction) {
    const position = object.geometry.attributes.position;
    for (let i = 0; i <= 100; i++) { const p = curve(i / 100); position.setXYZ(i, p.x, p.y, p.z); }
    position.needsUpdate = true;
    object.geometry.setDrawRange(0, Math.max(0, Math.floor(100 * fraction) + 1));
    object.geometry.computeBoundingSphere();
  }
  function pose(t) {
    const wind = Math.sin(Math.PI * Math.min(t / .68, 1)), release = THREE.MathUtils.smoothstep(t, .4, .72);
    torso.rotation.x = -.13 * wind + .48 * release;
    torso.rotation.y = handSign * (.45 * wind - .6 * release);
    arm.rotation.x = -.35 - 2.4 * wind + 2.8 * release;
    arm.rotation.z = handSign * (-.2 - .6 * wind);
    gloveArm.rotation.x = -.9 + .6 * release;
    leftLeg.rotation.x = handSign > 0 ? -.65 * wind + .35 * release : -.1;
    rightLeg.rotation.x = handSign < 0 ? -.65 * wind + .35 * release : -.1;
    pitcher.position.z = 18 - .45 * release;
    scene.updateMatrixWorld(true);
  }
  pose(.61); throwingHand.getWorldPosition(start); start.z -= .05;
  endFraction = groundContactFraction(data, start);
  const referenceEnd = groundContactFraction(reference, start);
  ghost.geometry.setFromPoints(Array.from({ length: 101 }, (_, i) => new THREE.Vector3(...pitchPoint(i / 100 * referenceEnd, reference, start))));
  ghost.computeLineDistances();
  const arrival = mesh(new THREE.RingGeometry(.14, .19, 32), new THREE.MeshBasicMaterial({ color: '#c82c38', transparent: true, opacity: .85, side: THREE.DoubleSide, depthWrite: false }));
  arrival.position.copy(curve(1)); arrival.castShadow = false;
  const movement = document.getElementById('movement');
  movement.textContent = `Movimiento lateral: ${Math.abs(data.HorzBreak).toFixed(1)}″ · Vertical inducido: ${data.InducedVertBreak > 0 ? '+' : ''}${data.InducedVertBreak.toFixed(1)}″`;
  const play = document.getElementById('play'), rate = document.getElementById('rate'), status = document.getElementById('status');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused = reduced.matches, elapsed = paused ? 1.05 + flightSeconds(data, start) * endFraction / .25 : 0;
  let previous = null, disposed = false;
  const windupDuration = 1.05, flightDuration = flightSeconds(data, start) * endFraction;
  function sync() { play.textContent = paused ? 'Reproducir' : 'Pausar'; play.setAttribute('aria-label', paused ? 'Reproducir escena 3D' : 'Pausar escena 3D'); }
  sync();
  play.onclick = () => { paused = !paused; previous = null; sync(); };
  document.getElementById('replay').onclick = () => { elapsed = 0; paused = false; previous = null; sync(); };
  reduced.addEventListener('change', event => { if (event.matches) { paused = true; sync(); } });
  document.getElementById('camera').onchange = event => {
    const positions = { side: [20, 12, -6], catcher: [3, 3.4, -8], pitcher: [2, 4.8, 24] };
    camera.position.set(...positions[event.target.value]); orbit.target.set(0, 1.3, event.target.value === 'pitcher' ? 6 : 11); orbit.update();
  };
  const resize = new ResizeObserver(() => {
    camera.aspect = stage.clientWidth / stage.clientHeight; camera.updateProjectionMatrix();
    renderer.setSize(stage.clientWidth, stage.clientHeight, false);
  }); resize.observe(stage);
  function frame(now) {
    if (disposed) return;
    requestAnimationFrame(frame);
    const dt = previous === null ? 0 : Math.min((now - previous) / 1000, .06); previous = now;
    if (!paused && !document.hidden) elapsed += dt;
    const flight = flightDuration / Number(rate.value), total = windupDuration + flight + 1.1;
    if (elapsed > total) elapsed = 0;
    if (elapsed < windupDuration) {
      pose(elapsed / windupDuration * .61); throwingHand.getWorldPosition(ball.position);
      trajectory.geometry.setDrawRange(0, 0); status.textContent = 'Preparación';
    } else {
      const t = Math.min(1, (elapsed - windupDuration) / flight);
      pose(.61 + .39 * t); ball.position.copy(curve(t)); setPath(trajectory, t);
      status.textContent = t < 1 ? 'Pelota en vuelo' : endFraction < 1 ? 'Contacto con el suelo (ilustrado)' : 'Llegada al plato';
    }
    if (!paused) ball.rotation.x += dt * 13;
    orbit.update(); renderer.render(scene, camera);
  } requestAnimationFrame(frame);
  window.addEventListener('pagehide', () => { disposed = true; resize.disconnect(); orbit.dispose(); renderer.dispose(); });
}
try { startScene(); } catch (error) {
  canvas.style.display = 'none'; document.getElementById('unavailable').style.display = 'flex';
  document.getElementById('play').disabled = true; document.getElementById('replay').disabled = true;
  document.getElementById('status').textContent = 'Vista 3D no disponible';
  console.error('No se pudo iniciar la escena 3D', error);
}
