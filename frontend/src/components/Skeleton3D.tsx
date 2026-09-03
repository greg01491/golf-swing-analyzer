import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { Landmarks } from '../api'

// Bones as (jointA, jointB, radius-in-metres). Torso sides (shoulder->hip)
// are included so the trunk reads as a solid body, not just a spine line.
// Radii (metres) kept slim so the figure reads as an athletic mannequin, not
// a bloated balloon -- roughly half real limb thickness, since the capsules
// plus joint spheres visually fatten it.
const BONES: [string, string, number][] = [
  ['Head', 'Neck', 0.028],
  ['Neck', 'RShoulder', 0.03],
  ['Neck', 'LShoulder', 0.03],
  ['RShoulder', 'RElbow', 0.028],
  ['RElbow', 'RWrist', 0.022],
  ['LShoulder', 'LElbow', 0.028],
  ['LElbow', 'LWrist', 0.022],
  ['Neck', 'Hip', 0.045],
  ['RShoulder', 'RHip', 0.035],
  ['LShoulder', 'LHip', 0.035],
  ['Hip', 'RHip', 0.038],
  ['Hip', 'LHip', 0.038],
  ['RHip', 'RKnee', 0.045],
  ['RKnee', 'RAnkle', 0.032],
  ['LHip', 'LKnee', 0.045],
  ['LKnee', 'LAnkle', 0.032],
  ['RAnkle', 'RBigToe', 0.02],
  ['LAnkle', 'LBigToe', 0.02],
]

interface Props {
  landmarks: Landmarks
  time: number
  width?: number
  height?: number
  idealFrame?: Record<string, [number, number, number]> | null
}

type Vec3 = [number, number, number]

/** Which raw axis points up, and its sign, from the head-vs-ankle spread on a
 * mid-clip frame -- mirrors the backend's vertical_axis. */
function upAxis(lm: Landmarks): { axis: number; sign: number } {
  const headIdx = lm.marker_names.indexOf(lm.marker_names.includes('Head') ? 'Head' : 'Neck')
  const ankleIdx = lm.marker_names.indexOf('RAnkle')
  if (headIdx < 0 || ankleIdx < 0) return { axis: 1, sign: -1 }
  const mid = Math.floor(lm.frames.length / 2)
  const h = lm.frames[mid][headIdx]
  const a = lm.frames[mid][ankleIdx]
  let axis = 1
  let best = 0
  for (let i = 0; i < 3; i++) {
    const d = (h[i] ?? 0) - (a[i] ?? 0)
    if (Math.abs(d) > Math.abs(best)) {
      axis = i
      best = d
    }
  }
  return { axis, sign: best >= 0 ? 1 : -1 }
}

export default function Skeleton3D({ landmarks, time, idealFrame, width = 420, height = 420 }: Props) {
  const mountRef = useRef<HTMLDivElement>(null)
  const timeRef = useRef(time)
  timeRef.current = time
  const idealRef = useRef(idealFrame)
  idealRef.current = idealFrame
  const [mode, setMode] = useState<'body' | 'skeleton'>('body')

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const { axis: up, sign } = upAxis(landmarks)
    const horiz = [0, 1, 2].filter((i) => i !== up)

    // Frame the figure: centre X/Z on the whole-clip mean (so lateral sway
    // still shows without drifting out of view) and drop the feet to y=0.
    // Also track the vertical extent (bounding box) and mean height so the
    // camera can be aimed at the body's centre and pulled back just far
    // enough to fill the view -- otherwise a bent-over golfer sits low with
    // a lot of empty space above them.
    let cx = 0
    let cz = 0
    let cyRaw = 0
    let count = 0
    let minY = Infinity
    let maxY = -Infinity
    for (const f of landmarks.frames) {
      for (const m of f) {
        if (m[0] == null) continue
        cx += m[horiz[0]] as number
        cz += m[horiz[1]] as number
        const y = (m[up] as number) * sign
        cyRaw += y
        count++
        minY = Math.min(minY, y)
        maxY = Math.max(maxY, y)
      }
    }
    cx /= count || 1
    cz /= count || 1
    cyRaw /= count || 1
    if (!Number.isFinite(minY)) minY = 0
    if (!Number.isFinite(maxY)) maxY = minY + 1.7
    // world coords put the feet at y=0 (minY offset), so these are heights
    // above the mat: the swing's full vertical span and the body's mean.
    const modelHeight = Math.max(maxY - minY, 0.5)
    const centerY = cyRaw - minY

    const toWorld = (m: readonly (number | null)[]): THREE.Vector3 | null =>
      m[0] == null
        ? null
        : new THREE.Vector3(
            (m[horiz[0]] as number) - cx,
            (m[up] as number) * sign - minY,
            (m[horiz[1]] as number) - cz,
          )

    // --- scene / camera / renderer ---
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#0a0e12')

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
    // Aim at the body's vertical centre and pull back just enough that its
    // full height fills the frame (fov 45deg) with a small margin, so the
    // figure is centred instead of sitting low with dead space above.
    const fitDistance = (modelHeight / 2 / Math.tan((45 * Math.PI) / 180 / 2)) * 1.3
    camera.position.set(0, centerY, fitDistance)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(width, height)
    mount.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, centerY, 0)
    controls.enablePan = false
    controls.minDistance = 1.5
    controls.maxDistance = 8
    controls.update()

    scene.add(new THREE.AmbientLight(0xffffff, 0.7))
    const key = new THREE.DirectionalLight(0xffffff, 1.1)
    key.position.set(2, 4, 3)
    scene.add(key)

    // green hitting mat
    const mat = new THREE.Mesh(
      new THREE.PlaneGeometry(3, 3),
      new THREE.MeshStandardMaterial({ color: '#1f7a3d' }),
    )
    mat.rotation.x = -Math.PI / 2
    scene.add(mat)

    const disposables: { dispose: () => void }[] = []
    const track = <T extends THREE.BufferGeometry | THREE.Material>(x: T): T => {
      disposables.push(x)
      return x
    }

    // --- humanoid mannequin (body mode) ---
    // A smooth, stylised avatar (Sportsbox-like): tapered rounded capsules built
    // with LatheGeometry so limbs blend into their joints without hard tube
    // ends. Matte white throughout, short black neck, thin purple joint rings.
    const whiteMat = track(
      new THREE.MeshStandardMaterial({ color: '#eef0f4', roughness: 0.9, metalness: 0.0 }),
    )
    const blackMat = track(
      new THREE.MeshStandardMaterial({ color: '#15181d', roughness: 0.6, metalness: 0.05 }),
    )
    const ringMat = track(
      new THREE.MeshStandardMaterial({ color: '#7c3aed', roughness: 0.45, metalness: 0.15 }),
    )

    // A unit-height (local y in [-0.5, 0.5]) rounded capsule whose radius tapers
    // from rA (joint a, bottom) to rB (joint b, top), with hemispherical caps so
    // adjacent parts overlap into smooth blends rather than hard intersections.
    const capsuleGeo = (rA: number, rB: number): THREE.LatheGeometry => {
      const pts: THREE.Vector2[] = []
      const capSeg = 7
      for (let i = 0; i <= capSeg; i++) {
        const t = (Math.PI / 2) * (i / capSeg)
        pts.push(new THREE.Vector2(Math.sin(t) * rA, -Math.cos(t) * rA)) // bottom cap
      }
      const midSeg = 6
      for (let i = 1; i <= midSeg; i++) {
        const t = i / midSeg
        pts.push(new THREE.Vector2(rA + (rB - rA) * t, t)) // tapered shaft, y: 0..1
      }
      for (let i = 1; i <= capSeg; i++) {
        const t = (Math.PI / 2) * (i / capSeg)
        pts.push(new THREE.Vector2(Math.cos(t) * rB, 1 + Math.sin(t) * rB)) // top cap
      }
      for (const p of pts) p.y -= 0.5 // centre the shaft on the origin
      return track(new THREE.LatheGeometry(pts, 26))
    }

    const segMeshes: { mesh: THREE.Mesh; a: string; b: string }[] = []
    const ringMeshes: { mesh: THREE.Mesh; at: string; a: string; b: string }[] = []
    const handMeshes: { mesh: THREE.Mesh; wrist: string; elbow: string }[] = []
    const footMeshes: { mesh: THREE.Mesh; ankle: string; toe: string }[] = []
    let headMesh: THREE.Mesh | null = null
    let neckMesh: THREE.Mesh | null = null
    const bodyGroup = new THREE.Group()
    const skeletonGroup = new THREE.Group()

    if (mode === 'body') {
      // Smooth tapered limbs (thicker near the body, narrowing toward the far
      // joint) plus a single rounded tapered torso and a thin pelvis block.
      // Once oriented, local +Y maps to joint b, so rB is the radius at b.
      const SEGMENTS: { a: string; b: string; rA: number; rB: number }[] = [
        { a: 'Neck', b: 'Hip', rA: 0.135, rB: 0.092 }, // torso: wide shoulders -> waist
        { a: 'RHip', b: 'LHip', rA: 0.075, rB: 0.075 }, // pelvis: thin rounded block
        { a: 'RShoulder', b: 'RElbow', rA: 0.05, rB: 0.032 }, // upper arms
        { a: 'LShoulder', b: 'LElbow', rA: 0.05, rB: 0.032 },
        { a: 'RElbow', b: 'RWrist', rA: 0.032, rB: 0.022 }, // forearms (thinner)
        { a: 'LElbow', b: 'LWrist', rA: 0.032, rB: 0.022 },
        { a: 'RHip', b: 'RKnee', rA: 0.082, rB: 0.05 }, // thighs: wide hips -> knees
        { a: 'LHip', b: 'LKnee', rA: 0.082, rB: 0.05 },
        { a: 'RKnee', b: 'RAnkle', rA: 0.052, rB: 0.033 }, // lower legs
        { a: 'LKnee', b: 'LAnkle', rA: 0.052, rB: 0.033 },
      ]
      for (const s of SEGMENTS) {
        const mesh = new THREE.Mesh(capsuleGeo(s.rA, s.rB), whiteMat)
        segMeshes.push({ mesh, a: s.a, b: s.b })
        bodyGroup.add(mesh)
      }

      // Thin purple ring around each major joint; torus axis = adjacent limb dir.
      const RINGS: { at: string; a: string; b: string; r: number }[] = [
        { at: 'RShoulder', a: 'RShoulder', b: 'RElbow', r: 0.052 },
        { at: 'LShoulder', a: 'LShoulder', b: 'LElbow', r: 0.052 },
        { at: 'RElbow', a: 'RElbow', b: 'RWrist', r: 0.036 },
        { at: 'LElbow', a: 'LElbow', b: 'LWrist', r: 0.036 },
        { at: 'RWrist', a: 'RElbow', b: 'RWrist', r: 0.026 },
        { at: 'LWrist', a: 'LElbow', b: 'LWrist', r: 0.026 },
        { at: 'RHip', a: 'RHip', b: 'RKnee', r: 0.07 },
        { at: 'LHip', a: 'LHip', b: 'LKnee', r: 0.07 },
        { at: 'RKnee', a: 'RKnee', b: 'RAnkle', r: 0.056 },
        { at: 'LKnee', a: 'LKnee', b: 'LAnkle', r: 0.056 },
        { at: 'RAnkle', a: 'RKnee', b: 'RAnkle', r: 0.04 },
        { at: 'LAnkle', a: 'LKnee', b: 'LAnkle', r: 0.04 },
      ]
      for (const rg of RINGS) {
        const geo = track(new THREE.TorusGeometry(rg.r, 0.008, 8, 28))
        const mesh = new THREE.Mesh(geo, ringMat)
        ringMeshes.push({ mesh, at: rg.at, a: rg.a, b: rg.b })
        bodyGroup.add(mesh)
      }

      // Egg-shaped white head (smooth vertical ellipsoid, no features).
      headMesh = new THREE.Mesh(track(new THREE.SphereGeometry(0.093, 28, 20)), whiteMat)
      headMesh.scale.set(0.82, 1.16, 0.9)
      bodyGroup.add(headMesh)

      // Short, narrow black neck.
      neckMesh = new THREE.Mesh(track(new THREE.CylinderGeometry(0.028, 0.032, 1, 18)), blackMat)
      bodyGroup.add(neckMesh)

      // Rounded paddle hands (no fingers).
      for (const [wrist, elbow] of [
        ['RWrist', 'RElbow'],
        ['LWrist', 'LElbow'],
      ] as const) {
        const mesh = new THREE.Mesh(track(new THREE.SphereGeometry(0.04, 18, 14)), whiteMat)
        mesh.scale.set(0.62, 1.15, 0.36)
        handMeshes.push({ mesh, wrist, elbow })
        bodyGroup.add(mesh)
      }

      // Wedge feet with flat soles (flattened box along ankle -> toe).
      for (const [ankle, toe] of [
        ['RAnkle', 'RBigToe'],
        ['LAnkle', 'LBigToe'],
      ] as const) {
        const mesh = new THREE.Mesh(track(new THREE.BoxGeometry(0.08, 1, 0.055)), whiteMat)
        footMeshes.push({ mesh, ankle, toe })
        bodyGroup.add(mesh)
      }

      scene.add(bodyGroup)
    } else {
      // thin-line skeleton
      const lineMat = track(new THREE.LineBasicMaterial({ color: '#4ade80' }))
      const geo = track(new THREE.BufferGeometry())
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(BONES.length * 6), 3))
      const lines = new THREE.LineSegments(geo, lineMat)
      skeletonGroup.add(lines)
      scene.add(skeletonGroup)
      ;(skeletonGroup.userData as { geo: THREE.BufferGeometry }).geo = geo
    }

    // ideal-pose ghost (amber lines)
    const ghostMat = track(new THREE.LineBasicMaterial({ color: '#fbbf24' }))
    const ghostGeo = track(new THREE.BufferGeometry())
    ghostGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(BONES.length * 6), 3))
    const ghostLines = new THREE.LineSegments(ghostGeo, ghostMat)
    ghostLines.visible = false
    scene.add(ghostLines)

    const Y = new THREE.Vector3(0, 1, 0)
    const Z = new THREE.Vector3(0, 0, 1)
    const orient = (mesh: THREE.Mesh, a: THREE.Vector3, b: THREE.Vector3) => {
      const dir = new THREE.Vector3().subVectors(b, a)
      const len = dir.length() || 1e-6
      mesh.position.copy(a).addScaledVector(dir, 0.5)
      mesh.quaternion.setFromUnitVectors(Y, dir.clone().normalize())
      mesh.scale.set(1, len, 1)
    }

    const nameIdx = (n: string) => landmarks.marker_names.indexOf(n)

    const updateLines = (
      geo: THREE.BufferGeometry,
      lookup: (n: string) => THREE.Vector3 | null,
    ) => {
      const pos = geo.getAttribute('position') as THREE.BufferAttribute
      let i = 0
      for (const [a, b] of BONES) {
        const pa = lookup(a)
        const pb = lookup(b)
        if (pa && pb) {
          pos.setXYZ(i, pa.x, pa.y, pa.z)
          pos.setXYZ(i + 1, pb.x, pb.y, pb.z)
        } else {
          pos.setXYZ(i, 0, 0, 0)
          pos.setXYZ(i + 1, 0, 0, 0)
        }
        i += 2
      }
      pos.needsUpdate = true
    }

    let raf = 0
    const renderLoop = () => {
      const fi = Math.min(
        landmarks.frames.length - 1,
        Math.max(0, Math.round(timeRef.current * landmarks.fps)),
      )
      const frame = landmarks.frames[fi]
      const at = (n: string): THREE.Vector3 | null => {
        const idx = nameIdx(n)
        return idx < 0 ? null : toWorld(frame[idx])
      }

      if (mode === 'body') {
        for (const { mesh, a, b } of segMeshes) {
          const pa = at(a)
          const pb = at(b)
          if (pa && pb) {
            mesh.visible = true
            orient(mesh, pa, pb)
          } else {
            mesh.visible = false
          }
        }
        for (const { mesh, at: joint, a, b } of ringMeshes) {
          const p = at(joint)
          const pa = at(a)
          const pb = at(b)
          if (p && pa && pb) {
            mesh.visible = true
            mesh.position.copy(p)
            mesh.quaternion.setFromUnitVectors(Z, new THREE.Vector3().subVectors(pb, pa).normalize())
          } else {
            mesh.visible = false
          }
        }
        // head + short neck, oriented along the neck->head (spine top) axis
        const neckP = at('Neck')
        const headP = at('Head') ?? neckP
        if (headMesh && neckMesh && neckP && headP) {
          const spine = new THREE.Vector3().subVectors(headP, neckP)
          const len = spine.length() || 1e-6
          const dir = spine.clone().normalize()
          neckMesh.visible = true
          orient(neckMesh, neckP, neckP.clone().addScaledVector(dir, len * 0.45))
          headMesh.visible = true
          headMesh.position.copy(neckP).addScaledVector(dir, len * 0.82)
          headMesh.quaternion.setFromUnitVectors(Y, dir)
        } else {
          if (headMesh) headMesh.visible = false
          if (neckMesh) neckMesh.visible = false
        }
        // paddle hands, just past the wrist along the forearm
        for (const { mesh, wrist, elbow } of handMeshes) {
          const pw = at(wrist)
          const pe = at(elbow)
          if (pw && pe) {
            mesh.visible = true
            const dir = new THREE.Vector3().subVectors(pw, pe).normalize()
            mesh.position.copy(pw).addScaledVector(dir, 0.05)
            mesh.quaternion.setFromUnitVectors(Y, dir)
          } else {
            mesh.visible = false
          }
        }
        // wedge feet, ankle -> big toe
        for (const { mesh, ankle, toe } of footMeshes) {
          const pa = at(ankle)
          const pt = at(toe)
          if (pa && pt) {
            mesh.visible = true
            const dir = new THREE.Vector3().subVectors(pt, pa)
            const len = dir.length() || 1e-6
            mesh.position.copy(pa).addScaledVector(dir, 0.5)
            mesh.quaternion.setFromUnitVectors(Y, dir.clone().normalize())
            mesh.scale.set(1, Math.max(len, 0.14), 1)
          } else {
            mesh.visible = false
          }
        }
      } else {
        updateLines((skeletonGroup.userData as { geo: THREE.BufferGeometry }).geo, at)
      }

      const ideal = idealRef.current
      if (ideal) {
        ghostLines.visible = true
        updateLines(ghostGeo, (n) => {
          const xyz = ideal[n] as Vec3 | undefined
          return xyz ? toWorld(xyz) : null
        })
      } else {
        ghostLines.visible = false
      }

      controls.update()
      renderer.render(scene, camera)
      raf = requestAnimationFrame(renderLoop)
    }
    raf = requestAnimationFrame(renderLoop)

    return () => {
      cancelAnimationFrame(raf)
      controls.dispose()
      renderer.dispose()
      for (const d of disposables) d.dispose()
      mat.geometry.dispose()
      ;(mat.material as THREE.Material).dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
    }
  }, [landmarks, width, height, mode])

  return (
    <div className="skeleton-canvas">
      <div className="figure-mode">
        <button className={mode === 'body' ? 'active' : ''} onClick={() => setMode('body')}>
          body
        </button>
        <button className={mode === 'skeleton' ? 'active' : ''} onClick={() => setMode('skeleton')}>
          skeleton
        </button>
      </div>
      <div ref={mountRef} style={{ width, height }} />
      <p className="muted azimuth">drag to rotate · scroll to zoom</p>
      {idealFrame && (
        <div className="ghost-legend">
          <span className="swatch actual" /> you &nbsp;
          <span className="swatch ideal" /> reference
        </div>
      )}
    </div>
  )
}
