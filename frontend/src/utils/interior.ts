import axios from 'axios'
import { useProjectStore, type Furniture } from '../stores/projectStore'
import { snapshot } from './model'
import type { Point } from '../types/model'

export function currentPlan() {
  const state=useProjectStore.getState()
  if(!state.floorPlan) throw new Error('Primero importa un plano.')
  return snapshot(state.floorPlan,state.walls)
}

export function furnitureFromModel(item:Record<string,unknown>):Furniture {
  const tuple=(p:unknown):[number,number,number]=>{
    const point=p as Point; return [point.x,point.y,point.z]
  }
  return {...item,id:String(item.id),name:String(item.name),category:String(item.category),
    position:tuple(item.position),rotation:tuple(item.rotation),scale:tuple(item.scale),
    dimensions:tuple(item.dimensions),color:String(item.color),material:String(item.material)}
}

export function furnitureToModel(item:Furniture) {
  const point=(p:[number,number,number])=>({x:p[0],y:p[1],z:p[2]})
  return {...item,position:point(item.position),rotation:point(item.rotation),scale:point(item.scale),
    dimensions:point(item.dimensions??[1,1,1])}
}

export async function moveFurniture(item:Furniture) {
  const state=useProjectStore.getState(),projectId=state.projectId
  const plan=currentPlan(),signature=JSON.stringify(plan)
  await axios.post('/api/v1/furnish/placement',{floor_plan:plan,item:furnitureToModel(item)})
  if(useProjectStore.getState().projectId!==projectId) return
  if(JSON.stringify(currentPlan())!==signature)throw new Error('El diseño cambió durante la comprobación. Vuelve a colocar el mueble.')
  useProjectStore.getState().updateFurniture(item.id,item)
}

export function interiorError(error:unknown) {
  if(axios.isAxiosError(error)) {
    const detail=error.response?.data?.detail
    return typeof detail==='string'?detail:'No se pudo completar la operación. Inténtalo de nuevo.'
  }
  return error instanceof Error?error.message:'No se pudo completar la operación.'
}
