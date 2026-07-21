import pygame
import os
from config import WIDTH, HEIGHT, SKILL_EFFECT_CONFIG

class SkillEffect(pygame.sprite.Sprite):
    """Generic one-shot animated VFX for passive skills."""

    _frames_cache = {}

    CONFIG = SKILL_EFFECT_CONFIG

    def __init__(self, skill_name, x, y, facing=1):
        super().__init__()
        self.skill_name = skill_name
        self.facing = facing
        cfg = self.CONFIG.get(skill_name, self.CONFIG['fire'])
        self.anchor_bottom = bool(cfg.get('anchor_bottom', False))
        self.frame_ms = cfg.get('frame_ms', 50)
        self.timer = 0
        self.frame_idx = 0

        frames = self._get_frames(skill_name)
        if not frames:
            self._frames = [pygame.Surface((8, 8), pygame.SRCALPHA)]
        else:
            self._frames = frames

        if facing == -1:
            self._frames = [pygame.transform.flip(f, True, False) for f in self._frames]

        self.image = self._frames[0]
        if self.anchor_bottom:
            self.rect = self.image.get_rect(midbottom=(x, y))
        else:
            self.rect = self.image.get_rect(center=(x, y))

    @property
    def floor_y(self):
        return self.rect.bottom

    @classmethod
    def _get_frames(cls, skill_name):
        if skill_name in cls._frames_cache:
            return cls._frames_cache[skill_name]

        cfg = cls.CONFIG.get(skill_name, cls.CONFIG['fire'])
        base_dir = os.path.dirname(os.path.dirname(__file__))
        abs_path = os.path.join(base_dir, cfg['path'])
        frames = []

        try:
            sheet = pygame.image.load(abs_path).convert_alpha()
            fw = int(cfg.get('frame_w', sheet.get_height()))
            fh = int(cfg.get('frame_h', sheet.get_height()))
            src_y = int(cfg.get('src_y', 0))
            src_h = int(cfg.get('src_h', fh))
            row_start = int(cfg.get('row_start', 0))
            row_count = int(cfg.get('row_count', 0))
            col_start = int(cfg.get('col_start', 0))
            col_count = int(cfg.get('col_count', 0))
            src_h = max(1, min(src_h, fh))
            src_y = max(0, min(src_y, fh - src_h))
            scale = float(cfg.get('scale', 1.0))
            vertical = bool(cfg.get('vertical', False))

            if vertical:
                rows = max(1, sheet.get_height() // fh)
                row_start = max(0, min(row_start, rows - 1))
                row_end = rows if row_count <= 0 else min(rows, row_start + row_count)
                for r in range(row_start, row_end):
                    sub = pygame.Surface((fw, src_h), pygame.SRCALPHA)
                    sub.blit(sheet, (0, 0), (0, r * fh + src_y, fw, src_h))
                    if scale != 1.0:
                        sub = pygame.transform.scale(sub, (max(1, int(fw * scale)), max(1, int(src_h * scale))))
                    frames.append(sub)
            else:
                cols = max(1, sheet.get_width() // fw)
                rows = max(1, sheet.get_height() // fh)
                row_start = max(0, min(row_start, rows - 1))
                col_start = max(0, min(col_start, cols - 1))
                row_end = rows if row_count <= 0 else min(rows, row_start + row_count)
                col_end = cols if col_count <= 0 else min(cols, col_start + col_count)
                for r in range(row_start, row_end):
                    for c in range(col_start, col_end):
                        sub = pygame.Surface((fw, src_h), pygame.SRCALPHA)
                        sub.blit(sheet, (0, 0), (c * fw, r * fh + src_y, fw, src_h))
                        if scale != 1.0:
                            sub = pygame.transform.scale(sub, (max(1, int(fw * scale)), max(1, int(src_h * scale))))
                        frames.append(sub)
        except Exception:
            frames = []

        cls._frames_cache[skill_name] = frames
        return frames

    def update(self, dt):
        self.timer += dt
        while self.timer >= self.frame_ms:
            self.timer -= self.frame_ms
            self.frame_idx += 1
            if self.frame_idx >= len(self._frames):
                self.kill()
                return
            anchor = self.rect.midbottom if self.anchor_bottom else self.rect.center
            self.image = self._frames[self.frame_idx]
            if self.anchor_bottom:
                self.rect = self.image.get_rect(midbottom=anchor)
            else:
                self.rect = self.image.get_rect(center=anchor)


class WindStreamEffect(pygame.sprite.Sprite):
    """Directional wind projectile that travels outward and can collide."""

    _frames_cache = None

    @classmethod
    def _get_projectile_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache
        base_dir = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(
            base_dir,
            'assets', 'skills', 'effects', 'Wind Effect 01', 'Wind Projectile.png'
        )
        frames = []
        try:
            sheet = pygame.image.load(path).convert_alpha()
            fw, fh = 32, 32
            cols = max(1, sheet.get_width() // fw)
            rows = max(1, sheet.get_height() // fh)
            for r in range(rows):
                for c in range(cols):
                    sub = pygame.Surface((fw, fh), pygame.SRCALPHA)
                    sub.blit(sheet, (0, 0), (c * fw, r * fh, fw, fh))
                    frames.append(pygame.transform.scale(sub, (56, 56)))
        except Exception:
            frames = []

        cls._frames_cache = frames
        return cls._frames_cache

    def __init__(self, x, y, dir_x, dir_y, owner=None, damage=12, speed_px_per_ms=0.80, life_ms=320):
        super().__init__()
        base_frames = self._get_projectile_frames()
        if not base_frames:
            base_frames = [pygame.Surface((8, 8), pygame.SRCALPHA)]

        self._frames = base_frames
        if dir_x < 0:
            self._frames = [pygame.transform.flip(frame, True, False) for frame in self._frames]

        self.frame_ms = 45
        self.timer = 0
        self.frame_idx = 0
        self.image = self._frames[0]
        self.rect = self.image.get_rect(center=(x, y))

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        self.vel = vec * speed_px_per_ms
        self.life_ms = life_ms
        self.owner = owner
        self.damage = int(damage)
        self.already_hit_targets = set()

    @property
    def floor_y(self):
        return self.rect.bottom

    def update(self, dt):
        self.life_ms -= dt
        if self.life_ms <= 0:
            self.kill()
            return

        self.rect.x += int(self.vel.x * dt)
        self.rect.y += int(self.vel.y * dt)

        self.timer += dt
        while self.timer >= self.frame_ms:
            self.timer -= self.frame_ms
            if self.frame_idx < len(self._frames) - 1:
                self.frame_idx += 1
                center = self.rect.center
                self.image = self._frames[self.frame_idx]
                self.rect = self.image.get_rect(center=center)

        if self.rect.right < -48 or self.rect.left > WIDTH + 48 or self.rect.bottom < -48 or self.rect.top > HEIGHT + 48:
            self.kill()


class WaterBallProjectile(pygame.sprite.Sprite):
    """Water ball projectile that uses startup/infinite sheet while flying."""

    _frames_cache = None

    @classmethod
    def _get_projectile_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache
        base_dir = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(
            base_dir,
            'assets', 'skills', 'effects', 'Water Ball - Spritesheet', 'WaterBall - Startup and Infinite.png'
        )
        frames = []
        try:
            sheet = pygame.image.load(path).convert_alpha()
            fw, fh = 64, 64
            cols = max(1, sheet.get_width() // fw)
            rows = max(1, sheet.get_height() // fh)
            for r in range(rows):
                for c in range(cols):
                    sub = pygame.Surface((fw, fh), pygame.SRCALPHA)
                    sub.blit(sheet, (0, 0), (c * fw, r * fh, fw, fh))
                    frames.append(pygame.transform.scale(sub, (72, 72)))
        except Exception:
            frames = []

        cls._frames_cache = frames
        return cls._frames_cache

    def __init__(self, x, y, dir_x, dir_y, owner=None, damage=13, speed_px_per_ms=0.70, life_ms=700):
        super().__init__()
        base_frames = self._get_projectile_frames()
        if not base_frames:
            base_frames = [pygame.Surface((10, 10), pygame.SRCALPHA)]

        self._frames = base_frames
        self.frame_ms = 45
        self.timer = 0
        self.frame_idx = 0
        self.image = self._frames[0]
        self.rect = self.image.get_rect(center=(x, y))

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        self.vel = vec * speed_px_per_ms
        self.life_ms = life_ms
        self.owner = owner
        self.damage = int(damage)
        self.already_hit_targets = set()

    @property
    def floor_y(self):
        return self.rect.bottom

    def update(self, dt):
        self.life_ms -= dt
        if self.life_ms <= 0:
            self.kill()
            return

        self.rect.x += int(self.vel.x * dt)
        self.rect.y += int(self.vel.y * dt)

        self.timer += dt
        while self.timer >= self.frame_ms:
            self.timer -= self.frame_ms
            self.frame_idx = (self.frame_idx + 1) % len(self._frames)
            center = self.rect.center
            self.image = self._frames[self.frame_idx]
            self.rect = self.image.get_rect(center=center)

        if self.rect.right < -72 or self.rect.left > WIDTH + 72 or self.rect.bottom < -72 or self.rect.top > HEIGHT + 72:
            self.kill()


class WaterBlastProjectile(pygame.sprite.Sprite):
    """Water blast projectile: startup frames once, then loop infinity frames."""

    _frames_cache = None

    @classmethod
    def _get_projectile_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache
        base_dir = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(
            base_dir,
            'assets', 'skills', 'effects', 'Water Blast - Spritesheet', 'Water Blast - Startup and Infinite.png'
        )
        frames = []
        try:
            sheet = pygame.image.load(path).convert_alpha()
            fw, fh = 128, 128
            cols = max(1, sheet.get_width() // fw)
            rows = max(1, sheet.get_height() // fh)
            for r in range(rows):
                for c in range(cols):
                    sub = pygame.Surface((fw, fh), pygame.SRCALPHA)
                    sub.blit(sheet, (0, 0), (c * fw, r * fh, fw, fh))
                    frames.append(pygame.transform.scale(sub, (96, 96)))
        except Exception:
            frames = []

        cls._frames_cache = frames
        return cls._frames_cache

    def __init__(self, x, y, dir_x, dir_y, owner=None, damage=20, speed_px_per_ms=0.74, life_ms=820):
        super().__init__()
        base_frames = self._get_projectile_frames()
        if not base_frames:
            base_frames = [pygame.Surface((12, 12), pygame.SRCALPHA)]

        self._frames = base_frames
        if dir_x < 0:
            self._frames = [pygame.transform.flip(frame, True, False) for frame in self._frames]

        # Frame 0-3: startup progression, frame 3..end: repeatable loop.
        self.loop_start_idx = min(3, len(self._frames) - 1)
        self.frame_ms = 52
        self.timer = 0
        self.frame_idx = 0
        self.image = self._frames[0]
        self.rect = self.image.get_rect(center=(x, y))

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        self.vel = vec * speed_px_per_ms
        self.life_ms = life_ms
        self.owner = owner
        self.damage = int(damage)
        self.already_hit_targets = set()

    @property
    def floor_y(self):
        return self.rect.bottom

    def update(self, dt):
        self.life_ms -= dt
        if self.life_ms <= 0:
            self.kill()
            return

        self.rect.x += int(self.vel.x * dt)
        self.rect.y += int(self.vel.y * dt)

        self.timer += dt
        while self.timer >= self.frame_ms:
            self.timer -= self.frame_ms
            if self.frame_idx < self.loop_start_idx:
                self.frame_idx += 1
            else:
                self.frame_idx += 1
                if self.frame_idx >= len(self._frames):
                    self.frame_idx = self.loop_start_idx

            center = self.rect.center
            self.image = self._frames[self.frame_idx]
            self.rect = self.image.get_rect(center=center)

        if self.rect.right < -96 or self.rect.left > WIDTH + 96 or self.rect.bottom < -96 or self.rect.top > HEIGHT + 96:
            self.kill()


class LightProjectile(pygame.sprite.Sprite):
    """Light projectile that uses Holy VFX 01 Repeatable while flying."""

    _frames_cache = None

    @classmethod
    def _get_projectile_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache

        base_dir = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(
            base_dir,
            'assets', 'skills', 'effects', 'Holy VFX 01', 'Holy VFX 01 Repeatable.png'
        )
        frames = []
        try:
            sheet = pygame.image.load(path).convert_alpha()
            fw, fh = 32, 32
            cols = max(1, sheet.get_width() // fw)
            rows = max(1, sheet.get_height() // fh)
            for r in range(rows):
                for c in range(cols):
                    sub = pygame.Surface((fw, fh), pygame.SRCALPHA)
                    sub.blit(sheet, (0, 0), (c * fw, r * fh, fw, fh))
                    frames.append(pygame.transform.scale(sub, (62, 62)))
        except Exception:
            frames = []

        cls._frames_cache = frames
        return cls._frames_cache

    def __init__(self, x, y, dir_x, dir_y, owner=None, damage=17, speed_px_per_ms=0.86, life_ms=720):
        super().__init__()
        base_frames = self._get_projectile_frames()
        if not base_frames:
            base_frames = [pygame.Surface((10, 10), pygame.SRCALPHA)]

        self._frames = base_frames
        if dir_x < 0:
            self._frames = [pygame.transform.flip(frame, True, False) for frame in self._frames]

        self.frame_ms = 42
        self.timer = 0
        self.frame_idx = 0
        self.image = self._frames[0]
        self.rect = self.image.get_rect(center=(x, y))

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        self.vel = vec * speed_px_per_ms
        self.life_ms = life_ms
        self.owner = owner
        self.damage = int(damage)
        self.already_hit_targets = set()

    @property
    def floor_y(self):
        return self.rect.bottom

    def update(self, dt):
        self.life_ms -= dt
        if self.life_ms <= 0:
            self.kill()
            return

        self.rect.x += int(self.vel.x * dt)
        self.rect.y += int(self.vel.y * dt)

        self.timer += dt
        while self.timer >= self.frame_ms:
            self.timer -= self.frame_ms
            self.frame_idx = (self.frame_idx + 1) % len(self._frames)
            center = self.rect.center
            self.image = self._frames[self.frame_idx]
            self.rect = self.image.get_rect(center=center)

        if self.rect.right < -72 or self.rect.left > WIDTH + 72 or self.rect.bottom < -72 or self.rect.top > HEIGHT + 72:
            self.kill()


class DarkProjectile(pygame.sprite.Sprite):
    """Dark projectile that flies first, then triggers dark hit effect on contact."""

    _frames_cache = None

    @classmethod
    def _get_projectile_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache

        base_dir = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(
            base_dir,
            'assets', 'skills', 'effects', 'Dark VFX 2', 'Dark VFX 1 (40x32).png'
        )
        frames = []
        try:
            sheet = pygame.image.load(path).convert_alpha()
            fw, fh = 40, 32
            cols = max(1, sheet.get_width() // fw)
            rows = max(1, sheet.get_height() // fh)
            for r in range(rows):
                for c in range(cols):
                    sub = pygame.Surface((fw, fh), pygame.SRCALPHA)
                    sub.blit(sheet, (0, 0), (c * fw, r * fh, fw, fh))
                    frames.append(pygame.transform.scale(sub, (72, 58)))
        except Exception:
            frames = []

        cls._frames_cache = frames
        return cls._frames_cache

    def __init__(self, x, y, dir_x, dir_y, owner=None, damage=15, speed_px_per_ms=0.86, life_ms=680):
        super().__init__()
        base_frames = self._get_projectile_frames()
        if not base_frames:
            base_frames = [pygame.Surface((12, 10), pygame.SRCALPHA)]

        self._frames = base_frames
        if dir_x < 0:
            self._frames = [pygame.transform.flip(frame, True, False) for frame in self._frames]

        self.frame_ms = 42
        self.timer = 0
        self.frame_idx = 0
        self.image = self._frames[0]
        self.rect = self.image.get_rect(center=(x, y))

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        self.vel = vec * speed_px_per_ms
        self.life_ms = life_ms
        self.owner = owner
        self.damage = int(damage)
        self.already_hit_targets = set()

    @property
    def floor_y(self):
        return self.rect.bottom

    def update(self, dt):
        self.life_ms -= dt
        if self.life_ms <= 0:
            self.kill()
            return

        self.rect.x += int(self.vel.x * dt)
        self.rect.y += int(self.vel.y * dt)

        self.timer += dt
        while self.timer >= self.frame_ms:
            self.timer -= self.frame_ms
            self.frame_idx = (self.frame_idx + 1) % len(self._frames)
            center = self.rect.center
            self.image = self._frames[self.frame_idx]
            self.rect = self.image.get_rect(center=center)

        if self.rect.right < -80 or self.rect.left > WIDTH + 80 or self.rect.bottom < -80 or self.rect.top > HEIGHT + 80:
            self.kill()


class WoodProjectile(pygame.sprite.Sprite):
    """Wood projectile that flies first and triggers wood hit effect on contact."""

    _frames_cache = None

    @classmethod
    def _get_projectile_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache
        base_dir = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(
            base_dir,
            'assets', 'skills', 'effects', 'Wood VFX 01', 'Wood VFX 01 Repeatable.png'
        )
        frames = []
        try:
            sheet = pygame.image.load(path).convert_alpha()
            fw, fh = 32, 32
            cols = max(1, sheet.get_width() // fw)
            rows = max(1, sheet.get_height() // fh)
            for r in range(rows):
                for c in range(cols):
                    sub = pygame.Surface((fw, fh), pygame.SRCALPHA)
                    sub.blit(sheet, (0, 0), (c * fw, r * fh, fw, fh))
                    frames.append(pygame.transform.scale(sub, (62, 62)))
        except Exception:
            frames = []

        cls._frames_cache = frames
        return cls._frames_cache

    def __init__(self, x, y, dir_x, dir_y, owner=None, damage=12, speed_px_per_ms=0.72, life_ms=760):
        super().__init__()
        base_frames = self._get_projectile_frames()
        if not base_frames:
            base_frames = [pygame.Surface((10, 10), pygame.SRCALPHA)]

        self._frames = base_frames
        if dir_x < 0:
            self._frames = [pygame.transform.flip(frame, True, False) for frame in self._frames]

        self.frame_ms = 44
        self.timer = 0
        self.frame_idx = 0
        self.image = self._frames[0]
        self.rect = self.image.get_rect(center=(x, y))

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        self.vel = vec * speed_px_per_ms
        self.life_ms = life_ms
        self.owner = owner
        self.damage = int(damage)
        self.already_hit_targets = set()

    @property
    def floor_y(self):
        return self.rect.bottom

    def update(self, dt):
        self.life_ms -= dt
        if self.life_ms <= 0:
            self.kill()
            return

        self.rect.x += int(self.vel.x * dt)
        self.rect.y += int(self.vel.y * dt)

        self.timer += dt
        while self.timer >= self.frame_ms:
            self.timer -= self.frame_ms
            self.frame_idx = (self.frame_idx + 1) % len(self._frames)
            center = self.rect.center
            self.image = self._frames[self.frame_idx]
            self.rect = self.image.get_rect(center=center)

        if self.rect.right < -72 or self.rect.left > WIDTH + 72 or self.rect.bottom < -72 or self.rect.top > HEIGHT + 72:
            self.kill()


class AcidProjectile(pygame.sprite.Sprite):
    """Acid projectile that flies first and applies acid passive on impact."""

    _frames_cache = None

    @classmethod
    def _get_projectile_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache
        base_dir = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(
            base_dir,
            'assets', 'skills', 'effects', 'Acid VFX 2', 'Acid VFX 02Repeatable.png'
        )
        frames = []
        try:
            sheet = pygame.image.load(path).convert_alpha()
            fw, fh = 56, 64
            lane_h = 32
            rows = max(1, sheet.get_height() // fh)
            for r in range(rows):
                sub = pygame.Surface((fw, lane_h), pygame.SRCALPHA)
                # Source frame contains two parallel lanes (top+bottom). Keep only top lane.
                sub.blit(sheet, (0, 0), (0, r * fh, fw, lane_h))
                frames.append(pygame.transform.scale(sub, (68, 40)))
        except Exception:
            frames = []

        cls._frames_cache = frames
        return cls._frames_cache

    def __init__(self, x, y, dir_x, dir_y, owner=None, damage=12, speed_px_per_ms=0.68, life_ms=820):
        super().__init__()
        base_frames = self._get_projectile_frames()
        if not base_frames:
            base_frames = [pygame.Surface((10, 8), pygame.SRCALPHA)]

        self._frames = base_frames
        if dir_x < 0:
            self._frames = [pygame.transform.flip(frame, True, False) for frame in self._frames]

        self.image = self._frames[0]
        self.rect = self.image.get_rect(center=(x, y))

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        self.vel = vec * speed_px_per_ms
        self.life_ms = life_ms
        self.owner = owner
        self.damage = int(damage)
        self.already_hit_targets = set()

    @property
    def floor_y(self):
        return self.rect.bottom

    def update(self, dt):
        self.life_ms -= dt
        if self.life_ms <= 0:
            self.kill()
            return

        self.rect.x += int(self.vel.x * dt)
        self.rect.y += int(self.vel.y * dt)

        if self.rect.right < -72 or self.rect.left > WIDTH + 72 or self.rect.bottom < -72 or self.rect.top > HEIGHT + 72:
            self.kill()

