import { useEffect, useMemo } from 'react'
import * as THREE from 'three'
import { useProjectStore } from '../stores/projectStore'
import type { RoofMesh } from '../types/model'

function geometry(mesh:RoofMesh) {
  const result=new THREE.BufferGeometry()
  const positions:number[]=[],uv:number[]=[]
  for(const triangle of mesh.triangles)for(const index of triangle) {
    const p=mesh.vertices[index];positions.push(p.x,p.y,p.z);uv.push(p.x,p.z)
  }
  result.setAttribute('position',new THREE.Float32BufferAttribute(positions,3))
  result.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2))
  result.computeVertexNormals()
  return result
}

export default function Roof3D() {
  const roof=useProjectStore(s=>s.floorPlan?.roof)
  const visible=useProjectStore(s=>s.roofVisible)
  const wallColor=useProjectStore(s=>s.floorPlan?.interior_style?.wall??'#f5f5f0')
  const surface=useMemo(()=>roof?geometry(roof.surface):null,[roof?.surface])
  const gables=useMemo(()=>roof?geometry(roof.gables):null,[roof?.gables])
  const material=roof?.settings.material
  const texture=useMemo(()=>{
    const canvas=document.createElement('canvas');canvas.width=256;canvas.height=256
    const c=canvas.getContext('2d')!
    c.fillStyle='#e0e0e0';c.fillRect(0,0,256,256)
    if(material==='shingle') {
      for(let row=0;row<8;row++)for(let column=-1;column<5;column++) {
        c.fillStyle=`rgb(${205+(row*17+column*11+99)%30},${205+(row*17+column*11+99)%30},${205+(row*17+column*11+99)%30})`
        c.fillRect(column*64+(row%2)*32,row*32,63,31)
        c.fillStyle='#a4a4a4';c.fillRect(column*64+(row%2)*32,row*32+30,64,2)
      }
    }else if(material==='metal') {
      for(let i=0;i<8;i++){c.fillStyle='#b1b1b1';c.fillRect(i*32,0,2,256);c.fillStyle='#f2f2f2';c.fillRect(i*32+2,0,2,256)}
    }else if(material==='tile') {
      for(let i=0;i<8;i++) {
        const gradient=c.createLinearGradient(i*32,0,i*32+32,0)
        gradient.addColorStop(0,'#b7b7b7');gradient.addColorStop(.5,'#ffffff');gradient.addColorStop(1,'#b7b7b7')
        c.fillStyle=gradient;c.fillRect(i*32,0,32,256)
      }
      for(let i=0;i<4;i++){c.fillStyle='#b5b5b5';c.fillRect(0,i*64,256,2)}
    }
    const map=new THREE.CanvasTexture(canvas);map.wrapS=map.wrapT=THREE.RepeatWrapping
    map.repeat.set(.6,.6);map.colorSpace=THREE.SRGBColorSpace
    return map
  },[material])
  useEffect(()=>()=>{surface?.dispose();gables?.dispose()},[surface,gables])
  useEffect(()=>()=>texture.dispose(),[texture])
  if(!roof||!visible||!surface||!gables)return null
  return <group name="roof-proposal">
    <mesh geometry={surface}>
      <meshStandardMaterial map={texture} color={roof.settings.color} metalness={material==='metal'?.35:0} roughness={material==='metal'?.45:.9} side={THREE.DoubleSide}/>
    </mesh>
    <mesh geometry={gables}><meshStandardMaterial color={wallColor} roughness={.9} side={THREE.DoubleSide}/></mesh>
  </group>
}
