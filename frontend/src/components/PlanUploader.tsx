import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileImage, Loader2 } from 'lucide-react'
import axios from 'axios'
import { useProjectStore } from '../stores/projectStore'

export default function PlanUploader() {
  const [isUploading, setIsUploading] = useState(false)
  const { setProjectId, setWalls, setIsProcessing } = useProjectStore()

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return

    const file = acceptedFiles[0]
    setIsUploading(true)
    setIsProcessing(true)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await axios.post('/api/v1/plans/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      const data = response.data
      setProjectId(data.project_id)

      const walls = data.floor_plan.walls.map((w: any) => ({
        id: w.id,
        start: [w.start.x, w.start.y, w.start.z] as [number, number, number],
        end: [w.end.x, w.end.y, w.end.z] as [number, number, number],
        height: w.height,
        thickness: w.thickness
      }))

      setWalls(walls)
      alert(`Plan processed! Detected ${data.detected_walls} walls, ${data.detected_rooms} rooms.`)
    } catch (error) {
      console.error('Upload failed:', error)
      alert('Failed to process plan. Please try again.')
    } finally {
      setIsUploading(false)
      setIsProcessing(false)
    }
  }, [setProjectId, setWalls, setIsProcessing])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg'],
      'application/pdf': ['.pdf']
    },
    maxFiles: 1
  })

  return (
    <div
      {...getRootProps()}
      className={`
        relative flex flex-col items-center justify-center
        w-full max-w-md p-8 rounded-2xl border-2 border-dashed
        transition-all duration-300 cursor-pointer
        ${isDragActive 
          ? 'border-blue-500 bg-blue-50 scale-105' 
          : 'border-gray-300 bg-white hover:border-gray-400 hover:bg-gray-50'
        }
        ${isUploading ? 'pointer-events-none opacity-70' : ''}
      `}
    >
      <input {...getInputProps()} />

      {isUploading ? (
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
          <p className="text-sm text-gray-600 font-medium">Processing your floor plan...</p>
          <p className="text-xs text-gray-400">Detecting walls, doors, and rooms</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <div className="p-4 rounded-full bg-blue-50">
            {isDragActive ? (
              <FileImage className="w-8 h-8 text-blue-500" />
            ) : (
              <Upload className="w-8 h-8 text-gray-400" />
            )}
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-gray-700">
              {isDragActive ? 'Drop your plan here' : 'Upload floor plan'}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              PDF, PNG, JPG or even hand-drawn sketches
            </p>
          </div>
          <button className="mt-2 px-4 py-2 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 transition-colors">
            Select File
          </button>
        </div>
      )}
    </div>
  )
}
