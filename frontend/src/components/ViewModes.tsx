import { useProjectStore } from '../stores/projectStore'
import { OrbitControls, PerspectiveCamera, OrthographicCamera } from '@react-three/drei'
import type { ViewMode } from '../stores/projectStore'
import { useThree } from '@react-three/fiber'
import { useMemo } from 'react'

const modes: { id: ViewMode; label: string; shortcut: string }[] = [
  { id: '3d-orbit', label: '3D Orbit', shortcut: '1' },
  { id: 'top-down', label: 'Top View', shortcut: '2' },
  { id: 'elevation', label: 'Elevation', shortcut: '3' },
  { id: 'walkthrough', label: 'Walkthrough', shortcut: '4' },
]

export function ViewModeControls() {
  const { viewMode, setViewMode, isPlaying, setIsPlaying } = useProjectStore()

  return (
    <div className="bg-white rounded-xl shadow-lg p-2 flex gap-1">
      {modes.map((mode) => (
        <button
          key={mode.id}
          onClick={() => setViewMode(mode.id)}
          className={`
            px-3 py-2 rounded-lg text-xs font-medium transition-all
            ${viewMode === mode.id
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-gray-600 hover:bg-gray-100'
            }
          `}
        >
          <span className="block">{mode.label}</span>
          <span className="block text-[10px] opacity-70 mt-0.5">⌘{mode.shortcut}</span>
        </button>
      ))}

      {viewMode === 'walkthrough' && (
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className={`
            ml-2 px-3 py-2 rounded-lg text-xs font-bold transition-all
            ${isPlaying 
              ? 'bg-red-500 text-white' 
              : 'bg-green-500 text-white'
            }
          `}
        >
          {isPlaying ? '⏹ Stop Tour' : '▶ Play Tour'}
        </button>
      )}
    </div>
  )
}

export function CameraController() {
  const { viewMode, walls, floorPlan } = useProjectStore()
  const size = useThree(state=>state.size)
  const bounds = useMemo(()=>{
    const xs=walls.flatMap(w=>[w.start[0],w.end[0]])
    const zs=walls.flatMap(w=>[w.start[2],w.end[2]])
    for(const c of floorPlan?.columns??[]) {
      xs.push(c.position.x-c.width/2,c.position.x+c.width/2)
      zs.push(c.position.z-c.depth/2,c.position.z+c.depth/2)
    }
    if(!xs.length)return {x:0,z:0,width:8,depth:8,height:2.8}
    return {x:(Math.min(...xs)+Math.max(...xs))/2,z:(Math.min(...zs)+Math.max(...zs))/2,
      width:Math.max(2,Math.max(...xs)-Math.min(...xs)),depth:Math.max(2,Math.max(...zs)-Math.min(...zs)),
      height:Math.max(2.8,...walls.map(w=>w.height),...(floorPlan?.columns??[]).map(c=>c.height))}
  },[walls,floorPlan])
  const span=Math.max(bounds.width,bounds.depth)
  const distance=Math.max(span,bounds.height*2)*1.3
  const target:[number,number,number]=[bounds.x,bounds.height*.35,bounds.z]

  if (viewMode === 'walkthrough') {
    return <PerspectiveCamera makeDefault position={[-4, 1.7, -4]} fov={75} />
  }

  if (viewMode === 'top-down') {
    return (
      <>
        <OrthographicCamera makeDefault position={[bounds.x,Math.max(20,bounds.height*3),bounds.z]}
          rotation={[-Math.PI/2,0,0]} zoom={Math.min(size.width*.7/bounds.width,size.height*.7/bounds.depth)} far={2000}/>
        <OrbitControls enableRotate={false} target={[bounds.x,0,bounds.z]}/>
      </>
    )
  }

  if (viewMode === 'elevation') {
    return (
      <>
        <PerspectiveCamera makeDefault position={[bounds.x+distance,bounds.height/2,bounds.z]} fov={50} far={5000}/>
        <OrbitControls 
          target={target}
          enableZoom={true}
          minPolarAngle={Math.PI / 2}
          maxPolarAngle={Math.PI / 2}
        />
      </>
    )
  }

  return (
    <>
      <PerspectiveCamera makeDefault position={[bounds.x+distance,bounds.height+distance*.8,bounds.z+distance]} fov={50} far={5000}/>
      <OrbitControls
        target={target}
        enableDamping
        dampingFactor={0.05}
        minDistance={3}
        maxDistance={Math.max(50,span*5)}
        maxPolarAngle={Math.PI / 2 - 0.05}
      />
    </>
  )
}
