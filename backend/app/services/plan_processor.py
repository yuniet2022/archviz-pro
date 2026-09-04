import cv2
import numpy as np
from PIL import Image
import uuid
from typing import Tuple, List
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
import os

from app.models.schemas import Wall, Door, Window, Room, Vector3, FloorPlanData

class PlanProcessor:
    def __init__(self):
        self.wall_thickness_threshold = 15
        self.min_wall_length = 30
        self.pixel_to_meter = 0.05

    def process_image(self, image_path: str) -> FloorPlanData:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Could not load image")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        walls = self._detect_walls(gray)
        doors, windows = self._detect_openings(gray, walls)
        rooms = self._detect_rooms(gray, walls)

        h, w = gray.shape
        dimensions = {
            "width_pixels": w,
            "height_pixels": h,
            "estimated_width_m": w * self.pixel_to_meter,
            "estimated_height_m": h * self.pixel_to_meter,
            "pixel_to_meter": self.pixel_to_meter
        }

        return FloorPlanData(
            walls=walls,
            doors=doors,
            windows=windows,
            rooms=rooms,
            dimensions=dimensions
        )

    def _detect_walls(self, gray: np.ndarray) -> List[Wall]:
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        thickened = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(thickened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        walls = []
        height, width = gray.shape

        for contour in contours:
            if len(contour) < 4:
                continue

            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            points = [(float(p[0][0]), float(p[0][1])) for p in approx]

            for i in range(len(points)):
                x1, y1 = points[i]
                x2, y2 = points[(i + 1) % len(points)]

                length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                if length < self.min_wall_length:
                    continue

                mx1 = (x1 - width/2) * self.pixel_to_meter
                my1 = (height/2 - y1) * self.pixel_to_meter
                mx2 = (x2 - width/2) * self.pixel_to_meter
                my2 = (height/2 - y2) * self.pixel_to_meter

                walls.append(Wall(
                    start=Vector3(x=mx1, y=0, z=my1),
                    end=Vector3(x=mx2, y=0, z=my2),
                    height=2.8,
                    thickness=0.15
                ))

        if len(walls) == 0:
            lines = cv2.HoughLinesP(thickened, 1, np.pi/180, threshold=50, 
                                   minLineLength=50, maxLineGap=10)
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    mx1 = (x1 - width/2) * self.pixel_to_meter
                    my1 = (height/2 - y1) * self.pixel_to_meter
                    mx2 = (x2 - width/2) * self.pixel_to_meter
                    my2 = (height/2 - y2) * self.pixel_to_meter

                    walls.append(Wall(
                        start=Vector3(x=mx1, y=0, z=my1),
                        end=Vector3(x=mx2, y=0, z=my2),
                        height=2.8,
                        thickness=0.15
                    ))

        return walls

    def _detect_openings(self, gray: np.ndarray, walls: List[Wall]) -> Tuple[List[Door], List[Window]]:
        doors = []
        windows = []

        for i, wall in enumerate(walls):
            wx = wall.end.x - wall.start.x
            wz = wall.end.z - wall.start.z
            length = np.sqrt(wx**2 + wz**2)

            if length > 3.0:
                doors.append(Door(
                    wall_id=wall.id,
                    position=0.5,
                    width=0.9,
                    height=2.1
                ))

                if length > 5.0:
                    windows.append(Window(
                        wall_id=wall.id,
                        position=0.75,
                        width=1.2,
                        height=1.5,
                        sill_height=0.9
                    ))

        return doors, windows

    def _detect_rooms(self, gray: np.ndarray, walls: List[Wall]) -> List[Room]:
        rooms = []

        if walls:
            all_x = []
            all_z = []
            for w in walls:
                all_x.extend([w.start.x, w.end.x])
                all_z.extend([w.start.z, w.end.z])

            if all_x and all_z:
                min_x, max_x = min(all_x), max(all_x)
                min_z, max_z = min(all_z), max(all_z)

                points = [
                    Vector3(x=min_x, y=0, z=min_z),
                    Vector3(x=max_x, y=0, z=min_z),
                    Vector3(x=max_x, y=0, z=max_z),
                    Vector3(x=min_x, y=0, z=max_z),
                ]

                area = (max_x - min_x) * (max_z - min_z)

                rooms.append(Room(
                    name="Main Room",
                    points=points,
                    area_sqm=abs(area),
                    ceiling_height=2.8
                ))

        return rooms
