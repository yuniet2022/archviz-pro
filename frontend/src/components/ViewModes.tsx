import { useProjectStore } from '../stores/projectStore'
import { OrbitControls, PerspectiveCamera, OrthographicCamera } from '@react-three/drei'
import type { ViewMode } from '../stores/projectStore'

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
  const { viewMode } = useProjectStore()

  if (viewMode === 'walkthrough') {
    return <PerspectiveCamera makeDefault position={[-4, 1.7, -4]} fov={75} />
  }

  if (viewMode === 'top-down') {
    return (
      <>
        <OrthographicCamera makeDefault position={[0, 20, 0]} zoom={30} />
      </>
    )
  }

  if (viewMode === 'elevation') {
    return (
      <>
        <PerspectiveCamera makeDefault position={[15, 5, 0]} fov={50} />
        <OrbitControls 
          target={[0, 2, 0]} 
          enableZoom={true}
          minPolarAngle={Math.PI / 2}
          maxPolarAngle={Math.PI / 2}
        />
      </>
    )
  }

  return (
    <>
      <PerspectiveCamera makeDefault position={[10, 10, 10]} fov={50} />
      <OrbitControls 
        target={[0, 2, 0]}
        enableDamping
        dampingFactor={0.05}
        minDistance={3}
        maxDistance={50}
        maxPolarAngle={Math.PI / 2 - 0.05}
      />
    </>
  )
}
