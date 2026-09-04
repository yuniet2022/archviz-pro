import { Canvas } from '@react-three/fiber'
import { Suspense } from 'react'
import House3D from './scenes/House3D'
import WalkthroughCamera from './scenes/WalkthroughCamera'
import PlanUploader from './components/PlanUploader'
import StylePresets from './components/StylePresets'
import { ViewModeControls, CameraController } from './components/ViewModes'
import VideoExporter from './components/VideoExporter'
import { useProjectStore } from './stores/projectStore'
import { Box, Layers, MousePointer } from 'lucide-react'

function LoadingScreen() {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-white text-sm">Loading 3D Engine...</p>
      </div>
    </div>
  )
}

export default function App() {
  const { projectId, viewMode, furniture } = useProjectStore()

  return (
    <div className="relative w-screen h-screen bg-gray-900 overflow-hidden">
      <div className="absolute inset-0">
        <Canvas shadows gl={{ antialias: true, alpha: false }}>
          <color attach="background" args={['#1a1a2e']} />
          <fog attach="fog" args={['#1a1a2e', 20, 60]} />

          <Suspense fallback={null}>
            <CameraController />
            {viewMode === 'walkthrough' && <WalkthroughCamera />}
            <House3D />
          </Suspense>
        </Canvas>
      </div>

      <header className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-6 py-4 bg-gradient-to-b from-black/60 to-transparent">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Box className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-white font-bold text-lg leading-tight">ArchViz Pro</h1>
            <p className="text-white/60 text-xs">Professional Architectural Visualization</p>
          </div>
        </div>

        {projectId && (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-white/10 backdrop-blur rounded-full">
              <Layers className="w-3.5 h-3.5 text-blue-400" />
              <span className="text-white/80 text-xs">{furniture.length} items</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-white/10 backdrop-blur rounded-full">
              <MousePointer className="w-3.5 h-3.5 text-green-400" />
              <span className="text-white/80 text-xs">{viewMode}</span>
            </div>
          </div>
        )}
      </header>

      <div className="absolute inset-0 z-10 pointer-events-none">
        <div className="h-full flex flex-col justify-between p-6">
          {!projectId && (
            <div className="flex-1 flex items-center justify-center pointer-events-auto">
              <PlanUploader />
            </div>
          )}

          {projectId && (
            <div className="flex justify-center pt-16 pointer-events-auto">
              <ViewModeControls />
            </div>
          )}

          <div className="flex justify-between items-end">
            {projectId && (
              <div className="pointer-events-auto">
                <StylePresets />
              </div>
            )}

            {projectId && (
              <div className="pointer-events-auto">
                <VideoExporter />
              </div>
            )}
          </div>
        </div>
      </div>

      {projectId && viewMode === 'walkthrough' && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 bg-black/70 backdrop-blur text-white px-4 py-2 rounded-full text-xs">
          Use <kbd className="px-1.5 py-0.5 bg-white/20 rounded text-[10px] mx-1">W</kbd>
          <kbd className="px-1.5 py-0.5 bg-white/20 rounded text-[10px] mx-1">A</kbd>
          <kbd className="px-1.5 py-0.5 bg-white/20 rounded text-[10px] mx-1">S</kbd>
          <kbd className="px-1.5 py-0.5 bg-white/20 rounded text-[10px] mx-1">D</kbd> to move • Click <strong>Play Tour</strong> for cinematic mode
        </div>
      )}
    </div>
  )
}
