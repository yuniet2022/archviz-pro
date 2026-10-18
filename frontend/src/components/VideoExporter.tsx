import { useState } from 'react'
import { Video, Download, X, Route, MapPin, Play, Pause, RotateCcw } from 'lucide-react'
import axios from 'axios'
import { useProjectStore } from '../stores/projectStore'
import { currentPlan, interiorError } from '../utils/interior'

export default function VideoExporter() {
  const {activePanel,floorPlan,tour,tourProgress,tourDuration,isPlaying,recording,recordingError,recordingQuality,videoResult,tourPointMode}=useProjectStore()
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('')
  if(!floorPlan)return null
  const open=activePanel==='tour'
  const points=floorPlan.tour_waypoints??[]
  const prepare=async()=>{
    if(points.length===1){setMessage('Añade al menos dos puntos o borra el punto para crear la ruta automática.');return}
    setBusy(true);setMessage('')
    const projectId=useProjectStore.getState().projectId,signature=JSON.stringify(currentPlan())
    try {
      const result=await axios.post('/api/v1/furnish/tour',{floor_plan:currentPlan(),waypoints:points})
      if(useProjectStore.getState().projectId!==projectId)return
      if(JSON.stringify(currentPlan())!==signature)throw new Error('El diseño cambió durante el cálculo. Prepara otra vez el recorrido.')
      useProjectStore.setState({tour:result.data,tourProgress:0,isPlaying:false,tourPointMode:false})
      setMessage('Recorrido preparado. Puedes reproducirlo o entrar y caminar libremente.')
    }catch(error){setMessage(interiorError(error))}finally{setBusy(false)}
  }
  const enter=()=>useProjectStore.setState({viewMode:'walkthrough',placementMode:false,tourPointMode:false,selectedFurnitureId:'',isPlaying:false})
  const record=()=>{
    if(!tour)return
    enter()
    useProjectStore.setState({recording:true,recordingError:'',tourProgress:0,tour:{...tour}})
  }
  const setting=(patch:{tourDuration?:number;recordingQuality?:'720p'|'1080p'})=>{
    const state=useProjectStore.getState()
    useProjectStore.setState({...patch,dirty:true,floorPlan:state.floorPlan?{...state.floorPlan,tour_settings:{duration:patch.tourDuration??state.tourDuration,quality:patch.recordingQuality??state.recordingQuality}}:null})
  }
  return <>
    <button onClick={()=>useProjectStore.setState({activePanel:open?null:'tour'})} className="bg-white text-gray-800 px-4 py-3 rounded-xl flex gap-2 items-center text-sm font-semibold"><Video size={18}/>{recording?'Grabando…':open?'Cerrar recorrido':'Recorrido y vídeo'}</button>
    {open&&<aside aria-label="Recorrido y vídeo" className="absolute right-4 sm:right-6 bottom-20 w-[340px] max-w-[calc(100vw-2rem)] max-h-[calc(100dvh-14rem)] overflow-y-auto rounded-2xl bg-white p-4 text-gray-800 space-y-3 pointer-events-auto">
      <div className="flex items-center justify-between"><h2 className="font-bold flex gap-2 items-center"><Route size={18}/>Paseo virtual</h2><button aria-label="Cerrar panel del recorrido" onClick={()=>useProjectStore.setState({activePanel:null})}><X size={18}/></button></div>
      <fieldset disabled={busy||recording} className="space-y-3 disabled:opacity-60">
        <p className="text-xs text-gray-500">La ruta se calcula sobre el suelo, con puertas, muros, columnas y muebles. Si un ambiente no tiene paso libre, se indica abajo.</p>
        <div className="flex gap-2"><button onClick={()=>useProjectStore.setState({viewMode:'top-down',tourPointMode:!tourPointMode,placementMode:false,isPlaying:false})} className={`flex-1 text-xs border rounded-lg p-2 ${tourPointMode?'border-blue-600 text-blue-700':''}`}><MapPin size={14} className="inline mr-1"/>{tourPointMode?'Terminar de marcar':'Marcar puntos en planta'}</button>
          <button disabled={!points.length} onClick={()=>useProjectStore.setState({floorPlan:{...floorPlan,tour_waypoints:[]},tour:null,dirty:true,isPlaying:false})} className="text-xs border rounded-lg p-2">Borrar puntos</button></div>
        {!!points.length&&<p className="text-xs text-blue-800">{points.length} puntos marcados. Se conectarán en ese orden por los pasos libres.</p>}
        {tourPointMode&&<p className="text-xs bg-blue-50 p-2 rounded">Haz clic sobre el suelo de la planta para marcar las paradas.</p>}
        <button onClick={prepare} className="w-full bg-blue-600 text-white rounded-lg p-2.5 text-sm font-semibold">{busy?'Calculando pasos libres…':points.length?'Preparar ruta marcada':'Preparar recorrido automático'}</button>
        <label className="block text-xs">Duración: {tourDuration} segundos<input aria-label="Duración del recorrido" type="range" min="10" max="180" step="5" value={tourDuration} onChange={e=>setting({tourDuration:Number(e.target.value)})} className="block w-full mt-2 accent-blue-600"/></label>
        <button onClick={enter} className="w-full border rounded-lg p-2 text-sm">Entrar y caminar libremente</button>
        {tour&&<>
          <p className="text-xs text-gray-600">{tour.distance_m.toFixed(1)} m de recorrido · {tour.stops.length} paradas</p>
          <div className="flex gap-2"><button onClick={()=>{enter();useProjectStore.setState({isPlaying:!isPlaying})}} className="flex-1 bg-green-700 text-white rounded-lg p-2 text-sm flex items-center justify-center gap-1">{isPlaying?<Pause size={14}/>:<Play size={14}/>} {isPlaying?'Pausar':'Reproducir'}</button>
            <button onClick={()=>useProjectStore.setState({tour:{...tour},tourProgress:0,isPlaying:false})} className="border rounded-lg p-2 text-xs flex gap-1 items-center"><RotateCcw size={14}/>Inicio</button></div>
          <progress aria-label="Avance del recorrido" value={tourProgress} max="1" className="w-full accent-blue-600"/>
          <details className="text-xs"><summary className="cursor-pointer">Ambientes y avisos</summary><ul className="mt-2 space-y-1">{tour.stops.map((stop,i)=><li key={i}>{i+1}. {stop.name}</li>)}</ul>{tour.warnings.map((warning,i)=><p key={i} className="text-amber-800 mt-2">{warning}</p>)}</details>
        </>}
        <div className="border-t pt-3 space-y-2">
          <h3 className="text-sm font-semibold">Grabar la escena</h3>
          <label className="text-xs block">Resolución de salida<select aria-label="Resolución del vídeo" value={recordingQuality} onChange={e=>setting({recordingQuality:e.target.value as '720p'|'1080p'})} className="block border rounded-lg p-2 w-full mt-1"><option value="720p">720p · más ligero</option><option value="1080p">1080p</option></select></label>
          <p className="text-xs text-gray-500">Se graba el visor en este equipo. Mantén visible la pestaña. La fluidez depende del dispositivo; el archivo será MP4 o WebM según el navegador.</p>
          <button disabled={!tour} onClick={record} className="w-full bg-red-600 text-white rounded-lg p-2.5 text-sm font-semibold disabled:opacity-40">Grabar vídeo del recorrido</button>
        </div>
      </fieldset>
      {recording&&<div className="space-y-2"><p className="text-sm text-red-700">● Grabando la escena… {Math.round(tourProgress*100)} %</p><button onClick={()=>useProjectStore.setState({recording:false,isPlaying:false})} className="w-full border border-red-600 text-red-700 p-2 rounded-lg text-sm">Detener y guardar grabación</button></div>}
      {videoResult&&<a href={videoResult.url} download={`recorrido.${videoResult.extension}`} className="flex gap-2 items-center justify-center bg-blue-50 text-blue-700 p-2 rounded-lg text-sm"><Download size={15}/>Descargar vídeo .{videoResult.extension}</a>}
      {(recordingError||message)&&<p role="status" className="text-xs bg-blue-50 p-3 rounded-lg">{recordingError||message}</p>}
      <p className="text-[11px] text-gray-500">Guarda el proyecto para conservar puntos y ajustes del recorrido. Descarga el vídeo antes de cerrar la página.</p>
    </aside>}
  </>
}

export function WalkingControls() {
  const isPlaying=useProjectStore(s=>s.isPlaying),recording=useProjectStore(s=>s.recording)
  const set=(forward:number,turn:number)=>useProjectStore.setState({walkInput:{forward,turn}})
  if(isPlaying||recording)return null
  return <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-20 bg-black/65 text-white p-3 rounded-xl text-xs text-center max-w-[calc(100vw-2rem)]">
    <p className="mb-2">WASD para caminar · Arrastra para mirar · Flechas para girar</p>
    <div className="flex gap-2 justify-center">{[[0,1,'↶'],[1,0,'↑'],[-1,0,'↓'],[0,-1,'↷']].map(([forward,turn,label])=><button key={label} aria-label={`Caminar ${label}`} style={{touchAction:'none'}} className="bg-white/20 rounded-lg w-10 h-9" onPointerDown={event=>{event.currentTarget.setPointerCapture(event.pointerId);set(Number(forward),Number(turn))}} onPointerUp={()=>set(0,0)} onPointerCancel={()=>set(0,0)} onLostPointerCapture={()=>set(0,0)}>{label}</button>)}</div>
  </div>
}
