"""A local, metre-based catalogue. No third-party meshes or downloads are needed."""
from app.models.schemas import StylePreset


# Dimensions are always width X, height Y, depth Z, in metres.
CATALOG = [
    ('sofa', 'Sofá de tres plazas', 'seating', (2.20, .86, .92)),
    ('armchair', 'Butaca', 'seating', (.82, .85, .83)),
    ('coffee_table', 'Mesa de centro', 'table', (1.10, .40, .60)),
    ('side_table', 'Mesa auxiliar', 'table', (.48, .52, .48)),
    ('tv_console', 'Mueble con TV', 'storage', (1.60, 1.25, .40)),
    ('rug', 'Alfombra', 'decor', (2.40, .025, 1.70)),
    ('floor_lamp', 'Lámpara de pie', 'lighting', (.40, 1.65, .40)),
    ('plant', 'Planta en maceta', 'decor', (.45, 1.25, .45)),
    ('bed_queen', 'Cama queen', 'bed', (1.60, 1.05, 2.10)),
    ('bed_king', 'Cama king', 'bed', (1.93, 1.05, 2.13)),
    ('bed_single', 'Cama individual', 'bed', (1.00, .95, 2.00)),
    ('nightstand', 'Mesita de noche', 'storage', (.48, .52, .40)),
    ('dresser', 'Cómoda', 'storage', (1.10, .85, .45)),
    ('wardrobe', 'Armario', 'storage', (1.20, 2.10, .58)),
    ('desk', 'Escritorio', 'table', (1.20, .75, .60)),
    ('dining_table', 'Mesa de comedor', 'table', (1.60, .76, .85)),
    ('dining_chair', 'Silla de comedor', 'seating', (.48, .85, .50)),
    ('island', 'Isla de cocina', 'counter', (1.80, .92, .85)),
    ('stool', 'Taburete', 'seating', (.40, .78, .40)),
    ('fridge', 'Refrigerador', 'appliance', (.85, 1.85, .72)),
    ('range', 'Cocina / horno', 'appliance', (.76, .90, .65)),
    ('vanity', 'Lavabo con mueble', 'fixture', (.80, .85, .48)),
    ('toilet', 'Inodoro', 'fixture', (.40, .78, .68)),
    ('bathtub', 'Bañera', 'fixture', (1.60, .55, .72)),
    ('washer', 'Lavadora', 'appliance', (.62, .88, .65)),
    ('outdoor_sofa', 'Sofá de terraza', 'seating', (1.65, .80, .75)),
]

STYLE_DATA = {
    'warm_modern': ('Moderno cálido', 'Roble claro, lino y arena', '#eee8dd', '#c8a579', '#c7b499', '#8d7052', '#4b5145'),
    'contemporary': ('Contemporáneo', 'Blanco, grafito y contraste', '#f4f3ef', '#c2b8a8', '#a8adb0', '#4a4037', '#222b32'),
    'classic': ('Clásico', 'Crema, nogal y detalles dorados', '#f2eadb', '#99734d', '#d2bb93', '#654631', '#826746'),
    'modern_farmhouse': ('Farmhouse moderno', 'Blancos cálidos y madera rústica', '#f3f0e8', '#b88c62', '#d8ccb8', '#806044', '#444a45'),
    'coastal': ('Costero', 'Arena, blanco y azul suave', '#f2f6f4', '#d2bc96', '#b7d1db', '#ad987b', '#467488'),
    'mid_century': ('Mid-century', 'Nogal, mostaza y formas retro', '#ede7db', '#a8794d', '#c89b58', '#765138', '#52634c'),
    'industrial': ('Industrial', 'Hormigón, cuero y metal', '#d4d1cc', '#a29b90', '#9e755a', '#70533f', '#30383b'),
    'craftsman': ('Artesano', 'Madera natural y verde profundo', '#e9e2d4', '#ac8256', '#b2b393', '#795535', '#4b6657'),
    'minimalist': ('Minimalista', 'Blanco mate y pocos elementos', '#f6f5ef', '#ded8ca', '#dfddd4', '#b8a183', '#696c68'),
    'scandinavian': ('Escandinavo', 'Abedul, texturas suaves y luz', '#f5f1e8', '#d8c3a0', '#d5d4c9', '#b79b76', '#7f9992'),
    'japandi': ('Japandi', 'Calma japonesa y madera clara', '#e8e2d5', '#bba789', '#bab5a5', '#877358', '#4c554b'),
    'mediterranean': ('Mediterráneo', 'Cal, terracota y tonos tierra', '#f5ead7', '#bd8c6b', '#dcc6a3', '#a07952', '#a96649'),
    'tropical': ('Tropical', 'Fibras naturales y verde', '#edf0df', '#c5aa7c', '#c5ccb0', '#96764f', '#3b7256'),
    'luxury': ('Elegante', 'Piedra clara, nogal y latón', '#eee8df', '#d8cfc0', '#c2b8aa', '#69503f', '#a18b60'),
}


def style_config(style):
    key = style.value if isinstance(style, StylePreset) else style
    name, description, wall, floor, fabric, wood, accent = STYLE_DATA[key]
    return dict(id=key, name=name, description=description, wall=wall, floor=floor,
                fabric=fabric, wood=wood, accent=accent,
                colors=[fabric, wood, wall, accent], materials=['wood', 'fabric', 'stone', 'metal'])


def catalogue():
    return [dict(model=model, name=name, category=category,
                 dimensions=dict(zip(('x', 'y', 'z'), dims)))
            for model, name, category, dims in CATALOG]
