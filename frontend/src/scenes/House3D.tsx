import { useMemo, useEffect } from 'react'
import * as THREE from 'three'
import { useProjectStore } from '../stores/projectStore'
import FurnitureMesh from './FurnitureMesh'
import { moveFurniture, interiorError } from '../utils/interior'
import type { ModelRoom } from '../types/model'

function WallMesh({ id, start, end, height = 2.8, thickness = 0.15 }: {
  id: string
  start: [number, number, number]
  end: [number, number, number]
  height?: number
  thickness?: number
}) {
  const selected = useProjectStore(s=>s.selectedElementId===id)
  const plan = useProjectStore(s=>s.floorPlan)
  const wallColor=plan?.interior_style?.wall??'#f5f5f0'
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
      <meshStandardMaterial color={selected?'#18b9d8':wallColor} roughness={.9}/>
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

function FloorMesh({ points, holes = [], texture }: { points: [number, number, number][]; holes?: [number, number, number][][]; texture:THREE.Texture }) {
  const color=useProjectStore(s=>s.floorPlan?.interior_style?.floor??'#d4a574')
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
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]} onClick={async event=>{
      const state=useProjectStore.getState()
      if(state.recording)return
      if(state.tourPointMode&&state.floorPlan) {
        event.stopPropagation()
        const points=state.floorPlan.tour_waypoints??[]
        if(points.length>=64)return
        useProjectStore.setState({floorPlan:{...state.floorPlan,tour_waypoints:[...points,{x:event.point.x,y:1.6,z:event.point.z}]},dirty:true,tour:null,isPlaying:false})
      } else if(state.placementMode) {
        event.stopPropagation()
        const item=state.furniture.find(f=>f.id===state.selectedFurnitureId)
        if(!item)return
        try {
          await moveFurniture({...item,position:[event.point.x,item.position[1],event.point.z]})
          useProjectStore.setState({placementMode:false,interiorMessage:'Mueble colocado.'})
        } catch(error){useProjectStore.setState({interiorMessage:interiorError(error)})}
      }
    }}>
      <shapeGeometry args={[shape]} />
      <meshStandardMaterial color={color} map={texture} roughness={.82} side={THREE.DoubleSide} />
    </mesh>
  )
}

function RoomCeiling({room}:{room:ModelRoom}) {
  const shape=useMemo(()=>new THREE.Shape(room.points.map(p=>new THREE.Vector2(p.x,-p.z))),[room])
  return <mesh rotation={[-Math.PI/2,0,0]} position={[0,room.ceiling_height,0]}>
    <shapeGeometry args={[shape]}/><meshStandardMaterial color="#f6f3eb" roughness={.95} side={THREE.DoubleSide}/>
  </mesh>
}

export default function House3D() {
  const walls=useProjectStore(s=>s.walls),furniture=useProjectStore(s=>s.furniture)
  const floorPlan=useProjectStore(s=>s.floorPlan),selectedElementId=useProjectStore(s=>s.selectedElementId)
  const viewMode=useProjectStore(s=>s.viewMode)
  const texture=useMemo(()=>{
    const canvas=document.createElement('canvas');canvas.width=256;canvas.height=256
    const context=canvas.getContext('2d')!
    context.fillStyle='#ebe7df';context.fillRect(0,0,256,256)
    for(let i=0;i<64;i++) {
      context.strokeStyle=`rgba(85,65,40,${.025+(i%5)*.012})`;context.lineWidth=.5
      context.beginPath();context.moveTo(0,i*4);context.bezierCurveTo(60,i*4+3,150,i*4-2,256,i*4);context.stroke()
    }
    context.strokeStyle='rgba(65,55,40,.16)';context.lineWidth=1
    for(let row=0;row<4;row++) {context.strokeRect(0,row*64,256,64);context.strokeRect(row%2?160:80,row*64,256,64)}
    const map=new THREE.CanvasTexture(canvas);map.wrapS=map.wrapT=THREE.RepeatWrapping;map.repeat.set(.5,.5);map.colorSpace=THREE.SRGBColorSpace
    return map
  },[])
  const tileTexture=useMemo(()=>{
    const canvas=document.createElement('canvas');canvas.width=128;canvas.height=128
    const context=canvas.getContext('2d')!
    context.fillStyle='#ebe9e3';context.fillRect(0,0,128,128)
    context.strokeStyle='#c9c6bf';context.lineWidth=1;context.strokeRect(0,0,128,128)
    for(let i=0;i<300;i++) {context.fillStyle=`rgba(80,75,65,${.015+(i%5)*.005})`;context.fillRect((i*53)%128,(i*71)%128,2,1)}
    const map=new THREE.CanvasTexture(canvas);map.wrapS=map.wrapT=THREE.RepeatWrapping;map.repeat.set(1.65,1.65);map.colorSpace=THREE.SRGBColorSpace
    return map
  },[])
  useEffect(()=>()=>{texture.dispose();tileTexture.dispose()},[texture,tileTexture])
  const stoneFloor=['industrial','contemporary','luxury','mediterranean'].includes(floorPlan?.interior_style?.id??'')

  const floorRegions = useMemo(() => {
    const regions = floorPlan?.floor_regions?.length ? floorPlan.floor_regions :
      (floorPlan?.rooms ?? []).filter(room=>room.points.length>=3).map(room=>({points:room.points,holes:[]}))
    const tuple = (p: {x:number;y:number;z:number}): [number,number,number] => [p.x,0,p.z]
    return regions.map(region=>({points:region.points.map(tuple),holes:region.holes.map(ring=>ring.map(tuple))}))
  }, [floorPlan])

  return (
    <group>
      <ambientLight intensity={.85} />
      <hemisphereLight args={['#fff7e9','#c5cbd0',.75]}/>
      <directionalLight 
        position={[10, 20, 10]} 
        intensity={1.5} 
      />
      <pointLight position={[-10, 10, -10]} intensity={0.5} color="#ffd4a3" />

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]}>
        <planeGeometry args={[100, 100]} />
        <meshStandardMaterial color="#e0e0e0" />
      </mesh>

      {floorRegions.map((region,i)=><FloorMesh key={i} points={region.points} holes={region.holes} texture={stoneFloor?tileTexture:texture}/>)}
      {viewMode==='walkthrough'&&floorPlan?.rooms.filter(room=>room.points.length>=3).map(room=><RoomCeiling key={room.id} room={room}/>)}

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
        <meshStandardMaterial color={selectedElementId===column.id?'#18b9d8':floorPlan.interior_style?.wall??'#f5f5f0'} roughness={.9}/>
      </mesh>)}

      {furniture.map((item) => (
        <FurnitureMesh key={item.id} item={item} woodTexture={texture}/>
      ))}

      {viewMode!=='walkthrough'&&<gridHelper args={[50, 50, '#cccccc', '#eeeeee']} position={[0, -0.03, 0]} />}
      {viewMode==='top-down'&&(floorPlan?.tour_waypoints??[]).map((p,i)=><mesh key={i} position={[p.x,.08,p.z]} rotation={[-Math.PI/2,0,0]}><circleGeometry args={[.15,24]}/><meshBasicMaterial color="#2463eb"/></mesh>)}
    </group>
  )
}
