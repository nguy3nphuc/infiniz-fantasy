"""1:1 renderer for the Pixel Ruins arena.

The overview and every texture atlas stay at their native pixel size.  Details
and their collision areas are read from ``pixel_ruins_layout.json``, which is
authored with ``pixel_ruins_tuner.py``.
"""

import json
from pathlib import Path

import pygame


MAP_DIR = Path(__file__).parent / "assets" / "maps" / "Pixel Art Top Down - Basic v1.2.3"
OVERVIEW_PATH = MAP_DIR / "Scene Overview.png"
LAYOUT_PATH = Path(__file__).parent / "assets" / "maps" / "pixel_ruins_layout.json"

TEXTURE_PATHS = {
    'wall': MAP_DIR / "Texture" / "TX Tileset Wall.png",
    'struct': MAP_DIR / "Texture" / "TX Struct.png",
    'props': MAP_DIR / "Texture" / "TX Props.png",
    'plant': MAP_DIR / "Texture" / "TX Plant.png",
    'player': MAP_DIR / "Texture" / "TX Player.png",
    'shadow_plant': MAP_DIR / "Texture" / "TX Shadow Plant.png",
    'grass': MAP_DIR / "Texture" / "TX Tileset Grass.png",
    'stone_ground': MAP_DIR / "Texture" / "TX Tileset Stone Ground.png",
    'shadow': MAP_DIR / "Texture" / "TX Shadow.png",
}


class PixelRuinsMap:
    """Render the overview at 1:1 and overlay JSON-authored texture details."""

    def __init__(self, width: int, height: int):
        # width/height are kept for API compatibility with Game, while the
        # playable surface itself uses the full native overview dimensions.
        self.width = width
        self.height = height
        self.wall_rects: list[pygame.Rect] = []
        self._textures = self._load_textures()
        self.world_surface = self._load_overview()
        self.surface = self.world_surface
        self.layout = self._load_layout()
        self.collision_zones = self._rectangles_from_layout('collision_zones')
        self.tunnel_zones = self._tunnels_from_layout()
        self.tunnels = [tunnel['rect'] for tunnel in self.tunnel_zones]
        self.floors = self._regions_from_layout('floors')
        self.map_boundaries = self._lines_from_layout('map_boundaries')
        self.stairs = self._stairs_from_layout()
        self.stairs = self._regions_from_layout('stairs')
        self.wall_rects.extend(self._cut_tunnels_from_colliders(self.collision_zones, self.tunnels))
        self.wall_rects.extend(self._line_collision_rects(self.map_boundaries))
        self._draw()

    def _load_textures(self):
        textures = {}
        for name, path in TEXTURE_PATHS.items():
            try:
                textures[name] = pygame.image.load(str(path)).convert_alpha()
            except Exception:
                textures[name] = pygame.Surface((1, 1), pygame.SRCALPHA)
        return textures

    def _load_overview(self):
        try:
            overview = pygame.image.load(str(OVERVIEW_PATH)).convert()
        except Exception:
            overview = pygame.Surface((self.width, self.height))
            overview.fill((45, 55, 45))
        # Keep every overview/detail pixel at native 1:1 size.  Game draws a
        # moving 960x640 viewport over this full surface.
        return overview

    def _load_layout(self):
        try:
            with LAYOUT_PATH.open('r', encoding='utf-8') as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {'details': []}
        except (OSError, json.JSONDecodeError):
            return {'details': []}

    def _draw(self):
        for detail in self.layout.get('details', []):
            texture = self._textures.get(detail.get('texture'))
            source_data = detail.get('source', [])
            position = detail.get('position', [])
            if texture is None or len(source_data) != 4 or len(position) != 2:
                continue
            source = pygame.Rect(source_data)
            if source.width <= 0 or source.height <= 0:
                continue
            if source.left < 0 or source.top < 0 or source.right > texture.get_width() or source.bottom > texture.get_height():
                continue
            world_pos = (int(position[0]), int(position[1]))
            self.surface.blit(texture, world_pos, source)

    def _rectangles_from_layout(self, key):
        """Read only explicit tuner-authored rectangles as collision zones."""
        rectangles = []
        for zone in self.layout.get(key, []):
            rect_data = zone.get('rect', []) if isinstance(zone, dict) else zone
            if not isinstance(rect_data, list) or len(rect_data) != 4:
                continue
            rect = pygame.Rect(*(int(value) for value in rect_data))
            if rect.width > 0 and rect.height > 0:
                rectangles.append(rect)
        return rectangles

    def _tunnels_from_layout(self):
        tunnels = []
        for tunnel in self.layout.get('tunnels', []):
            if not isinstance(tunnel, dict):
                continue
            rect_data = tunnel.get('rect', [])
            if not isinstance(rect_data, list) or len(rect_data) != 4:
                continue
            rect = pygame.Rect(*(int(value) for value in rect_data))
            if rect.width <= 0 or rect.height <= 0:
                continue
            start_line, end_line = tunnel.get('start_line'), tunnel.get('end_line')
            if not (isinstance(start_line, list) and isinstance(end_line, list) and len(start_line) == len(end_line) == 2):
                start_line = [[rect.left, rect.top], [rect.left, rect.bottom]]
                end_line = [[rect.right, rect.top], [rect.right, rect.bottom]]
            tunnels.append({
                'rect': rect,
                'start_line': tuple(tuple(int(value) for value in point) for point in start_line),
                'end_line': tuple(tuple(int(value) for value in point) for point in end_line),
                'floor': max(0, int(tunnel.get('floor', 0))),
            })
        return tunnels

    @staticmethod
    def _tunnel_side_lines(tunnel):
        """Return the two rails parallel to travel through an A→B tunnel."""
        start, end = tunnel['start_line'], tunnel['end_line']
        # Vertical end lines mean travel is horizontal, so rails are top/bottom.
        if abs(start[0][0] - start[1][0]) < abs(start[0][1] - start[1][1]):
            return ((start[0], end[0]), (start[1], end[1]))
        # Horizontal end lines mean travel is vertical, so rails are left/right.
        return ((start[0], end[0]), (start[1], end[1]))

    def tunnel_side_collision_rects(self, index):
        if not 0 <= index < len(self.tunnel_zones):
            return []
        return self._line_collision_rects(self._tunnel_side_lines(self.tunnel_zones[index]), thickness=8)

    def _regions_from_layout(self, key):
        regions = []
        for index, region in enumerate(self.layout.get(key, [])):
            if not isinstance(region, dict):
                continue
            rect_data = region.get('rect', [])
            if not isinstance(rect_data, list) or len(rect_data) != 4:
                continue
            rect = pygame.Rect(*(int(value) for value in rect_data))
            if rect.width <= 0 or rect.height <= 0:
                continue
            copy = dict(region)
            copy['rect'] = rect
            copy.setdefault('id', index + 1)
            regions.append(copy)
        return regions

    def _lines_from_layout(self, key):
        lines = []
        for line in self.layout.get(key, []):
            if not isinstance(line, dict):
                continue
            start, end = line.get('start', []), line.get('end', [])
            if not (isinstance(start, list) and isinstance(end, list) and len(start) == len(end) == 2):
                continue
            start = (int(start[0]), int(start[1]))
            end = (int(end[0]), int(end[1]))
            if start != end:
                lines.append((start, end))
        return lines

    @staticmethod
    def _line_collision_rects(lines, thickness=8):
        """Approximate arbitrary boundary lines with overlapping small blocks."""
        rectangles = []
        half = thickness // 2
        for start, end in lines:
            dx, dy = end[0] - start[0], end[1] - start[1]
            steps = max(1, int(max(abs(dx), abs(dy)) / 3))
            for step in range(steps + 1):
                ratio = step / steps
                x = round(start[0] + dx * ratio)
                y = round(start[1] + dy * ratio)
                rectangles.append(pygame.Rect(x - half, y - half, thickness, thickness))
        return rectangles

    @staticmethod
    def _cut_tunnels_from_colliders(colliders, tunnels):
        """Subtract every tunnel area from authored collision rectangles."""
        remaining = list(colliders)
        for tunnel in tunnels:
            next_remaining = []
            for collider in remaining:
                overlap = collider.clip(tunnel)
                if not overlap:
                    next_remaining.append(collider)
                    continue
                # Four rectangles cover everything around the removed centre.
                candidates = (
                    pygame.Rect(collider.left, collider.top, collider.width, overlap.top - collider.top),
                    pygame.Rect(collider.left, overlap.bottom, collider.width, collider.bottom - overlap.bottom),
                    pygame.Rect(collider.left, overlap.top, overlap.left - collider.left, overlap.height),
                    pygame.Rect(overlap.right, overlap.top, collider.right - overlap.right, overlap.height),
                )
                next_remaining.extend(rect for rect in candidates if rect.width > 0 and rect.height > 0)
            remaining = next_remaining
        return remaining

    def _stairs_from_layout(self):
        stairs = []
        for stair in self.layout.get('stairs', []):
            if not isinstance(stair, dict):
                continue
            rect_data = stair.get('rect', [])
            if not (isinstance(rect_data, list) and len(rect_data) == 4):
                continue
            rect = pygame.Rect(*(int(value) for value in rect_data))
            if rect.width <= 0 or rect.height <= 0:
                continue
            start_line = stair.get('start_line')
            end_line = stair.get('end_line')
            if not (isinstance(start_line, list) and isinstance(end_line, list) and len(start_line) == len(end_line) == 2):
                start = tuple(stair.get('start', (rect.left, rect.centery)))
                end = tuple(stair.get('end', (rect.right, rect.centery)))
                if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
                    start_line = [[start[0], rect.top], [start[0], rect.bottom]]
                    end_line = [[end[0], rect.top], [end[0], rect.bottom]]
                else:
                    start_line = [[rect.left, start[1]], [rect.right, start[1]]]
                    end_line = [[rect.left, end[1]], [rect.right, end[1]]]
            stairs.append({
                'rect': rect,
                'start_line': tuple(tuple(int(value) for value in point) for point in start_line),
                'end_line': tuple(tuple(int(value) for value in point) for point in end_line),
                'from_floor': max(0, int(stair.get('from_floor', 1))),
                'to_floor': max(0, int(stair.get('to_floor', 2))),
                'from_zoom': max(0.70, min(2.40, float(stair.get('from_zoom', 1.30)))),
                'to_zoom': max(0.70, min(2.40, float(stair.get('to_zoom', 1.30)))),
            })
        return stairs

    @staticmethod
    def _segments_intersect(a, b, c, d):
        def orient(p, q, r):
            return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        ab_c, ab_d = orient(a, b, c), orient(a, b, d)
        cd_a, cd_b = orient(c, d, a), orient(c, d, b)
        return (ab_c == 0 or ab_d == 0 or (ab_c > 0) != (ab_d > 0)) and (cd_a == 0 or cd_b == 0 or (cd_a > 0) != (cd_b > 0))

    def stair_end_line_crossed(self, previous_point, current_point):
        """Return the floor selected by crossing a stair's start/end line."""
        for stair in self.stairs:
            for line, floor_key, zoom_key in (
                (stair['start_line'], 'from_floor', 'from_zoom'),
                (stair['end_line'], 'to_floor', 'to_zoom'),
            ):
                if self._segments_intersect(previous_point, current_point, line[0], line[1]):
                    return {'floor': stair[floor_key], 'zoom': stair[zoom_key]}
        return None

    def tunnel_end_line_crossed(self, previous_point, current_point):
        """Return the tunnel index when a player crosses one of its end lines."""
        for index, tunnel in enumerate(self.tunnel_zones):
            for line in (tunnel['start_line'], tunnel['end_line']):
                if self._segments_intersect(previous_point, current_point, line[0], line[1]):
                    return index
        return None

    def floor_at(self, world_position):
        for floor in self.floors:
            if floor['rect'].collidepoint(world_position):
                return floor
        return None
