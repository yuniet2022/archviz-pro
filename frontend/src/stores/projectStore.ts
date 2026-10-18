import { create } from 'zustand'
import type { FloorPlan, LearningInfo, TourPlan } from '../types/model'

export type ViewMode = '3d-orbit' | 'top-down' | 'elevation' | 'walkthrough'

export interface Wall {
  [key: string]: unknown
  id: string
  start: [number, number, number]
  end: [number, number, number]
  height: number
  thickness: number
}

export interface Furniture {
  [key:string]: unknown
  id: string
  name: string
  category: string
  position: [number, number, number]
  rotation: [number, number, number]
  scale: [number, number, number]
  color: string
  material: string
  dimensions?: [number, number, number]
  model?: string
  room_id?: string
  style?: string
}

export interface ProjectState {
  projectId: string | null
  projectName: string
  walls: Wall[]
  furniture: Furniture[]
  viewMode: ViewMode
  selectedStyle: string | null
  isProcessing: boolean
  isPlaying: boolean
  floorPlan: FloorPlan | null
  revision: number
  dirty: boolean
  measurementsConfirmed: boolean
  learning: LearningInfo | null
  selectedElementId: string
  selectedFurnitureId: string
  placementMode: boolean
  tourPointMode: boolean
  interiorMessage: string
  activePanel: 'furniture' | 'tour' | null
  tour: TourPlan | null
  tourProgress: number
  tourDuration: number
  recording: boolean
  recordingError: string
  recordingQuality: '720p' | '1080p'
  videoResult: {url:string; extension:string} | null
  walkInput: {forward:number; turn:number}

  setProjectId: (id: string) => void
  setWalls: (walls: Wall[]) => void
  addFurniture: (item: Furniture) => void
  removeFurniture: (id: string) => void
  updateFurniture: (id: string, updates: Partial<Furniture>) => void
  setViewMode: (mode: ViewMode) => void
  setSelectedStyle: (style: string | null) => void
  setIsProcessing: (v: boolean) => void
  setIsPlaying: (v: boolean) => void
  clearProject: () => void
}

export const useProjectStore = create<ProjectState>((set,get) => ({
  projectId: null,
  projectName: 'Untitled Project',
  walls: [],
  furniture: [],
  viewMode: '3d-orbit',
  selectedStyle: null,
  isProcessing: false,
  isPlaying: false,
  floorPlan: null,
  revision: 0,
  dirty: false,
  measurementsConfirmed: false,
  learning: null,
  selectedElementId: '',
  selectedFurnitureId: '',
  placementMode: false,
  tourPointMode: false,
  interiorMessage: '',
  activePanel: null,
  tour: null,
  tourProgress: 0,
  tourDuration: 60,
  recording: false,
  recordingError: '',
  recordingQuality: '720p',
  videoResult: null,
  walkInput: {forward:0,turn:0},

  setProjectId: (id) => set({ projectId: id }),
  setWalls: (walls) => set({ walls, dirty: true, measurementsConfirmed: false, furniture: [], tour:null, isPlaying:false }),
  addFurniture: (item) => set((state) => ({ 
    furniture: [...state.furniture, item], dirty: true, tour:null, isPlaying:false
  })),
  removeFurniture: (id) => set((state) => ({
    furniture: state.furniture.filter((f) => f.id !== id), dirty: true, tour:null, isPlaying:false,
    selectedFurnitureId:state.selectedFurnitureId===id?'':state.selectedFurnitureId
  })),
  updateFurniture: (id, updates) => set((state) => ({
    dirty: true, tour:null, isPlaying:false, furniture: state.furniture.map((f) =>
      f.id === id ? { ...f, ...updates } : f
    )
  })),
  setViewMode: (mode) => set({ viewMode: mode, isPlaying:false, placementMode:false,tourPointMode:false }),
  setSelectedStyle: (style) => set({ selectedStyle: style, dirty:true }),
  setIsProcessing: (v) => set({ isProcessing: v }),
  setIsPlaying: (v) => set({ isPlaying: v }),
  clearProject: () => {
    const video=get().videoResult
    if(video)URL.revokeObjectURL(video.url)
    set({
    projectId: null,
    floorPlan: null,
    revision: 0,
    dirty: false,
    measurementsConfirmed: false,
    learning: null,
    walls: [],
    furniture: [],
    selectedStyle: null,
    selectedFurnitureId:'', selectedElementId:'', placementMode:false, tourPointMode:false,interiorMessage:'',activePanel:null,
    tour:null, isPlaying:false, tourProgress:0, recording:false, recordingError:'',videoResult:null,
    walkInput:{forward:0,turn:0}
  })}
}))
