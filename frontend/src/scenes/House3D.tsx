import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useProjectStore } from '../stores/projectStore'

function WallMesh({ start, end, height = 2.8, thickness = 0.15 }: {
  start: [number, number, number]
  end: [number, number, number]
  height?: number
  thickness?: number
}) {
  const meshRef = useRef<THREE.Mesh>(null)

  const { position, rotation, scale } = useMemo(() => {
    const startVec = new THREE.Vector3(...start)
    const endVec = new THREE.Vector3(...end)
    const direction = new THREE.Vector3().subVectors(endVec, startVec)
    const length = direction.length()
    const center = new THREE.Vector3().addVectors(startVec, endVec).multiplyScalar(0.5)
    const angle = Math.atan2(direction.x, direction.z)

    return {
      position: [center.x, height / 2, center.z] as [number, number, number],
      rotation: [0, angle, 0] as [number, number, number],
      scale: [thickness, height, length] as [number, number, number]
    }
  }, [start, end, height, thickness])

  return (
    <group>
      <mesh ref={meshRef} position={position} rotation={rotation} scale={scale} castShadow receiveShadow>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color="#f5f5f0" roughness={0.9} />
      </mesh>
      {Array.from({ length: Math.floor(scale[2] / 0.4) }).map((_, i) => (
        <mesh 
          key={i}
          position={[
            position[0] + (i * 0.4 - scale[2]/2) * Math.sin(rotation[1]) * 0.1,
            position[1],
            position[2] + (i * 0.4 - scale[2]/2) * Math.cos(rotation[1]) * 0.1
          ]}
          rotation={rotation}
          scale={[thickness + 0.02, height, 0.05]}
        >
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial color="#e8e8e0" roughness={0.8} />
        </mesh>
      ))}
    </group>
  )
}

function FloorMesh({ points }: { points: [number, number, number][] }) {
  const shape = useMemo(() => {
    const s = new THREE.Shape()
    if (points.length > 0) {
      s.moveTo(points[0][0], points[0][2])
      for (let i = 1; i < points.length; i++) {
        s.lineTo(points[i][0], points[i][2])
      }
      s.closePath()
    }
    return s
  }, [points])

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow>
      <shapeGeometry args={[shape]} />
      <meshStandardMaterial color="#d4a574" roughness={0.6} side={THREE.DoubleSide} />
    </mesh>
  )
}

function FurnitureMesh({ item }: { item: any }) {
  const color = item.color || '#ffffff'
  const [w, h, d] = item.dimensions || [1, 1, 1]

  const renderGeometry = () => {
    switch (item.category) {
      case 'seating':
        return (
          <group>
            <mesh position={[0, h*0.2, 0]} castShadow>
              <boxGeometry args={[w, h*0.4, d]} />
              <meshStandardMaterial color={color} roughness={0.8} />
            </mesh>
            <mesh position={[0, h*0.6, -d*0.35]} castShadow>
              <boxGeometry args={[w, h*0.6, d*0.1]} />
              <meshStandardMaterial color={color} roughness={0.8} />
            </mesh>
            <mesh position={[0, h*0.45, 0]} castShadow>
              <boxGeometry args={[w*0.9, h*0.1, d*0.9]} />
              <meshStandardMaterial color={color} roughness={0.9} />
            </mesh>
            {[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([lx, lz], i) => (
              <mesh key={i} position={[lx * w*0.4, 0, lz * d*0.4]} castShadow>
                <cylinderGeometry args={[0.02, 0.015, h*0.2, 8]} />
                <meshStandardMaterial color="#8B4513" metalness={0.3} />
              </mesh>
            ))}
          </group>
        )
      case 'bed':
        return (
          <group>
            <mesh position={[0, h*0.3, 0]} castShadow>
              <boxGeometry args={[w, h*0.3, d]} />
              <meshStandardMaterial color="#f0f0f0" roughness={0.9} />
            </mesh>
            <mesh position={[0, h*0.6, -d*0.45]} castShadow>
              <boxGeometry args={[w, h*0.6, d*0.08]} />
              <meshStandardMaterial color={color} roughness={0.7} />
            </mesh>
            {[-0.3, 0.3].map((x, i) => (
              <mesh key={i} position={[x, h*0.5, -d*0.25]} castShadow>
                <boxGeometry args={[w*0.25, h*0.15, d*0.15]} />
                <meshStandardMaterial color="#ffffff" roughness={1} />
              </mesh>
            ))}
            <mesh position={[0, h*0.1, 0]} castShadow>
              <boxGeometry args={[w, h*0.15, d]} />
              <meshStandardMaterial color={color} roughness={0.6} />
            </mesh>
          </group>
        )
      case 'table':
        return (
          <group>
            <mesh position={[0, h*0.45, 0]} castShadow>
              <boxGeometry args={[w, h*0.05, d]} />
              <meshStandardMaterial color={color} roughness={0.5} />
            </mesh>
            {[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([lx, lz], i) => (
              <mesh key={i} position={[lx * w*0.4, h*0.2, lz * d*0.4]} castShadow>
                <boxGeometry args={[0.05, h*0.4, 0.05]} />
                <meshStandardMaterial color={color} roughness={0.5} />
              </mesh>
            ))}
          </group>
        )
      default:
        return (
          <mesh castShadow>
            <boxGeometry args={[w, h, d]} />
            <meshStandardMaterial color={color} roughness={0.7} />
          </mesh>
        )
    }
  }

  return (
    <group 
      position={item.position}
      rotation={item.rotation}
      scale={item.scale}
    >
      {renderGeometry()}
    </group>
  )
}

export default function House3D() {
  const { walls, furniture } = useProjectStore()

  const floorPoints = useMemo(() => {
    if (walls.length === 0) return [] as [number, number, number][]
    const xs = walls.flatMap(w => [w.start[0], w.end[0]])
    const zs = walls.flatMap(w => [w.start[2], w.end[2]])
    const minX = Math.min(...xs), maxX = Math.max(...xs)
    const minZ = Math.min(...zs), maxZ = Math.max(...zs)
    return [
      [minX, 0, minZ],
      [maxX, 0, minZ],
      [maxX, 0, maxZ],
      [minX, 0, maxZ],
    ] as [number, number, number][]
  }, [walls])

  return (
    <group>
      <ambientLight intensity={0.4} />
      <directionalLight 
        position={[10, 20, 10]} 
        intensity={1.5} 
        castShadow 
        shadow-mapSize={[2048, 2048]}
      />
      <pointLight position={[-10, 10, -10]} intensity={0.5} color="#ffd4a3" />

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} receiveShadow>
        <planeGeometry args={[100, 100]} />
        <meshStandardMaterial color="#e0e0e0" />
      </mesh>

      {floorPoints.length > 0 && <FloorMesh points={floorPoints} />}

      {walls.map((wall) => (
        <WallMesh 
          key={wall.id}
          start={wall.start}
          end={wall.end}
          height={wall.height}
          thickness={wall.thickness}
        />
      ))}

      {walls.length === 0 && (
        <>
          <WallMesh start={[-5, 0, -5]} end={[5, 0, -5]} />
          <WallMesh start={[5, 0, -5]} end={[5, 0, 5]} />
          <WallMesh start={[5, 0, 5]} end={[-5, 0, 5]} />
          <WallMesh start={[-5, 0, 5]} end={[-5, 0, -5]} />
          <WallMesh start={[-5, 0, 0]} end={[2, 0, 0]} />
          <WallMesh start={[2, 0, 0]} end={[2, 0, 5]} />
        </>
      )}

      {furniture.map((item) => (
        <FurnitureMesh key={item.id} item={item} />
      ))}

      <gridHelper args={[50, 50, '#cccccc', '#eeeeee']} position={[0, 0.001, 0]} />
    </group>
  )
}
