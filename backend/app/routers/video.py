from fastapi import APIRouter, HTTPException

router = APIRouter(prefix='/video', tags=['video'])


@router.post('/generate')
def generate_video():
    raise HTTPException(410, 'La grabación real se realiza en el visor: Recorrido y vídeo → Grabar vídeo del recorrido.')


@router.get('/status/{video_id}')
def video_status(video_id: str):
    raise HTTPException(410, 'El vídeo se graba y descarga en el navegador; este servicio antiguo está retirado.')
