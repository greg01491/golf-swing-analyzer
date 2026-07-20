import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { Landmarks } from '../api'

// Bones as (jointA, jointB, radius-in-metres). Torso sides (shoulder->hip)
// are included so the trunk reads as a solid body, not just a spine line.
const BONES: [string, string, number][] = [
  ['Head', 'Neck', 0.045],
  ['Neck', 'RShoulder', 0.05],
  ['Neck', 'LShoulder', 0.05],
  ['RShoulder', 'RElbow', 0.045],
  ['RElbow', 'RWrist', 0.035],
  ['LShoulder', 'LElbow', 0.045],
  ['LElbow', 'LWrist', 0.035],
  ['Neck', 'Hip', 0.07],
  ['RShoulder', 'RHip', 0.055],
  ['LShoulder', 'LHip', 0.055],
  ['Hip', 'RHip', 0.06],
  ['Hip', 'LHip', 0.06],
  ['RHip', 'RKnee', 0.07],
  ['RKnee', 'RAnkle', 0.05],
  ['LHip', 'LKnee', 0.07],
  ['LKnee', 'LAnkle', 0.05],
  ['RAnkle', 'RBigToe', 0.03],
  ['LAnkle', 'LBigToe', 0.03],
]
const JOINTS = [
  'Neck',
  'RShoulder',
  'LShoulder',
  'RElbow',
  'LElbow',
  'RWrist',
  'LWrist',
  'Hip',
  'RHip',
  'LHip',
  'RKnee',
  'LKnee',
  'RAnkle',
  'LAnkle',
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
    let cx = 0
    let cz = 0
    let count = 0
    let minY = Infinity
    for (const f of landmarks.frames) {
      for (const m of f) {
        if (m[0] == null) continue
        cx += m[horiz[0]] as number
        cz += m[horiz[1]] as number
        count++
        minY = Math.min(minY, (m[up] as number) * sign)
      }
    }
    cx /= count || 1
    cz /= count || 1
    if (!Number.isFinite(minY)) minY = 0

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
    camera.position.set(0, 1.1, 3.4)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(width, height)
    mount.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, 1.0, 0)
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

    // --- humanoid meshes (body mode) ---
    // low roughness + a touch of metalness reads as the smooth injection-
    // moulded mannequin look rather than matte tubes
    const limbMat = track(
      new THREE.MeshStandardMaterial({ color: '#eef1f5', roughness: 0.35, metalness: 0.1 }),
    )
    const jointMat = track(
      new THREE.MeshStandardMaterial({ color: '#6d5cf6', roughness: 0.3, metalness: 0.15 }),
    )
    const headMat = track(
      new THREE.MeshStandardMaterial({ color: '#f4f6fa', roughness: 0.3, metalness: 0.1 }),
    )

    const boneMeshes: { mesh: THREE.Mesh; a: string; b: string }[] = []
    const jointMeshes: { mesh: THREE.Mesh; name: string }[] = []
    let headMesh: THREE.Mesh | null = null
    const bodyGroup = new THREE.Group()
    const skeletonGroup = new THREE.Group()

    if (mode === 'body') {
      for (const [a, b, r] of BONES) {
        // unit-length capsule along +Y, scaled to bone length each frame; the
        // rounded caps overlap the joint spheres so limbs blend smoothly into
        // joints instead of showing hard tube ends
        const geo = track(new THREE.CapsuleGeometry(r, 1, 6, 16))
        const mesh = new THREE.Mesh(geo, limbMat)
        boneMeshes.push({ mesh, a, b })
        bodyGroup.add(mesh)
      }
      for (const name of JOINTS) {
        const geo = track(new THREE.SphereGeometry(0.05, 16, 12))
        const mesh = new THREE.Mesh(geo, jointMat)
        jointMeshes.push({ mesh, name })
        bodyGroup.add(mesh)
      }
      headMesh = new THREE.Mesh(track(new THREE.SphereGeometry(0.11, 20, 16)), headMat)
      bodyGroup.add(headMesh)
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
        for (const { mesh, a, b } of boneMeshes) {
          const pa = at(a)
          const pb = at(b)
          if (pa && pb) {
            mesh.visible = true
            orient(mesh, pa, pb)
          } else {
            mesh.visible = false
          }
        }
        for (const { mesh, name } of jointMeshes) {
          const p = at(name)
          if (p) {
            mesh.visible = true
            mesh.position.copy(p)
          } else {
            mesh.visible = false
          }
        }
        if (headMesh) {
          const head = at('Head') ?? at('Neck')
          if (head) {
            headMesh.visible = true
            headMesh.position.copy(head)
          } else {
            headMesh.visible = false
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
