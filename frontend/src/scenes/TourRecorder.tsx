import { useEffect } from 'react'
import { addAfterEffect, useThree } from '@react-three/fiber'
import { useProjectStore } from '../stores/projectStore'

/** Record the real WebGL scene locally; no microphone, demo frames or Redis worker. */
export default function TourRecorder() {
  const gl=useThree(s=>s.gl)
  const recording=useProjectStore(s=>s.recording)
  useEffect(()=>{
    if(!recording)return
    const state=useProjectStore.getState(),projectId=state.projectId
    let recorder:MediaRecorder|undefined,stream:MediaStream|undefined
    let unsubscribe:(()=>void)|undefined,timer:number|undefined
    const visibility=()=>{
      if(document.hidden)useProjectStore.setState({recording:false,isPlaying:false,
        recordingError:'Grabación detenida al ocultar la pestaña. Puedes descargar el fragmento o volver a grabar.'})
    }
    const fail=(message:string)=>useProjectStore.setState({recording:false,isPlaying:false,recordingError:message})
    try {
      if(!window.MediaRecorder||!HTMLCanvasElement.prototype.captureStream)throw new Error('Este navegador no admite grabación. Prueba Chrome o Edge actualizados.')
      const type=['video/mp4;codecs=avc1.42001E','video/mp4','video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'].find(value=>MediaRecorder.isTypeSupported(value))
      if(!type)throw new Error('El navegador no dispone de un formato de vídeo compatible.')
      const output=document.createElement('canvas')
      output.width=state.recordingQuality==='1080p'?1920:1280
      output.height=state.recordingQuality==='1080p'?1080:720
      const context=output.getContext('2d',{alpha:false})
      if(!context)throw new Error('No se pudo preparar el vídeo.')
      const copyFrame=()=>{
        const source=gl.domElement
        const factor=Math.min(output.width/source.width,output.height/source.height)
        const width=source.width*factor,height=source.height*factor
        context.fillStyle='#e0e0e0';context.fillRect(0,0,output.width,output.height)
        context.drawImage(source,(output.width-width)/2,(output.height-height)/2,width,height)
      }
      copyFrame()
      stream=output.captureStream(30)
      recorder=new MediaRecorder(stream,{mimeType:type,videoBitsPerSecond:state.recordingQuality==='1080p'?6_000_000:3_000_000})
      const chunks:Blob[]=[]
      recorder.ondataavailable=event=>{if(event.data.size)chunks.push(event.data)}
      recorder.onerror=()=>fail('Falló la grabación en el navegador. Prueba con calidad 720p.')
      recorder.onstop=()=>{
        stream?.getTracks().forEach(track=>track.stop())
        if(useProjectStore.getState().projectId!==projectId)return
        const blob=new Blob(chunks,{type:recorder?.mimeType??type})
        if(!blob.size){fail('La grabación quedó vacía. Mantén visible la pestaña e inténtalo de nuevo.');return}
        const previous=useProjectStore.getState().videoResult
        if(previous)URL.revokeObjectURL(previous.url)
        useProjectStore.setState({recording:false,isPlaying:false,videoResult:{url:URL.createObjectURL(blob),extension:blob.type.includes('mp4')?'mp4':'webm'}})
      }
      recorder.start(250)
      document.addEventListener('visibilitychange',visibility)
      unsubscribe=addAfterEffect(copyFrame)
      useProjectStore.setState({tourProgress:0,isPlaying:true,recordingError:'',selectedFurnitureId:''})
      timer=window.setTimeout(()=>useProjectStore.setState({recording:false,isPlaying:false}),state.tourDuration*1000+100)
    } catch(error) {
      fail(error instanceof Error?error.message:'No se pudo iniciar la grabación.')
    }
    return ()=>{
      if(timer!==undefined)window.clearTimeout(timer)
      document.removeEventListener('visibilitychange',visibility)
      unsubscribe?.()
      if(recorder&&recorder.state!=='inactive')recorder.stop()
      else stream?.getTracks().forEach(track=>track.stop())
    }
  },[recording,gl])
  return null
}
