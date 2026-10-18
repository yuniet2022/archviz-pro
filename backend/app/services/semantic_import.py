"""Input adapters; all detected geometry needs review and manual calibration."""
import math
import hashlib
from pathlib import Path
import tempfile
import ezdxf
import pypdfium2 as pdfium
from app.models.schemas import FloorPlanData, Wall, Column, Vector3
from app.services.plan_processor import PlanProcessor
from app.services.vector_engine import VectorEngine


def pdf_engine_recipe(mode: str):
    if mode not in ('vector', 'raster'):
        raise ValueError('Modo PDF inválido')
    module = Path(__file__).with_name('vector_engine.py') if mode == 'vector' else Path(__file__)
    return {'mode':mode, 'sha256':hashlib.sha256(module.read_bytes()).hexdigest()}


def import_vector_pdf(path: str, page_number: int):
    import fitz
    with fitz.open(path) as document:
        if document.needs_pass:
            raise ValueError('El PDF necesita contraseña')
        if not 1 <= page_number <= len(document):
            raise ValueError('Número de página fuera del documento')
        selected = document[page_number-1]
        if selected.rect.width*selected.rect.height > 25_000_000:
            raise ValueError('Página demasiado grande')
        if page_number == 1:
            result = VectorEngine().process_pdf(path)
        else:
            with tempfile.TemporaryDirectory() as temp, fitz.open() as single_page:
                single_page.insert_pdf(document, from_page=page_number-1, to_page=page_number-1)
                isolated = str(Path(temp)/'selected.pdf')
                single_page.save(isolated)
                result = VectorEngine().process_pdf(isolated)
    result.warnings.append('Escala y alturas propuestas por el motor vectorial: confirmar con cotas y alzados antes de aprobar.')
    return result


def import_drawing(path: str, suffix: str, page: int, meters_per_pixel: float, dxf_units: str, pdf_mode: str = 'vector'):
    if suffix == '.pdf' and pdf_mode == 'vector':
        return import_vector_pdf(path, page)
    if suffix == '.pdf' and pdf_mode != 'raster':
        raise ValueError('Modo PDF inválido')
    if suffix == '.dxf':
        document = ezdxf.readfile(path)
        unit_codes = {1: .0254, 2: .3048, 4: .001, 5: .01, 6: 1}
        factors = {'m': 1, 'cm': .01, 'mm': .001, 'in': .0254, 'ft': .3048}
        factor = factors.get(dxf_units) if dxf_units != 'auto' else unit_codes.get(document.units)
        if factor is None:
            raise ValueError('El DXF no declara unidades reconocidas. Selecciona sus unidades.')
        walls, columns = [], []
        for entity in document.modelspace():
            if len(walls)+len(columns) >= 3000:
                raise ValueError('DXF demasiado complejo: selecciona una planta y simplifica las capas.')
            if entity.dxftype() == 'LINE':
                a, b = entity.dxf.start, entity.dxf.end
                if abs(a.z-b.z)*factor > .001 or abs(a.z)*factor > .001:
                    continue
                length = math.hypot(b.x-a.x, b.y-a.y)*factor
                if .05 <= length <= 1000:
                    walls.append(Wall(start=Vector3(x=a.x*factor, z=-a.y*factor),
                                      end=Vector3(x=b.x*factor, z=-b.y*factor)))
            elif entity.dxftype() == 'LWPOLYLINE' and any(tag in entity.dxf.layer.upper() for tag in ('COL', 'PILAR')):
                points = list(entity.get_points('xy'))
                if entity.closed and len(points) == 4:
                    xs, ys = [p[0] for p in points], [p[1] for p in points]
                    # Only axis-aligned rectangular columns; do not turn rotated outlines into wrong boxes.
                    if len(set(xs)) == 2 and len(set(ys)) == 2:
                        columns.append(Column(position=Vector3(x=(min(xs)+max(xs))*factor/2,
                            z=-(min(ys)+max(ys))*factor/2), width=(max(xs)-min(xs))*factor,
                            depth=(max(ys)-min(ys))*factor))
        if not walls and not columns:
            raise ValueError('No hay líneas ni columnas rectangulares compatibles en el DXF.')
        return FloorPlanData(walls=walls, columns=columns, dimensions={'unit_factor_m': factor},
            warnings=['DXF básico: líneas como ejes de muro; revisar capas, dobles líneas y alturas. Bloques y arcos no se interpretan.'])
    processor = PlanProcessor()
    processor.pixel_to_meter = meters_per_pixel
    if suffix == '.pdf':
        with pdfium.PdfDocument(path) as document:
            if page < 1 or page > len(document):
                raise ValueError('Número de página fuera del documento')
            pdf_page = document[page-1]
            width, height = pdf_page.get_size()
            if width*height > 25_000_000:
                raise ValueError('Página demasiado grande')
            bitmap = pdf_page.render(scale=1)
            with tempfile.TemporaryDirectory() as temp:
                image_path = str(Path(temp)/'page.png')
                bitmap.to_pil().save(image_path)
                result = processor.process_image(image_path)
            bitmap.close()
            pdf_page.close()
    else:
        result = processor.process_image(path)
    result.warnings = ['Detección raster aproximada: comprueba escala, muros, columnas y alturas. No se inventan puertas ni ventanas.']
    return result
