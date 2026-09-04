from typing import List, Dict
from app.models.schemas import FurnitureItem, Vector3, Room, StylePreset

class FurnishEngine:
    def __init__(self):
        self.catalog = self._build_catalog()

    def _build_catalog(self) -> Dict[str, List[Dict]]:
        return {
            "living_room": [
                {"name": "Sofa", "category": "seating", "dims": (2.2, 0.9, 0.85)},
                {"name": "Coffee Table", "category": "table", "dims": (1.2, 0.6, 0.45)},
                {"name": "TV Stand", "category": "storage", "dims": (1.8, 0.5, 0.6)},
                {"name": "Armchair", "category": "seating", "dims": (0.9, 0.9, 0.85)},
                {"name": "Rug", "category": "decor", "dims": (2.5, 0.02, 3.0)},
                {"name": "Floor Lamp", "category": "lighting", "dims": (0.3, 1.6, 0.3)},
                {"name": "Bookshelf", "category": "storage", "dims": (1.0, 0.3, 2.0)},
                {"name": "Side Table", "category": "table", "dims": (0.5, 0.5, 0.55)},
            ],
            "bedroom": [
                {"name": "Bed Queen", "category": "bed", "dims": (2.0, 1.6, 0.6)},
                {"name": "Nightstand", "category": "table", "dims": (0.5, 0.4, 0.55)},
                {"name": "Dresser", "category": "storage", "dims": (1.5, 0.5, 0.8)},
                {"name": "Wardrobe", "category": "storage", "dims": (1.2, 0.6, 2.1)},
                {"name": "Desk", "category": "table", "dims": (1.2, 0.6, 0.75)},
                {"name": "Desk Chair", "category": "seating", "dims": (0.6, 0.6, 0.9)},
            ],
            "kitchen": [
                {"name": "Kitchen Island", "category": "counter", "dims": (2.0, 1.0, 0.9)},
                {"name": "Bar Stool", "category": "seating", "dims": (0.4, 0.4, 0.75)},
                {"name": "Dining Table", "category": "table", "dims": (1.8, 0.9, 0.75)},
                {"name": "Dining Chair", "category": "seating", "dims": (0.5, 0.5, 0.85)},
                {"name": "Refrigerator", "category": "appliance", "dims": (0.9, 0.7, 1.8)},
                {"name": "Range", "category": "appliance", "dims": (0.76, 0.7, 0.9)},
            ],
            "bathroom": [
                {"name": "Vanity", "category": "fixture", "dims": (1.2, 0.5, 0.85)},
                {"name": "Toilet", "category": "fixture", "dims": (0.7, 0.5, 0.75)},
                {"name": "Bathtub", "category": "fixture", "dims": (1.7, 0.75, 0.55)},
                {"name": "Towel Rack", "category": "decor", "dims": (0.6, 0.15, 0.1)},
            ]
        }

    def get_style_config(self, style: StylePreset) -> Dict:
        configs = {
            StylePreset.MODERN_FARMHOUSE: {
                "colors": ["#F5F5DC", "#8B4513", "#FFFFFF", "#D2B48C"],
                "materials": ["reclaimed_wood", "shiplap", "oak_floor", "linen"],
                "furniture_mods": {"rustic": True, "distressed": True}
            },
            StylePreset.COASTAL: {
                "colors": ["#F0F8FF", "#4682B4", "#FFFFFF", "#D3D3D3"],
                "materials": ["white_washed_wood", "wicker", "linen", "glass"],
                "furniture_mods": {"light": True, "airy": True}
            },
            StylePreset.MID_CENTURY: {
                "colors": ["#D2691E", "#DAA520", "#8B4513", "#FF6347"],
                "materials": ["teak", "walnut", "vinyl", "brass"],
                "furniture_mods": {"tapered_legs": True, "clean_lines": True}
            },
            StylePreset.INDUSTRIAL: {
                "colors": ["#2F2F2F", "#8B0000", "#696969", "#A0522D"],
                "materials": ["exposed_brick", "steel", "leather", "concrete"],
                "furniture_mods": {"raw": True, "metal_accents": True}
            },
            StylePreset.CRAFTSMAN: {
                "colors": ["#654321", "#228B22", "#8B4513", "#DEB887"],
                "materials": ["quarter_sawn_oak", "cherry", "handmade_tile", "velvet"],
                "furniture_mods": {"built_in": True, "wood_detailing": True}
            },
            StylePreset.CONTEMPORARY: {
                "colors": ["#000000", "#FFFFFF", "#C0C0C0", "#FF4500"],
                "materials": ["polished_concrete", "glass", "chrome", "leather"],
                "furniture_mods": {"modular": True, "minimal": True}
            },
            StylePreset.MINIMALIST: {
                "colors": ["#FFFFFF", "#F5F5F5", "#E0E0E0", "#333333"],
                "materials": ["white_oak", "concrete", "linen", "matte_black"],
                "furniture_mods": {"hidden_storage": True, "clean": True}
            },
            StylePreset.SCANDINAVIAN: {
                "colors": ["#FFFAF0", "#87CEEB", "#F5F5DC", "#D3D3D3"],
                "materials": ["birch", "wool", "sheepskin", "light_oak"],
                "furniture_mods": {"hygge": True, "functional": True}
            }
        }
        return configs.get(style, configs[StylePreset.CONTEMPORARY])

    def auto_furnish(self, rooms: List[Room], style: StylePreset) -> List[FurnitureItem]:
        furniture = []
        style_config = self.get_style_config(style)
        colors = style_config["colors"]
        materials = style_config["materials"]

        for room in rooms:
            room_type = self._classify_room(room)
            items = self.catalog.get(room_type, self.catalog["living_room"])

            xs = [p.x for p in room.points]
            zs = [p.z for p in room.points]
            center_x = sum(xs) / len(xs)
            center_z = sum(zs) / len(zs)
            width = max(xs) - min(xs)
            depth = max(zs) - min(zs)

            placed = self._place_furniture_layout(
                room_type, items, center_x, center_z, width, depth, colors, materials
            )
            furniture.extend(placed)

        return furniture

    def _classify_room(self, room: Room) -> str:
        area = room.area_sqm
        name = room.name.lower()

        if any(w in name for w in ["bed", "master", "guest"]):
            return "bedroom"
        elif any(w in name for w in ["bath", "powder"]):
            return "bathroom"
        elif any(w in name for w in ["kitchen", "pantry"]):
            return "kitchen"
        elif area > 30:
            return "living_room"
        elif area > 15:
            return "living_room"
        else:
            return "bedroom"

    def _place_furniture_layout(self, room_type: str, items: List[Dict], 
                                cx: float, cz: float, w: float, d: float,
                                colors: List[str], materials: List[str]) -> List[FurnitureItem]:
        placed = []
        color_idx = 0

        if room_type == "living_room":
            placed.append(self._create_item(items[0], cx, cz - d*0.3, 0, colors[0], materials[0]))
            placed.append(self._create_item(items[1], cx, cz, 0, colors[1], materials[1]))
            placed.append(self._create_item(items[2], cx, cz + d*0.35, 0, colors[2], materials[0]))
            placed.append(self._create_item(items[3], cx - w*0.35, cz, 0, colors[0], materials[0]))
            placed.append(self._create_item(items[4], cx, cz, 0, colors[3], materials[2]))
            placed.append(self._create_item(items[5], cx - w*0.4, cz - d*0.4, 0, colors[3], materials[3]))

        elif room_type == "bedroom":
            placed.append(self._create_item(items[0], cx, cz - d*0.2, 0, colors[0], materials[0]))
            placed.append(self._create_item(items[1], cx - 1.2, cz - d*0.2, 0, colors[1], materials[0]))
            placed.append(self._create_item(items[1], cx + 1.2, cz - d*0.2, 0, colors[1], materials[0]))
            placed.append(self._create_item(items[2], cx + w*0.35, cz, 0, colors[2], materials[0]))
            placed.append(self._create_item(items[3], cx - w*0.35, cz, 0, colors[2], materials[0]))

        elif room_type == "kitchen":
            placed.append(self._create_item(items[0], cx, cz, 0, colors[2], materials[1]))
            for i in range(2):
                placed.append(self._create_item(items[1], cx - 0.3 + i*0.6, cz + 0.6, 0, colors[0], materials[0]))
            placed.append(self._create_item(items[2], cx, cz - d*0.3, 0, colors[0], materials[0]))
            for i, offset in enumerate([(-0.8, 0), (0.8, 0), (0, -0.5), (0, 0.5)]):
                placed.append(self._create_item(items[3], cx + offset[0], cz - d*0.3 + offset[1], 0, colors[1], materials[3]))

        return placed

    def _create_item(self, item_def: Dict, x: float, z: float, rot_y: float, 
                     color: str, material: str) -> FurnitureItem:
        dims = item_def["dims"]
        return FurnitureItem(
            name=item_def["name"],
            category=item_def["category"],
            position=Vector3(x=x, y=dims[2]/2, z=z),
            rotation=Vector3(x=0, y=rot_y, z=0),
            dimensions=Vector3(x=dims[0], y=dims[2], z=dims[1]),
            color=color,
            material=material
        )
