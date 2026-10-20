import { useEffect, useState } from 'react'
import axios from 'axios'
import { useProjectStore, type Wall } from '../stores/projectStore'
import type { ArchitecturalInfo, FloorPlan, ModelColumn } from '../types/model'
import { loadProject, snapshot } from '../utils/model'

function errorMessage(error: unknown) {
  if (!axios.isAxiosError(error)) return 'No se pudo completar la operación.'
  const detail = error.response?.data?.detail
  return Array.isArray(detail) ? detail.map(e=>e.msg).join('. ') : String(detail ?? error.message)
}

function NumberField({label,value,onChange}:{label:string;value:number;onChange:(v:number)=>void}) {
  return <label className="block text-xs text-gray-600">{label}<input aria-label={label} type="number" step=".01" value={value}
    onChange={e=>onChange(Number(e.target.value))} className="block w-full border rounded p-1.5 mt-1"/></label>
}

export default function ProjectReview() {
  const {projectId, floorPlan, walls, dirty, revision, measurementsConfirmed, learning, setWalls} = useProjectStore()
  const [open,setOpen] = useState(false)
  const activePanel=useProjectStore(s=>s.activePanel),recording=useProjectStore(s=>s.recording)
  useEffect(()=>{if(activePanel||recording)setOpen(false)},[activePanel,recording])
  const selected = useProjectStore(s=>s.selectedElementId)
  const setSelected = (id:string)=>useProjectStore.setState({selectedElementId:id})
  const [approved,setApproved] = useState(false)
  const [consent,setConsent] = useState(false)
  const [notes,setNotes] = useState('')
  const [message,setMessage] = useState('')
  const [busy,setBusy] = useState(false)
  const [stats,setStats] = useState<{approved_examples:number;reused_imports:number}|null>(null)
  const [sources,setSources] = useState<{id:string;name:string;role:string}[]>([])
  const [factor,setFactor] = useState(1)
  const refresh = async () => {
    const [memory, files] = await Promise.all([axios.get('/api/v1/plans/learning/status'),axios.get(`/api/v1/plans/${projectId}/sources`)])
    setStats(memory.data); setSources(files.data.sources)
  }
  useEffect(()=>{ if(open && projectId) refresh().catch(e=>setMessage(errorMessage(e))) },[open,projectId])
  useEffect(()=>{setApproved(false);setConsent(false);setNotes('');setMessage('');setSelected('')},[projectId])
  if (!projectId || !floorPlan) return null
  const wall = walls.find(w=>w.id===selected)
  const column = floorPlan.columns.find(c=>c.id===selected)
  const door = floorPlan.doors.find(o=>o.id===selected)
  const windowOpening = floorPlan.windows.find(o=>o.id===selected)
  const opening = door ?? windowOpening
  const changed = (plan:FloorPlan) => {
    useProjectStore.setState({floorPlan:plan,dirty:true,measurementsConfirmed:false,tour:null,isPlaying:false})
    setApproved(false)
  }
  const updateWall = (patch:Partial<Wall>) => {
    if (!wall) return
    setWalls(walls.map(w=>w.id===wall.id?{...w,...patch}:w)); setApproved(false)
    changed({...floorPlan,rooms:[],roof:null})
  }
  const updateColumn = (patch:Partial<ModelColumn>) => {
    if (!column) return
    changed({...floorPlan,roof:null,columns:floorPlan.columns.map(c=>c.id===column.id?{...c,...patch}:c)})
  }
  const updateOpening = (patch:Partial<NonNullable<typeof opening>>) => {
    if(!opening)return
    changed({...floorPlan,
      doors:floorPlan.doors.map(o=>o.id===selected?{...o,...patch}:o),
      windows:floorPlan.windows.map(o=>o.id===selected?{...o,...patch}:o)})
  }
  const updateInfo = (patch:Partial<ArchitecturalInfo>)=>changed({...floorPlan,architectural_info:{...floorPlan.architectural_info,...patch}})
  const save = async () => {
    setBusy(true);setMessage('')
    try {
      const response = await axios.put(`/api/v1/plans/${projectId}/review`,{
        base_revision:revision, floor_plan:snapshot(floorPlan,walls), approved,
        measurements_confirmed:measurementsConfirmed, allow_learning:consent, notes,
      })
      loadProject(response.data)
      setMessage(approved && consent?'Revisión guardada y disponible para reutilizar.':'Revisión guardada en el proyecto.')
      await refresh()
    } catch(error) {setMessage(errorMessage(error))} finally {setBusy(false)}
  }
  const download = async (path:string, filename:string) => {
    setBusy(true);setMessage('')
    try {
      const response = await axios.get(path,{responseType:'blob'})
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement('a');anchor.href=url;anchor.download=filename
      document.body.appendChild(anchor);anchor.click();anchor.remove()
      window.setTimeout(()=>URL.revokeObjectURL(url),30000)
    } catch {setMessage('No se pudo descargar. Guarda el proyecto y vuelve a intentarlo.')} finally {setBusy(false)}
  }
  const attach = async (file?:File) => {
    if(!file) return
    setBusy(true)
    try {
      const form = new FormData(); form.append('file',file)
      await axios.post(`/api/v1/plans/${projectId}/sources`,form)
      await refresh();setMessage('Fuente conservada. Los modelos GLB/IFC/OBJ se guardan como referencia, sin convertir.')
    } catch(error) {setMessage(errorMessage(error))} finally {setBusy(false)}
  }
  const scale = () => {
    if(!Number.isFinite(factor) || factor<=0 || factor>100) {setMessage('Usa un factor mayor que 0 y hasta 100.');return}
    const current = snapshot(floorPlan,walls)
    const p = (v:{x:number;y:number;z:number})=>({x:v.x*factor,y:v.y*factor,z:v.z*factor})
    const scaled:FloorPlan = {...current,roof:null,walls:current.walls.map(w=>({...w,start:p(w.start),end:p(w.end),height:w.height*factor,thickness:w.thickness*factor})),
      columns:current.columns.map(c=>({...c,position:p(c.position),width:c.width*factor,depth:c.depth*factor,height:c.height*factor})),
      floor_regions:(current.floor_regions??[]).map(r=>({...r,points:r.points.map(p),holes:r.holes.map(ring=>ring.map(p))})),
      fixtures:(current.fixtures??[]).map(f=>({...f,position:p(f.position),dimensions:p(f.dimensions),
        outline:f.outline.map(p),body_outline:(f.body_outline??[]).map(p),top_outline:(f.top_outline??[]).map(p),
        basin_centers:f.basin_centers.map(p),source_basin_centers:f.source_basin_centers.map(p),
        basin_sizes:f.basin_sizes.map(p),source_basin_sizes:f.source_basin_sizes.map(p),
        source_basin_outlines:(f.source_basin_outlines??[]).map(ring=>ring.map(p))})),
      doors:current.doors.map(d=>({...d,width:d.width*factor,height:d.height*factor})),
      windows:current.windows.map(w=>({...w,width:w.width*factor,height:w.height*factor,sill_height:(w.sill_height??0)*factor})),rooms:[]}
    const transform=current.source_transform as {format?:string;points_per_foot?:number}|undefined
    if(transform?.format==='pdf'&&typeof transform.points_per_foot==='number')scaled.source_transform={...transform,points_per_foot:transform.points_per_foot/factor}
    useProjectStore.setState({walls:scaled.walls.map(w=>({...w,start:[w.start.x,0,w.start.z],end:[w.end.x,0,w.end.z]})),furniture:[]})
    changed({...scaled,furniture:[]}); setFactor(1); setMessage('Geometría reescalada. Techo y mobiliario retirados; comprueba medidas y vuelve a guardarlo.')
  }
  return <>
    <button disabled={recording} onClick={()=>{useProjectStore.setState({activePanel:null});setOpen(!open)}} className="absolute top-20 right-6 z-30 bg-white text-gray-800 rounded-lg px-4 py-2 shadow-lg text-sm">{open?'Cerrar revisión':'Revisión y archivo'}</button>
    {open && <aside aria-label="Revisión y archivo" className="absolute z-30 right-6 top-32 bottom-6 w-96 max-w-[calc(100vw-3rem)] overflow-y-auto rounded-xl bg-white shadow-2xl p-5 text-gray-800 space-y-4">
      <h2 className="font-bold text-lg">Proyecto y aprendizaje</h2>
      <p className="text-xs text-gray-600">Revisión {revision} · {dirty?'Cambios sin guardar':'Guardado'} · {learning?.reused?'Corrección recuperada del mismo archivo':'Modelo para revisar'}</p>
      <section className="space-y-2">
        <label className="block text-xs">Nombre del proyecto<input aria-label="Nombre del proyecto" maxLength={200} value={floorPlan.architectural_info.project_name} onChange={e=>updateInfo({project_name:e.target.value})} className="border rounded p-2 w-full"/></label>
        <label className="block text-xs">Planta<input aria-label="Nombre de planta" maxLength={100} value={floorPlan.architectural_info.floor_name} onChange={e=>updateInfo({floor_name:e.target.value})} className="border rounded p-2 w-full"/></label>
        <label className="block text-xs">Jurisdicción / normativa de referencia<input aria-label="Jurisdicción" maxLength={200} value={floorPlan.architectural_info.jurisdiction} onChange={e=>updateInfo({jurisdiction:e.target.value})} className="border rounded p-2 w-full"/></label>
        <NumberField label="Norte (grados)" value={floorPlan.architectural_info.north_degrees} onChange={v=>updateInfo({north_degrees:v})}/>
        <label className="block text-xs">Notas constructivas<textarea aria-label="Notas constructivas" maxLength={10000} value={floorPlan.architectural_info.construction_notes} onChange={e=>updateInfo({construction_notes:e.target.value})} className="border rounded p-2 w-full"/></label>
      </section>
      <section className="space-y-2 border-t pt-3">
        <h3 className="font-semibold text-sm">Corregir el modelo · metros</h3>
        <select aria-label="Elemento a revisar" value={selected} onChange={e=>setSelected(e.target.value)} className="border rounded w-full p-2 text-sm">
          <option value="">Seleccionar elemento</option>
          {walls.map((w,i)=><option key={w.id} value={w.id}>Muro {i+1}</option>)}
          {floorPlan.columns.map((c,i)=><option key={c.id} value={c.id}>Columna {i+1}</option>)}
          {floorPlan.doors.map((o,i)=><option key={o.id} value={o.id}>Puerta {i+1}</option>)}
          {floorPlan.windows.map((o,i)=><option key={o.id} value={o.id}>Ventana {i+1}</option>)}
        </select>
        <div className="flex gap-2 text-xs">
          <button className="border p-2 rounded" onClick={()=>{const id=crypto.randomUUID();setWalls([...walls,{id,start:[0,0,0],end:[1,0,0],height:2.8,thickness:.15}]);setSelected(id);changed({...floorPlan,rooms:[],roof:null})}}>Añadir muro</button>
          <button className="border p-2 rounded" onClick={()=>{const id=crypto.randomUUID();changed({...floorPlan,roof:null,columns:[...floorPlan.columns,{id,position:{x:0,y:0,z:0},width:.3,depth:.3,height:2.8}]});setSelected(id)}}>Añadir columna</button>
        </div>
        {wall && <div className="grid grid-cols-2 gap-2">
          {(['start','end'] as const).flatMap(side=>([0,2] as const).map(index=><NumberField key={`${side}${index}`} label={`${side==='start'?'Inicio':'Final'} ${index===0?'X':'Z'} (m)`} value={wall[side][index]} onChange={v=>{const point=[...wall[side]] as [number,number,number];point[index]=v;updateWall({[side]:point})}}/>))}
          <NumberField label="Altura muro (m)" value={wall.height} onChange={v=>updateWall({height:v})}/>
          <NumberField label="Grosor muro (m)" value={wall.thickness} onChange={v=>updateWall({thickness:v})}/>
        </div>}
        {column && <div className="grid grid-cols-2 gap-2">
          <NumberField label="Columna X (m)" value={column.position.x} onChange={v=>updateColumn({position:{...column.position,x:v}})}/>
          <NumberField label="Columna Z (m)" value={column.position.z} onChange={v=>updateColumn({position:{...column.position,z:v}})}/>
          <NumberField label="Ancho columna (m)" value={column.width} onChange={v=>updateColumn({width:v})}/>
          <NumberField label="Fondo columna (m)" value={column.depth} onChange={v=>updateColumn({depth:v})}/>
          <NumberField label="Altura columna (m)" value={column.height} onChange={v=>updateColumn({height:v})}/>
          <NumberField label="Giro columna (grados)" value={(column.rotation??0)*180/Math.PI} onChange={v=>updateColumn({rotation:v*Math.PI/180})}/>
          <label className="text-xs text-gray-600">Sección de columna<select aria-label="Sección de columna" value={column.shape??'rectangular'} onChange={e=>updateColumn({shape:e.target.value as ModelColumn['shape']})} className="block border rounded p-1.5 w-full"><option value="rectangular">Rectangular</option><option value="circular">Circular</option></select></label>
        </div>}
        {opening && <div className="grid grid-cols-2 gap-2">
          <label className="text-xs col-span-2">Muro de la abertura<select aria-label="Muro de la abertura" value={opening.wall_id} onChange={e=>updateOpening({wall_id:e.target.value})} className="block border rounded p-1.5 w-full">{walls.map((w,i)=><option key={w.id} value={w.id}>Muro {i+1}</option>)}</select></label>
          <NumberField label="Posición en el muro (0–1)" value={opening.position} onChange={v=>updateOpening({position:v})}/>
          <NumberField label="Ancho abertura (m)" value={opening.width} onChange={v=>updateOpening({width:v})}/>
          <NumberField label="Alto abertura (m)" value={opening.height} onChange={v=>updateOpening({height:v})}/>
          {windowOpening && <NumberField label="Antepecho ventana (m)" value={opening.sill_height??0} onChange={v=>updateOpening({sill_height:v})}/>}
          {door && <label className="text-xs">Tipo de puerta<select aria-label="Tipo de puerta" value={door.operation??'hinged'} onChange={e=>updateOpening({operation:e.target.value as typeof door.operation})} className="block border rounded p-1.5 w-full">{[['hinged','Abatible'],['double_hinged','Doble'],['sliding','Corredera'],['overhead','Garaje'],['bifold','Plegable']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>}
        </div>}
        {opening && <button className="text-xs text-red-700" onClick={()=>{changed({...floorPlan,doors:floorPlan.doors.filter(o=>o.id!==selected),windows:floorPlan.windows.filter(o=>o.id!==selected)});setSelected('')}}>Eliminar abertura seleccionada</button>}
        {(wall||column) && <button className="text-xs text-red-700" onClick={()=>{if(wall)setWalls(walls.filter(w=>w.id!==wall.id));changed({...floorPlan,roof:null,rooms:[],columns:floorPlan.columns.filter(c=>c.id!==selected)});setSelected('')}}>Eliminar elemento seleccionado</button>}
        <div className="flex items-end gap-2"><NumberField label="Factor de escala global" value={factor} onChange={setFactor}/><button className="border rounded p-2 text-xs" onClick={scale}>Aplicar escala</button></div>
      </section>
      <section className="space-y-2 border-t pt-3 text-xs">
        <label className="flex gap-2"><input type="checkbox" checked={measurementsConfirmed} onChange={e=>{useProjectStore.setState({measurementsConfirmed:e.target.checked});if(!e.target.checked)setApproved(false)}}/>He comprobado escala y medidas contra las fuentes.</label>
        <label className="flex gap-2"><input type="checkbox" checked={approved} disabled={!measurementsConfirmed} onChange={e=>setApproved(e.target.checked)}/>Aprobar esta revisión de geometría.</label>
        <label className="flex gap-2"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>Autorizar el uso de esta revisión para aprendizaje local.</label>
        <p className="text-gray-500">Ahora reutiliza correcciones del mismo archivo y configuración. Guarda ejemplos para futuro entrenamiento; todavía no aprende a interpretar casas diferentes.</p>
        <label className="block">Notas de revisión<textarea aria-label="Notas de revisión" maxLength={2000} value={notes} onChange={e=>setNotes(e.target.value)} className="border rounded w-full p-2"/></label>
        <button disabled={busy} onClick={save} className="w-full bg-blue-600 text-white rounded p-2 disabled:opacity-50">Guardar revisión</button>
        {learning?.contributing && <button disabled={busy} className="text-red-700" onClick={async()=>{setBusy(true);try{const r=await axios.delete(`/api/v1/plans/${projectId}/learning`);useProjectStore.setState({learning:r.data.learning});setConsent(false);await refresh();setMessage('Esta revisión ya no se reutilizará ni se incluirá en nuevos datasets. Las copias ya descargadas no cambian.')}catch(e){setMessage(errorMessage(e))}finally{setBusy(false)}}}>Retirar del aprendizaje</button>}
        {stats && <p>{stats.approved_examples} ejemplos disponibles · {stats.reused_imports} importaciones reutilizadas.</p>}
      </section>
      <section className="space-y-2 border-t pt-3 text-xs">
        <h3 className="font-semibold text-sm">Fuentes y descarga</h3>
        <p>Conserva alzados, secciones, cotas y modelos originales. GLB, IFC y OBJ se archivan como referencias.</p>
        <label className="block">Añadir documento o modelo de referencia<input aria-label="Añadir referencia" type="file" disabled={busy} accept=".pdf,.dxf,.png,.jpg,.jpeg,.json,.glb,.gltf,.obj,.ifc,.archviz" onChange={e=>{attach(e.target.files?.[0]);e.target.value=''}} className="block w-full mt-2"/></label>
        <ul className="space-y-1">{sources.map(s=><li key={s.id} className="truncate">{s.role==='original'?'Original':'Referencia'}: {s.name}</li>)}</ul>
        <p>Las descargas contienen la última revisión guardada.</p>
        <button disabled={busy||dirty} onClick={()=>download(`/api/v1/plans/${projectId}/export/archviz`,'proyecto.archviz')} className="w-full bg-blue-600 text-white rounded p-2 disabled:opacity-40">Proyecto ligero .archviz</button>
        <p>Modelo, medidas, revisiones y referencias comprimidos. Excluye los archivos originales; guárdalos aparte o descarga el ZIP completo.</p>
        <div className="grid grid-cols-2 gap-2">
          {(['dxf','svg','json'] as const).map(format=><button key={format} disabled={busy||dirty} onClick={()=>download(`/api/v1/plans/${projectId}/export/${format}`,`modelo.${format}`)} className="border rounded p-2 disabled:opacity-40">{format==='json'?'Modelo JSON':`Planta ${format.toUpperCase()}`}</button>)}
          <button disabled={busy||dirty} onClick={()=>download(`/api/v1/plans/${projectId}/archive`,'proyecto-completo.zip')} className="bg-gray-800 text-white rounded p-2 disabled:opacity-40">Proyecto completo ZIP</button>
        </div>
        <button disabled={busy} className="text-blue-700" onClick={()=>download('/api/v1/plans/learning/dataset','ejemplos-revisados.jsonl')}>Descargar ejemplos autorizados para futuro entrenamiento</button>
        <p>La planta exportada es un borrador del modelo. Información pendiente: {floorPlan.architectural_info.missing_information.join(', ')}.</p>
      </section>
      {floorPlan.warnings.map((warning,i)=><p key={i} className="text-xs text-amber-800">{warning}</p>)}
      {message && <p role="status" className="bg-blue-50 p-3 rounded text-xs">{message}</p>}
    </aside>}
  </>
}
