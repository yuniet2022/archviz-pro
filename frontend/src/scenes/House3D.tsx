import { useMemo } from 'react'
import * as THREE from 'three'
import { useProjectStore } from '../stores/projectStore'

function WallMesh({ id, start, end, height = 2.8, thickness = 0.15 }: {
  id: string
  start: [number, number, number]
  end: [number, number, number]
  height?: number
  thickness?: number
}) {
  const selected = useProjectStore(s=>s.selectedElementId===id)
  const plan = useProjectStore(s=>s.floorPlan)
  const openings = [...(plan?.doors??[]),...(plan?.windows??[])].filter(o=>o.wall_id===id)

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

  const length=scale[2]
  const edges=[...new Set([0,length,...openings.flatMap(o=>[
    Math.max(0,o.position*length-o.width/2),Math.min(length,o.position*length+o.width/2)
  ])])].sort((a,b)=>a-b)
  const pieces:{from:number;to:number;low:number;high:number}[]=[]
  for(let i=0;i<edges.length-1;i++) {
    const from=edges[i],to=edges[i+1],mid=(from+to)/2
    const holes=openings.filter(o=>Math.abs(mid-o.position*length)<o.width/2)
      .map(o=>({low:o.sill_height??0,high:Math.min(height,(o.sill_height??0)+o.height)})).sort((a,b)=>a.low-b.low)
    let low=0
    for(const hole of [...holes,{low:height,high:height}]) {
      if(hole.low>low && to>from)pieces.push({from,to,low,high:hole.low})
      low=Math.max(low,hole.high)
    }
  }
  return <group position={[position[0],0,position[2]]} rotation={rotation}
    onClick={e=>{e.stopPropagation();useProjectStore.setState({selectedElementId:id})}}>
    {pieces.map((piece,i)=><mesh key={i} position={[0,(piece.low+piece.high)/2,(piece.from+piece.to)/2-length/2]}>
      <boxGeometry args={[thickness,piece.high-piece.low,piece.to-piece.from]}/>
      <meshStandardMaterial color={selected?'#18b9d8':'#f5f5f0'} roughness={.9}/>
    </mesh>)}
    {openings.map(o=>o.sill_height!==undefined ? <group key={o.id} position={[0,o.sill_height,(o.position-.5)*length]}>
      <mesh position={[0,o.height/2,0]}>
        <boxGeometry args={[.015,o.height,o.width]}/>
        <meshStandardMaterial color="#8bc2dd" transparent opacity={.3} depthWrite={false}/>
      </mesh>
      {[0,o.height].map(y=><mesh key={y} position={[0,y,0]}>
        <boxGeometry args={[thickness,.045,o.width]}/><meshStandardMaterial color="#e5e7eb"/>
      </mesh>)}
      {[-o.width/2,o.width/2].map(z=><mesh key={z} position={[0,o.height/2,z]}>
        <boxGeometry args={[thickness,o.height,.045]}/><meshStandardMaterial color="#e5e7eb"/>
      </mesh>)}
    </group> : o.operation==='overhead' ? <mesh key={o.id} position={[0,o.height+.08,(o.position-.5)*length]}>
      <boxGeometry args={[.2,.12,o.width]}/><meshStandardMaterial color="#e5e7eb"/>
    </mesh> : o.operation==='sliding' ? <group key={o.id} position={[0,0,(o.position-.5)*length]}>
      {[0,1].map(i=><mesh key={i} position={[i*.035,o.height/2,o.width/4]}>
        <boxGeometry args={[.02,o.height,o.width/2]}/><meshStandardMaterial color="#8bc2dd" transparent opacity={.35} depthWrite={false}/>
      </mesh>)}
    </group> : o.operation==='double_hinged' || o.operation==='bifold' ? <group key={o.id} position={[0,0,(o.position-.5)*length]}>
      {[-1,1].map(side=><group key={side} position={[0,0,side*o.width/2]} rotation={[0,side*Math.PI*.44,0]}>
        <mesh position={[0,o.height/2,-side*o.width/4]}>
          <boxGeometry args={[.035,o.height,o.width/2]}/><meshStandardMaterial color="#b89470"/>
        </mesh>
      </group>)}
    </group> : <group key={o.id} position={[0,0,(o.position-.5)*length-o.width/2]} rotation={[0,Math.PI*.44,0]}>
      <mesh position={[0,o.height/2,o.width/2]}>
        <boxGeometry args={[.035,o.height,o.width]}/><meshStandardMaterial color="#b89470"/>
      </mesh>
    </group>)}
  </group>
}

function FloorMesh({ points, holes = [] }: { points: [number, number, number][]; holes?: [number, number, number][][] }) {
  const shape = useMemo(() => {
    const s = new THREE.Shape()
    if (points.length > 0) {
      s.moveTo(points[0][0], -points[0][2])
      for (let i = 1; i < points.length; i++) {
        s.lineTo(points[i][0], -points[i][2])
      }
      s.closePath()
      for (const ring of holes) {
        const hole = new THREE.Path()
        ring.forEach((p,i)=>i===0?hole.moveTo(p[0],-p[2]):hole.lineTo(p[0],-p[2]))
        hole.closePath()
        s.holes.push(hole)
      }
    }
    return s
  }, [points, holes])

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
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
            <mesh position={[0, h*0.2, 0]}>
              <boxGeometry args={[w, h*0.4, d]} />
              <meshStandardMaterial color={color} roughness={0.8} />
            </mesh>
            <mesh position={[0, h*0.6, -d*0.35]}>
              <boxGeometry args={[w, h*0.6, d*0.1]} />
              <meshStandardMaterial color={color} roughness={0.8} />
            </mesh>
            <mesh position={[0, h*0.45, 0]}>
              <boxGeometry args={[w*0.9, h*0.1, d*0.9]} />
              <meshStandardMaterial color={color} roughness={0.9} />
            </mesh>
            {[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([lx, lz], i) => (
              <mesh key={i} position={[lx * w*0.4, 0, lz * d*0.4]}>
                <cylinderGeometry args={[0.02, 0.015, h*0.2, 8]} />
                <meshStandardMaterial color="#8B4513" metalness={0.3} />
              </mesh>
            ))}
          </group>
        )
      case 'bed':
        return (
          <group>
            <mesh position={[0, h*0.3, 0]}>
              <boxGeometry args={[w, h*0.3, d]} />
              <meshStandardMaterial color="#f0f0f0" roughness={0.9} />
            </mesh>
            <mesh position={[0, h*0.6, -d*0.45]}>
              <boxGeometry args={[w, h*0.6, d*0.08]} />
              <meshStandardMaterial color={color} roughness={0.7} />
            </mesh>
            {[-0.3, 0.3].map((x, i) => (
              <mesh key={i} position={[x, h*0.5, -d*0.25]}>
                <boxGeometry args={[w*0.25, h*0.15, d*0.15]} />
                <meshStandardMaterial color="#ffffff" roughness={1} />
              </mesh>
            ))}
            <mesh position={[0, h*0.1, 0]}>
              <boxGeometry args={[w, h*0.15, d]} />
              <meshStandardMaterial color={color} roughness={0.6} />
            </mesh>
          </group>
        )
      case 'table':
        return (
          <group>
            <mesh position={[0, h*0.45, 0]}>
              <boxGeometry args={[w, h*0.05, d]} />
              <meshStandardMaterial color={color} roughness={0.5} />
            </mesh>
            {[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([lx, lz], i) => (
              <mesh key={i} position={[lx * w*0.4, h*0.2, lz * d*0.4]}>
                <boxGeometry args={[0.05, h*0.4, 0.05]} />
                <meshStandardMaterial color={color} roughness={0.5} />
              </mesh>
            ))}
          </group>
        )
      default:
        return (
          <mesh>
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
  const { walls, furniture, floorPlan, selectedElementId } = useProjectStore()

  const floorRegions = useMemo(() => {
    const regions = floorPlan?.floor_regions?.length ? floorPlan.floor_regions :
      (floorPlan?.rooms ?? []).filter(room=>room.points.length>=3).map(room=>({points:room.points,holes:[]}))
    const tuple = (p: {x:number;y:number;z:number}): [number,number,number] => [p.x,0,p.z]
    return regions.map(region=>({points:region.points.map(tuple),holes:region.holes.map(ring=>ring.map(tuple))}))
  }, [floorPlan])

  return (
    <group>
      <ambientLight intensity={0.4} />
      <directionalLight 
        position={[10, 20, 10]} 
        intensity={1.5} 
      />
      <pointLight position={[-10, 10, -10]} intensity={0.5} color="#ffd4a3" />

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]}>
        <planeGeometry args={[100, 100]} />
        <meshStandardMaterial color="#e0e0e0" />
      </mesh>

      {floorRegions.map((region,i)=><FloorMesh key={i} points={region.points} holes={region.holes}/>)}

      {walls.map((wall) => (
        <WallMesh 
          key={wall.id}
          id={wall.id}
          start={wall.start}
          end={wall.end}
          height={wall.height}
          thickness={wall.thickness}
        />
      ))}

      {floorPlan?.columns.map(column=><mesh key={column.id} position={[column.position.x,column.height/2,column.position.z]} rotation={[0,column.rotation??0,0]}
        onClick={e=>{e.stopPropagation();useProjectStore.setState({selectedElementId:column.id})}}>
        {column.shape==='circular' ? <cylinderGeometry args={[column.width/2,column.width/2,column.height,32]}/> : <boxGeometry args={[column.width,column.height,column.depth]}/>}
        <meshStandardMaterial color={selectedElementId===column.id?'#18b9d8':'#f5f5f0'} roughness={.9}/>
      </mesh>)}

      {furniture.map((item) => (
        <FurnitureMesh key={item.id} item={item} />
      ))}

      <gridHelper args={[50, 50, '#cccccc', '#eeeeee']} position={[0, -0.03, 0]} />
    </group>
  )
}
