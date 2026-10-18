import { useRef, useEffect, useMemo } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { useProjectStore } from '../stores/projectStore'
import { currentPlan } from '../utils/interior'
import { walkable, walkSpawn } from '../utils/walking'

export default function WalkthroughCamera() {
  const camera=useThree(s=>s.camera),canvas=useThree(s=>s.gl.domElement)
  const tour=useProjectStore(s=>s.tour)
  const isPlaying=useProjectStore(s=>s.isPlaying)
  const keys=useRef(new Set<string>())
  const angles=useRef({yaw:0,pitch:0}),drag=useRef<{x:number;y:number}|null>(null)
  const progress=useRef(0),lastPublish=useRef(0)
  const path=useMemo(()=>{
    const points=(tour?.points??[]).map(p=>new THREE.Vector3(p.x,p.y,p.z))
    const lengths=[0]
    for(let i=1;i<points.length;i++)lengths.push(lengths[i-1]+points[i].distanceTo(points[i-1]))
    return {points,lengths,total:lengths[lengths.length-1]??0}
  },[tour])
  useEffect(()=>{
    const state=useProjectStore.getState()
    if(!state.floorPlan)return
    const spawn=path.points[0]??new THREE.Vector3(...walkSpawn(currentPlan(),state.furniture))
    camera.position.copy(spawn)
    const next=path.points[1]
    const direction=next?next.clone().sub(spawn):new THREE.Vector3(0,0,-1)
    angles.current={yaw:Math.atan2(-direction.x,-direction.z),pitch:0}
    camera.rotation.set(0,angles.current.yaw,0,'YXZ')
    progress.current=0
    useProjectStore.setState({tourProgress:0})
  },[camera,path])
  useEffect(()=>{if(isPlaying)progress.current=useProjectStore.getState().tourProgress>=1?0:useProjectStore.getState().tourProgress},[isPlaying])
  useEffect(()=>{
    canvas.tabIndex=0
    const down=(event:KeyboardEvent)=>{
      if(event.target instanceof HTMLElement&&event.target.closest('input,textarea,select,button,aside'))return
      const key=event.key.toLowerCase()
      if(['w','a','s','d','arrowup','arrowdown','arrowleft','arrowright'].includes(key)){event.preventDefault();keys.current.add(key)}
    }
    const up=(event:KeyboardEvent)=>keys.current.delete(event.key.toLowerCase())
    const reset=()=>{keys.current.clear();drag.current=null;useProjectStore.setState({walkInput:{forward:0,turn:0}})}
    const pointerDown=(event:PointerEvent)=>{
      if(useProjectStore.getState().isPlaying)return
      canvas.focus();drag.current={x:event.clientX,y:event.clientY};canvas.setPointerCapture(event.pointerId)
    }
    const pointerMove=(event:PointerEvent)=>{
      if(!drag.current||useProjectStore.getState().isPlaying)return
      angles.current.yaw-=(event.clientX-drag.current.x)*.004
      angles.current.pitch=THREE.MathUtils.clamp(angles.current.pitch-(event.clientY-drag.current.y)*.003,-1.05,1.05)
      drag.current={x:event.clientX,y:event.clientY}
    }
    const pointerUp=()=>{drag.current=null}
    window.addEventListener('keydown',down);window.addEventListener('keyup',up);window.addEventListener('blur',reset)
    canvas.addEventListener('pointerdown',pointerDown);canvas.addEventListener('pointermove',pointerMove)
    window.addEventListener('pointerup',pointerUp);window.addEventListener('pointercancel',reset)
    return ()=>{
      window.removeEventListener('keydown',down);window.removeEventListener('keyup',up);window.removeEventListener('blur',reset)
      canvas.removeEventListener('pointerdown',pointerDown);canvas.removeEventListener('pointermove',pointerMove)
      window.removeEventListener('pointerup',pointerUp);window.removeEventListener('pointercancel',reset)
      reset()
    }
  },[canvas])
  useFrame((_,delta)=>{
    const state=useProjectStore.getState()
    if(state.isPlaying&&path.points.length>1) {
      progress.current=Math.min(1,progress.current+delta/state.tourDuration)
      const distance=progress.current*path.total
      let index=1
      while(index<path.lengths.length-1&&path.lengths[index]<distance)index++
      const segment=path.lengths[index]-path.lengths[index-1]
      const t=segment?THREE.MathUtils.clamp((distance-path.lengths[index-1])/segment,0,1):0
      camera.position.lerpVectors(path.points[index-1],path.points[index],t)
      const direction=path.points[index].clone().sub(path.points[index-1]).normalize()
      const yaw=Math.atan2(-direction.x,-direction.z)
      const diff=Math.atan2(Math.sin(yaw-angles.current.yaw),Math.cos(yaw-angles.current.yaw))
      angles.current.yaw+=diff*(1-Math.exp(-delta*5));angles.current.pitch*=Math.exp(-delta*5)
      if(performance.now()-lastPublish.current>180||progress.current>=1) {
        lastPublish.current=performance.now()
        useProjectStore.setState({tourProgress:progress.current,...(progress.current>=1?{isPlaying:false}:{})})
      }
    } else if(!state.recording&&state.floorPlan) {
      const forward=(keys.current.has('w')||keys.current.has('arrowup')?1:0)-(keys.current.has('s')||keys.current.has('arrowdown')?1:0)+state.walkInput.forward
      const side=(keys.current.has('d')?1:0)-(keys.current.has('a')?1:0)
      const turn=(keys.current.has('arrowleft')?1:0)-(keys.current.has('arrowright')?1:0)+state.walkInput.turn
      angles.current.yaw+=turn*delta*1.5
      const dx=-Math.sin(angles.current.yaw)*forward+Math.cos(angles.current.yaw)*side
      const dz=-Math.cos(angles.current.yaw)*forward-Math.sin(angles.current.yaw)*side
      if(dx||dz) {
        const magnitude=Math.hypot(dx,dz),distance=Math.min(delta,.1)*1.35
        const steps=Math.max(1,Math.ceil(distance/.04)),plan=currentPlan()
        for(let i=0;i<steps;i++) {
          const x=camera.position.x+dx/magnitude*distance/steps,z=camera.position.z+dz/magnitude*distance/steps
          if(walkable(x,camera.position.z,plan,state.furniture))camera.position.x=x
          if(walkable(camera.position.x,z,plan,state.furniture))camera.position.z=z
        }
      }
    }
    camera.position.y=1.6
    camera.rotation.set(angles.current.pitch,angles.current.yaw,0,'YXZ')
  })
  return null
}
