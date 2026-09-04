import { useRef, useEffect } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { useProjectStore } from '../stores/projectStore'

export default function WalkthroughCamera() {
  const { camera } = useThree()
  const { viewMode, isPlaying } = useProjectStore()
  const pathRef = useRef<THREE.CatmullRomCurve3 | null>(null)
  const progressRef = useRef(0)
  const keysRef = useRef({ w: false, a: false, s: false, d: false })

  useEffect(() => {
    if (viewMode === 'walkthrough') {
      pathRef.current = new THREE.CatmullRomCurve3([
        new THREE.Vector3(-4, 1.7, -4),
        new THREE.Vector3(-2, 1.7, -2),
        new THREE.Vector3(0, 1.7, 0),
        new THREE.Vector3(2, 1.7, 2),
        new THREE.Vector3(4, 1.7, 4),
        new THREE.Vector3(4, 1.7, -4),
        new THREE.Vector3(-4, 1.7, 4),
      ])
      progressRef.current = 0
    }
  }, [viewMode])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase()
      if (['w', 'a', 's', 'd'].includes(key)) {
        keysRef.current[key as keyof typeof keysRef.current] = true
      }
    }
    const handleKeyUp = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase()
      if (['w', 'a', 's', 'd'].includes(key)) {
        keysRef.current[key as keyof typeof keysRef.current] = false
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [])

  useFrame((state, delta) => {
    if (viewMode === 'walkthrough') {
      if (isPlaying && pathRef.current) {
        progressRef.current += delta * 0.05
        if (progressRef.current > 1) progressRef.current = 0

        const point = pathRef.current.getPointAt(progressRef.current)
        const lookAt = pathRef.current.getPointAt((progressRef.current + 0.01) % 1)

        camera.position.lerp(point, 0.1)
        camera.lookAt(lookAt)
      } else {
        const speed = 3 * delta
        const direction = new THREE.Vector3()
        const front = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion)
        front.y = 0
        front.normalize()
        const right = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion)
        right.y = 0
        right.normalize()

        if (keysRef.current.w) direction.add(front)
        if (keysRef.current.s) direction.sub(front)
        if (keysRef.current.d) direction.add(right)
        if (keysRef.current.a) direction.sub(right)

        if (direction.length() > 0) {
          direction.normalize()
          camera.position.add(direction.multiplyScalar(speed))
        }

        camera.position.y = 1.7
      }
    }
  })

  return null
}
