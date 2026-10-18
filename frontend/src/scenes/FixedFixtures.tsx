import { useMemo } from 'react'
import * as THREE from 'three'
import { useProjectStore } from '../stores/projectStore'
import type { FixedFixture, Point } from '../types/model'
import FurnitureMesh from './FurnitureMesh'
import { furnitureFromModel } from '../utils/interior'

function outlinePath(points:Point[]) {
  const path=new THREE.Path()
  points.forEach((p,i)=>i?path.lineTo(p.x,-p.z):path.moveTo(p.x,-p.z))
  path.closePath();return path
}

function Counter({fixture,children,woodTexture}:{fixture:FixedFixture;children:FixedFixture[];woodTexture:THREE.Texture}) {
  const style=useProjectStore(s=>s.floorPlan?.interior_style)
  const h=fixture.dimensions.y,angle=fixture.rotation.y
  const divisions=Math.max(1,Math.round(fixture.dimensions.x/.6))
  const {body,top}=useMemo(()=>{
    const base=new THREE.Shape(),surface=new THREE.Shape()
    for(const [shape,points] of [[base,fixture.body_outline?.length?fixture.body_outline:fixture.outline],[surface,fixture.top_outline?.length?fixture.top_outline:fixture.outline]] as const) {
      points.forEach((p,i)=>i?shape.lineTo(p.x,-p.z):shape.moveTo(p.x,-p.z));shape.closePath()
    }
    for(const child of children) {
      if(!fixture.body_outline?.length&&child.outline.length>=3)base.holes.push(outlinePath(child.outline))
      if(!fixture.top_outline?.length&&child.kind==='cooktop'&&child.outline.length>=3)surface.holes.push(outlinePath(child.outline))
    }
    fixture.basin_centers.slice(0,fixture.basin_count).forEach((p,i)=>{
      const size=fixture.basin_sizes[i]??{x:.48,z:.36}
      const original=fixture.basin_count===fixture.source_basin_count?fixture.source_basin_outlines?.[i]:undefined
      const hole=original?.length?outlinePath(original):new THREE.Path()
      if(!original?.length)hole.absellipse(p.x,-p.z,size.x*.44,size.z*.44,0,Math.PI*2,false,angle)
      surface.holes.push(hole)
      base.holes.push(hole.clone())
    })
    return {body:base,top:surface}
  },[fixture,children,angle])
  return <>
    <mesh rotation={[-Math.PI/2,0,0]}>
      <extrudeGeometry args={[body,{depth:h-.05,bevelEnabled:false}]}/>
      <meshStandardMaterial color={style?.wood??'#a98c68'} map={woodTexture} roughness={.72}/>
    </mesh>
    <mesh rotation={[-Math.PI/2,0,0]} position={[0,h-.05,0]}>
      <extrudeGeometry args={[top,{depth:.05,bevelEnabled:false}]}/>
      <meshStandardMaterial color={style?.id==='industrial'?'#999a96':'#ece9df'} roughness={.4}/>
    </mesh>
    <group position={[fixture.position.x,0,fixture.position.z]} rotation={[0,angle,0]}>
      {Array.from({length:divisions},(_,i)=><mesh key={i} position={[(i-(divisions-1)/2)*fixture.dimensions.x/divisions,h*.65,fixture.dimensions.z/2+.008]}>
        <boxGeometry args={[.14,.012,.018]}/><meshStandardMaterial color={style?.accent??'#66665a'} metalness={.5} roughness={.3}/>
      </mesh>)}
    </group>
    {fixture.basin_centers.slice(0,fixture.basin_count).map((p,i)=>{
      const size=fixture.basin_sizes[i]??{x:.48,z:.36}
      return <group key={i} position={[p.x,h-.008,p.z]} rotation={[0,angle,0]}>
        {fixture.kind==='island'?<>
          <mesh position={[0,-.14,0]}><boxGeometry args={[size.x*.98,.018,size.z*.98]}/><meshStandardMaterial color="#bec9c7" roughness={.25} metalness={.5}/></mesh>
          {[-1,1].map(side=><group key={side}>
            <mesh position={[side*size.x*.48,-.065,0]}><boxGeometry args={[.018,.15,size.z]}/><meshStandardMaterial color="#c8d1cf" roughness={.2} metalness={.5}/></mesh>
            <mesh position={[0,-.065,side*size.z*.48]}><boxGeometry args={[size.x,.15,.018]}/><meshStandardMaterial color="#c8d1cf" roughness={.2} metalness={.5}/></mesh>
            <mesh position={[side*size.x*.5,.01,0]}><boxGeometry args={[.025,.012,size.z+.025]}/><meshStandardMaterial color="#dce0d9" roughness={.3} metalness={.5}/></mesh>
            <mesh position={[0,.01,side*size.z*.5]}><boxGeometry args={[size.x+.025,.012,.025]}/><meshStandardMaterial color="#dce0d9" roughness={.3} metalness={.5}/></mesh>
          </group>)}
        </>:<><mesh scale={[size.x*.49,.16,size.z*.49]}>
          <sphereGeometry args={[1,24,12,0,Math.PI*2,Math.PI/2,Math.PI/2]}/><meshStandardMaterial color="#f5f5ed" roughness={.2} side={THREE.DoubleSide}/>
        </mesh>
        <mesh rotation={[-Math.PI/2,0,0]} scale={[size.x/2,size.z/2,1]} position={[0,.01,0]}>
          <ringGeometry args={[.86,1,32]}/><meshStandardMaterial color="#fafaf4" roughness={.25} side={THREE.DoubleSide}/>
        </mesh></>}
        <mesh position={[0,-.152,0]}><cylinderGeometry args={[.018,.018,.006,12]}/><meshStandardMaterial color="#798484" metalness={.6}/></mesh>
        {fixture.kind!=='island'&&<><mesh position={[0,.085,-size.z*.56]}><cylinderGeometry args={[.014,.018,.18,12]}/><meshStandardMaterial color="#a8b6b6" metalness={.8} roughness={.2}/></mesh>
        <mesh position={[0,.17,-size.z*.34]}><boxGeometry args={[.024,.025,size.z*.48]}/><meshStandardMaterial color="#a8b6b6" metalness={.8} roughness={.2}/></mesh></>}
      </group>
    })}
    {fixture.kind==='island'&&fixture.basin_count>0&&<group position={[
      fixture.basin_centers.reduce((n,p)=>n+p.x,0)/fixture.basin_count,h,
      fixture.basin_centers.reduce((n,p)=>n+p.z,0)/fixture.basin_count]} rotation={[0,angle,0]}>
      <mesh position={[0,.12,-(fixture.basin_sizes[0]?.z??.3)/2-.1]}><cylinderGeometry args={[.016,.02,.25,12]}/><meshStandardMaterial color="#a8b6b6" metalness={.8} roughness={.2}/></mesh>
      <mesh position={[0,.245,-.10]}><boxGeometry args={[.026,.026,.30]}/><meshStandardMaterial color="#a8b6b6" metalness={.8} roughness={.2}/></mesh>
    </group>}
  </>
}

function Appliance({fixture}:{fixture:FixedFixture}) {
  const {x:w,y:h,z:d}=fixture.dimensions
  const cooker=fixture.kind==='cooktop'
  return <group position={[fixture.position.x,0,fixture.position.z]} rotation={[0,fixture.rotation.y,0]}>
    <mesh position={[0,h/2,0]}><boxGeometry args={[w,h,d]}/><meshStandardMaterial color="#ced4d1" roughness={.35} metalness={.5}/></mesh>
    <mesh position={[0,h*.52,d/2+.003]}><boxGeometry args={[w*.86,h*.60,.012]}/><meshStandardMaterial color={cooker?'#263337':'#bdc6c5'} roughness={.35}/></mesh>
    <mesh position={[0,h*.86,d/2+.018]}><boxGeometry args={[w*.72,.025,.03]}/><meshStandardMaterial color="#697c80" metalness={.7} roughness={.2}/></mesh>
    {cooker&&<>
      <mesh position={[0,h+.004,0]}><boxGeometry args={[w,.016,d]}/><meshStandardMaterial color="#253033" roughness={.3}/></mesh>
      {[-1,1].flatMap(x=>[-1,1].map(z=><mesh key={`${x}${z}`} position={[x*w*.24,h+.014,z*d*.23]} rotation={[-Math.PI/2,0,0]}>
        <ringGeometry args={[Math.min(w,d)*.095,Math.min(w,d)*.15,24]}/><meshStandardMaterial color="#9eaaab" side={THREE.DoubleSide} metalness={.7}/>
      </mesh>))}
    </>}
  </group>
}

export default function FixedFixtures({woodTexture}:{woodTexture:THREE.Texture}) {
  const fixtures=useProjectStore(s=>s.floorPlan?.fixtures??[])
  const selected=useProjectStore(s=>s.selectedFixtureId)
  return <>{fixtures.map(fixture=>{
    const children=fixtures.filter(child=>child.parent_id===fixture.id)
    const furniture={...furnitureFromModel(fixture),model:fixture.kind,color:'#edf0e9',material:'stone'}
    return <group key={fixture.id} name={`fixture:${fixture.id}`} onClick={event=>{
      event.stopPropagation();const state=useProjectStore.getState()
      if(state.recording||state.viewMode==='walkthrough'||state.tourPointMode||state.placementMode)return
      useProjectStore.setState({selectedFixtureId:fixture.id,selectedFurnitureId:'',activePanel:'furniture'})
    }}>
      {['vanity','counter','island'].includes(fixture.kind)&&fixture.outline.length>=3?<Counter fixture={fixture} children={children} woodTexture={woodTexture}/>:
        ['cooktop','dishwasher'].includes(fixture.kind)?<Appliance fixture={fixture}/>:
        <FurnitureMesh item={furniture} woodTexture={woodTexture} selectable={false}/>}
      {selected===fixture.id&&<mesh position={[fixture.position.x,.04,fixture.position.z]} rotation={[-Math.PI/2,0,-fixture.rotation.y]}><planeGeometry args={[fixture.dimensions.x,fixture.dimensions.z]}/><meshBasicMaterial color="#17b9d3" transparent opacity={.25} depthWrite={false}/></mesh>}
    </group>
  })}</>
}
