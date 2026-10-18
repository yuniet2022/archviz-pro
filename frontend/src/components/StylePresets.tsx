import { useEffect, useState } from 'react'
import axios from 'axios'
import { Armchair, X, Palette, Plus, Move, RotateCw, Trash2 } from 'lucide-react'
import { useProjectStore, type Furniture } from '../stores/projectStore'
import type { InteriorStyle, Point } from '../types/model'
import { currentPlan, furnitureFromModel, interiorError, moveFurniture } from '../utils/interior'

type CatalogItem={model:string;name:string;category:string;dimensions:Point}

export default function StylePresets() {
  const {floorPlan,furniture,selectedStyle,selectedFurnitureId,activePanel,recording,placementMode,interiorMessage}=useProjectStore()
  const [styles,setStyles]=useState<InteriorStyle[]>([])
  const [catalog,setCatalog]=useState<CatalogItem[]>([])
  const [tab,setTab]=useState<'styles'|'choice'|'catalog'|'edit'|'auto'>('styles')
  const [roomId,setRoomId]=useState('')
  const [busy,setBusy]=useState(false)
  const [search,setSearch]=useState('')
  const [draft,setDraft]=useState<Furniture|null>(null)
  const selected=furniture.find(item=>item.id===selectedFurnitureId)
  const message=(text:string)=>useProjectStore.setState({interiorMessage:text})
  useEffect(()=>{
    const controller=new AbortController()
    Promise.all([axios.get('/api/v1/furnish/styles',{signal:controller.signal}),axios.get('/api/v1/furnish/catalog',{signal:controller.signal})])
      .then(([a,b])=>{setStyles(a.data.styles);setCatalog(b.data.items)})
      .catch(error=>{if(!axios.isCancel(error))message('No se pudo cargar el catálogo. Vuelve a abrir la aplicación.')})
    return ()=>controller.abort()
  },[])
  useEffect(()=>{setDraft(selected?{...selected}:null)},[selected])
  useEffect(()=>{if(selectedFurnitureId)setTab('edit')},[selectedFurnitureId])
  useEffect(()=>{if(roomId&&!floorPlan?.rooms.some(r=>r.id===roomId))setRoomId('')},[floorPlan,roomId])
  if(!floorPlan)return null
  const open=activePanel==='furniture'
  const style=styles.find(s=>s.id===selectedStyle)
  const chooseStyle=(value:InteriorStyle)=>{
    const state=useProjectStore.getState()
    if(!state.floorPlan)return
    const changed=state.furniture.map(item=>({...item,style:value.id,
      color:item.model==='plant'?'#4e7651':item.material==='fabric'?value.fabric:
        item.material==='wood'?value.wood:item.color}))
    useProjectStore.setState({selectedStyle:value.id,floorPlan:{...state.floorPlan,interior_style:value},
      furniture:changed,dirty:true,interiorMessage:`Estilo ${value.name} aplicado. Se conserva la distribución.`})
    setTab('choice')
  }
  const run=async(action:()=>Promise<void>)=>{
    setBusy(true);message('')
    try{await action()}catch(error){message(interiorError(error))}finally{setBusy(false)}
  }
  const autoFurnish=()=>run(async()=>{
    if(!style)return
    if(furniture.length&&!window.confirm(roomId?'¿Sustituir los muebles de este ambiente?':'¿Sustituir la distribución actual con una propuesta nueva?'))return
    const plan=currentPlan(),projectId=useProjectStore.getState().projectId,signature=JSON.stringify(currentPlan())
    const keep=roomId?furniture.filter(item=>item.room_id!==roomId):[]
    const response=await axios.post(`/api/v1/furnish/layout/${style.id}`,{
      floor_plan:{...plan,furniture:plan.furniture instanceof Array?plan.furniture.filter((item:{room_id?:string})=>roomId&&item.room_id!==roomId):[]},
      room_ids:roomId?[roomId]:null,keep_existing:!!roomId,
    })
    if(useProjectStore.getState().projectId!==projectId)return
    if(JSON.stringify(currentPlan())!==signature)throw new Error('El plano cambió mientras se preparaba la propuesta. Vuelve a generarla.')
    const items=response.data.furniture.map(furnitureFromModel)
    useProjectStore.setState({furniture:items,dirty:true,tour:null,isPlaying:false,
      selectedFurnitureId:'',placementMode:false,
      interiorMessage:`Propuesta: ${items.length-keep.length} muebles. ${response.data.warnings.join(' ')}`})
    setTab('catalog')
  })
  const add=(model:string)=>run(async()=>{
    const projectId=useProjectStore.getState().projectId,signature=JSON.stringify(currentPlan())
    const response=await axios.post('/api/v1/furnish/add',{floor_plan:currentPlan(),model,room_id:roomId,style:style?.id})
    if(useProjectStore.getState().projectId!==projectId)return
    if(JSON.stringify(currentPlan())!==signature)throw new Error('El plano cambió mientras se añadía el mueble. Vuelve a intentarlo.')
    const item=furnitureFromModel(response.data.item)
    useProjectStore.getState().addFurniture(item)
    useProjectStore.setState({selectedFurnitureId:item.id,interiorMessage:'Mueble añadido. Puedes moverlo, girarlo o cambiar sus medidas.'})
    setTab('edit')
  })
  const commit=(item:Furniture)=>run(async()=>{await moveFurniture(item);message('Mueble actualizado.')})
  const update=(patch:Partial<Furniture>)=>setDraft(draft?{...draft,...patch}:null)
  const nudge=(x:number,z:number)=>{if(selected)void commit({...selected,position:[selected.position[0]+x,selected.position[1],selected.position[2]+z]})}
  return <>
    <button disabled={recording} onClick={()=>useProjectStore.setState({activePanel:open?null:'furniture'})}
      className="flex items-center gap-2 bg-white text-gray-800 px-4 py-3 rounded-xl font-semibold text-sm disabled:opacity-50">
      <Armchair size={18}/>{open?'Cerrar muebles':'Muebles y estilos'}
    </button>
    {open&&<aside aria-label="Muebles y estilos" className="absolute left-4 sm:left-6 bottom-20 w-[350px] max-w-[calc(100vw-2rem)] max-h-[calc(100dvh-14rem)] overflow-y-auto bg-white rounded-2xl p-4 text-gray-800 space-y-3 pointer-events-auto">
      <div className="flex items-center justify-between"><h2 className="font-bold flex gap-2 items-center"><Armchair size={18}/>Diseño de interiores</h2>
        <button aria-label="Cerrar diseño de interiores" onClick={()=>useProjectStore.setState({activePanel:null})}><X size={18}/></button></div>
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 text-xs">
        {([['styles','Estilos'],['catalog','Manual'],['auto','Asistente'],['edit','Editar mueble']] as const).map(([value,label])=><button key={value} onClick={()=>setTab(value)} className={`flex-1 p-2 rounded ${tab===value?'bg-white font-semibold':''}`}>{label}</button>)}
      </div>
      <fieldset disabled={busy||recording} className="space-y-3 disabled:opacity-60">
        {tab==='styles'&&<>
          <p className="text-xs text-gray-500">Elige los colores de paredes, suelo y mobiliario. Cambiar de estilo conserva las posiciones.</p>
          <div className="grid grid-cols-2 gap-2">{styles.map(value=><button key={value.id} aria-pressed={selectedStyle===value.id} onClick={()=>chooseStyle(value)} className={`border rounded-xl p-2 text-left ${selectedStyle===value.id?'border-blue-600 ring-1 ring-blue-600':'border-gray-200'}`}>
            <div className="flex h-6 rounded overflow-hidden mb-2">{[value.wall,value.floor,value.fabric,value.wood,value.accent].map((color,i)=><span key={i} className="flex-1" style={{backgroundColor:color}}/>)}</div>
            <span className="text-xs font-semibold block">{value.name}</span><span className="text-[10px] text-gray-500 block mt-1">{value.description}</span>
          </button>)}</div>
        </>}
        {tab==='choice'&&<><div className="bg-gray-50 p-3 rounded-xl"><p className="text-sm font-semibold">{style?.name}</p><p className="text-xs text-gray-500 mt-1">¿Cómo quieres decorar la casa?</p></div><div className="grid grid-cols-2 gap-2">
          <button disabled={!style} onClick={()=>setTab('catalog')} className="border border-blue-600 text-blue-700 p-3 rounded-xl text-sm font-semibold disabled:opacity-40">Decorar yo<span className="block text-[11px] font-normal mt-1">Elegir y colocar cada mueble</span></button>
          <button disabled={!style} onClick={()=>setTab('auto')} className="bg-blue-600 text-white p-3 rounded-xl text-sm font-semibold disabled:opacity-40">Decorar automáticamente<span className="block text-[11px] font-normal mt-1">Propuesta según estilo y medidas</span></button>
        </div></>}
        {tab==='auto'&&<p className="text-xs text-gray-500">El asistente propone muebles por ambiente, comprueba el suelo y deja libres las puertas. Puedes editar la propuesta después.</p>}
        {(tab==='auto'||tab==='catalog')&&<>
          <label className="block text-xs font-medium">Ambiente<select aria-label="Ambiente para muebles" value={roomId} onChange={e=>setRoomId(e.target.value)} className="block border rounded-lg w-full mt-1 p-2">
            <option value="">Toda la casa / selecciona para añadir</option>{floorPlan.rooms.map((room,i)=><option key={room.id} value={room.id}>{room.name} · {i+1}</option>)}
          </select></label>
          {roomId&&<label className="block text-xs">Uso del ambiente<select aria-label="Uso del ambiente" value={floorPlan.rooms.find(room=>room.id===roomId)?.room_type??''} onChange={e=>useProjectStore.setState({floorPlan:{...floorPlan,rooms:floorPlan.rooms.map(room=>room.id===roomId?{...room,room_type:e.target.value}:room)},dirty:true,tour:null,isPlaying:false})} className="block border rounded-lg w-full p-2 mt-1">
            {([['','Según nombre del plano'],['living','Sala'],['bedroom','Dormitorio'],['dining','Comedor'],['kitchen','Cocina'],['bathroom','Baño'],['laundry','Lavandería'],['outdoor','Terraza'],['closet','Clóset'],['circulation','Paso / garaje sin amueblar']] as const).map(([value,label])=><option key={value} value={value}>{label}</option>)}
          </select></label>}
          {tab==='auto'&&<button disabled={!style} onClick={autoFurnish} className="w-full bg-blue-600 text-white text-sm font-semibold p-2.5 rounded-lg disabled:opacity-40">
            {busy?'Preparando…':roomId?'Amueblar este ambiente':'Amueblar automáticamente'}
          </button>}
          {!style&&<p className="text-xs text-amber-800">Elige primero un estilo.</p>}
        </>}
        {tab==='catalog'&&<>
          <p className="text-xs text-gray-500">{style?.name??'Sin estilo'} · Medidas reales en metros. Selecciona un ambiente para añadir piezas.</p>
          <input aria-label="Buscar mueble" placeholder="Buscar sofá, cama, mesa…" value={search} onChange={e=>setSearch(e.target.value)} className="w-full border rounded-lg p-2 text-sm"/>
          <div className="grid grid-cols-2 gap-2">{catalog.filter(item=>item.name.toLowerCase().includes(search.toLowerCase())).map(item=><button key={item.model} disabled={!roomId||!style} onClick={()=>add(item.model)} className="border rounded-xl p-3 text-left hover:border-blue-500 disabled:opacity-40">
            <Plus size={16} className="text-blue-600 mb-1"/><span className="block text-xs font-semibold">{item.name}</span>
            <span className="text-[10px] text-gray-500">{item.dimensions.x.toFixed(2)} × {item.dimensions.z.toFixed(2)} × {item.dimensions.y.toFixed(2)} m</span>
          </button>)}</div>
        </>}
        {tab==='edit'&&<>
          <select aria-label="Mueble seleccionado" value={selectedFurnitureId} onChange={e=>useProjectStore.setState({selectedFurnitureId:e.target.value})} className="border rounded-lg w-full p-2 text-sm">
            <option value="">Selecciona un mueble</option>{furniture.map((item,i)=><option key={item.id} value={item.id}>{item.name} · {i+1}</option>)}
          </select>
          {draft&&selected&&<>
            <label className="block text-xs">Nombre<input aria-label="Nombre del mueble" value={draft.name} maxLength={100} onChange={e=>update({name:e.target.value})} className="border rounded p-2 w-full mt-1"/></label>
            <div className="grid grid-cols-2 gap-2">{(['X','Z'] as const).map((axis,i)=><label key={axis} className="text-xs">Posición {axis} (m)<input aria-label={`Mueble posición ${axis}`} type="number" step=".1" value={draft.position[i===0?0:2]} onChange={e=>update({position:i===0?[Number(e.target.value),draft.position[1],draft.position[2]]:[draft.position[0],draft.position[1],Number(e.target.value)]})} className="block border rounded p-1.5 w-full mt-1"/></label>)}</div>
            <div className="grid grid-cols-3 gap-2">{['Ancho','Alto','Fondo'].map((label,i)=><label key={label} className="text-xs">{label} (m)<input aria-label={`Mueble ${label.toLowerCase()}`} type="number" min=".05" max="10" step=".05" value={(draft.dimensions??[1,1,1])[i]} onChange={e=>{const dimensions:[number,number,number]=[...(draft.dimensions??[1,1,1])];dimensions[i]=Number(e.target.value);update({dimensions,position:[draft.position[0],dimensions[1]*draft.scale[1]/2,draft.position[2]]})}} className="block border rounded p-1.5 w-full mt-1"/></label>)}</div>
            <div className="grid grid-cols-2 gap-2"><label className="text-xs">Giro (grados)<input aria-label="Giro del mueble" type="number" step="15" value={Math.round(draft.rotation[1]*180/Math.PI)} onChange={e=>update({rotation:[0,Number(e.target.value)*Math.PI/180,0]})} className="block border rounded p-1.5 w-full mt-1"/></label>
              <label className="text-xs">Color<input aria-label="Color del mueble" type="color" value={draft.color} onChange={e=>update({color:e.target.value})} className="block w-full h-9 mt-1"/></label></div>
            <button onClick={()=>commit(draft)} className="bg-blue-600 text-white rounded-lg w-full p-2 text-sm">Aplicar cambios al mueble</button>
            <div className="flex justify-center gap-1">{[[0,-.1,'↑'],[-.1,0,'←'],[.1,0,'→'],[0,.1,'↓']].map(([x,z,label])=><button key={label} aria-label={`Mover mueble ${label}`} onClick={()=>nudge(Number(x),Number(z))} className="border rounded p-2 w-10">{label}</button>)}
              <button aria-label="Girar mueble 90 grados" onClick={()=>commit({...selected,rotation:[0,selected.rotation[1]+Math.PI/2,0]})} className="border rounded p-2"><RotateCw size={16}/></button></div>
            <button className={`border rounded-lg p-2 text-xs flex items-center gap-2 w-full ${placementMode?'border-blue-600 text-blue-700':''}`} onClick={()=>useProjectStore.setState({viewMode:'top-down',placementMode:!placementMode,tourPointMode:false,isPlaying:false,interiorMessage:'Haz clic sobre el suelo para colocar el mueble. Se comprobarán los obstáculos.'})}><Move size={15}/>{placementMode?'Cancelar colocación en planta':'Colocar con un clic en planta'}</button>
            <button onClick={()=>useProjectStore.getState().removeFurniture(selected.id)} className="text-red-700 text-xs flex items-center gap-2"><Trash2 size={14}/>Eliminar mueble</button>
          </>}
          {!selected&&<p className="text-xs text-gray-500">Haz clic en una pieza del modelo o selecciónala en la lista.</p>}
        </>}
      </fieldset>
      {interiorMessage&&<p role="status" className="text-xs bg-blue-50 text-blue-900 p-3 rounded-lg">{interiorMessage}</p>}
      {!!furniture.length&&<button disabled={busy||recording} onClick={()=>{if(window.confirm('¿Retirar todos los muebles y conservar la casa?'))useProjectStore.setState({furniture:[],selectedFurnitureId:'',tour:null,dirty:true,isPlaying:false,placementMode:false,interiorMessage:'Mobiliario retirado. La geometría de la casa se conserva.'})}} className="text-xs text-red-700">Vaciar mobiliario</button>}
      <p className="text-[11px] text-gray-500 flex gap-1"><Palette size={13}/>Guarda en «Revisión y archivo» para conservar muebles y acabados.</p>
    </aside>}
  </>
}
