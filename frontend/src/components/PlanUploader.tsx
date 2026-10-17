import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileImage, Loader2 } from 'lucide-react'
import axios from 'axios'
import { useProjectStore } from '../stores/projectStore'
import { loadProject } from '../utils/model'

export default function PlanUploader() {
  const [isUploading, setIsUploading] = useState(false)
  const { setIsProcessing } = useProjectStore()
  const [metersPerPixel, setMetersPerPixel] = useState(.05)
  const [page, setPage] = useState(1)
  const [units, setUnits] = useState('auto')
  const [message, setMessage] = useState('')

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return

    const file = acceptedFiles[0]
    setIsUploading(true)
    setIsProcessing(true)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('meters_per_pixel', String(metersPerPixel))
    formData.append('page', String(page))
    formData.append('dxf_units', units)

    try {
      const response = await axios.post('/api/v1/plans/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      const data = response.data
      loadProject(data)
    } catch (error) {
      console.error('Upload failed:', error)
      setMessage(axios.isAxiosError(error) ? String(error.response?.data?.detail ?? 'No se pudo importar el archivo') : 'No se pudo importar el archivo')
    } finally {
      setIsUploading(false)
      setIsProcessing(false)
    }
  }, [setIsProcessing, metersPerPixel, page, units])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg'],
      'application/pdf': ['.pdf'],
      'application/dxf': ['.dxf'],
      'application/json': ['.json'],
      'application/octet-stream': ['.archviz'],
    },
    maxFiles: 1
    , maxSize: 20*1024*1024,
    onDropRejected: () => setMessage('Usa un archivo compatible de hasta 20 MB.'),
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
              {isDragActive ? 'Suelta el archivo aquí' : 'Importar planta o modelo arquitectónico'}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              PDF, DXF, PNG, JPG, modelo JSON o .archviz · hasta 20 MB
            </p>
          </div>
          <button className="mt-2 px-4 py-2 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 transition-colors">
            Elegir archivo
          </button>
          <div className="text-xs w-full space-y-2 text-gray-700" onClick={e=>e.stopPropagation()}>
            <label className="block">Página PDF <input aria-label="Página PDF" type="number" min="1" value={page} onChange={e=>setPage(Math.max(1,Number(e.target.value)))} className="border rounded w-20 ml-2 p-1"/></label>
            <label className="block">Metros por píxel / punto PDF <input aria-label="Metros por píxel" type="number" min=".00001" max="10" step=".001" value={metersPerPixel} onChange={e=>setMetersPerPixel(Number(e.target.value))} className="border rounded w-24 ml-2 p-1"/></label>
            <label className="block">Unidades DXF <select aria-label="Unidades DXF" value={units} onChange={e=>setUnits(e.target.value)} className="border rounded ml-2 p-1">{['auto','m','cm','mm','ft','in'].map(u=><option key={u}>{u}</option>)}</select></label>
            <p>La escala inicial es aproximada. Comprueba las medidas antes de aprobar el modelo.</p>
          </div>
          {message && <p role="alert" className="text-sm text-red-700">{message}</p>}
        </div>
      )}
    </div>
  )
}
