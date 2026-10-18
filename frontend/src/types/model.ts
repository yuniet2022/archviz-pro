export interface Point { x: number; y: number; z: number }
export interface ModelWall { id: string; start: Point; end: Point; height: number; thickness: number; [key: string]: unknown }
export interface ModelColumn { id: string; position: Point; width: number; depth: number; height: number; shape?: 'rectangular' | 'circular'; rotation?: number }
export interface FloorRegion { points: Point[]; holes: Point[][] }
export interface Opening { id: string; wall_id: string; position: number; width: number; height: number; sill_height?: number; operation?: 'hinged' | 'double_hinged' | 'sliding' | 'overhead' | 'bifold' }
export interface ModelRoom { id: string; name: string; points: Point[]; area_sqm: number; ceiling_height: number }
export interface ArchitecturalInfo {
  project_name: string; floor_name: string; jurisdiction: string; north_degrees: number
  construction_notes: string; missing_information: string[]
}
export interface FloorPlan {
  walls: ModelWall[]; columns: ModelColumn[]; doors: Opening[]; windows: Opening[]
  rooms: ModelRoom[]; dimensions: Record<string, number>; warnings: string[]
  floor_regions?: FloorRegion[]
  architectural_info: ArchitecturalInfo; [key: string]: unknown
}
export interface LearningInfo { reused: boolean; contributing: boolean; trained_model: boolean }
