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
    'grass': MAP_DIR / "Texture" / "TX Tileset Grass.png",
    'stone_ground': MAP_DIR / "Texture" / "TX Tileset Stone Ground.png",
    'shadow': MAP_DIR / "Texture" / "TX Shadow.png",
}


class PixelRuinsMap:
    """Render the overview at 1:1 and overlay JSON-authored texture details."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.surface = pygame.Surface((width, height)).convert()
        self.wall_rects: list[pygame.Rect] = []
        self._textures = self._load_textures()
        self._overview, self.world_offset = self._load_overview()
        self.layout = self._load_layout()
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
        # Native pixels only: this crops the larger overview around its centre.
        offset = ((self.width - overview.get_width()) // 2,
                  (self.height - overview.get_height()) // 2)
        return overview, offset

    def _load_layout(self):
        try:
            with LAYOUT_PATH.open('r', encoding='utf-8') as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {'details': []}
        except (OSError, json.JSONDecodeError):
            return {'details': []}

    def _draw(self):
        self.surface.blit(self._overview, self.world_offset)
        ox, oy = self.world_offset
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
            screen_pos = (ox + int(position[0]), oy + int(position[1]))
            self.surface.blit(texture, screen_pos, source)

            if detail.get('solid', False):
                collider_data = detail.get('collider', [0, source.height // 3, source.width, source.height - source.height // 3])
                if len(collider_data) == 4:
                    cx, cy, cw, ch = (int(value) for value in collider_data)
                    if cw > 0 and ch > 0:
                        self.wall_rects.append(pygame.Rect(screen_pos[0] + cx, screen_pos[1] + cy, cw, ch))
