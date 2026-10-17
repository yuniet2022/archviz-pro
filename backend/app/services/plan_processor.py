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
        # Wall length alone is not evidence of an opening and must not become a training label.
        return [], []

    def _detect_rooms(self, gray: np.ndarray, walls: List[Wall]) -> List[Room]:
        from shapely.ops import polygonize
        lines = [LineString([(w.start.x, w.start.z), (w.end.x, w.end.z)]) for w in walls]
        return [Room(points=[Vector3(x=x, z=z) for x, z in polygon.exterior.coords[:-1]],
                     area_sqm=polygon.area) for polygon in polygonize(unary_union(lines))
                if polygon.area >= 1]
