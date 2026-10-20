import { useEffect, useState } from 'react'
import axios from 'axios'
import { Home, X } from 'lucide-react'
import { useProjectStore } from '../stores/projectStore'
import type { RoofSettings } from '../types/model'
import { currentPlan, interiorError } from '../utils/interior'
import { loadProject } from '../utils/model'

type Source={id:string;name:string;role:string;metadata?:{document_type?:string;page?:number}}
type Analysis={parameters:Partial<RoofSettings>;evidence:{field:string;value:unknown;text:string}[];warnings:string[];page_count:number;source:{id:string;page:number;name:string}}
const types=[['floor_plan','Planta arquitectónica'],['elevation','Fachadas y secciones'],['roof','Planta de cubierta'],['structure','Estructura y cimentación'],['electrical','Electricidad'],['plumbing','Plomería'],['reference','Otra referencia']]
const defaults:RoofSettings={kind:'gable',pitch:6,eave_height:3.1,overhang:.4,axis:'z',material:'shingle',color:'#626267'}

export default function RoofAndPlans() {
  const {projectId,floorPlan,activePanel,recording,roofVisible,dirty}=useProjectStore()
  const open=activePanel==='roof'
  const [tab,setTab]=useState<'documents'|'roof'>('documents')
  const [sources,setSources]=useState<Source[]>([])
  const [sourceId,setSourceId]=useState(''),[documentType,setDocumentType]=useState('reference'),[page,setPage]=useState(1)
  const [analysis,setAnalysis]=useState<Analysis|null>(null)
  const [parameterSource,setParameterSource]=useState<{id:string;page:number}|null>(null)
  const [settings,setSettings]=useState<RoofSettings>(defaults)
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('')
  const [preview,setPreview]=useState('')
  useEffect(()=>{
    const saved=useProjectStore.getState().floorPlan?.roof
    setSources([]);setSourceId('');setAnalysis(null);setParameterSource(saved?.source.id?{id:saved.source.id,page:saved.source.page??1}:null);setPreview('');setMessage('');setTab('documents')
    setSettings(useProjectStore.getState().floorPlan?.roof?.settings??{...defaults,eave_height:Math.ceil(Math.max(2.8,...useProjectStore.getState().walls.map(w=>w.height))*100)/100+.12})
  },[projectId])
  useEffect(()=>{
    if(!open||!projectId)return
    const controller=new AbortController()
    axios.get(`/api/v1/plans/${projectId}/sources`,{signal:controller.signal})
      .then(r=>setSources(r.data.sources)).catch(e=>{if(!axios.isCancel(e))setMessage(interiorError(e))})
    return ()=>controller.abort()
  },[open,projectId])
  useEffect(()=>{if(floorPlan?.roof)setSettings(floorPlan.roof.settings)},[floorPlan?.roof])
  if(!projectId||!floorPlan)return null
  const selected=sources.find(s=>s.id===sourceId)
  const isPdf=selected?.name.toLowerCase().endsWith('.pdf')
  const run=async(action:()=>Promise<void>)=>{
    setBusy(true);setMessage('')
    try{await action()}catch(e){setMessage(interiorError(e))}finally{setBusy(false)}
  }
  const current=()=>useProjectStore.getState().projectId===projectId
  const chooseDocument=(id:string)=>{
    const source=sources.find(s=>s.id===id)
    setSourceId(id);setDocumentType(source?.metadata?.document_type??(source?.role==='original'?'floor_plan':'reference'))
    setPage(source?.metadata?.page??1);setAnalysis(null);setPreview('')
  }
  const attach=(files:File[])=>run(async()=>{
    let count=0
    for(const file of files) {
      if(!current())return
      if(file.size>20*1024*1024)throw new Error(`${file.name} supera 20 MB. ${count} documentos añadidos.`)
      const form=new FormData();form.append('file',file);form.append('document_type','reference')
      try{
        const response=await axios.post(`/api/v1/plans/${projectId}/sources`,form)
        if(!current())return
        setSources(response.data.sources);count++
      }catch(e){throw new Error(`${count} documentos añadidos. ${file.name}: ${interiorError(e)}`)}
    }
    setMessage(`${count} archivos revisados y conservados en esta casa. Los duplicados se guardan una sola vez. Selecciona cada documento para indicar su función y página.`)
  })
  const describe=()=>run(async()=>{
    const response=await axios.patch(`/api/v1/plans/${projectId}/sources/${sourceId}`,{document_type:documentType,page})
    if(!current())return
    setSources(response.data.sources);setMessage('Función y página guardadas. La planta 3D se conserva.')
  })
  const inspect=()=>run(async()=>{
    const id=sourceId,p=page
    const response=await axios.get(`/api/v1/plans/${projectId}/sources/${id}/inspect`,{params:{page:p}})
    if(!current())return
    setAnalysis(response.data);setPreview(`/api/v1/plans/${projectId}/sources/${id}/preview?page=${p}`)
    setMessage(response.data.evidence.length?'Datos encontrados. Comprueba la página antes de usarlos.':'No se encontraron parámetros de techo reconocibles en esta página. Puedes elegir un diseño manual.')
  })
  const generate=()=>run(async()=>{
    const plan=currentPlan(),signature=JSON.stringify(plan)
    const response=await axios.post('/api/v1/roofs/preview',{floor_plan:plan,settings,
      project_id:projectId,source_id:parameterSource?.id,source_page:parameterSource?.page??1})
    if(!current())return
    if(JSON.stringify(currentPlan())!==signature)throw new Error('El modelo cambió durante el cálculo. Vuelve a generar el techo.')
    const state=useProjectStore.getState()
    useProjectStore.setState({floorPlan:{...state.floorPlan!,roof:response.data.roof},dirty:true,roofVisible:true,isPlaying:false,viewMode:'3d-orbit'})
    setMessage('Techo añadido como propuesta visual. Revisa el resultado y guarda el proyecto.')
  })
  const save=()=>run(async()=>{
    const state=useProjectStore.getState(),signature=JSON.stringify(currentPlan())
    const response=await axios.put(`/api/v1/plans/${projectId}/review`,{base_revision:state.revision,floor_plan:currentPlan(),
      approved:false,measurements_confirmed:state.measurementsConfirmed,allow_learning:false,notes:'Techo y documentos: propuesta visual para revisar.'})
    if(!current())return
    if(JSON.stringify(currentPlan())===signature)loadProject(response.data)
    else useProjectStore.setState({revision:response.data.revision,dirty:true})
    setMessage('Proyecto guardado con techo, interiores y referencias. La cubierta sigue pendiente de revisión.')
  })
  const number=(label:string,key:'pitch'|'eave_height'|'overhang',step:number,min:number,max:number)=><label className="block text-xs">{label}<input aria-label={label} type="number" value={settings[key]} step={step} min={min} max={max} onChange={e=>setSettings({...settings,[key]:Number(e.target.value)})} className="border rounded w-full p-2 mt-1"/></label>
  return <>
    <button disabled={recording} onClick={()=>useProjectStore.setState({activePanel:open?null:'roof',placementMode:false,tourPointMode:false})} className="absolute top-20 left-6 z-30 flex gap-2 items-center bg-white text-gray-800 rounded-lg px-4 py-2 shadow-lg text-sm disabled:opacity-50"><Home size={17}/>Techo y planos</button>
    {floorPlan.roof&&!open&&<button disabled={recording} onClick={()=>useProjectStore.setState({roofVisible:!roofVisible})} className="absolute top-32 left-6 z-20 rounded-lg bg-white/95 p-2 text-xs text-gray-800">{roofVisible?'Ocultar techo · ver interiores':'Mostrar techo'}</button>}
    {open&&<aside aria-label="Techo y planos" className="absolute top-32 left-6 bottom-6 z-30 w-[370px] max-w-[calc(100vw-3rem)] bg-white rounded-xl shadow-xl p-4 overflow-y-auto text-gray-800 space-y-3">
      <div className="flex justify-between"><h2 className="font-bold text-lg">Techo y planos</h2><button aria-label="Cerrar techo y planos" onClick={()=>useProjectStore.setState({activePanel:null})}><X size={18}/></button></div>
      <div className="flex gap-2">{[['documents','1. Documentos'],['roof','2. Techo']].map(([id,label])=><button key={id} disabled={busy} className={`rounded px-3 py-2 text-xs ${tab===id?'bg-blue-600 text-white':'bg-gray-100'}`} onClick={()=>setTab(id as typeof tab)}>{label}</button>)}</div>
      <fieldset disabled={busy||recording} className="space-y-3 disabled:opacity-60">
      {tab==='documents'?<>
        <p className="text-xs">Una casa, varios planos. Añade fachadas, cubierta, estructura e instalaciones a este proyecto. Los originales se conservan; adjuntarlos no sustituye los muros ni los muebles.</p>
        <label className="block text-xs font-semibold">Añadir planos a esta casa<input aria-label="Añadir planos a esta casa" type="file" multiple accept=".pdf,.dxf,.png,.jpg,.jpeg,.json,.glb,.gltf,.obj,.ifc,.archviz" onChange={e=>{const files=Array.from(e.target.files??[]);e.target.value='';if(files.length)void attach(files)}} className="block text-xs mt-2 w-full"/></label>
        <p className="text-xs text-gray-500">20 MB por archivo · 100 MB por proyecto. El ZIP completo incluye los originales.</p>
        <label className="block text-xs">Documento<select aria-label="Documento de la casa" value={sourceId} onChange={e=>chooseDocument(e.target.value)} className="block w-full border p-2 rounded mt-1"><option value="">Selecciona un plano</option>{sources.map(s=><option key={s.id} value={s.id}>{s.role==='original'?'Base · ':''}{s.name}</option>)}</select></label>
        {selected&&<>
          <label className="block text-xs">Función del plano<select aria-label="Función del plano" value={documentType} onChange={e=>setDocumentType(e.target.value)} className="block w-full border p-2 rounded mt-1">{types.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
          <label className="block text-xs">Página del documento<input aria-label="Página del documento" type="number" min={1} max={1000} value={page} onChange={e=>{setPage(Math.max(1,Math.floor(Number(e.target.value))));setAnalysis(null);setPreview('')}} className="block border p-2 rounded mt-1 w-full"/></label>
          <button onClick={describe} className="border rounded p-2 text-xs w-full">Guardar función y página</button>
          {isPdf?<button onClick={inspect} className="bg-blue-600 text-white rounded p-2 text-xs w-full">Ver página y leer datos de techo</button>:<p className="text-xs text-amber-800">Documento conservado como referencia. La lectura de notas del techo está disponible para PDF vectorial.</p>}
        </>}
        {preview&&<a href={preview} target="_blank" rel="noreferrer" aria-label="Abrir página del plano"><img src={preview} alt="Página seleccionada del plano" className="border rounded w-full"/></a>}
        {analysis&&<div className="space-y-2 bg-blue-50 p-3 rounded text-xs">
          <p className="font-semibold">{analysis.source.name} · página {analysis.source.page} de {analysis.page_count}</p>
          {analysis.evidence.map((e,i)=><p key={i}>{e.text}</p>)}
          {analysis.warnings.map((w,i)=><p key={i}>{w}</p>)}
          {Object.keys(analysis.parameters).length>0&&<button className="rounded bg-blue-600 text-white p-2 w-full" onClick={()=>{setSettings({...settings,...analysis.parameters});setParameterSource({id:analysis.source.id,page:analysis.source.page});setTab('roof');setMessage('Datos del documento cargados. Elige la forma y orientación; la geometría será una propuesta para revisar.')}}>Usar estos datos en la propuesta</button>}
        </div>}
      </>:<>
        <p className="text-xs">Elige una cubierta y ajusta pendiente, altura y aleros. La propuesta respeta el contorno del suelo y deja abiertos sus patios.</p>
        <p className="text-xs bg-amber-50 p-2 rounded">Esta etapa genera una cubierta continua. Una casa con varios volúmenes necesita revisar alturas, cumbreras y encuentros antes de considerarla fiel al plano.</p>
        {parameterSource&&<p className="text-xs bg-blue-50 p-2 rounded">Parámetros vinculados a un documento · página {parameterSource.page}. <button className="underline" onClick={()=>setParameterSource(null)}>Usar solo diseño manual</button></p>}
        <label className="block text-xs">Forma del techo<select aria-label="Forma del techo" value={settings.kind} onChange={e=>setSettings({...settings,kind:e.target.value as RoofSettings['kind']})} className="block border p-2 rounded w-full mt-1"><option value="flat">Plano</option><option value="shed">Una agua</option><option value="gable">Dos aguas</option><option value="hip">Cuatro aguas · aproximación</option></select></label>
        {settings.kind!=='flat'&&number('Pendiente (subida por cada 12)', 'pitch',.5,.5,24)}
        {number('Altura de apoyo del techo (m)','eave_height',.01,1.9,30)}
        {number('Alero exterior (m)','overhang',.01,0,1.5)}
        {['gable','shed'].includes(settings.kind)&&<label className="block text-xs">Orientación<select aria-label="Orientación del techo" value={settings.axis} onChange={e=>setSettings({...settings,axis:e.target.value as 'x'|'z'})} className="block w-full border p-2 rounded mt-1"><option value="z">Cumbrera / borde alto sobre eje Z</option><option value="x">Cumbrera / borde alto sobre eje X</option></select></label>}
        <label className="block text-xs">Acabado<select aria-label="Acabado del techo" value={settings.material} onChange={e=>setSettings({...settings,material:e.target.value as RoofSettings['material']})} className="block w-full border p-2 rounded mt-1"><option value="shingle">Shingle asfáltico</option><option value="metal">Metal</option><option value="tile">Teja</option><option value="membrane">Membrana</option></select></label>
        <label className="flex gap-3 items-center text-xs">Color del techo<input aria-label="Color del techo" type="color" value={settings.color} onChange={e=>setSettings({...settings,color:e.target.value})}/></label>
        <button className="w-full rounded bg-blue-600 text-white p-2 text-sm" onClick={generate}>{floorPlan.roof?'Actualizar propuesta de techo':'Generar propuesta de techo'}</button>
        {floorPlan.roof&&<>
          <p className="text-xs">{floorPlan.roof.origin==='document_parameters'?'Con datos de '+floorPlan.roof.source.name:'Diseño elegido por el usuario'} · propuesta para revisar</p>
          <label className="flex gap-2 text-xs"><input type="checkbox" checked={roofVisible} onChange={e=>useProjectStore.setState({roofVisible:e.target.checked})}/>Mostrar techo · desmarca para ver los interiores</label>
          <button className="text-xs text-red-700" onClick={()=>{const state=useProjectStore.getState();useProjectStore.setState({floorPlan:{...state.floorPlan!,roof:null},dirty:true})}}>Retirar techo de la propuesta</button>
          {floorPlan.roof.warnings.map((w,i)=><p className="text-xs text-amber-800" key={i}>{w}</p>)}
        </>}
      </>}
      <button disabled={!dirty} onClick={save} className="bg-gray-800 text-white rounded p-2 text-sm w-full disabled:opacity-40">Guardar proyecto</button>
      </fieldset>
      {busy&&<p role="status" className="text-xs">Procesando…</p>}
      {message&&<p role="status" className="text-xs bg-blue-50 p-3 rounded">{message}</p>}
    </aside>}
  </>
}
