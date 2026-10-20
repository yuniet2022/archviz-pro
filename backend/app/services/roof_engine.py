"""Visual roof proposals. PDF notes supply parameters, never an invented roof layout."""
import hashlib
import json
import math
import re

from shapely.geometry import Polygon, Point, MultiPoint, LineString
from shapely.ops import triangulate, split, unary_union

from app.models.schemas import RoofDefinition, RoofMesh, RoofSettings, Vector3
from app.services.interior_geometry import floor_polygon


def footprint_hash(plan):
    # Include wall heights: a roof must be regenerated after an architectural edit.
    value={'regions':[r.model_dump() for r in plan.floor_regions],
           'rooms':[r.model_dump(include={'points'}) for r in plan.rooms] if not plan.floor_regions else [],
           'walls':[w.model_dump(include={'start','end','height','thickness'}) for w in plan.walls],
           'columns':[c.model_dump(include={'position','width','depth','height','shape','rotation'}) for c in plan.columns]}
    def canonical(item):
        if isinstance(item,(int,float)):
            return round(float(item),7) if item else 0.0
        if isinstance(item,list):return [canonical(x) for x in item]
        if isinstance(item,dict):return {key:canonical(v) for key,v in item.items()}
        return item
    return hashlib.sha256(json.dumps(canonical(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def polygons(geometry):
    if geometry.geom_type=='Polygon':
        return [geometry] if geometry.area>1e-8 else []
    return [p for item in getattr(geometry,'geoms',[]) for p in polygons(item)]


def roof_proposal(plan, settings: RoofSettings, source=None):
    floor=floor_polygon(plan)
    if floor.is_empty or not floor.is_valid or floor.area<1:
        raise ValueError('El techo necesita un contorno de suelo válido. Revisa primero la planta.')
    if floor.area>20000:
        raise ValueError('El contorno es demasiado grande para generar esta propuesta.')
    if settings.kind!='flat' and settings.pitch<=0:
        raise ValueError('Un techo inclinado necesita una pendiente mayor que cero.')
    tallest=max([w.height for w in plan.walls]+[c.height for c in plan.columns]+[1.9])
    if settings.eave_height<tallest-.01:
        raise ValueError(f'La base del techo debe estar a {tallest:.2f} m o más para no atravesar los muros.')
    # Exterior eaves can extend outwards; inner courtyards remain open in full.
    regions=[]
    for polygon in polygons(floor):
        outside=Polygon(polygon.exterior).buffer(settings.overhang,join_style=2)
        patios=unary_union([Polygon(ring) for ring in polygon.interiors])
        regions.extend(polygons(outside.difference(patios)))
    vertices=[];triangles=[];gvertices=[];gtriangles=[]
    def triangle(target_vertices,target_triangles,points):
        offset=len(target_vertices)
        target_vertices.extend(Vector3(x=x,y=y,z=z) for x,y,z in points)
        target_triangles.append([offset,offset+1,offset+2])
    for region in regions:
        minx,minz,maxx,maxz=region.bounds
        span=(maxz-minz) if settings.axis=='x' else (maxx-minx)
        middle=(minz+maxz)/2 if settings.axis=='x' else (minx+maxx)/2
        def height(x,z):
            across=z if settings.axis=='x' else x
            low=minz if settings.axis=='x' else minx
            rise=0 if settings.kind=='flat' else across-low if settings.kind=='shed' else \
                max(0,span/2-abs(across-middle)) if settings.kind=='gable' else Point(x,z).distance(region.boundary)
            return settings.eave_height+rise*settings.pitch/12
        step=max(.55,math.sqrt(region.area/3000))
        if (maxx-minx)*(maxz-minz)/step**2>18000:
            raise ValueError('El contorno es demasiado disperso. Revisa las regiones del suelo.')
        parts=[region]
        if settings.kind=='gable':
            line=LineString([(minx-2,middle),(maxx+2,middle)]) if settings.axis=='x' else \
                LineString([(middle,minz-2),(middle,maxz+2)])
            parts=polygons(split(region,line))
        for part in parts:
            points=[]
            for ring in [part.exterior,*part.interiors]:
                count=max(4,math.ceil(ring.length/step))
                points.extend(ring.interpolate(i/count,normalized=True) for i in range(count))
                points.extend(Point(x,z) for x,z in ring.coords)
            if settings.kind=='hip':
                for ix in range(1,math.ceil((maxx-minx)/step)):
                    for iz in range(1,math.ceil((maxz-minz)/step)):
                        point=Point(minx+ix*step,minz+iz*step)
                        if part.contains(point):points.append(point)
            # Clip each Delaunay triangle to the real footprint, including holes.
            covered=0
            for candidate in triangulate(MultiPoint(points)):
                for piece in polygons(candidate.intersection(part)):
                    for face in triangulate(piece):
                        if not piece.covers(face):continue
                        xyz=[(x,height(x,z),z) for x,z in list(face.exterior.coords)[:3]]
                        triangle(vertices,triangles,xyz)
                        covered+=face.area
            if abs(covered-part.area)>max(.005,part.area*.00001):
                raise ValueError('No se pudo cerrar el techo sobre este contorno. Revisa los patios y entrantes.')
        for ring in [region.exterior,*region.interiors]:
            coords=list(ring.coords)
            for a,b in zip(coords,coords[1:]):
                # Thin fascia around the outer edge and courtyard openings.
                ha,hb=height(*a),height(*b)
                q=[(a[0],ha,a[1]),(b[0],hb,b[1]),(b[0],hb-.12,b[1]),(a[0],ha-.12,a[1])]
                triangle(vertices,triangles,[q[0],q[1],q[2]])
                triangle(vertices,triangles,[q[0],q[2],q[3]])
        # End walls close the space below sloped roofs. The house walls stay intact.
        for polygon in polygons(floor.intersection(region)):
            for ring in [polygon.exterior,*polygon.interiors]:
                coords=list(ring.coords)
                for a,b in zip(coords,coords[1:]):
                    count=max(1,math.ceil(math.dist(a,b)/step))
                    for index in range(count):
                        c=tuple(a[i]+(b[i]-a[i])*index/count for i in (0,1))
                        d=tuple(a[i]+(b[i]-a[i])*(index+1)/count for i in (0,1))
                        midpoint=Point((c[0]+d[0])/2,(c[1]+d[1])/2)
                        nearest=min(plan.walls,key=lambda w:midpoint.distance(LineString([(w.start.x,w.start.z),(w.end.x,w.end.z)])),default=None)
                        base=nearest.height if nearest else settings.eave_height-.12
                        hc,hd=max(base,height(*c)-.12),max(base,height(*d)-.12)
                        if max(hc,hd)<=base+.001:continue
                        q=[(c[0],base,c[1]),(d[0],base,d[1]),(d[0],hd,d[1]),(c[0],hc,c[1])]
                        if hd>base+.001:triangle(gvertices,gtriangles,[q[0],q[1],q[2]])
                        if hc>base+.001:triangle(gvertices,gtriangles,[q[0],q[2],q[3]])
    warnings=['Propuesta visual de una cubierta continua. Revisa cumbreras, limatesas, encuentros y alturas por volumen contra los planos.']
    if settings.kind=='hip':
        warnings.append('Cuatro aguas aproximado al contorno; las uniones en entrantes requieren ajuste de diseño.')
    if source:
        warnings.append('Se usan los parámetros encontrados en el documento; no se ha reconstruido su geometría de cubierta.')
    return RoofDefinition(settings=settings,surface=RoofMesh(vertices=vertices,triangles=triangles),
        gables=RoofMesh(vertices=gvertices,triangles=gtriangles),footprint_hash=footprint_hash(plan),
        origin='document_parameters' if source else 'design',source=source or {},warnings=warnings)


def inspect_pdf(page):
    text=page.get_text()[:250000]
    normalized=re.sub(r'\s+',' ',text).upper()
    evidence=[];parameters={}
    def found(field,value,match):
        evidence.append({'field':field,'value':value,'text':match.group(0)[:250]})
    pitches=[]
    for match in re.finditer(r'\b(\d{1,2}(?:\.\d+)?)\s*/\s*12\s+(?:ROOF\s+)?(?:PITCH|SLOPE)\b',normalized):
        value=float(match.group(1))
        if 0<value<=24:pitches.append(value);found('pitch',value,match)
    if len(set(pitches))==1:parameters['pitch']=pitches[0]
    overhangs=[]
    for match in re.finditer(r'\b(\d{1,2}(?:\.\d+)?)\s*["″]\s*(?:OVERHANG|O\.?\s*H\.?)',normalized):
        value=round(float(match.group(1))*.0254,5)
        if value<=1.5:overhangs.append(value);found('overhang',value,match)
    if len(set(overhangs))==1:parameters['overhang']=overhangs[0]
    materials=[]
    for pattern,value in [(r'\bSHINGLES?\s+ROOF(?:\s+LOAD)?\b','shingle'),(r'\bMETAL\s+ROOF\b','metal'),(r'\bTILE\s+ROOF\b','tile')]:
        for match in re.finditer(pattern,normalized):materials.append(value);found('material',value,match)
    if len(set(materials))==1:parameters['material']=materials[0]
    # Detail sheets often mention many roof types. Never infer a house's roof shape
    # from generic construction details, or a single 'GABLE END' note.
    warnings=['Los datos de texto no definen la forma del techo. Hace falta revisar la planta de cubierta y los alzados.']
    if any(len(set(values))>1 for values in (pitches,overhangs,materials)):
        warnings.append('La página contiene valores distintos. Los parámetros en conflicto no se han elegido automáticamente.')
    return {'parameters':parameters,'evidence':evidence[:40],
            'page_count':page.parent.page_count,
            'warnings':warnings}
