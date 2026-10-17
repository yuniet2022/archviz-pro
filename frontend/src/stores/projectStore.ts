import { create } from 'zustand'
import type { FloorPlan, LearningInfo } from '../types/model'

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
  id: string
  name: string
  category: string
  position: [number, number, number]
  rotation: [number, number, number]
  scale: [number, number, number]
  color: string
  material: string
  dimensions?: [number, number, number]
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

export const useProjectStore = create<ProjectState>((set) => ({
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

  setProjectId: (id) => set({ projectId: id }),
  setWalls: (walls) => set({ walls, dirty: true, measurementsConfirmed: false, furniture: [] }),
  addFurniture: (item) => set((state) => ({ 
    furniture: [...state.furniture, item], dirty: true
  })),
  removeFurniture: (id) => set((state) => ({
    furniture: state.furniture.filter((f) => f.id !== id), dirty: true
  })),
  updateFurniture: (id, updates) => set((state) => ({
    dirty: true, furniture: state.furniture.map((f) =>
      f.id === id ? { ...f, ...updates } : f
    )
  })),
  setViewMode: (mode) => set({ viewMode: mode }),
  setSelectedStyle: (style) => set({ selectedStyle: style }),
  setIsProcessing: (v) => set({ isProcessing: v }),
  setIsPlaying: (v) => set({ isPlaying: v }),
  clearProject: () => set({
    projectId: null,
    floorPlan: null,
    revision: 0,
    dirty: false,
    measurementsConfirmed: false,
    learning: null,
    walls: [],
    furniture: [],
    selectedStyle: null
  })
}))
