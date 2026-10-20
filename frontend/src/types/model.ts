export interface Point { x: number; y: number; z: number }
export interface ModelWall { id: string; start: Point; end: Point; height: number; thickness: number; [key: string]: unknown }
export interface ModelColumn { id: string; position: Point; width: number; depth: number; height: number; shape?: 'rectangular' | 'circular'; rotation?: number }
export interface FloorRegion { points: Point[]; holes: Point[][] }
export interface Opening { id: string; wall_id: string; position: number; width: number; height: number; sill_height?: number; operation?: 'hinged' | 'double_hinged' | 'sliding' | 'overhead' | 'bifold' }
export interface ModelRoom { id: string; name: string; points: Point[]; area_sqm: number; ceiling_height: number; room_type?:string }
export interface ArchitecturalInfo {
  project_name: string; floor_name: string; jurisdiction: string; north_degrees: number
  construction_notes: string; missing_information: string[]
}
export interface InteriorStyle {
  id: string; name: string; description: string
  wall: string; floor: string; fabric: string; wood: string; accent: string
}
export interface TourPlan {
  points: Point[]; stops: {name:string; point:Point}[]; distance_m:number; warnings:string[]
}
export interface FixedFixture {
  id:string; name:string; kind:'vanity'|'toilet'|'island'|'counter'|'cooktop'|'dishwasher'|'fridge'
  position:Point; rotation:Point; dimensions:Point; scale:Point
  outline:Point[]; body_outline:Point[];top_outline:Point[];basin_count:number; source_basin_count:number
  basin_centers:Point[]; source_basin_centers:Point[]; basin_sizes:Point[]
  source_basin_sizes:Point[]
  source_basin_outlines:Point[][]
  room_id?:string; parent_id?:string; [key:string]:unknown
}
export interface RoofSettings {
  kind:'flat'|'shed'|'gable'|'hip'; pitch:number; eave_height:number; overhang:number
  axis:'x'|'z'; material:'shingle'|'metal'|'tile'|'membrane'; color:string
}
export interface RoofMesh {vertices:Point[];triangles:number[][]}
export interface RoofDefinition {
  settings:RoofSettings; surface:RoofMesh; gables:RoofMesh; footprint_hash:string
  status:'proposal'|'reviewed';origin:'design'|'document_parameters'|'imported_geometry'
  source:{id?:string;name?:string;page?:number;sha256?:string;[key:string]:unknown}; warnings:string[]
}
export interface FloorPlan {
  walls: ModelWall[]; columns: ModelColumn[]; doors: Opening[]; windows: Opening[]
  rooms: ModelRoom[]; dimensions: Record<string, number>; warnings: string[]
  floor_regions?: FloorRegion[]
  interior_style?: InteriorStyle
  tour_waypoints?: Point[]
  tour_settings?: {duration:number;quality:'720p'|'1080p'}
  fixtures?: FixedFixture[]
  fixture_status?: {engine:number;status:string;warnings:string[]}
  roof?:RoofDefinition|null
  architectural_info: ArchitecturalInfo; [key: string]: unknown
}
export interface LearningInfo { reused: boolean; contributing: boolean; trained_model: boolean }
