import { Canvas } from '@react-three/fiber'
import { Suspense, useEffect } from 'react'
import House3D from './scenes/House3D'
import WalkthroughCamera from './scenes/WalkthroughCamera'
import PlanUploader from './components/PlanUploader'
import StylePresets from './components/StylePresets'
import { ViewModeControls, CameraController } from './components/ViewModes'
import VideoExporter, { WalkingControls } from './components/VideoExporter'
import TourRecorder from './scenes/TourRecorder'
import { useProjectStore } from './stores/projectStore'
import { Box, Layers, MousePointer } from 'lucide-react'
import ProjectReview from './components/ProjectReview'
import axios from 'axios'
import { loadProject } from './utils/model'

export default function App() {
  const projectId=useProjectStore(s=>s.projectId),viewMode=useProjectStore(s=>s.viewMode)
  const furniture=useProjectStore(s=>s.furniture),recording=useProjectStore(s=>s.recording)
  useEffect(()=>{
    let active=true
    let previous:string|null=null
    try {previous=localStorage.getItem('archviz-project')} catch {return}
    if(previous) axios.get(`/api/v1/plans/${previous}`).then(r=>{
      if(active && !useProjectStore.getState().projectId) loadProject(r.data)
    }).catch(()=>{ /* A missing project leaves the uploader available. */ })
    return ()=>{active=false}
  },[])

  return (
    <div className="relative w-screen h-screen bg-gray-900 overflow-hidden">
      <div className="absolute inset-0">
        <Canvas shadows={false} gl={{ antialias: true, alpha: false, preserveDrawingBuffer:true }} dpr={[1,1.5]}>
          <color attach="background" args={[viewMode==='walkthrough'?'#dce7ec':'#1a1a2e']} />

          <Suspense fallback={null}>
            <CameraController key={viewMode} />
            {viewMode === 'walkthrough' && <WalkthroughCamera />}
            <House3D />
            <TourRecorder/>
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
            <p className="text-white/60 text-xs">Visualización y diseño de interiores</p>
          </div>
        </div>

        {projectId && (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-white/10 backdrop-blur rounded-full">
              <Layers className="w-3.5 h-3.5 text-blue-400" />
              <span className="text-white/80 text-xs">{furniture.length} muebles</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-white/10 backdrop-blur rounded-full">
              <MousePointer className="w-3.5 h-3.5 text-green-400" />
              <span className="text-white/80 text-xs">{viewMode}</span>
            </div>
          </div>
        )}
        {projectId && <button disabled={recording} className="text-white text-xs border border-white/30 rounded px-3 py-2" onClick={()=>{if(useProjectStore.getState().dirty && !window.confirm('Hay cambios sin guardar. ¿Descartarlos y abrir otro archivo?'))return;useProjectStore.getState().clearProject();try{localStorage.removeItem('archviz-project')}catch{/* optional */}}}>Importar otro archivo</button>}
      </header>
      <ProjectReview />

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

      {projectId && viewMode === 'walkthrough' && <WalkingControls/>}

    </div>
  )
}
