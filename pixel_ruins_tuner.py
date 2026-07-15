"""Interactive editor for Pixel Ruins details, collision, floors and stairs.

Run ``python pixel_ruins_tuner.py``.  Everything is stored in
``assets/maps/pixel_ruins_layout.json`` and Phase 4 reloads it on entry.
"""

import json

import pygame

from pixel_ruins_map import LAYOUT_PATH, OVERVIEW_PATH, TEXTURE_PATHS


WINDOW_W, WINDOW_H = 1280, 720
VIEWPORT = pygame.Rect(12, 48, 960, 640)
ATLAS_RECT = pygame.Rect(992, 72, 276, 276)
ZOOM_OUT_RECT = pygame.Rect(760, 8, 34, 28)
ZOOM_IN_RECT = pygame.Rect(890, 8, 34, 28)
GRID = 32
MOVE_SNAP = 2
MODES = ('details', 'collision_zones', 'floors', 'stairs', 'tunnels', 'map_boundaries')
MODE_LABELS = {
    'details': 'TEXTURE', 'collision_zones': 'COLLIDER',
    'floors': 'VUNG TANG', 'stairs': 'CAU THANG', 'tunnels': 'HAM', 'map_boundaries': 'VIEN MAP',
}
MODE_COLORS = {
    'collision_zones': (245, 80, 80), 'floors': (75, 185, 255), 'stairs': (255, 165, 65),
    'tunnels': (190, 105, 255), 'map_boundaries': (80, 235, 255),
}
TEXTURE_OUTLINE_COLORS = {
    'struct': (80, 210, 255),
    'props': (255, 180, 70),
    'plant': (80, 235, 120),
    'player': (255, 100, 220),
    'shadow_plant': (175, 120, 255),
    'grass': (160, 240, 80),
    'stone_ground': (210, 210, 225),
    'shadow': (130, 150, 185),
}


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
        self.layout = self._load_layout()
        self._ensure_layout_shape()

        self.mode = 'details'
        self.selected_index = -1
        self.atlas_drag_start = None
        self.detail_drag_index = -1
        self.detail_drag_offset = (0, 0)
        self.region_drag_index = -1
        self.region_drag_offset = (0, 0)
        self.region_drag_original = None
        self.region_create_start = None
        self.region_preview = None
        self.line_create_start = None
        self.line_preview_end = None
        self.line_drag_index = -1
        self.line_drag_anchor = None
        self.line_drag_original = None
        self.floor_picker = None
        self.floor_notice = ''
        self.show_help = True
        self.exit_confirm = False
        self.dirty = False
        self.camera_x = max(0, (self.overview.get_width() - VIEWPORT.width) // 2)
        self.camera_y = max(0, (self.overview.get_height() - VIEWPORT.height) // 2)
        self.map_zoom = 1.0

    def _load_layout(self):
        try:
            with LAYOUT_PATH.open('r', encoding='utf-8') as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _ensure_layout_shape(self):
        self.layout['version'] = 2
        for key in MODES:
            self.layout.setdefault(key, [])
            if not isinstance(self.layout[key], list):
                self.layout[key] = []
        # Layouts saved before A/B end lines existed remain editable.
        for key in ('stairs', 'tunnels'):
            for box in self.layout[key]:
                rect_data = box.get('rect', []) if isinstance(box, dict) else []
                if len(rect_data) != 4:
                    continue
                rect = pygame.Rect(rect_data)
                box.setdefault('start_line', [[rect.left, rect.top], [rect.left, rect.bottom]])
                box.setdefault('end_line', [[rect.right, rect.top], [rect.right, rect.bottom]])

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

    @property
    def items(self):
        return self.layout[self.mode]

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

    def _item_rect(self, item):
        if self.mode == 'details':
            return self._detail_rect(item)
        if self.mode == 'map_boundaries':
            start, end = item['start'], item['end']
            return pygame.Rect(min(start[0], end[0]) - 6, min(start[1], end[1]) - 6,
                               abs(end[0] - start[0]) + 12, abs(end[1] - start[1]) + 12)
        return pygame.Rect(item['rect'])

    def _world_from_mouse(self, pos):
        return ((pos[0] - VIEWPORT.x) / self.map_zoom + self.camera_x,
                (pos[1] - VIEWPORT.y) / self.map_zoom + self.camera_y)

    def _atlas_source_from_mouse(self, pos):
        texture = self.selected_texture
        scale = min(ATLAS_RECT.width / texture.get_width(), ATLAS_RECT.height / texture.get_height())
        draw_w, draw_h = round(texture.get_width() * scale), round(texture.get_height() * scale)
        draw_x = ATLAS_RECT.x + (ATLAS_RECT.width - draw_w) // 2
        draw_y = ATLAS_RECT.y + (ATLAS_RECT.height - draw_h) // 2
        if not pygame.Rect(draw_x, draw_y, draw_w, draw_h).collidepoint(pos):
            return None
        return (int((pos[0] - draw_x) / scale) // GRID * GRID,
                int((pos[1] - draw_y) / scale) // GRID * GRID)

    def _place_detail(self, world_pos):
        self.layout['details'].append({
            'texture': self.selected_texture_name,
            'source': [self.source.x, self.source.y, self.source.width, self.source.height],
            'position': [world_pos[0] // GRID * GRID, world_pos[1] // GRID * GRID],
            'solid': False,
        })
        self.selected_index = len(self.items) - 1
        self.dirty = True

    def _new_region(self, rect):
        if self.mode == 'collision_zones':
            return {'rect': list(rect)}
        if self.mode == 'floors':
            return {'rect': list(rect), 'floor': 0}
        if self.mode == 'floors':
            self._draw_text(f"TANG {item.get('floor', 0)}", rect.x + 3, rect.y + 3, color, True)
        elif self.mode == 'stairs':
            return {'rect': list(rect), 'start_line': [[rect.left, rect.top], [rect.left, rect.bottom]],
                    'end_line': [[rect.right, rect.top], [rect.right, rect.bottom]],
                    'from_floor': 1, 'to_floor': 2, 'from_zoom': 1.30, 'to_zoom': 1.30}
        if self.mode == 'tunnels':
            return {'rect': list(rect), 'start_line': [[rect.left, rect.top], [rect.left, rect.bottom]],
                    'end_line': [[rect.right, rect.top], [rect.right, rect.bottom]], 'floor': 0}
        if self.mode == 'map_boundaries':
            return {'start': list(rect.topleft), 'end': list(rect.bottomright)}
        floor_ids = self._floor_ids()
        return {'rect': list(rect), 'from_floor': floor_ids[0] if floor_ids else 1,
                'to_floor': floor_ids[1] if len(floor_ids) > 1 else (floor_ids[0] if floor_ids else 2)}

    @staticmethod
    def _box_end_lines(rect, start, end):
        """Create two full-width end lines from the direction of the drag."""
        if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
            return ([[round(start[0]), rect.top], [round(start[0]), rect.bottom]],
                    [[round(end[0]), rect.top], [round(end[0]), rect.bottom]])
        return ([[rect.left, round(start[1])], [rect.right, round(start[1])]],
                [[rect.left, round(end[1])], [rect.right, round(end[1])]])

    def _floor_ids(self):
        ids = set()
        for stair in self.layout['stairs']:
            ids.add(int(stair.get('from_floor', 1)))
            ids.add(int(stair.get('to_floor', 2)))
        return sorted(ids) or [1, 2]

    def _next_floor_id(self):
        return max(self._floor_ids(), default=0) + 1

    def _select_item(self, world_pos):
        self.selected_index = -1
        for index in range(len(self.items) - 1, -1, -1):
            if self._item_rect(self.items[index]).collidepoint(world_pos):
                self.selected_index = index
                return index
        return -1

    def _clamp_camera(self):
        view_width = VIEWPORT.width / self.map_zoom
        view_height = VIEWPORT.height / self.map_zoom
        self.camera_x = max(0, min(self.overview.get_width() - view_width, self.camera_x))
        self.camera_y = max(0, min(self.overview.get_height() - view_height, self.camera_y))

    def _minimum_map_zoom(self):
        """Smallest safe zoom that still fits the viewport inside overview."""
        return max(0.50, VIEWPORT.width / self.overview.get_width(),
                   VIEWPORT.height / self.overview.get_height())

    def _change_map_zoom(self, direction):
        """Zoom the editor around the current viewport centre, not the map."""
        old_width = VIEWPORT.width / self.map_zoom
        old_height = VIEWPORT.height / self.map_zoom
        centre_x = self.camera_x + old_width / 2
        centre_y = self.camera_y + old_height / 2
        self.map_zoom = max(self._minimum_map_zoom(), min(3.00, round(self.map_zoom + direction * 0.25, 2)))
        self.camera_x = centre_x - VIEWPORT.width / self.map_zoom / 2
        self.camera_y = centre_y - VIEWPORT.height / self.map_zoom / 2
        self._clamp_camera()

    def _screen_rect(self, world_rect):
        return pygame.Rect(
            round(VIEWPORT.x + (world_rect.x - self.camera_x) * self.map_zoom),
            round(VIEWPORT.y + (world_rect.y - self.camera_y) * self.map_zoom),
            max(1, round(world_rect.width * self.map_zoom)),
            max(1, round(world_rect.height * self.map_zoom)),
        )

    def _switch_mode(self, mode):
        self.mode = mode
        self.selected_index = -1
        self.detail_drag_index = self.region_drag_index = -1
        self.region_create_start = self.region_preview = None
        self.line_create_start = self.line_preview_end = None
        self.line_drag_index = -1
        self.floor_picker = None

    @staticmethod
    def _point_to_segment_distance(point, start, end):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return pygame.Vector2(point).distance_to(start)
        ratio = max(0, min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq))
        closest = (start[0] + dx * ratio, start[1] + dy * ratio)
        return pygame.Vector2(point).distance_to(closest)

    def _floor_picker_rects(self):
        return {level: pygame.Rect(1000 + (level % 3) * 86, 570 + (level // 3) * 48, 76, 36) for level in range(6)}

    def _floor_overlaps(self, rect, ignore_index=-1):
        return any(rect.colliderect(pygame.Rect(floor['rect'])) for index, floor in enumerate(self.layout['floors']) if index != ignore_index)

    def _move_selected(self, dx, dy):
        if not 0 <= self.selected_index < len(self.items):
            return
        if self.mode == 'details':
            self.items[self.selected_index]['position'][0] += dx
            self.items[self.selected_index]['position'][1] += dy
        elif self.mode == 'map_boundaries':
            line = self.items[self.selected_index]
            for point_name in ('start', 'end'):
                line[point_name][0] += dx
                line[point_name][1] += dy
        elif self.mode in ('stairs', 'tunnels'):
            box = self.items[self.selected_index]
            box['rect'][0] += dx
            box['rect'][1] += dy
            for line_name in ('start_line', 'end_line'):
                for point in box[line_name]:
                    point[0] += dx
                    point[1] += dy
        else:
            self.items[self.selected_index]['rect'][0] += dx
            self.items[self.selected_index]['rect'][1] += dy
        self.dirty = True

    def _change_stair_zoom(self, direction, target=False):
        if self.mode != 'stairs' or not 0 <= self.selected_index < len(self.items):
            return
        stair = self.items[self.selected_index]
        key = 'to_zoom' if target else 'from_zoom'
        stair[key] = round(max(0.70, min(2.40, float(stair.get(key, 1.30)) + direction * .05)), 2)
        self.dirty = True

    def _change_stair_floor(self, direction, target):
        if self.mode != 'stairs' or not 0 <= self.selected_index < len(self.items):
            return
        ids = self._floor_ids()
        if not ids:
            return
        stair = self.items[self.selected_index]
        key = 'to_floor' if target else 'from_floor'
        current = int(stair.get(key, ids[0]))
        position = ids.index(current) if current in ids else 0
        stair[key] = ids[(position + direction) % len(ids)]
        self.dirty = True

    def _reverse_box_direction(self):
        if self.mode not in ('stairs', 'tunnels') or not 0 <= self.selected_index < len(self.items):
            return
        box = self.items[self.selected_index]
        if self.mode == 'tunnels':
            # Tunnel traversal is bidirectional. F rotates its two entrance
            # lines by 90 degrees instead of assigning a one-way direction.
            rect = pygame.Rect(box['rect'])
            start_line = box['start_line']
            is_vertical = abs(start_line[0][0] - start_line[1][0]) < abs(start_line[0][1] - start_line[1][1])
            if is_vertical:
                box['start_line'] = [[rect.left, rect.top], [rect.right, rect.top]]
                box['end_line'] = [[rect.left, rect.bottom], [rect.right, rect.bottom]]
            else:
                box['start_line'] = [[rect.left, rect.top], [rect.left, rect.bottom]]
                box['end_line'] = [[rect.right, rect.top], [rect.right, rect.bottom]]
            self.dirty = True
            return
        box['start_line'], box['end_line'] = box['end_line'], box['start_line']
        if self.mode == 'stairs':
            for first, second in (('from_floor', 'to_floor'), ('from_zoom', 'to_zoom')):
                box[first], box[second] = box[second], box[first]
        self.dirty = True

    def _handle_key(self, key, modifiers):
        step = GRID if modifiers & pygame.KMOD_SHIFT else 1
        mode_keys = {pygame.K_1: 'details', pygame.K_2: 'collision_zones', pygame.K_3: 'floors', pygame.K_4: 'stairs', pygame.K_5: 'tunnels', pygame.K_6: 'map_boundaries'}
        if self.mode == 'stairs' and modifiers & pygame.KMOD_SHIFT and pygame.K_0 <= key <= pygame.K_9 and 0 <= self.selected_index < len(self.items):
            self.items[self.selected_index]['to_floor' if modifiers & pygame.KMOD_CTRL else 'from_floor'] = key - pygame.K_0
            self.dirty = True
            return
        if key in mode_keys:
            self._switch_mode(mode_keys[key])
        elif key == pygame.K_s:
            self._save_layout()
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._change_map_zoom(-1)
        # On many keyboards '+' is Shift+'='.  pygame.K_PLUS is not exposed
        # by every pygame build, so do not reference it here (it can crash the
        # tuner when any normal key is processed).
        elif key in (pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._change_map_zoom(1)
        elif key == pygame.K_h:
            self.show_help = True
        elif key == pygame.K_f:
            self._reverse_box_direction()
        elif key == pygame.K_DELETE and 0 <= self.selected_index < len(self.items):
            del self.items[self.selected_index]
            self.selected_index = -1
            self.dirty = True
        elif key == pygame.K_LEFTBRACKET:
            if self.mode == 'details':
                self.texture_index = (self.texture_index - 1) % len(self.texture_names)
                self._clamp_source()
            else:
                self._change_stair_zoom(-1, bool(modifiers & pygame.KMOD_SHIFT))
        elif key == pygame.K_RIGHTBRACKET:
            if self.mode == 'details':
                self.texture_index = (self.texture_index + 1) % len(self.texture_names)
                self._clamp_source()
            else:
                self._change_stair_zoom(1, bool(modifiers & pygame.KMOD_SHIFT))
        elif key == pygame.K_COMMA:
            self._change_stair_floor(-1, bool(modifiers & pygame.KMOD_SHIFT))
        elif key == pygame.K_PERIOD:
            self._change_stair_floor(1, bool(modifiers & pygame.KMOD_SHIFT))
        elif key == pygame.K_c and self.mode == 'details' and 0 <= self.selected_index < len(self.items):
            self.items[self.selected_index]['solid'] = not self.items[self.selected_index].get('solid', False)
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
            self.camera_x -= GRID
        elif key == pygame.K_l:
            self.camera_x += GRID
        elif key == pygame.K_i:
            self.camera_y -= GRID
        elif key == pygame.K_k:
            self.camera_y += GRID
        self._clamp_camera()

    def _region_rect_from_drag(self, start, end):
        left, right = sorted((start[0], end[0]))
        top, bottom = sorted((start[1], end[1]))
        return pygame.Rect(left, top, max(1, right - left), max(1, bottom - top))

    def _handle_mouse(self, event):
        if self.floor_picker is not None:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    for level, rect in self._floor_picker_rects().items():
                        if rect.collidepoint(event.pos):
                            item = self.layout[self.floor_picker['collection']][self.floor_picker['index']]
                            item[self.floor_picker['key']] = level
                            self.floor_picker = None
                            self.dirty = True
                            return
                if event.button in (1, 3):
                    self.floor_picker = None
            return
        if event.type == pygame.MOUSEWHEEL:
            if VIEWPORT.collidepoint(pygame.mouse.get_pos()):
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    self.camera_x -= event.y * GRID * 2
                else:
                    self.camera_y -= event.y * GRID * 2
                self._clamp_camera()
            return

        if event.type == pygame.MOUSEMOTION and self.atlas_drag_start and event.buttons[0]:
            end = self._atlas_source_from_mouse(event.pos)
            if end:
                sx, sy = self.atlas_drag_start
                self.source = pygame.Rect(min(sx, end[0]), min(sy, end[1]), abs(end[0] - sx) + GRID, abs(end[1] - sy) + GRID)
                self._clamp_source()
            return

        if event.type == pygame.MOUSEMOTION and self.detail_drag_index >= 0 and event.buttons[0]:
            wx, wy = self._world_from_mouse(event.pos)
            snap = 1 if pygame.key.get_mods() & pygame.KMOD_CTRL else MOVE_SNAP
            detail = self.layout['details'][self.detail_drag_index]
            detail['position'] = [round((wx - self.detail_drag_offset[0]) / snap) * snap, round((wy - self.detail_drag_offset[1]) / snap) * snap]
            self.dirty = True
            return

        if event.type == pygame.MOUSEMOTION and self.region_drag_index >= 0 and event.buttons[0]:
            wx, wy = self._world_from_mouse(event.pos)
            snap = 1 if pygame.key.get_mods() & pygame.KMOD_CTRL else MOVE_SNAP
            rect = self.items[self.region_drag_index]['rect']
            old_x, old_y = rect[0], rect[1]
            rect[0] = round((wx - self.region_drag_offset[0]) / snap) * snap
            rect[1] = round((wy - self.region_drag_offset[1]) / snap) * snap
            if self.mode in ('stairs', 'tunnels'):
                dx, dy = rect[0] - old_x, rect[1] - old_y
                for line_name in ('start_line', 'end_line'):
                    for point in self.items[self.region_drag_index][line_name]:
                        point[0] += dx
                        point[1] += dy
            self.dirty = True
            return

        if event.type == pygame.MOUSEMOTION and self.region_create_start and event.buttons[0]:
            self.region_preview = self._region_rect_from_drag(self.region_create_start, self._world_from_mouse(event.pos))
            return

        if event.type == pygame.MOUSEMOTION and self.line_create_start and event.buttons[0]:
            self.line_preview_end = self._world_from_mouse(event.pos)
            return

        if event.type == pygame.MOUSEMOTION and self.line_drag_index >= 0 and event.buttons[0]:
            world = self._world_from_mouse(event.pos)
            dx, dy = round(world[0] - self.line_drag_anchor[0]), round(world[1] - self.line_drag_anchor[1])
            item = self.items[self.line_drag_index]
            item['start'] = [self.line_drag_original[0][0] + dx, self.line_drag_original[0][1] + dy]
            item['end'] = [self.line_drag_original[1][0] + dx, self.line_drag_original[1][1] + dy]
            self.dirty = True
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.line_create_start and self.line_preview_end:
                start = self.line_create_start
                end = self.line_preview_end
                if round(start[0]) != round(end[0]) or round(start[1]) != round(end[1]):
                    self.items.append({'start': [round(start[0]), round(start[1])], 'end': [round(end[0]), round(end[1])]})
                    self.selected_index = len(self.items) - 1
                    self.dirty = True
            if self.region_create_start and self.region_preview and self.region_preview.width >= 4 and self.region_preview.height >= 4:
                item = self._new_region(self.region_preview)
                if self.mode in ('stairs', 'tunnels'):
                    end = self._world_from_mouse(event.pos)
                    item['start_line'], item['end_line'] = self._box_end_lines(self.region_preview, self.region_create_start, end)
                if self.mode == 'floors' and self._floor_overlaps(self.region_preview):
                    self.floor_notice = 'Khong the tao: vung tang dang chong len tang khac.'
                else:
                    self.items.append(item)
                    self.selected_index = len(self.items) - 1
                    self.dirty = True
            if self.mode == 'floors' and self.region_drag_index >= 0 and self._floor_overlaps(pygame.Rect(self.items[self.region_drag_index]['rect']), self.region_drag_index):
                self.items[self.region_drag_index]['rect'] = self.region_drag_original
                self.floor_notice = 'Da tra ve vi tri cu: vung tang khong duoc chong nhau.'
            self.atlas_drag_start = None
            self.detail_drag_index = self.region_drag_index = self.line_drag_index = -1
            self.region_create_start = self.region_preview = None
            self.line_create_start = self.line_preview_end = None
            return

        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        if event.button == 1 and ZOOM_OUT_RECT.collidepoint(event.pos):
            self._change_map_zoom(-1)
            return
        if event.button == 1 and ZOOM_IN_RECT.collidepoint(event.pos):
            self._change_map_zoom(1)
            return
        if self.mode == 'details' and ATLAS_RECT.collidepoint(event.pos) and event.button == 1:
            source = self._atlas_source_from_mouse(event.pos)
            if source:
                self.atlas_drag_start = source
                self.source = pygame.Rect(*source, GRID, GRID)
            return
        if not VIEWPORT.collidepoint(event.pos):
            return
        world = self._world_from_mouse(event.pos)
        if event.button == 3:
            if self.mode == 'stairs':
                # A/B are lines, not points. Right-click the line to choose
                # the floor for that specific end from the 0–5 picker.
                tolerance = 10 / self.map_zoom
                for index in range(len(self.items) - 1, -1, -1):
                    stair = self.items[index]
                    for line_key, floor_key in (('start_line', 'from_floor'), ('end_line', 'to_floor')):
                        line = stair.get(line_key, [])
                        if len(line) == 2 and self._point_to_segment_distance(world, line[0], line[1]) <= tolerance:
                            self.selected_index = index
                            self.floor_picker = {'collection': 'stairs', 'index': index, 'key': floor_key, 'end': 'A' if line_key == 'start_line' else 'B'}
                            return
            index = self._select_item(world)
            if index >= 0 and self.mode in ('floors', 'tunnels'):
                self.floor_picker = {'collection': self.mode, 'index': index, 'key': 'floor', 'end': 'VUNG' if self.mode == 'floors' else 'HAM'}
            return
        if event.button != 1:
            return
        index = -1 if pygame.key.get_mods() & pygame.KMOD_CTRL else self._select_item(world)
        if self.mode == 'map_boundaries':
            if index >= 0:
                self.line_drag_index = index
                self.line_drag_anchor = world
                item = self.items[index]
                self.line_drag_original = (list(item['start']), list(item['end']))
            else:
                self.line_create_start = world
                self.line_preview_end = world
            return
        if self.mode == 'details':
            if index >= 0:
                self.detail_drag_index = index
                x, y = self.items[index]['position']
                self.detail_drag_offset = world[0] - x, world[1] - y
            else:
                self._place_detail(world)
        elif index >= 0:
            self.region_drag_index = index
            rect = self.items[index]['rect']
            self.region_drag_offset = world[0] - rect[0], world[1] - rect[1]
            self.region_drag_original = list(rect)
        else:
            self.region_create_start = world
            self.region_preview = pygame.Rect(world, (1, 1))

    def _draw_text(self, text, x, y, color=(235, 235, 235), small=False):
        self.screen.blit((self.small_font if small else self.font).render(text, True, color), (x, y))

    def _draw_modal(self, title, lines, accent=(255, 225, 130)):
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(160, 88, 960, 545)
        pygame.draw.rect(self.screen, (30, 36, 46), panel, border_radius=10)
        pygame.draw.rect(self.screen, accent, panel, 2, border_radius=10)
        title_surface = pygame.font.SysFont('Arial', 29, bold=True).render(title, True, accent)
        self.screen.blit(title_surface, title_surface.get_rect(center=(panel.centerx, panel.y + 46)))
        font = pygame.font.SysFont('Arial', 18)
        for index, line in enumerate(lines):
            text = font.render(line, True, (235, 240, 245))
            self.screen.blit(text, text.get_rect(center=(panel.centerx, panel.y + 95 + index * 31)))

    def _draw_region(self, item, color, index):
        rect = self._screen_rect(pygame.Rect(item['rect']))
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill((*color, 42))
        self.screen.blit(overlay, rect.topleft)
        pygame.draw.rect(self.screen, color, rect, 2 if index == self.selected_index else 1)
        if self.mode == 'stairs':
            self._draw_text(f"T{item.get('from_floor', 1)} z:{float(item.get('from_zoom', 1.30)):.2f} <-> T{item.get('to_floor', 2)} z:{float(item.get('to_zoom', 1.30)):.2f}", rect.x + 3, rect.y + 3, color, True)
            for line, line_color, label in ((item['start_line'], (85, 255, 170), 'A'), (item['end_line'], (255, 95, 145), 'B')):
                screen_line = [(round(VIEWPORT.x + (point[0] - self.camera_x) * self.map_zoom), round(VIEWPORT.y + (point[1] - self.camera_y) * self.map_zoom)) for point in line]
                pygame.draw.line(self.screen, line_color, screen_line[0], screen_line[1], 5)
                self._draw_text(label, screen_line[0][0] + 4, screen_line[0][1] + 4, (20, 20, 20), True)
        elif self.mode == 'tunnels':
            self._draw_text(f"HAM - TANG {item.get('floor', 0)} | Cat line A/B moi mo", rect.x + 3, rect.y + 3, color, True)
            for line, line_color, label in ((item['start_line'], (85, 255, 170), 'A'), (item['end_line'], (255, 95, 145), 'B')):
                screen_line = [(round(VIEWPORT.x + (point[0] - self.camera_x) * self.map_zoom), round(VIEWPORT.y + (point[1] - self.camera_y) * self.map_zoom)) for point in line]
                pygame.draw.line(self.screen, line_color, screen_line[0], screen_line[1], 5)
                self._draw_text(label, screen_line[0][0] + 4, screen_line[0][1] + 4, (20, 20, 20), True)
        if self.mode == 'stairs':
            start_line, end_line = item['start_line'], item['end_line']
            start = pygame.Vector2((start_line[0][0] + start_line[1][0]) / 2, (start_line[0][1] + start_line[1][1]) / 2)
            end = pygame.Vector2((end_line[0][0] + end_line[1][0]) / 2, (end_line[0][1] + end_line[1][1]) / 2)
            start_screen = pygame.Vector2(VIEWPORT.x + (start.x - self.camera_x) * self.map_zoom, VIEWPORT.y + (start.y - self.camera_y) * self.map_zoom)
            end_screen = pygame.Vector2(VIEWPORT.x + (end.x - self.camera_x) * self.map_zoom, VIEWPORT.y + (end.y - self.camera_y) * self.map_zoom)
            direction = end_screen - start_screen
            if direction.length_squared() > 1:
                unit = direction.normalize()
                midpoint = start_screen.lerp(end_screen, 0.5)
                pygame.draw.line(self.screen, (255, 255, 255), midpoint - unit * 18, midpoint + unit * 18, 2)
                normal = pygame.Vector2(-unit.y, unit.x)
                pygame.draw.polygon(self.screen, (255, 255, 255), [midpoint + unit * 22, midpoint + unit * 10 + normal * 7, midpoint + unit * 10 - normal * 7])

    def _draw_boundary_line(self, item, index):
        start, end = item['start'], item['end']
        start_screen = (round(VIEWPORT.x + (start[0] - self.camera_x) * self.map_zoom), round(VIEWPORT.y + (start[1] - self.camera_y) * self.map_zoom))
        end_screen = (round(VIEWPORT.x + (end[0] - self.camera_x) * self.map_zoom), round(VIEWPORT.y + (end[1] - self.camera_y) * self.map_zoom))
        width = 5 if index == self.selected_index else 3
        color = MODE_COLORS[self.mode]
        pygame.draw.line(self.screen, color, start_screen, end_screen, width)
        pygame.draw.circle(self.screen, (245, 255, 255), start_screen, 3)
        pygame.draw.circle(self.screen, (245, 255, 255), end_screen, 3)

    def draw(self):
        self.screen.fill((30, 32, 38))
        self._draw_text(f'PIXEL RUINS TUNER — {MODE_LABELS[self.mode]}', 12, 12, MODE_COLORS.get(self.mode, (255, 225, 130)))
        self._draw_text(f'Texture dang chon: {self.selected_texture_name}', 430, 14, (160, 225, 255), True)
        self._draw_text('ZOOM', 705, 14, (255, 225, 130), True)
        pygame.draw.rect(self.screen, (65, 75, 90), ZOOM_OUT_RECT, border_radius=4)
        pygame.draw.rect(self.screen, (65, 75, 90), ZOOM_IN_RECT, border_radius=4)
        self._draw_text('-', ZOOM_OUT_RECT.x + 12, ZOOM_OUT_RECT.y + 5, (255, 255, 255))
        self._draw_text('+', ZOOM_IN_RECT.x + 10, ZOOM_IN_RECT.y + 5, (255, 255, 255))
        self._draw_text(f'{self.map_zoom:.2f}x', 800, 14, (255, 225, 130), True)
        # Rounding at the map edge can otherwise make a source crop one pixel
        # too large. Build a crop that is always guaranteed to be inside it.
        crop_width = min(self.overview.get_width(), max(1, round(VIEWPORT.width / self.map_zoom)))
        crop_height = min(self.overview.get_height(), max(1, round(VIEWPORT.height / self.map_zoom)))
        crop = pygame.Rect(
            max(0, min(self.overview.get_width() - crop_width, round(self.camera_x))),
            max(0, min(self.overview.get_height() - crop_height, round(self.camera_y))),
            crop_width, crop_height,
        )
        map_view = pygame.transform.scale(self.overview.subsurface(crop), VIEWPORT.size)
        self.screen.blit(map_view, VIEWPORT.topleft)
        for index, detail in enumerate(self.layout['details']):
            texture = self.textures.get(detail.get('texture'))
            if texture:
                source = pygame.Rect(detail['source'])
                rect = self._screen_rect(pygame.Rect(detail['position'], source.size))
                self.screen.blit(pygame.transform.scale(texture.subsurface(source), rect.size), rect.topleft)
                if self.mode == 'details':
                    color = TEXTURE_OUTLINE_COLORS.get(detail.get('texture'), (245, 245, 245))
                    width = 2 if index == self.selected_index else 1
                    pygame.draw.rect(self.screen, color, rect, width)
        if self.mode != 'details':
            if self.mode == 'map_boundaries':
                for index, item in enumerate(self.items):
                    self._draw_boundary_line(item, index)
                if self.line_create_start and self.line_preview_end:
                    self._draw_boundary_line({'start': self.line_create_start, 'end': self.line_preview_end}, -2)
            else:
                for index, item in enumerate(self.items):
                    self._draw_region(item, MODE_COLORS[self.mode], index)
                if self.region_preview:
                    preview_item = self._new_region(self.region_preview)
                    self._draw_region(preview_item, MODE_COLORS[self.mode], -2)
        pygame.draw.rect(self.screen, (240, 240, 240), VIEWPORT, 1)

        texture = self.selected_texture
        scale = min(ATLAS_RECT.width / texture.get_width(), ATLAS_RECT.height / texture.get_height())
        preview = pygame.transform.scale(texture, (round(texture.get_width() * scale), round(texture.get_height() * scale)))
        preview_rect = preview.get_rect(center=ATLAS_RECT.center)
        self.screen.blit(preview, preview_rect)
        select = pygame.Rect(preview_rect.x + round(self.source.x * scale), preview_rect.y + round(self.source.y * scale), max(1, round(self.source.width * scale)), max(1, round(self.source.height * scale)))
        pygame.draw.rect(self.screen, (255, 225, 70), select, 2)
        pygame.draw.rect(self.screen, (220, 220, 220), ATLAS_RECT, 1)
        info = [
            '1 Texture | 2 Collider | 3 Vung tang | 4 Cau thang box | 5 Ham | 6 Vien map',
            'Keo chuot o map: tao vung/line | keo doi tuong: di chuyen',
            'Ctrl khi keo: chinh 1px | mac dinh: 2px',
            'R-click: chon | F: xoay line ham 90 do | Delete: xoa | S: luu',
            'Zoom: nut -/+ hoac phim -/= | Wheel: cuon map',
        ]
        if self.mode == 'details':
            info += ['[ / ]: doi texture | Keo atlas: chon crop | Ctrl+click: dat moi',
                     'Khung mau: struct xanh | props cam | plant xanh la | player hong | shadow tim']
        elif self.mode == 'stairs':
            info += ['Shift+0..9: tang dau | Ctrl+Shift+0..9: tang cuoi', '[ / ]: zoom dau | Shift+[ / ]: zoom cuoi']
        elif self.mode in ('floors', 'tunnels'):
            info += ['R-click box: chon so tang 0-5']
        elif self.mode == 'stairs':
            info += [', / .: doi tang di | Shift+, / Shift+.: doi tang den']
        for index, line in enumerate(info):
            self._draw_text(line, 992, 365 + index * 21, (185, 225, 235), True)
        status = 'CHUA LUU' if self.dirty else 'DA LUU'
        self._draw_text(f'{MODE_LABELS[self.mode]}: {len(self.items)} | Chon: {self.selected_index} | {status}', 992, 535, (255, 140, 100) if self.dirty else (130, 235, 160), True)
        self._draw_text(f'Camera: {self.camera_x}, {self.camera_y}', 992, 556, (255, 225, 130), True)
        if self.show_help:
            self._draw_modal('HUONG DAN TUNER MAP', [
                '1: dat texture trang tri (khong tu tao va cham).',
                '2: keo vung DO de ve collider, nhan vat khong the di vao.',
                '3: keo vung XANH de danh dau tang. Vung tang khong duoc chong nhau.',
                '4: keo box CAM phu cau thang. Vao box de chuyen qua lai giua hai tang.',
                'Shift+so gan tang goc; Ctrl+Shift+so gan tang dich; [ ] chinh zoom.',
                '5: keo box TIM cho ham. Cat A/B moi mo; hai canh ben se giu ban trong ham.',
                '6: keo tung line CYAN lam vien map; nhan vat khong the cat qua line.',
                'Keo o vung trong de tao. Keo vung da co de di chuyen. Ctrl = 1 pixel.',
                'Nhan S de luu JSON. Khi thoat, tuner se nhac ban luu.',
                'Enter, H, Esc hoac click de bat dau.',
            ])
        elif self.exit_confirm:
            self._draw_modal('LUU LAYOUT TRUOC KHI THOAT?', ['S: Luu JSON va thoat.', 'D: Thoat khong luu.', 'Esc: Quay lai tuner.'], (255, 170, 110))
        if self.floor_picker is not None:
            panel = pygame.Rect(992, 522, 276, 160)
            pygame.draw.rect(self.screen, (28, 35, 48), panel, border_radius=6)
            pygame.draw.rect(self.screen, (255, 165, 65), panel, 2, border_radius=6)
            self._draw_text(f"Chon tang cho dau {self.floor_picker['end']} (0-5)", 1002, 534, (255, 220, 150), True)
            for level, rect in self._floor_picker_rects().items():
                pygame.draw.rect(self.screen, (70, 86, 110), rect, border_radius=4)
                pygame.draw.rect(self.screen, (210, 225, 240), rect, 1, border_radius=4)
                label = self.font.render(str(level), True, (255, 255, 255))
                self.screen.blit(label, label.get_rect(center=rect.center))
        if self.floor_notice:
            self._draw_text(self.floor_notice, 16, WINDOW_H - 20, (255, 120, 100), True)
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
                            self._save_layout(); self.running = False
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
