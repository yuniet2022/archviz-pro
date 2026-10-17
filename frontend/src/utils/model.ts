import { useProjectStore, type Wall } from '../stores/projectStore'
import type { FloorPlan, LearningInfo } from '../types/model'
import type { Point } from '../types/model'
const tuple = (point: Point): [number,number,number] => [point.x,point.y,point.z]

export function loadProject(data: {project_id: string; floor_plan: FloorPlan; revision: number; learning: LearningInfo; measurements_confirmed?: boolean}) {
  const walls = data.floor_plan.walls.map(wall => ({...wall,
    start: [wall.start.x, wall.start.y, wall.start.z] as [number,number,number],
    end: [wall.end.x, wall.end.y, wall.end.z] as [number,number,number],
  }))
  useProjectStore.setState({ projectId: data.project_id, projectName: data.floor_plan.architectural_info.project_name,
    floorPlan: data.floor_plan, walls, revision: data.revision, learning: data.learning,
    measurementsConfirmed: data.measurements_confirmed ?? false, dirty: false,
    furniture: ((data.floor_plan.furniture ?? []) as {id:string;name:string;category:string;position:Point;rotation:Point;scale:Point;color:string;material:string;dimensions:Point}[])
      .map(f=>({...f,position:tuple(f.position),rotation:tuple(f.rotation),scale:tuple(f.scale),dimensions:tuple(f.dimensions)})), selectedStyle: null })
  try { localStorage.setItem('archviz-project', data.project_id) } catch { /* storage may be unavailable */ }
}

export function snapshot(plan: FloorPlan, walls: Wall[]): FloorPlan {
  const ids = new Set(walls.map(w=>w.id))
  const point = (v:[number,number,number])=>({x:v[0],y:v[1],z:v[2]})
  return {...plan, furniture: useProjectStore.getState().furniture.map(f=>({...f,
    position:point(f.position),rotation:point(f.rotation),scale:point(f.scale),dimensions:point(f.dimensions ?? [1,1,1])})), walls: walls.map(w=>({...w,
    start:{x:w.start[0],y:w.start[1],z:w.start[2]}, end:{x:w.end[0],y:w.end[1],z:w.end[2]},
  })), doors:plan.doors.filter(d=>ids.has(d.wall_id)), windows:plan.windows.filter(w=>ids.has(w.wall_id))}
}
