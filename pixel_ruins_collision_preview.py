"""Move through the Pixel Ruins layout while visualising tuned collisions.

Run: ``python pixel_ruins_collision_preview.py``
The preview reads ``assets/maps/pixel_ruins_layout.json`` every time it starts
and when F5 is pressed, so it is safe to keep open next to the map tuner.
"""

import pygame

from config import HEIGHT, WIDTH
from pixel_ruins_map import PixelRuinsMap


PLAYER_SIZE = (28, 38)
PLAYER_SPEED = 260
CAMERA_ZOOM = 1.30


class CollisionMapPreview:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption('Pixel Ruins — Collision Preview')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Consolas', 16)
        self.small_font = pygame.font.SysFont('Consolas', 13)
        self.running = True
        self.zoom = CAMERA_ZOOM
        self.camera = pygame.Vector2()
        self.load_layout()

    def load_layout(self):
        self.map_data = PixelRuinsMap(WIDTH, HEIGHT)
        self.world = self.map_data.surface
        self.world_width, self.world_height = self.world.get_size()
        self.colliders = list(self.map_data.wall_rects)
        self.player = pygame.Rect(0, 0, *PLAYER_SIZE)
        self.player.center = self._find_safe_spawn()
        self._update_camera()

    def _find_safe_spawn(self):
        # Pick the first 32px grid point outside all tuned collision zones.
        for y in range(80, self.world_height - 80, 32):
            for x in range(80, self.world_width - 80, 32):
                candidate = pygame.Rect(0, 0, *PLAYER_SIZE)
                candidate.center = (x, y)
                if not any(candidate.colliderect(rect) for rect in self.colliders):
                    return x, y
        return self.world_width // 2, self.world_height // 2

    def _update_camera(self):
        view_width = WIDTH / self.zoom
        view_height = HEIGHT / self.zoom
        self.camera.x = max(0, min(self.world_width - view_width, self.player.centerx - view_width / 2))
        self.camera.y = max(0, min(self.world_height - view_height, self.player.centery - view_height / 2))

    def _screen_rect(self, world_rect):
        return pygame.Rect(
            round((world_rect.x - self.camera.x) * self.zoom),
            round((world_rect.y - self.camera.y) * self.zoom),
            max(1, round(world_rect.width * self.zoom)),
            max(1, round(world_rect.height * self.zoom)),
        )

    def _blocked(self, candidate):
        return any(candidate.colliderect(rect) for rect in self.colliders)

    def _move_player(self, dt):
        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(
            int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT]),
            int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        if direction.length_squared() == 0:
            return
        direction = direction.normalize() * PLAYER_SPEED * dt
        # Resolve one axis at a time so the test avatar can slide along walls.
        self.player.x += round(direction.x)
        self.player.clamp_ip(pygame.Rect(0, 0, self.world_width, self.world_height))
        if self._blocked(self.player):
            self.player.x -= round(direction.x)
        self.player.y += round(direction.y)
        self.player.clamp_ip(pygame.Rect(0, 0, self.world_width, self.world_height))
        if self._blocked(self.player):
            self.player.y -= round(direction.y)

    def _draw_overlay_rect(self, rect, color, alpha, width=1):
        screen_rect = self._screen_rect(rect)
        overlay = pygame.Surface(screen_rect.size, pygame.SRCALPHA)
        overlay.fill((*color, alpha))
        self.screen.blit(overlay, screen_rect.topleft)
        pygame.draw.rect(self.screen, color, screen_rect, width)

    def draw(self):
        crop = pygame.Rect(round(self.camera.x), round(self.camera.y),
                           round(WIDTH / self.zoom), round(HEIGHT / self.zoom))
        crop.clamp_ip(self.world.get_rect())
        self.screen.blit(pygame.transform.scale(self.world.subsurface(crop), (WIDTH, HEIGHT)), (0, 0))

        # Raw red zones are what was drawn in the tuner. Bright red outlines
        # are the actual collision pieces after tunnel areas have been cut out.
        for rect in self.map_data.collision_zones:
            self._draw_overlay_rect(rect, (255, 70, 70), 42)
        for rect in self.map_data.tunnels:
            self._draw_overlay_rect(rect, (190, 105, 255), 72, 2)
        for floor in self.map_data.floors:
            rect = self._screen_rect(floor['rect'])
            pygame.draw.rect(self.screen, (75, 185, 255), rect, 2)
            self.screen.blit(self.small_font.render(f"T{floor.get('floor', 0)}", True, (75, 185, 255)), (rect.x + 3, rect.y + 3))
        for tunnel in self.map_data.tunnel_zones:
            for end_line, color in ((tunnel['start_line'], (85, 255, 170)), (tunnel['end_line'], (255, 95, 145))):
                start = (round((end_line[0][0] - self.camera.x) * self.zoom), round((end_line[0][1] - self.camera.y) * self.zoom))
                end = (round((end_line[1][0] - self.camera.x) * self.zoom), round((end_line[1][1] - self.camera.y) * self.zoom))
                pygame.draw.line(self.screen, color, start, end, 5)
        for start, end in self.map_data.map_boundaries:
            pygame.draw.line(self.screen, (80, 235, 255),
                             ((start[0] - self.camera.x) * self.zoom, (start[1] - self.camera.y) * self.zoom),
                             ((end[0] - self.camera.x) * self.zoom, (end[1] - self.camera.y) * self.zoom), 3)
        for line in self.map_data.stairs:
            rect = self._screen_rect(line['rect'])
            pygame.draw.rect(self.screen, (255, 165, 65), rect, 3)
            self.screen.blit(self.small_font.render(f"T{line['from_floor']} <-> T{line['to_floor']}", True, (255, 165, 65)), (rect.x + 4, rect.y + 4))
            for end_line, color in ((line['start_line'], (85, 255, 170)), (line['end_line'], (255, 95, 145))):
                start = (round((end_line[0][0] - self.camera.x) * self.zoom), round((end_line[0][1] - self.camera.y) * self.zoom))
                end = (round((end_line[1][0] - self.camera.x) * self.zoom), round((end_line[1][1] - self.camera.y) * self.zoom))
                pygame.draw.line(self.screen, color, start, end, 5)
        for rect in self.colliders:
            pygame.draw.rect(self.screen, (255, 235, 90), self._screen_rect(rect), 1)

        player_screen = self._screen_rect(self.player)
        shadow = pygame.Rect(player_screen.x + 4, player_screen.bottom - 7, player_screen.width - 8, 8)
        pygame.draw.ellipse(self.screen, (20, 25, 30), shadow)
        pygame.draw.rect(self.screen, (70, 215, 255), player_screen, border_radius=6)
        pygame.draw.rect(self.screen, (240, 255, 255), player_screen, 2, border_radius=6)
        pygame.draw.circle(self.screen, (255, 225, 170), (player_screen.centerx, player_screen.y + 9), max(3, player_screen.width // 6))

        panel = pygame.Surface((455, 72), pygame.SRCALPHA)
        panel.fill((15, 20, 27, 210))
        self.screen.blit(panel, (8, 8))
        self.screen.blit(self.font.render('COLLISION MAP PREVIEW', True, (255, 230, 120)), (18, 14))
        self.screen.blit(self.small_font.render('Move: WASD / Arrow keys | F5: reload JSON | Esc: exit', True, (230, 235, 240)), (18, 38))
        self.screen.blit(self.small_font.render(f'Red: zone  Yellow: collider  Purple: tunnel  Cyan: boundary line ({len(self.colliders)} pieces)', True, (230, 235, 240)), (18, 55))
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_F5:
                        self.load_layout()
            self._move_player(dt)
            self._update_camera()
            self.draw()
        pygame.quit()


if __name__ == '__main__':
    CollisionMapPreview().run()
