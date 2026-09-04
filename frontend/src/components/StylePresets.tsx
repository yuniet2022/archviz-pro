import { useState } from 'react'
import axios from 'axios'
import { Home, Waves, Clock, Factory, TreePine, Box, Minus, Snowflake } from 'lucide-react'
import { useProjectStore } from '../stores/projectStore'

const styles = [
  { id: 'modern_farmhouse', name: 'Modern Farmhouse', icon: Home, desc: 'Rustic warmth', color: 'bg-amber-100 text-amber-800' },
  { id: 'coastal', name: 'Coastal', icon: Waves, desc: 'Beach living', color: 'bg-blue-100 text-blue-800' },
  { id: 'mid_century', name: 'Mid-Century', icon: Clock, desc: 'Retro elegance', color: 'bg-orange-100 text-orange-800' },
  { id: 'industrial', name: 'Industrial', icon: Factory, desc: 'Urban edge', color: 'bg-gray-200 text-gray-800' },
  { id: 'craftsman', name: 'Craftsman', icon: TreePine, desc: 'Handcrafted', color: 'bg-green-100 text-green-800' },
  { id: 'contemporary', name: 'Contemporary', icon: Box, desc: 'Sleek & bold', color: 'bg-purple-100 text-purple-800' },
  { id: 'minimalist', name: 'Minimalist', icon: Minus, desc: 'Less is more', color: 'bg-neutral-100 text-neutral-800' },
  { id: 'scandinavian', name: 'Scandinavian', icon: Snowflake, desc: 'Hygge living', color: 'bg-sky-100 text-sky-800' },
]

export default function StylePresets() {
  const [activeStyle, setActiveStyle] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const { setSelectedStyle, walls, furniture, addFurniture } = useProjectStore()

  const applyStyle = async (styleId: string) => {
    if (walls.length === 0) {
      alert('Please upload a floor plan first')
      return
    }

    setIsLoading(true)
    setActiveStyle(styleId)

    try {
      const rooms = [{
        id: 'room-1',
        name: 'Living Room',
        points: [
          {x: -5, y: 0, z: -5},
          {x: 5, y: 0, z: -5},
          {x: 5, y: 0, z: 5},
          {x: -5, y: 0, z: 5}
        ],
        area_sqm: 50,
        ceiling_height: 2.8
      }]

      const response = await axios.post(`/api/v1/furnish/auto/${styleId}`, rooms)
      const newFurniture = response.data.furniture.map((f: any) => ({
        id: f.id,
        name: f.name,
        category: f.category,
        position: [f.position.x, f.position.y, f.position.z] as [number, number, number],
        rotation: [f.rotation.x, f.rotation.y, f.rotation.z] as [number, number, number],
        scale: [f.scale.x, f.scale.y, f.scale.z] as [number, number, number],
        color: f.color,
        material: f.material,
        dimensions: [f.dimensions.x, f.dimensions.y, f.dimensions.z]
      }))

      useProjectStore.setState({ furniture: [] })
      newFurniture.forEach((item: any) => addFurniture(item))

      setSelectedStyle(styleId)
    } catch (error) {
      console.error('Auto-furnish failed:', error)
      alert('Failed to apply style. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-lg p-4 w-64">
      <h3 className="text-sm font-bold text-gray-800 mb-3 uppercase tracking-wider">
        Auto-Furnish Style
      </h3>
      <div className="space-y-2">
        {styles.map((style) => {
          const Icon = style.icon
          const isActive = activeStyle === style.id

          return (
            <button
              key={style.id}
              onClick={() => applyStyle(style.id)}
              disabled={isLoading}
              className={`
                w-full flex items-center gap-3 p-2 rounded-lg text-left
                transition-all duration-200
                ${isActive 
                  ? 'ring-2 ring-blue-500 bg-blue-50' 
                  : 'hover:bg-gray-50'
                }
                ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              `}
            >
              <div className={`p-2 rounded-lg ${style.color}`}>
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">
                  {style.name}
                </p>
                <p className="text-xs text-gray-400">{style.desc}</p>
              </div>
              {isActive && isLoading && (
                <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
