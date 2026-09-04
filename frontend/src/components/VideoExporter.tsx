import { useState } from 'react'
import { Video, Settings, Download } from 'lucide-react'
import axios from 'axios'
import { useProjectStore } from '../stores/projectStore'

export default function VideoExporter() {
  const [quality, setQuality] = useState<'720p' | '1080p' | '4K'>('1080p')
  const [duration, setDuration] = useState(30)
  const [isGenerating, setIsGenerating] = useState(false)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const { projectId } = useProjectStore()

  const generateVideo = async () => {
    if (!projectId) {
      alert('Please upload a floor plan first')
      return
    }

    setIsGenerating(true)

    try {
      const response = await axios.post('/api/v1/video/generate', {
        project_id: projectId,
        quality,
        duration,
        path_points: [
          {x: -4, y: 1.7, z: -4},
          {x: 0, y: 1.7, z: 0},
          {x: 4, y: 1.7, z: 4}
        ]
      })

      const { video_id } = response.data

      const interval = setInterval(async () => {
        const status = await axios.get(`/api/v1/video/status/${video_id}`)
        if (status.data.status === 'completed') {
          clearInterval(interval)
          setVideoUrl(`/exports/videos/${video_id}.mp4`)
          setIsGenerating(false)
        }
      }, 5000)

    } catch (error) {
      console.error('Video generation failed:', error)
      setIsGenerating(false)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-lg p-4 w-72">
      <div className="flex items-center gap-2 mb-4">
        <Video className="w-5 h-5 text-red-500" />
        <h3 className="text-sm font-bold text-gray-800">Export Video Tour</h3>
      </div>

      <div className="space-y-3">
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Quality</label>
          <div className="flex gap-1">
            {(['720p', '1080p', '4K'] as const).map((q) => (
              <button
                key={q}
                onClick={() => setQuality(q)}
                className={`
                  flex-1 py-1.5 text-xs rounded-md font-medium transition-all
                  ${quality === q 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }
                `}
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">
            Duration: {duration}s
          </label>
          <input
            type="range"
            min="10"
            max="120"
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            className="w-full accent-blue-600"
          />
        </div>

        <button
          onClick={generateVideo}
          disabled={isGenerating}
          className={`
            w-full py-2.5 rounded-lg text-sm font-bold text-white
            transition-all flex items-center justify-center gap-2
            ${isGenerating 
              ? 'bg-gray-400 cursor-not-allowed' 
              : 'bg-red-600 hover:bg-red-700 shadow-sm'
            }
          `}
        >
          {isGenerating ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Rendering...
            </>
          ) : (
            <>
              <Settings className="w-4 h-4" />
              Generate Tour Video
            </>
          )}
        </button>

        {videoUrl && (
          <a
            href={videoUrl}
            download
            className="w-full py-2 rounded-lg text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 flex items-center justify-center gap-2 transition-colors"
          >
            <Download className="w-4 h-4" />
            Download MP4
          </a>
        )}
      </div>
    </div>
  )
}
