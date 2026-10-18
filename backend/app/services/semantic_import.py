"""Input adapters; all detected geometry needs review and manual calibration."""
import hashlib
from pathlib import Path
import tempfile
import pypdfium2 as pdfium
from app.services.plan_processor import PlanProcessor
from app.services.architectural_pdf import ArchitecturalPDFEngine


def pdf_engine_recipe(mode: str):
    if mode not in ('vector', 'raster'):
        raise ValueError('Modo PDF inválido')
    modules = ['architectural_pdf.py','vector_engine.py','semantic_import.py','plan_fixtures.py'] if mode == 'vector' else ['semantic_import.py','plan_processor.py']
    content=b''.join(Path(__file__).with_name(name).read_bytes() for name in modules)
    return {'mode':mode, 'sha256':hashlib.sha256(content).hexdigest()}


def dxf_engine_recipe():
    module=Path(__file__).with_name('cad_geometry.py')
    return {'version':2,'sha256':hashlib.sha256(module.read_bytes()).hexdigest()}


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
            result = ArchitecturalPDFEngine().process_pdf(path)
        else:
            with tempfile.TemporaryDirectory() as temp, fitz.open() as single_page:
                single_page.insert_pdf(document, from_page=page_number-1, to_page=page_number-1)
                isolated = str(Path(temp)/'selected.pdf')
                single_page.save(isolated)
                result = ArchitecturalPDFEngine().process_pdf(isolated)
        from app.services.plan_fixtures import extract_pdf_fixtures
        from shapely.errors import GEOSException
        try:
            result.fixtures,fixture_warnings=extract_pdf_fixtures(selected,result)
        except (ValueError,GEOSException):
            result.fixtures=[]
            fixture_warnings=['Se conservó la geometría de la casa; los símbolos de equipos no pudieron cerrarse y requieren colocación manual.']
        result.fixture_status={'engine':1,'status':'detected' if result.fixtures else 'not_detected','warnings':fixture_warnings}
    result.warnings.append('Escala y alturas propuestas por el motor vectorial: confirmar con cotas y alzados antes de aprobar.')
    return result


def import_drawing(path: str, suffix: str, page: int, meters_per_pixel: float, dxf_units: str, pdf_mode: str = 'vector'):
    if suffix == '.pdf' and pdf_mode == 'vector':
        return import_vector_pdf(path, page)
    if suffix == '.pdf' and pdf_mode != 'raster':
        raise ValueError('Modo PDF inválido')
    if suffix == '.dxf':
        from app.services.cad_geometry import import_dxf
        return import_dxf(path, dxf_units)
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
