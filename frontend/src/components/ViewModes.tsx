import { useProjectStore } from '../stores/projectStore'
import { OrbitControls, PerspectiveCamera, OrthographicCamera } from '@react-three/drei'
import type { ViewMode } from '../stores/projectStore'
import { useThree } from '@react-three/fiber'
import { useMemo } from 'react'
import { walkSpawn } from '../utils/walking'
import { currentPlan } from '../utils/interior'

const modes: { id: ViewMode; label: string; shortcut: string }[] = [
  { id: '3d-orbit', label: 'Vista 3D', shortcut: '1' },
  { id: 'top-down', label: 'Planta', shortcut: '2' },
  { id: 'elevation', label: 'Alzado', shortcut: '3' },
  { id: 'walkthrough', label: 'Paseo virtual', shortcut: '4' },
]

export function ViewModeControls() {
  const { viewMode, setViewMode, isPlaying, setIsPlaying, tour, recording } = useProjectStore()

  return (
    <div className="bg-white rounded-xl shadow-lg p-2 flex gap-1">
      {modes.map((mode) => (
        <button
          key={mode.id}
          disabled={recording} onClick={() => {setViewMode(mode.id);if(mode.id==='walkthrough')useProjectStore.setState({activePanel:'tour'})}}
          className={`
            px-3 py-2 rounded-lg text-xs font-medium transition-all
            ${viewMode === mode.id
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-gray-600 hover:bg-gray-100'
            }
          `}
        >
          <span className="block">{mode.label}</span>

        </button>
      ))}

      {viewMode === 'walkthrough' && (
        <button
          disabled={recording} onClick={() => {if(tour)setIsPlaying(!isPlaying);else useProjectStore.setState({activePanel:'tour'})}}
          className={`
            ml-2 px-3 py-2 rounded-lg text-xs font-bold transition-all
            ${isPlaying 
              ? 'bg-red-500 text-white' 
              : 'bg-green-500 text-white'
            }
          `}
        >
          {isPlaying ? '⏸ Pausar' : tour?'▶ Reproducir':'Preparar recorrido'}
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
      height:Math.max(2.8,...walls.map(w=>w.height),...(floorPlan?.columns??[]).map(c=>c.height),
        ...(floorPlan?.roof?.surface.vertices.map(p=>p.y)??[]))}
  },[walls,floorPlan])
  const span=Math.max(bounds.width,bounds.depth)
  const distance=Math.max(span,bounds.height*2)*1.3
  const target:[number,number,number]=[bounds.x,bounds.height*.35,bounds.z]

  if (viewMode === 'walkthrough') {
    const state=useProjectStore.getState(),point=state.tour?.points[0]
    const spawn:[number,number,number]=point?[point.x,point.y,point.z]:floorPlan?walkSpawn(currentPlan(),state.furniture):[0,1.6,0]
    return <PerspectiveCamera makeDefault position={spawn} fov={65} near={.05} far={1000}/>
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
