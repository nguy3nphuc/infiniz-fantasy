"""Interactive 1:1 layout editor for Pixel Ruins.

Run with ``python pixel_ruins_tuner.py``.  It writes
``assets/maps/pixel_ruins_layout.json``, which Phase 4 loads automatically.
"""

import json

import pygame

from tools.pixel_ruins_map import LAYOUT_PATH, OVERVIEW_PATH, TEXTURE_PATHS


WINDOW_W, WINDOW_H = 1280, 720
VIEWPORT = pygame.Rect(12, 48, 960, 640)  # exactly the game's resolution
ATLAS_RECT = pygame.Rect(992, 72, 276, 276)
GRID = 32
MOVE_SNAP = 2


class PixelRuinsTuner:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption('Pixel Ruins Map Tuner — 1:1')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Consolas', 15)
        self.small_font = pygame.font.SysFont('Consolas', 13)
        self.running = True

        self.overview = pygame.image.load(str(OVERVIEW_PATH)).convert()
        self.textures = {name: pygame.image.load(str(path)).convert_alpha() for name, path in TEXTURE_PATHS.items()}
        self.texture_names = list(self.textures)
        self.texture_index = 0
        self.source = pygame.Rect(0, 0, GRID, GRID)
        self.atlas_drag_start = None
        self.map_drag_index = -1
        self.map_drag_offset = (0, 0)
        self.layout = self._load_layout()
        self.selected_index = -1
        self.show_help = True
        self.exit_confirm = False
        self.dirty = False

        # Camera is expressed in original overview pixels.  It starts on the
        # same centre crop used by the game, so coordinates match at 1:1.
        self.camera_x = max(0, (self.overview.get_width() - VIEWPORT.width) // 2)
        self.camera_y = max(0, (self.overview.get_height() - VIEWPORT.height) // 2)

    def _load_layout(self):
        try:
            with LAYOUT_PATH.open('r', encoding='utf-8') as file:
                data = json.load(file)
            if isinstance(data, dict) and isinstance(data.get('details'), list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {'version': 1, 'details': []}

    def _save_layout(self):
        LAYOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LAYOUT_PATH.open('w', encoding='utf-8') as file:
            json.dump(self.layout, file, indent=2)
        self.dirty = False

    @property
    def selected_texture_name(self):
        return self.texture_names[self.texture_index]

    @property
    def selected_texture(self):
        return self.textures[self.selected_texture_name]

    def _clamp_source(self):
        texture = self.selected_texture
        self.source.width = max(GRID, min(texture.get_width(), self.source.width))
        self.source.height = max(GRID, min(texture.get_height(), self.source.height))
        self.source.x = max(0, min(texture.get_width() - self.source.width, self.source.x))
        self.source.y = max(0, min(texture.get_height() - self.source.height, self.source.y))

    def _detail_rect(self, detail):
        x, y = detail['position']
        _, _, w, h = detail['source']
        return pygame.Rect(x, y, w, h)

    def _world_from_mouse(self, pos):
        return (pos[0] - VIEWPORT.x + self.camera_x, pos[1] - VIEWPORT.y + self.camera_y)

    def _atlas_source_from_mouse(self, pos):
        """Translate an atlas-preview mouse position into a grid cell."""
        texture = self.selected_texture
        scale = min(ATLAS_RECT.width / texture.get_width(), ATLAS_RECT.height / texture.get_height())
        draw_w, draw_h = round(texture.get_width() * scale), round(texture.get_height() * scale)
        draw_x = ATLAS_RECT.x + (ATLAS_RECT.width - draw_w) // 2
        draw_y = ATLAS_RECT.y + (ATLAS_RECT.height - draw_h) // 2
        draw_rect = pygame.Rect(draw_x, draw_y, draw_w, draw_h)
        if not draw_rect.collidepoint(pos):
            return None
        source_x = int((pos[0] - draw_x) / scale) // GRID * GRID
        source_y = int((pos[1] - draw_y) / scale) // GRID * GRID
        return source_x, source_y

    def _place_detail(self, world_pos):
        x = (world_pos[0] // GRID) * GRID
        y = (world_pos[1] // GRID) * GRID
        detail = {
            'texture': self.selected_texture_name,
            'source': [self.source.x, self.source.y, self.source.width, self.source.height],
            'position': [x, y],
            'solid': False,
        }
        self.layout['details'].append(detail)
        self.selected_index = len(self.layout['details']) - 1
        self.dirty = True

    def _select_detail(self, world_pos):
        self.selected_index = -1
        for index in range(len(self.layout['details']) - 1, -1, -1):
            if self._detail_rect(self.layout['details'][index]).collidepoint(world_pos):
                self.selected_index = index
                return index
        return -1

    def _clamp_camera(self):
        self.camera_x = max(0, min(self.overview.get_width() - VIEWPORT.width, self.camera_x))
        self.camera_y = max(0, min(self.overview.get_height() - VIEWPORT.height, self.camera_y))

    def _move_selected(self, dx, dy):
        if not (0 <= self.selected_index < len(self.layout['details'])):
            return
        detail = self.layout['details'][self.selected_index]
        detail['position'][0] += dx
        detail['position'][1] += dy
        self.dirty = True

    def _handle_key(self, key, modifiers):
        step = GRID if modifiers & pygame.KMOD_SHIFT else 1
        if key == pygame.K_s:
            self._save_layout()
        elif key == pygame.K_h:
            self.show_help = True
        elif key == pygame.K_LEFTBRACKET:
            self.texture_index = (self.texture_index - 1) % len(self.texture_names)
            self._clamp_source()
        elif key == pygame.K_RIGHTBRACKET:
            self.texture_index = (self.texture_index + 1) % len(self.texture_names)
            self._clamp_source()
        elif key == pygame.K_COMMA:
            self.source.width -= GRID
            self.source.height -= GRID
            self._clamp_source()
        elif key == pygame.K_PERIOD:
            self.source.width += GRID
            self.source.height += GRID
            self._clamp_source()
        elif key == pygame.K_DELETE and 0 <= self.selected_index < len(self.layout['details']):
            del self.layout['details'][self.selected_index]
            self.selected_index = -1
            self.dirty = True
        elif key == pygame.K_c and 0 <= self.selected_index < len(self.layout['details']):
            detail = self.layout['details'][self.selected_index]
            detail['solid'] = not detail.get('solid', False)
            self.dirty = True
        elif key == pygame.K_LEFT:
            self._move_selected(-step, 0)
        elif key == pygame.K_RIGHT:
            self._move_selected(step, 0)
        elif key == pygame.K_UP:
            self._move_selected(0, -step)
        elif key == pygame.K_DOWN:
            self._move_selected(0, step)
        elif key == pygame.K_j:
            self.camera_x = max(0, self.camera_x - GRID)
        elif key == pygame.K_l:
            self.camera_x = min(self.overview.get_width() - VIEWPORT.width, self.camera_x + GRID)
        elif key == pygame.K_i:
            self.camera_y = max(0, self.camera_y - GRID)
        elif key == pygame.K_k:
            self.camera_y = min(self.overview.get_height() - VIEWPORT.height, self.camera_y + GRID)

    def _handle_mouse(self, event):
        if event.type == pygame.MOUSEWHEEL:
            if not VIEWPORT.collidepoint(pygame.mouse.get_pos()):
                return
            # Wheel pans vertically through the full native-size overview.
            # Hold Shift to pan horizontally when fine-tuning side areas.
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self.camera_x -= event.y * GRID * 2
            else:
                self.camera_y -= event.y * GRID * 2
            self._clamp_camera()
            return

        if event.type == pygame.MOUSEMOTION and self.atlas_drag_start is not None and event.buttons[0]:
            end = self._atlas_source_from_mouse(event.pos)
            if end is not None:
                start_x, start_y = self.atlas_drag_start
                end_x, end_y = end
                self.source.x = min(start_x, end_x)
                self.source.y = min(start_y, end_y)
                self.source.width = abs(end_x - start_x) + GRID
                self.source.height = abs(end_y - start_y) + GRID
                self._clamp_source()
            return

        if event.type == pygame.MOUSEMOTION and self.map_drag_index >= 0 and event.buttons[0]:
            if VIEWPORT.collidepoint(event.pos):
                world_x, world_y = self._world_from_mouse(event.pos)
                offset_x, offset_y = self.map_drag_offset
                detail = self.layout['details'][self.map_drag_index]
                # Detail placement needs fine alignment with the painted map,
                # unlike atlas crops which stay on a 32px tile grid.
                snap = 1 if pygame.key.get_mods() & pygame.KMOD_CTRL else MOVE_SNAP
                detail['position'][0] = round((world_x - offset_x) / snap) * snap
                detail['position'][1] = round((world_y - offset_y) / snap) * snap
                self.dirty = True
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.atlas_drag_start = None
            self.map_drag_index = -1
            return

        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        if ATLAS_RECT.collidepoint(event.pos) and event.button == 1:
            source_pos = self._atlas_source_from_mouse(event.pos)
            if source_pos is not None:
                self.atlas_drag_start = source_pos
                self.source.x, self.source.y = source_pos
                self.source.width = GRID
                self.source.height = GRID
                self._clamp_source()
            return
        if VIEWPORT.collidepoint(event.pos):
            world_pos = self._world_from_mouse(event.pos)
            if event.button == 1:
                # Drag an existing detail. Ctrl+click always places a new one,
                # even when the click lands on an existing texture.
                index = -1 if pygame.key.get_mods() & pygame.KMOD_CTRL else self._select_detail(world_pos)
                if index >= 0:
                    self.map_drag_index = index
                    detail_x, detail_y = self.layout['details'][index]['position']
                    self.map_drag_offset = (world_pos[0] - detail_x, world_pos[1] - detail_y)
                else:
                    self._place_detail(world_pos)
            elif event.button == 3:
                self._select_detail(world_pos)

    def _draw_text(self, text, x, y, color=(235, 235, 235), small=False):
        font = self.small_font if small else self.font
        self.screen.blit(font.render(text, True, color), (x, y))

    def _draw_modal(self, title, lines, accent=(255, 225, 130)):
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(210, 115, 860, 480)
        pygame.draw.rect(self.screen, (30, 36, 46), panel, border_radius=10)
        pygame.draw.rect(self.screen, accent, panel, 2, border_radius=10)
        title_surface = pygame.font.SysFont('Arial', 30, bold=True).render(title, True, accent)
        self.screen.blit(title_surface, title_surface.get_rect(center=(panel.centerx, panel.y + 52)))
        line_font = pygame.font.SysFont('Arial', 19)
        for index, line in enumerate(lines):
            text = line_font.render(line, True, (235, 240, 245))
            self.screen.blit(text, text.get_rect(center=(panel.centerx, panel.y + 112 + index * 34)))

    def draw(self):
        self.screen.fill((30, 32, 38))
        self._draw_text('PIXEL RUINS TUNER — native 1:1 pixels', 12, 12, (255, 225, 130))

        crop = pygame.Rect(self.camera_x, self.camera_y, VIEWPORT.width, VIEWPORT.height)
        self.screen.blit(self.overview, VIEWPORT.topleft, crop)
        for index, detail in enumerate(self.layout['details']):
            texture = self.textures.get(detail.get('texture'))
            if texture is None:
                continue
            source = pygame.Rect(detail['source'])
            world_x, world_y = detail['position']
            screen_pos = (VIEWPORT.x + world_x - self.camera_x, VIEWPORT.y + world_y - self.camera_y)
            self.screen.blit(texture, screen_pos, source)
            rect = pygame.Rect(screen_pos, source.size)
            if detail.get('solid', False):
                pygame.draw.rect(self.screen, (0, 220, 255), rect, 1)
            if index == self.selected_index:
                pygame.draw.rect(self.screen, (255, 225, 70), rect, 2)
        pygame.draw.rect(self.screen, (240, 240, 240), VIEWPORT, 1)

        texture = self.selected_texture
        scale = min(ATLAS_RECT.width / texture.get_width(), ATLAS_RECT.height / texture.get_height())
        preview = pygame.transform.scale(texture, (round(texture.get_width() * scale), round(texture.get_height() * scale)))
        preview_rect = preview.get_rect(center=ATLAS_RECT.center)
        self.screen.blit(preview, preview_rect)
        selection = pygame.Rect(
            preview_rect.x + round(self.source.x * scale), preview_rect.y + round(self.source.y * scale),
            max(1, round(self.source.width * scale)), max(1, round(self.source.height * scale)),
        )
        pygame.draw.rect(self.screen, (255, 225, 70), selection, 2)
        pygame.draw.rect(self.screen, (220, 220, 220), ATLAS_RECT, 1)

        self._draw_text(f'Texture: {self.selected_texture_name}  [ / ] change', 992, 362, (160, 225, 255))
        self._draw_text(f'Source: {list(self.source)}', 992, 388, small=True)
        self._draw_text('Drag atlas: select any large texture region', 992, 408, small=True)
        self._draw_text('[,/.]: shrink/grow selected crop by 32px', 992, 428, small=True)
        self._draw_text('L-drag detail: 2px move | Ctrl: 1px move', 992, 452, small=True)
        self._draw_text('Ctrl+L-click: place over detail | R-click: select', 992, 472, small=True)
        self._draw_text('Arrows: move selected | Shift: 32px', 992, 492, small=True)
        self._draw_text('C: toggle wall | Delete: remove | S: save', 992, 512, small=True)
        self._draw_text('Wheel: scroll map | Shift+Wheel: horizontal', 992, 532, small=True)
        self._draw_text(f'Details: {len(self.layout["details"])} | Selected: {self.selected_index}', 992, 552, (255, 225, 130), small=True)
        status = 'CHUA LUU' if self.dirty else 'DA LUU'
        status_color = (255, 130, 100) if self.dirty else (130, 235, 160)
        self._draw_text(f'Camera: {self.camera_x}, {self.camera_y} | {status}', 992, 574, status_color, small=True)

        if self.show_help:
            self._draw_modal('HUONG DAN PIXEL RUINS TUNER', [
                '1. Dung [ / ] de chon texture atlas.',
                '2. Keo chuot tren atlas ben phai de chon vung texture lon.',
                '3. Click trai map de dat texture; keo detail de di chuyen.',
                '4. C bat/tat collider tuong; mau cyan la collider.',
                '5. Lan chuot de xem map day du; Shift + lan de di ngang.',
                '6. Nhan S de luu pixel_ruins_layout.json.',
                'Nhan Enter, H, Esc hoac click de bat dau.',
            ])
        elif self.exit_confirm:
            self._draw_modal('LUU LAYOUT TRUOC KHI THOAT?', [
                'S: Luu JSON va thoat.',
                'D: Thoat khong luu.',
                'Esc: Quay lai tuner.',
                'Trang thai hien tai: ' + ('co thay doi chua luu.' if self.dirty else 'da luu.'),
            ], (255, 170, 110))
        pygame.display.flip()

    def run(self):
        while self.running:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.show_help = False
                    self.exit_confirm = True
                elif self.show_help:
                    if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_h):
                        self.show_help = False
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        self.show_help = False
                elif self.exit_confirm:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_s:
                            self._save_layout()
                            self.running = False
                        elif event.key == pygame.K_d:
                            self.running = False
                        elif event.key == pygame.K_ESCAPE:
                            self.exit_confirm = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.exit_confirm = True
                    else:
                        self._handle_key(event.key, pygame.key.get_mods())
                else:
                    self._handle_mouse(event)
            self.draw()
        pygame.quit()


if __name__ == '__main__':
    PixelRuinsTuner().run()
