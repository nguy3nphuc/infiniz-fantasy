import pygame
import sys
import math
import random
import os
import json
import config as config_module
import entities as entities_module
from types import SimpleNamespace
from pixel_ruins_map import PixelRuinsMap
from config import (WIDTH, HEIGHT, FPS, MAP_IMAGE, MIN_Y, MAX_Y,
                     CRIT_CHANCE, CRIT_MULTIPLIER,
                     CAMERA_SHAKE_INTENSITY, CAMERA_SHAKE_DURATION,
                     PLAYER_RESOURCE_PRESETS, PLAYER_RESOURCE_REGEN_PER_MS,
                     SKILL_MANA_COST, DEFAULT_ARMOR_REDUCTION_PCT,
                     SKILL_EFFECT_CONFIG, SKILL_DROP_CONFIG,
                     SKILL_COMBAT_CONFIG,
                     ABILITY_VIAL_DROP_CHANCE, ABILITY_MAX_LEVEL,
                     ABILITY_ATTACK_BONUS_PER_LEVEL, ABILITY_ARMOR_BONUS_PER_LEVEL,
                     ABILITY_SPEED_BONUS_PER_LEVEL, ARCHER_ARROW_CONFIG,
                     BERSERK_VIAL_DROP_CHANCE, BERSERK_VIAL_DURATION_MS,
                     BERSERK_DAMAGE_MULTIPLIER, BERSERK_ARMOR_EFFECTIVENESS_MULTIPLIER,
                     HOLY_EFFECT_DURATION_MS, PIXEL_RUINS_CAMERA_ZOOM,
                     PIXEL_RUINS_ENTITY_SCALE, PIXEL_RUINS_TUNNEL_ENTITY_ALPHA,
                     PIXEL_RUINS_FOOTBOX_WIDTH_RATIO, PIXEL_RUINS_FOOTBOX_HEIGHT_RATIO)
from entities import (Knight, Archer, Lizardman, Cyclop, Kobold, Fireworm, DamageNumber,
                       GoblinWarrior, GoblinSpearman, GoblinTank,
                       FatCultist, DeathBringer,
                       DashSmoke, UltimateEffect, KnightUltimateShockwave, BloodVFX, HitVFX,
                       HealthPotion, AbilityVial, BerserkVial, SkillIcon)


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
        abs_path = os.path.join(os.path.dirname(__file__), cfg['path'])
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

        path = os.path.join(
            os.path.dirname(__file__),
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

        path = os.path.join(
            os.path.dirname(__file__),
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

        path = os.path.join(
            os.path.dirname(__file__),
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

        path = os.path.join(
            os.path.dirname(__file__),
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

        path = os.path.join(
            os.path.dirname(__file__),
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

        path = os.path.join(
            os.path.dirname(__file__),
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

        path = os.path.join(
            os.path.dirname(__file__),
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


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Beat-em-up Test")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "SELECT"
        self.paused = False
        self.DEBUG_DRAW = False # Set to True to see hitboxes and hurtboxes
        self.selected_hero = 'knight'
        self.selected_phase = 1

        # Camera shake state
        self.camera_offset = [0, 0]
        self.shake_timer = 0
        self.shake_intensity = 0

        # Map initialized dynamically in load()
        self.map = pygame.Surface((WIDTH, HEIGHT))

        # Shadow sprite – drawn beneath every entity each frame
        import os as _os
        _shadow_path = _os.path.join(_os.path.dirname(__file__), 'assets', 'shadow.png')
        try:
            self._shadow_src = pygame.image.load(_shadow_path).convert_alpha()
        except Exception:
            # Fallback: simple dark ellipse if asset is missing
            self._shadow_src = pygame.Surface((64, 16), pygame.SRCALPHA)
            pygame.draw.ellipse(self._shadow_src, (0, 0, 0, 80), self._shadow_src.get_rect())
        self._shadow_cache: dict = {}  # width → scaled surface
        self._skill_icon_cache: dict = {}
        self._skill_icon_ratio = 0.5
        self._skill_icon_offset_y = 2
        self._skill_target_ratio = 1.0
        self._skill_target_offset_x = 0
        self._skill_target_offset_y = 2
        self._skill_bar_cfg = {
            'p1': {
                'reverse': False,
                'icon_offsets': [[0, self._skill_icon_offset_y], [0, self._skill_icon_offset_y], [0, self._skill_icon_offset_y]],
                'icon_scales': [1.0, 1.0, 1.0],
                'target_offsets': [[self._skill_target_offset_x, self._skill_target_offset_y],
                                   [self._skill_target_offset_x, self._skill_target_offset_y],
                                   [self._skill_target_offset_x, self._skill_target_offset_y]],
                'target_scales': [1.0, 1.0, 1.0],
            },
            'p2': {
                'reverse': True,
                'icon_offsets': [[0, self._skill_icon_offset_y], [0, self._skill_icon_offset_y], [0, self._skill_icon_offset_y]],
                'icon_scales': [1.0, 1.0, 1.0],
                'target_offsets': [[self._skill_target_offset_x, self._skill_target_offset_y],
                                   [self._skill_target_offset_x, self._skill_target_offset_y],
                                   [self._skill_target_offset_x, self._skill_target_offset_y]],
                'target_scales': [1.0, 1.0, 1.0],
            },
        }
        self._skill_frame_img, self._skill_target_img = self._load_skill_ui_assets()
        # Pixel-art UI should use integer ratio + nearest-neighbor scaling.
        self._skill_ui_scale = 1
        self._skill_margin_x = 18
        self._skill_margin_y = 12
        self._load_skill_ui_tune_config()

        # Standalone UI tuning sandbox is now provided via skill_ui_tuner.py.
        self.skill_ui_test_mode = False
        self._skill_test_p1 = SimpleNamespace(skills=['water_ball', 'fire', 'wind'], target_skill_idx=0, active_skill=None)
        self._skill_test_p2 = SimpleNamespace(skills=['shield', 'holy', 'acid'], target_skill_idx=1, active_skill='shield')

        self.knight_preview = Knight(pos=(WIDTH//3, HEIGHT//2 + 50))
        self.archer_preview = Archer(pos=(2*WIDTH//3, HEIGHT//2 + 50))

    def _load_skill_ui_assets(self):
        """Load prebuilt skill frame and target frame from assets/skills/frames."""
        frames_dir = os.path.join(os.path.dirname(__file__), "assets", "skills", "frames")
        frame_path = os.path.join(frames_dir, "skill_frame.png")
        target_path = os.path.join(frames_dir, "target_skill.png")

        frame_img = None
        target_img = None

        try:
            frame_img = pygame.image.load(frame_path).convert_alpha()
        except Exception:
            frame_img = pygame.Surface((150, 37), pygame.SRCALPHA)
            pygame.draw.rect(frame_img, (90, 90, 110), (0, 0, 150, 37), 2)

        try:
            target_img = pygame.image.load(target_path).convert_alpha()
        except Exception:
            target_img = pygame.Surface((40, 59), pygame.SRCALPHA)
            pygame.draw.rect(target_img, (255, 220, 80), (1, 20, 38, 38), 2)

        # Tune target overlay size to fit slot interior better.
        if self._skill_target_ratio != 1.0:
            tw = max(1, int(round(target_img.get_width() * self._skill_target_ratio)))
            th = max(1, int(round(target_img.get_height() * self._skill_target_ratio)))
            target_img = pygame.transform.scale(target_img, (tw, th))

        bbox = frame_img.get_bounding_rect()
        slot_pitch = bbox.width / 3.0
        self._skill_slot_centers = [
            int(round(bbox.x + slot_pitch * 0.5)),
            int(round(bbox.x + slot_pitch * 1.5)),
            int(round(bbox.x + slot_pitch * 2.5)),
        ]
        self._skill_slot_pitch = int(round(slot_pitch))

        # Compose at native size first, then scale the whole UI block.
        # Align by alpha centroid so swapped target assets still snap correctly.
        target_mask = pygame.mask.from_surface(target_img)
        target_centroid = target_mask.centroid() if target_mask.count() > 0 else None
        target_anchor_y = target_centroid[1] if target_centroid is not None else (target_img.get_height() // 2)

        frame_center_y = frame_img.get_bounding_rect().centery
        self._skill_frame_native_top = max(0, int(round(target_anchor_y - frame_center_y)))
        self._skill_slot_center_y = self._skill_frame_native_top + frame_center_y
        return frame_img, target_img

    def _load_skill_ui_tune_config(self):
        """Apply optional per-slot UI tuning from assets/skills/ui_tune.json."""
        tune_path = os.path.join(os.path.dirname(__file__), 'assets', 'skills', 'ui_tune.json')
        if not os.path.isfile(tune_path):
            return

        try:
            with open(tune_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load UI tune config: {e}")
            return

        self._skill_ui_scale = max(1, int(cfg.get('ui_scale', self._skill_ui_scale)))
        self._skill_margin_x = max(0, int(cfg.get('margin_x', self._skill_margin_x)))
        self._skill_margin_y = max(0, int(cfg.get('margin_y', self._skill_margin_y)))
        self._skill_frame_native_top = max(0, int(cfg.get('frame_top', self._skill_frame_native_top)))

        slot_centers = cfg.get('slot_centers')
        if isinstance(slot_centers, list) and len(slot_centers) == 3:
            parsed = []
            ok = True
            for p in slot_centers:
                if not isinstance(p, list) or len(p) != 2:
                    ok = False
                    break
                parsed.append([int(p[0]), int(p[1])])
            if ok:
                self._skill_slot_centers = [p[0] for p in parsed]
                self._skill_slot_center_y = int(round(sum(p[1] for p in parsed) / 3.0))

        bars = cfg.get('bars', {})
        for key in ('p1', 'p2'):
            bar_in = bars.get(key, {}) if isinstance(bars, dict) else {}
            bar_dst = self._skill_bar_cfg.get(key, {}).copy()

            bar_dst['reverse'] = bool(bar_in.get('reverse', bar_dst['reverse']))

            def _read_xy_list(name, fallback):
                v = bar_in.get(name, fallback)
                if not isinstance(v, list) or len(v) != 3:
                    return fallback
                out = []
                for i in range(3):
                    item = v[i]
                    if not isinstance(item, list) or len(item) != 2:
                        out.append(fallback[i])
                    else:
                        out.append([int(item[0]), int(item[1])])
                return out

            def _read_scale_list(name, fallback):
                v = bar_in.get(name, fallback)
                if not isinstance(v, list) or len(v) != 3:
                    return fallback
                out = []
                for i in range(3):
                    try:
                        out.append(float(v[i]))
                    except Exception:
                        out.append(float(fallback[i]))
                return out

            bar_dst['icon_offsets'] = _read_xy_list('icon_offsets', bar_dst['icon_offsets'])
            bar_dst['icon_scales'] = _read_scale_list('icon_scales', bar_dst['icon_scales'])
            bar_dst['target_offsets'] = _read_xy_list('target_offsets', bar_dst['target_offsets'])
            bar_dst['target_scales'] = _read_scale_list('target_scales', bar_dst['target_scales'])

            self._skill_bar_cfg[key] = bar_dst

    def _get_skill_icon(self, skill_type, icon_size):
        key = (skill_type, icon_size)
        if key in self._skill_icon_cache:
            return self._skill_icon_cache[key]

        icon_path = SkillIcon.SKILL_TYPES.get(skill_type, SkillIcon.SKILL_TYPES.get('fire'))
        try:
            img = pygame.image.load(icon_path).convert_alpha()
            img = pygame.transform.scale(img, (icon_size, icon_size))
        except Exception:
            img = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
            img.fill((180, 120, 80, 200))
        self._skill_icon_cache[key] = img
        return img

    def cycle_skill_target(self, player, reverse=False):
        if getattr(player, 'hp', 0) <= 0:
            return
        if not getattr(player, 'skills', None):
            player.target_skill_idx = 0
            return
        count = min(3, len(player.skills))
        step = -1 if reverse else 1
        player.target_skill_idx = (getattr(player, 'target_skill_idx', 0) + step) % count

    def cycle_archer_arrow(self):
        """Cycle P2's Magic Arrow without affecting either player's skills."""
        archer = next((player for player in self.players if isinstance(player, Archer) and player.hp > 0), None)
        if archer is not None:
            archer.cycle_arrow_type()

    def _ensure_player_resources(self, player):
        if not hasattr(player, 'max_armor'):
            if isinstance(player, Knight):
                preset = PLAYER_RESOURCE_PRESETS.get('knight', {})
            else:
                preset = PLAYER_RESOURCE_PRESETS.get('archer', {})
            player.max_armor = int(preset.get('max_armor', 45))
            player.max_mana = int(preset.get('max_mana', 100))
            player.armor_reduction_pct = float(preset.get('armor_reduction_pct', DEFAULT_ARMOR_REDUCTION_PCT))
            player.armor = float(player.max_armor)
            player.mana = float(player.max_mana)

    def _ensure_player_abilities(self, player):
        """Create the per-player upgrade state lazily for compatibility."""
        if hasattr(player, 'ability_points'):
            return
        player.ability_points = 0
        player.ability_levels = {'attack': 0, 'armor': 0, 'speed': 0}
        player.ability_attack_bonus = 0
        # Store the unmodified movement speed; passive skills build on it.
        player.base_speed = getattr(player, 'speed', 0)

    def upgrade_player_ability(self, player, ability_name):
        """Spend one Poison Vial point on a player-selected stat."""
        self._ensure_player_resources(player)
        self._ensure_player_abilities(player)
        if ability_name not in player.ability_levels:
            return False
        if player.ability_points <= 0 or player.ability_levels[ability_name] >= ABILITY_MAX_LEVEL:
            return False

        player.ability_points -= 1
        player.ability_levels[ability_name] += 1
        if ability_name == 'attack':
            player.ability_attack_bonus += ABILITY_ATTACK_BONUS_PER_LEVEL
        elif ability_name == 'armor':
            player.max_armor += ABILITY_ARMOR_BONUS_PER_LEVEL
            player.armor = min(player.max_armor, player.armor + ABILITY_ARMOR_BONUS_PER_LEVEL)
        elif ability_name == 'speed':
            player.base_speed += ABILITY_SPEED_BONUS_PER_LEVEL
        return True

    def _skill_mana_cost(self, skill_name):
        return int(SKILL_MANA_COST.get(skill_name, 10))

    def _skill_combat_value(self, skill_name, key, default=None):
        skill_cfg = SKILL_COMBAT_CONFIG.get(skill_name, {})
        return skill_cfg.get(key, default)

    def _enemy_drop_tier(self, enemy):
        class_name = enemy.__class__.__name__ if enemy is not None else ''
        tier_map = SKILL_DROP_CONFIG.get('enemy_tiers', {})
        return tier_map.get(class_name, 'normal')

    def _roll_skill_drops_for_enemy(self, enemy):
        tier_name = self._enemy_drop_tier(enemy)
        tiers_cfg = SKILL_DROP_CONFIG.get('tiers', {})
        tier_cfg = tiers_cfg.get(tier_name, tiers_cfg.get('normal', {}))
        chance = float(tier_cfg.get('chance', 0.5))
        if random.random() >= chance:
            return []

        count_min = max(1, int(tier_cfg.get('count_min', 1)))
        count_max = max(count_min, int(tier_cfg.get('count_max', count_min)))
        drop_count = random.randint(count_min, count_max)

        weights_map = tier_cfg.get('weights', {})
        skills = []
        weights = []
        for skill_name, weight in weights_map.items():
            w = float(weight)
            if w <= 0:
                continue
            skills.append(skill_name)
            weights.append(w)

        if not skills:
            skills = ['fire']
            weights = [1.0]

        return random.choices(skills, weights=weights, k=drop_count)

    def _try_spend_player_mana(self, player, skill_name):
        self._ensure_player_resources(player)
        cost = self._skill_mana_cost(skill_name)
        if player.mana < cost:
            return False
        player.mana -= cost
        return True

    def _is_berserk_active(self, player, now=None):
        if now is None:
            now = pygame.time.get_ticks()
        return now < getattr(player, 'berserk_until', 0)

    def _consume_entity_armor(self, entity, incoming_damage):
        if entity is None:
            return max(0, int(round(float(incoming_damage))))

        dmg = max(0.0, float(incoming_damage))
        max_armor = float(getattr(entity, 'max_armor', 0.0))
        if dmg <= 0.0 or max_armor <= 0.0:
            return max(0, int(round(dmg)))

        if not hasattr(entity, 'armor'):
            entity.armor = max_armor

        reduction_pct = float(getattr(entity, 'armor_reduction_pct', DEFAULT_ARMOR_REDUCTION_PCT))
        reduction_pct = max(0.0, min(0.9, reduction_pct))

        intended_absorb = dmg * reduction_pct
        absorbed = min(float(getattr(entity, 'armor', 0.0)), intended_absorb)
        entity.armor = max(0.0, float(getattr(entity, 'armor', 0.0)) - absorbed)
        dmg -= absorbed
        return max(0, int(round(dmg)))

    def _consume_player_armor(self, player, incoming_damage):
        self._ensure_player_resources(player)
        if not self._is_berserk_active(player):
            return self._consume_entity_armor(player, incoming_damage)

        # Do not permanently change the player preset; only weaken armor while
        # Berserk is active, then restore the original value automatically.
        original_reduction = player.armor_reduction_pct
        player.armor_reduction_pct = original_reduction * BERSERK_ARMOR_EFFECTIVENESS_MULTIPLIER
        remaining_damage = self._consume_entity_armor(player, incoming_damage)
        player.armor_reduction_pct = original_reduction
        return remaining_damage

    def use_target_skill(self, player):
        if getattr(player, 'hp', 0) <= 0:
            return
        if not getattr(player, 'skills', None):
            return

        idx = max(0, min(getattr(player, 'target_skill_idx', 0), len(player.skills) - 1))
        chosen_skill = player.skills[idx]
        if not self._try_spend_player_mana(player, chosen_skill):
            return

        player.active_skill = chosen_skill
        if chosen_skill == 'holy':
            player.holy_effect_until = pygame.time.get_ticks() + HOLY_EFFECT_DURATION_MS
        if player.active_skill == 'fire':
            self._cast_fire_burst(player)
        elif player.active_skill == 'wind':
            self._spawn_wind_projectile(player)
        elif player.active_skill == 'water_ball':
            self._spawn_water_ball_projectile(player)
        elif player.active_skill == 'water_blast':
            self._spawn_water_blast_projectile(player)
        elif player.active_skill == 'earth':
            self._cast_earth_spike(player)
        elif player.active_skill == 'light':
            self._spawn_light_projectile(player)
        elif player.active_skill == 'dark':
            self._spawn_dark_projectile(player)
        elif player.active_skill == 'wood':
            self._spawn_wood_projectile(player)
        elif player.active_skill == 'acid':
            self._spawn_acid_projectile(player)
        else:
            # Activation VFX around the player.
            self._spawn_skill_vfx(player.active_skill, player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1))

    def _spawn_skill_vfx(self, skill_name, x, y, facing=1):
        vfx = SkillEffect(skill_name, x, y, facing=facing)
        self.effects.add(vfx)

    def _get_skill_direction(self, player):
        """Get a normalized direction from movement input; fallback to facing."""
        vx = float(getattr(getattr(player, 'vel', None), 'x', 0.0))
        vy = float(getattr(getattr(player, 'vel', None), 'y', 0.0))

        dir_x = 0.0
        dir_y = 0.0
        if abs(vx) > 0.05:
            dir_x = 1.0 if vx > 0 else -1.0
        if abs(vy) > 0.05:
            dir_y = 1.0 if vy > 0 else -1.0

        if dir_x == 0.0 and dir_y == 0.0:
            keys = pygame.key.get_pressed()
            controls = getattr(player, 'controls', {})

            for key in controls.get('left', []):
                if keys[key]:
                    dir_x -= 1.0
            for key in controls.get('right', []):
                if keys[key]:
                    dir_x += 1.0
            for key in controls.get('up', []):
                if keys[key]:
                    dir_y -= 1.0
            for key in controls.get('down', []):
                if keys[key]:
                    dir_y += 1.0

        if dir_x == 0.0 and dir_y == 0.0:
            dir_x = float(getattr(player, 'facing', 1))

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            return (1.0, 0.0)
        vec = vec.normalize()
        return (vec.x, vec.y)

    def _spawn_wind_projectile(self, player):
        dir_x, dir_y = self._get_skill_direction(player)
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        # Cast breath uses its own dedicated sheet, separate from projectile/hit.
        self._spawn_skill_vfx('wind_breath', player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1))

        px = player.hurtbox.centerx + int(vec.x * 28)
        py = player.hurtbox.centery + int(vec.y * 18)
        proj = WindStreamEffect(
            px,
            py,
            vec.x,
            vec.y,
            owner=player,
            damage=14,
            speed_px_per_ms=0.95,
            life_ms=560,
        )
        self.wind_projectiles.add(proj)

    def _spawn_water_ball_projectile(self, player):
        dir_x, dir_y = self._get_skill_direction(player)
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px = player.hurtbox.centerx + int(vec.x * 28)
        py = player.hurtbox.centery + int(vec.y * 16)
        proj = WaterBallProjectile(
            px,
            py,
            vec.x,
            vec.y,
            owner=player,
            damage=14,
            speed_px_per_ms=0.70,
            life_ms=760,
        )
        self.water_projectiles.add(proj)

    def _spawn_dark_projectile(self, player):
        dir_x, dir_y = self._get_skill_direction(player)
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px = player.hurtbox.centerx + int(vec.x * 28)
        py = player.hurtbox.centery + int(vec.y * 14)
        proj = DarkProjectile(
            px,
            py,
            vec.x,
            vec.y,
            owner=player,
            damage=15,
            speed_px_per_ms=0.86,
            life_ms=680,
        )
        self.dark_projectiles.add(proj)

    def _spawn_water_blast_projectile(self, player):
        dir_x, dir_y = self._get_skill_direction(player)
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px = player.hurtbox.centerx + int(vec.x * 28)
        py = player.hurtbox.centery + int(vec.y * 14)
        proj = WaterBlastProjectile(
            px,
            py,
            vec.x,
            vec.y,
            owner=player,
            damage=20,
            speed_px_per_ms=0.74,
            life_ms=820,
        )
        self.water_blast_projectiles.add(proj)

    def _spawn_light_projectile(self, player):
        dir_x, dir_y = self._get_skill_direction(player)
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px = player.hurtbox.centerx + int(vec.x * 26)
        py = player.hurtbox.centery + int(vec.y * 14)
        proj = LightProjectile(
            px,
            py,
            vec.x,
            vec.y,
            owner=player,
            damage=17,
            speed_px_per_ms=0.86,
            life_ms=720,
        )
        self.light_projectiles.add(proj)

    def _spawn_wood_projectile(self, player):
        dir_x, dir_y = self._get_skill_direction(player)
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px = player.hurtbox.centerx + int(vec.x * 26)
        py = player.hurtbox.centery + int(vec.y * 14)
        proj = WoodProjectile(
            px,
            py,
            vec.x,
            vec.y,
            owner=player,
            damage=12,
            speed_px_per_ms=0.72,
            life_ms=760,
        )
        self.wood_projectiles.add(proj)

    def _spawn_acid_projectile(self, player):
        # Keep one acid lane at a time.
        for p in list(self.acid_projectiles):
            p.kill()

        dir_x, dir_y = self._get_skill_direction(player)
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px = player.hurtbox.centerx + int(vec.x * 26)
        py = player.hurtbox.centery + int(vec.y * 14)
        proj = AcidProjectile(
            px,
            py,
            vec.x,
            vec.y,
            owner=player,
            damage=12,
            speed_px_per_ms=0.68,
            life_ms=820,
        )
        self.acid_projectiles.add(proj)

    def _cast_fire_burst(self, player):
        """Fire cast immediately bursts a nearby enemy and applies burn."""
        if player is None or getattr(player, 'hp', 0) <= 0:
            return

        range_x = float(self._skill_combat_value('fire', 'cast_enemy_x_range', 210))
        range_y = float(self._skill_combat_value('fire', 'cast_enemy_y_range', 85))
        px = player.hurtbox.centerx

        candidates = [
            enemy for enemy in self.enemies
            if enemy.hp > 0
            and abs(enemy.hurtbox.centerx - px) <= range_x
            and math.fabs(enemy.foot_y - player.foot_y) <= range_y
        ]

        if not candidates:
            self._spawn_skill_vfx('fire', player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1))
            return

        candidates.sort(key=lambda enemy: (abs(enemy.hurtbox.centerx - px), abs(enemy.foot_y - player.foot_y)))
        target = candidates[0]

        base_damage = self._passive_attack_damage(player, self._skill_combat_value('fire', 'cast_damage', 16))
        final_damage = self._consume_entity_armor(target, base_damage)
        if final_damage <= 0:
            self._spawn_skill_vfx('fire', target.hurtbox.centerx, target.hurtbox.centery, getattr(player, 'facing', 1))
            return

        old_hp = target.hp
        target.take_damage(final_damage, source_x=player.hurtbox.centerx, is_crit=False)
        if target.hp < old_hp:
            self.damage_numbers.add(
                DamageNumber(target.hurtbox.centerx, target.hurtbox.top, final_damage, is_crit=False)
            )
            self._on_player_hit_enemy_passive(player, target, final_damage)

    def _cast_earth_spike(self, player):
        """Earth cast erupts upward from the target's foot position."""
        if player is None or getattr(player, 'hp', 0) <= 0:
            return

        candidates = [
            enemy for enemy in self.enemies
            if enemy.hp > 0 and math.fabs(enemy.foot_y - player.foot_y) <= 90
        ]

        if candidates:
            px = player.hurtbox.centerx
            candidates.sort(key=lambda enemy: (abs(enemy.hurtbox.centerx - px), abs(enemy.foot_y - player.foot_y)))
            target = candidates[0]
            base_damage = self._passive_attack_damage(player, self._skill_combat_value('earth', 'cast_damage', 18))
            base_damage = self._consume_entity_armor(target, base_damage)
            old_hp = target.hp
            if base_damage > 0:
                target.take_damage(base_damage, source_x=player.hurtbox.centerx, is_crit=False)
            self._spawn_skill_vfx('earth', target.hurtbox.centerx, target.foot_y, getattr(player, 'facing', 1))
            if target.hp < old_hp:
                self.damage_numbers.add(
                    DamageNumber(target.hurtbox.centerx, target.hurtbox.top, base_damage, is_crit=False)
                )
            return

        self._spawn_skill_vfx('earth', player.hurtbox.centerx, player.foot_y, getattr(player, 'facing', 1))

    def _apply_bonus_damage(self, enemy, amount, source_x, skill_name):
        """Apply extra passive damage cleanly with number + vfx."""
        if enemy is None or enemy.hp <= 0 or amount <= 0:
            return
        amount = self._consume_entity_armor(enemy, int(amount))
        if amount <= 0:
            return
        old_hp = enemy.hp
        enemy.take_damage(int(amount), source_x=source_x, is_crit=False)
        if enemy.hp < old_hp:
            self.damage_numbers.add(
                DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, int(amount), is_crit=False)
            )
            self._spawn_skill_vfx(skill_name, enemy.hurtbox.centerx, enemy.hurtbox.centery)

    def _is_enemy_zombie(self, enemy, now=None):
        if enemy is None:
            return False
        if now is None:
            now = pygame.time.get_ticks()
        return now < getattr(enemy, 'zombie_until', 0)

    def _enemy_can_hit_enemy(self, attacker, target):
        if attacker is None or target is None or attacker is target:
            return False
        if getattr(attacker, 'hp', 0) <= 0 or getattr(target, 'hp', 0) <= 0:
            return False
        return self._is_enemy_zombie(attacker) != self._is_enemy_zombie(target)

    def _enemy_ai_target(self, enemy, living_players):
        enemy_targets = [
            other for other in self.enemies
            if self._enemy_can_hit_enemy(enemy, other)
        ]
        if enemy_targets:
            return min(
                enemy_targets,
                key=lambda other: (abs(other.hurtbox.centerx - enemy.hurtbox.centerx), abs(other.foot_y - enemy.foot_y))
            )

        if self._is_enemy_zombie(enemy) or not living_players:
            return None

        return min(
            living_players,
            key=lambda player: abs(player.rect.centerx - enemy.rect.centerx)
        )

    def _update_zombie_enemy(self, enemy, dt):
        """Converted enemies attack nearby non-zombie enemies instead of players."""
        if enemy is None or enemy.hp <= 0:
            return

        preferred_targets = [
            other for other in self.enemies
            if other is not enemy and other.hp > 0 and not self._is_enemy_zombie(other)
        ]
        targets = preferred_targets or [
            other for other in self.enemies
            if other is not enemy and other.hp > 0
        ]
        if not targets:
            return

        target = min(
            targets,
            key=lambda other: (abs(other.hurtbox.centerx - enemy.hurtbox.centerx), abs(other.foot_y - enemy.foot_y))
        )

        if not hasattr(enemy, 'base_speed'):
            enemy.base_speed = getattr(enemy, 'speed', 1.0)
        move_mult = float(self._skill_combat_value('dark', 'zombie_move_multiplier', 0.90))
        zombie_speed = max(0.2, float(enemy.base_speed) * move_mult)
        dx = target.hurtbox.centerx - enemy.hurtbox.centerx
        dir_x = 1 if dx >= 0 else -1
        enemy.facing = dir_x

        x_range = float(self._skill_combat_value('dark', 'zombie_attack_x_range', 66))
        y_range = float(self._skill_combat_value('dark', 'zombie_attack_y_range', 60))
        in_range = abs(dx) <= x_range and math.fabs(target.foot_y - enemy.foot_y) <= y_range
        if not in_range:
            step = dir_x * zombie_speed * dt
            enemy.rect.x += int(round(step))
            if hasattr(enemy, 'hurtbox'):
                enemy.hurtbox.x += int(round(step))
            return

        now = pygame.time.get_ticks()
        next_hit = getattr(enemy, 'zombie_next_hit', 0)
        if now < next_hit:
            return

        attack_damage = int(self._skill_combat_value('dark', 'zombie_attack_damage', 9))
        attack_interval = int(self._skill_combat_value('dark', 'zombie_attack_interval_ms', 850))
        actual_damage = self._consume_entity_armor(target, attack_damage)
        if actual_damage <= 0:
            enemy.zombie_next_hit = now + attack_interval
            return

        old_hp = target.hp
        target.take_damage(actual_damage, source_x=enemy.hurtbox.centerx, is_crit=False)
        if target.hp < old_hp:
            self.damage_numbers.add(
                DamageNumber(target.hurtbox.centerx, target.hurtbox.top, actual_damage, is_crit=False)
            )
            self._spawn_skill_vfx('dark', target.hurtbox.centerx, target.hurtbox.centery, enemy.facing)
        enemy.zombie_next_hit = now + attack_interval

    def _apply_enemy_status_effects(self, enemy):
        """Handle temporary speed modifiers from passive skills."""
        if not hasattr(enemy, 'base_speed'):
            enemy.base_speed = getattr(enemy, 'speed', 1.0)

        now = pygame.time.get_ticks()
        slow_until = getattr(enemy, 'slow_until', 0)
        slow_mult = getattr(enemy, 'slow_mult', 1.0)
        if now < slow_until:
            enemy.speed = max(0.2, enemy.base_speed * slow_mult)
        else:
            enemy.speed = enemy.base_speed

    def _try_wood_reflect(self, player, attacker, incoming_damage):
        """Wood passive reflects part of taken damage back to attacker."""
        if attacker is None or not hasattr(attacker, 'hp') or attacker.hp <= 0:
            return
        reflect_damage = max(1, int(incoming_damage * 0.35))
        reflect_damage = self._consume_entity_armor(attacker, reflect_damage)
        if reflect_damage <= 0:
            return
        old_hp = attacker.hp
        attacker.take_damage(reflect_damage, source_x=player.rect.centerx, is_crit=False)
        if attacker.hp < old_hp:
            self.damage_numbers.add(
                DamageNumber(attacker.hurtbox.centerx, attacker.hurtbox.top, reflect_damage, is_crit=False)
            )
            self._spawn_skill_vfx('wood', attacker.hurtbox.centerx, attacker.hurtbox.centery, getattr(player, 'facing', 1))

    def _active_passive(self, player):
        skill = getattr(player, 'active_skill', None)
        if skill is None:
            return None
        if skill == 'holy' and pygame.time.get_ticks() >= getattr(player, 'holy_effect_until', 0):
            player.active_skill = None
            return None
        if skill not in getattr(player, 'skills', []):
            player.active_skill = None
            return None
        return skill

    def _update_player_passives(self, dt):
        for player in self.players:
            if not hasattr(player, 'base_speed'):
                player.base_speed = player.speed
            if not hasattr(player, '_passive_regen_timer'):
                player._passive_regen_timer = 0
            if not hasattr(player, '_passive_aura_timer'):
                player._passive_aura_timer = 0

            skill = self._active_passive(player)
            player.speed = player.base_speed + (1.2 if skill == 'wind' else 0)
            player._passive_aura_timer += dt

            if skill in ('holy', 'wood') and player._passive_aura_timer >= 700:
                player._passive_aura_timer = 0
                self._spawn_skill_vfx(skill, player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1))
            elif skill not in ('holy', 'wood'):
                player._passive_aura_timer = 0

            if skill == 'holy' and player.hp > 0:
                player._passive_regen_timer += dt
                while player._passive_regen_timer >= 1000:
                    player._passive_regen_timer -= 1000
                    player.hp = min(player.max_hp, player.hp + 2)
            elif skill == 'wood' and player.hp > 0:
                player._passive_regen_timer += dt
                while player._passive_regen_timer >= 1400:
                    player._passive_regen_timer -= 1400
                    player.hp = min(player.max_hp, player.hp + 1)
            else:
                player._passive_regen_timer = 0

    def _is_dark_eligible_enemy(self, enemy):
        """Return whether Dark may affect this small/normal enemy.

        Dark's control and damage bonus are deliberately limited to the
        ``normal`` enemy tier.  This keeps elite enemies, minibosses and bosses
        from being trivialised by the zombie effect.
        """
        return enemy is not None and self._enemy_drop_tier(enemy) == 'normal'

    def _passive_attack_damage(self, player, base_damage, enemy=None):
        if player is None:
            return max(1, int(base_damage))
        self._ensure_player_abilities(player)
        base_damage = float(base_damage) + player.ability_attack_bonus
        skill = self._active_passive(player)
        if skill == 'dark' and enemy is not None and not self._is_dark_eligible_enemy(enemy):
            return max(1, int(round(base_damage)))
        mult = float(self._skill_combat_value(skill, 'attack_multiplier', 1.0)) if skill else 1.0
        if self._is_berserk_active(player):
            mult *= BERSERK_DAMAGE_MULTIPLIER
        return max(1, int(round(base_damage * mult)))

    def _passive_defense_damage(self, player, incoming_damage):
        skill = self._active_passive(player)
        dmg = float(incoming_damage)
        if skill:
            defense_mult = self._skill_combat_value(skill, 'defense_multiplier', None)
            if defense_mult is not None:
                dmg *= float(defense_mult)
            flat_reduce = self._skill_combat_value(skill, 'defense_flat_reduce', None)
            if flat_reduce is not None:
                dmg = max(1.0, dmg - float(flat_reduce))
        return max(1, int(round(dmg)))

    def _on_player_hit_enemy_passive(self, player, enemy, dealt_damage):
        if player is None or enemy.hp <= 0:
            return
        skill = self._active_passive(player)
        if skill is None:
            return
        if skill == 'dark' and not self._is_dark_eligible_enemy(enemy):
            return

        self._spawn_skill_vfx(skill, enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(player, 'facing', 1))

        if skill == 'fire':
            now = pygame.time.get_ticks()
            fire_duration = int(self._skill_combat_value('fire', 'fire_dot_duration_ms', 2200))
            fire_tick = int(self._skill_combat_value('fire', 'fire_dot_tick_ms', 450))
            fire_damage = int(self._skill_combat_value('fire', 'fire_dot_damage', 3))
            enemy.fire_dot_until = max(getattr(enemy, 'fire_dot_until', 0), now + fire_duration)
            enemy.fire_dot_next_tick = min(getattr(enemy, 'fire_dot_next_tick', now + fire_tick), now + fire_tick)
            enemy.fire_dot_source_x = player.rect.centerx
            if random.random() < float(self._skill_combat_value('fire', 'splash_proc_chance', 0.20)):
                splash_damage = max(2, int(dealt_damage * float(self._skill_combat_value('fire', 'splash_damage_pct', 0.30))))
                for other in self.enemies:
                    if other is enemy or other.hp <= 0:
                        continue
                    if math.fabs(other.foot_y - enemy.foot_y) > float(self._skill_combat_value('fire', 'splash_enemy_y_range', 60)):
                        continue
                    if abs(other.hurtbox.centerx - enemy.hurtbox.centerx) > float(self._skill_combat_value('fire', 'splash_enemy_x_range', 95)):
                        continue
                    self._apply_bonus_damage(other, splash_damage, player.rect.centerx, 'fire')

        if skill == 'dark':
            lifesteal = max(1, int(dealt_damage * float(self._skill_combat_value('dark', 'lifesteal_pct', 0.18))))
            player.hp = min(player.max_hp, player.hp + lifesteal)
            now = pygame.time.get_ticks()
            if random.random() < float(self._skill_combat_value('dark', 'zombie_proc_chance', 1.0)):
                zombie_duration = int(self._skill_combat_value('dark', 'zombie_duration_ms', 5000))
                enemy.zombie_until = max(getattr(enemy, 'zombie_until', 0), now + zombie_duration)
                enemy.zombie_next_hit = min(getattr(enemy, 'zombie_next_hit', now), now + 260)
            if random.random() < float(self._skill_combat_value('dark', 'bonus_proc_chance', 0.22)):
                self._apply_bonus_damage(enemy, max(2, int(dealt_damage * float(self._skill_combat_value('dark', 'bonus_damage_pct', 0.32)))), player.rect.centerx, 'dark')
        elif skill == 'holy':
            player.hp = min(player.max_hp, player.hp + int(self._skill_combat_value('holy', 'heal_on_hit', 1)))
        elif skill == 'wind':
            if random.random() < float(self._skill_combat_value('wind', 'bonus_proc_chance', 0.30)):
                self._apply_bonus_damage(enemy, max(2, int(dealt_damage * float(self._skill_combat_value('wind', 'bonus_damage_pct', 0.25)))), player.rect.centerx, 'wind')
            now = pygame.time.get_ticks()
            bleed_duration = int(self._skill_combat_value('wind', 'bleed_duration_ms', 2200))
            bleed_tick = int(self._skill_combat_value('wind', 'bleed_tick_ms', 450))
            enemy.wind_bleed_until = max(getattr(enemy, 'wind_bleed_until', 0), now + bleed_duration)
            enemy.wind_bleed_next_tick = min(getattr(enemy, 'wind_bleed_next_tick', now + bleed_tick), now + bleed_tick)
            enemy.wind_bleed_source_x = player.rect.centerx
        elif skill == 'acid':
            now = pygame.time.get_ticks()
            acid_duration = int(self._skill_combat_value('acid', 'acid_dot_duration_ms', 4500))
            acid_tick = int(self._skill_combat_value('acid', 'acid_dot_tick_ms', 600))
            enemy.acid_dot_until = max(getattr(enemy, 'acid_dot_until', 0), now + acid_duration)
            enemy.acid_dot_next_tick = min(getattr(enemy, 'acid_dot_next_tick', now + acid_tick), now + acid_tick)
            enemy.acid_dot_source_x = player.rect.centerx
        elif skill == 'water_ball':
            enemy.slow_until = max(getattr(enemy, 'slow_until', 0), pygame.time.get_ticks() + int(self._skill_combat_value('water_ball', 'slow_duration_ms', 1300)))
            enemy.slow_mult = min(getattr(enemy, 'slow_mult', 0.75), float(self._skill_combat_value('water_ball', 'slow_mult', 0.72)))
            splash_damage = max(1, int(dealt_damage * float(self._skill_combat_value('water_ball', 'splash_damage_pct', 0.35))))
            for other in self.enemies:
                if other is enemy or other.hp <= 0:
                    continue
                if math.fabs(other.foot_y - enemy.foot_y) > float(self._skill_combat_value('water_ball', 'splash_enemy_y_range', 70)):
                    continue
                if abs(other.hurtbox.centerx - enemy.hurtbox.centerx) > float(self._skill_combat_value('water_ball', 'splash_enemy_x_range', 110)):
                    continue
                old_hp = other.hp
                splash_amount = self._consume_entity_armor(other, splash_damage)
                if splash_amount <= 0:
                    continue
                other.take_damage(splash_amount, source_x=player.rect.centerx, is_crit=False)
                if other.hp < old_hp:
                    self.damage_numbers.add(
                        DamageNumber(other.hurtbox.centerx, other.hurtbox.top, splash_amount, is_crit=False)
                    )
                    self._spawn_skill_vfx('water_ball', other.hurtbox.centerx, other.hurtbox.centery, getattr(player, 'facing', 1))

    def _update_enemy_dot_effects(self):
        now = pygame.time.get_ticks()
        for enemy in self.enemies:
            if enemy.hp <= 0:
                continue

            burn_until = getattr(enemy, 'magic_arrow_burn_until', 0)
            if burn_until > now:
                burn_next = getattr(enemy, 'magic_arrow_burn_next_tick', now + 450)
                burn_damage = int(getattr(enemy, 'magic_arrow_burn_damage', 2))
                burn_source_x = getattr(enemy, 'magic_arrow_burn_source_x', enemy.hurtbox.centerx)
                while now >= burn_next and burn_next < burn_until and enemy.hp > 0:
                    dealt_damage = self._consume_entity_armor(enemy, burn_damage)
                    if dealt_damage > 0:
                        old_hp = enemy.hp
                        enemy.take_damage(dealt_damage, source_x=burn_source_x, is_crit=False)
                        if enemy.hp < old_hp:
                            self.damage_numbers.add(
                                DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, dealt_damage, is_crit=False)
                            )
                            self._spawn_skill_vfx('fire', enemy.hurtbox.centerx, enemy.hurtbox.centery)
                    burn_next += int(getattr(enemy, 'magic_arrow_burn_tick_ms', 450))
                enemy.magic_arrow_burn_next_tick = burn_next

            fire_until = getattr(enemy, 'fire_dot_until', 0)
            if fire_until > now:
                fire_next = getattr(enemy, 'fire_dot_next_tick', now + int(self._skill_combat_value('fire', 'fire_dot_tick_ms', 450)))
                fire_src = getattr(enemy, 'fire_dot_source_x', enemy.hurtbox.centerx)
                while now >= fire_next and fire_next < fire_until and enemy.hp > 0:
                    dot_damage = self._consume_entity_armor(enemy, int(self._skill_combat_value('fire', 'fire_dot_damage', 3)))
                    if dot_damage <= 0:
                        fire_next += int(self._skill_combat_value('fire', 'fire_dot_tick_ms', 450))
                        continue
                    old_hp = enemy.hp
                    enemy.take_damage(dot_damage, source_x=fire_src, is_crit=False)
                    if enemy.hp < old_hp:
                        self.damage_numbers.add(
                            DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, dot_damage, is_crit=False)
                        )
                        self._spawn_skill_vfx('fire', enemy.hurtbox.centerx, enemy.hurtbox.centery)
                    fire_next += int(self._skill_combat_value('fire', 'fire_dot_tick_ms', 450))
                enemy.fire_dot_next_tick = fire_next

            bleed_until = getattr(enemy, 'wind_bleed_until', 0)
            if bleed_until > now:
                bleed_next = getattr(enemy, 'wind_bleed_next_tick', now + int(self._skill_combat_value('wind', 'bleed_tick_ms', 450)))
                bleed_src = getattr(enemy, 'wind_bleed_source_x', enemy.hurtbox.centerx)
                while now >= bleed_next and bleed_next < bleed_until and enemy.hp > 0:
                    dot_damage = self._consume_entity_armor(enemy, int(self._skill_combat_value('wind', 'bleed_damage', 3)))
                    if dot_damage <= 0:
                        bleed_next += int(self._skill_combat_value('wind', 'bleed_tick_ms', 450))
                        continue
                    old_hp = enemy.hp
                    enemy.take_damage(dot_damage, source_x=bleed_src, is_crit=False)
                    if enemy.hp < old_hp:
                        self.damage_numbers.add(
                            DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, dot_damage, is_crit=False)
                        )
                        self._spawn_skill_vfx('wind', enemy.hurtbox.centerx, enemy.hurtbox.centery)
                    bleed_next += int(self._skill_combat_value('wind', 'bleed_tick_ms', 450))
                enemy.wind_bleed_next_tick = bleed_next

            dot_until = getattr(enemy, 'acid_dot_until', 0)
            if dot_until <= now:
                continue
            next_tick = getattr(enemy, 'acid_dot_next_tick', now + 600)
            source_x = getattr(enemy, 'acid_dot_source_x', enemy.hurtbox.centerx)

            while now >= next_tick and next_tick < dot_until and enemy.hp > 0:
                dot_damage = self._consume_entity_armor(enemy, int(self._skill_combat_value('acid', 'acid_dot_damage', 4)))
                if dot_damage <= 0:
                    next_tick += int(self._skill_combat_value('acid', 'acid_dot_tick_ms', 600))
                    continue
                old_hp = enemy.hp
                enemy.take_damage(dot_damage, source_x=source_x, is_crit=False)
                if enemy.hp < old_hp:
                    self.damage_numbers.add(
                        DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, dot_damage, is_crit=False)
                    )
                next_tick += int(self._skill_combat_value('acid', 'acid_dot_tick_ms', 600))
            enemy.acid_dot_next_tick = next_tick

    def load(self):
        # sprite groups
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.potions = pygame.sprite.Group()
        self.ability_vials = pygame.sprite.Group()
        self.berserk_vials = pygame.sprite.Group()
        self.skills = pygame.sprite.Group()          # NEW: SkillIcon drops
        self.attacks = pygame.sprite.Group()
        self.arrows = pygame.sprite.Group()
        self.water_projectiles = pygame.sprite.Group()
        self.water_blast_projectiles = pygame.sprite.Group()
        self.wind_projectiles = pygame.sprite.Group()
        self.light_projectiles = pygame.sprite.Group()
        self.dark_projectiles = pygame.sprite.Group()
        self.wood_projectiles = pygame.sprite.Group()
        self.acid_projectiles = pygame.sprite.Group()
        self.enemy_projectiles = pygame.sprite.Group()
        self.enemy_attacks = pygame.sprite.Group()
        self.damage_numbers = pygame.sprite.Group()
        self.effects = pygame.sprite.Group()       # DashSmoke, UltimateEffect visuals
        self.ultimate_beams = pygame.sprite.Group() # UltimateEffect collision set
        self.knight_shockwaves = pygame.sprite.Group()  # KnightUltimateShockwave collision set

        self.groups = {
            'all': self.all_sprites,
            'enemies': self.enemies,
            'potions': self.potions,
            'ability_vials': self.ability_vials,
            'berserk_vials': self.berserk_vials,
            'skills': self.skills,                 # NEW
            'attacks': self.attacks,
            'arrows': self.arrows,
            'water_projectiles': self.water_projectiles,
            'water_blast_projectiles': self.water_blast_projectiles,
            'wind_projectiles': self.wind_projectiles,
            'light_projectiles': self.light_projectiles,
            'dark_projectiles': self.dark_projectiles,
            'wood_projectiles': self.wood_projectiles,
            'acid_projectiles': self.acid_projectiles,
            'enemy_projectiles': self.enemy_projectiles,
            'enemy_attacks': self.enemy_attacks,
            'damage_numbers': self.damage_numbers,
            'effects': self.effects,
            'ultimate_beams': self.ultimate_beams,
            'knight_shockwaves': self.knight_shockwaves,
        }

        # Dynamically load map depending on phase
        map_files = {
            1: "assets/maps/map1.jpeg",
            2: "assets/maps/map2.jpg",  # Might also be map2.png, but testing confirmed map2.jpg exists
            3: "assets/maps/map3.jpg",  # Might also be map3.png, but testing confirmed map3.jpg exists
        }
        self.pixel_ruins_map = None
        try:
            if self.selected_phase == 4:
                self.pixel_ruins_map = PixelRuinsMap(WIDTH, HEIGHT)
                self.map = self.pixel_ruins_map.surface
                self.world_width, self.world_height = self.map.get_size()
                self.world_zoom = PIXEL_RUINS_CAMERA_ZOOM
                self.current_floor = None
                self.world_render_map = pygame.transform.scale(
                    self.map,
                    (round(self.world_width * self.world_zoom), round(self.world_height * self.world_zoom)),
                )
                entities_module.MIN_X = 0
                entities_module.MAX_X = self.world_width
                entities_module.MIN_Y = 0
                entities_module.MAX_Y = self.world_height
            else:
                self.pixel_ruins_map = None
                loaded_map = pygame.image.load(map_files.get(self.selected_phase, MAP_IMAGE)).convert()
                self.map = loaded_map
                self.world_width, self.world_height = WIDTH, HEIGHT
                self.world_zoom = 1.0
                self.world_render_map = None
                entities_module.MIN_X = config_module.MIN_X
                entities_module.MAX_X = config_module.MAX_X
                entities_module.MIN_Y = config_module.MIN_Y
                entities_module.MAX_Y = config_module.MAX_Y
        except Exception as e:
            print(f"Failed to load map for phase {self.selected_phase}: {e}")
            self.map = pygame.Surface((WIDTH, HEIGHT))
            self.map.fill((50, 150, 50))

        # Two-player co-op setup
        if self.selected_phase == 4:
            spawn_y = self.world_height // 2 + 100
            self.players = [
                Knight(pos=(self.world_width // 2 - 90, spawn_y)),
                Archer(pos=(self.world_width // 2 + 90, spawn_y)),
            ]
        else:
            self.players = [
                Knight(pos=(WIDTH//3, HEIGHT-100)),
                Archer(pos=(2*WIDTH//3, HEIGHT-100)),
            ]
        self.player = self.players[0]
        for player in self.players:
            self._ensure_player_resources(player)
            self._ensure_player_abilities(player)
            player.map_floor = 1
            player.map_floor_zoom = PIXEL_RUINS_CAMERA_ZOOM
        for player in self.players:
            self.all_sprites.add(player)

        self.map_collision_rects = list(getattr(self.pixel_ruins_map, 'wall_rects', []))
        self.world_camera = pygame.math.Vector2(0, 0)
        self._update_world_camera()

        # spawn timer
        self.spawn_event = pygame.USEREVENT + 1
        pygame.time.set_timer(self.spawn_event, 3500)

        # Boss spawn tracking
        self.phase_start_time = pygame.time.get_ticks()
        self.boss_spawned = False
        self.miniboss_spawned = False
        self.miniboss_defeated = False

        # Reset camera shake
        self.camera_offset = [0, 0]
        self.shake_timer = 0
        self.shake_intensity = 0
        self.paused = False
        # Phase 4 is currently being authored in the map tuner, so keep its
        # collision view visible by default. F3 can hide it during play.
        self.DEBUG_DRAW = self.selected_phase == 4

    def _resolve_map_collision(self, entity, previous_rect, previous_hurtbox):
        """Keep an entity out of walls while allowing natural wall sliding."""
        if not hasattr(entity, 'hurtbox'):
            return
        walls = self.map_collision_rects + self._entity_tunnel_side_walls(entity)
        if not walls:
            return
        # A newly tuned layout can be reloaded while an entity is already
        # inside a marker collider. Do not trap it forever: let it move until
        # it exits, then apply normal blocking again on later wall entries.
        if any(previous_hurtbox.colliderect(wall) for wall in walls):
            return
        if not any(entity.hurtbox.colliderect(wall) for wall in walls):
            return

        current_rect = entity.rect.copy()
        current_hurtbox = entity.hurtbox.copy()

        # First cancel horizontal movement only. If this clears the collision,
        # vertical movement remains, so the entity slides along the wall.
        entity.rect.x = previous_rect.x
        entity.hurtbox.x = previous_hurtbox.x
        if not any(entity.hurtbox.colliderect(wall) for wall in walls):
            return

        # Otherwise restore X and cancel vertical movement only.
        entity.rect = current_rect
        entity.hurtbox = current_hurtbox
        entity.rect.y = previous_rect.y
        entity.hurtbox.y = previous_hurtbox.y
        if not any(entity.hurtbox.colliderect(wall) for wall in walls):
            return

        # Movement entered a closed corner: restore the prior safe position.
        entity.rect = previous_rect
        entity.hurtbox = previous_hurtbox

    def _fit_phase4_hurtbox(self, entity):
        """Use a compact foot-level collision box in the top-down map."""
        if self.selected_phase != 4 or not hasattr(entity, 'hurtbox'):
            return
        if not hasattr(entity, '_phase4_base_hurtbox_size'):
            entity._phase4_base_hurtbox_size = entity.hurtbox.size
        base_width, base_height = entity._phase4_base_hurtbox_size
        # The map needs a footprint, not a full body combat box. It is scaled
        # for the reduced Phase 4 sprite and anchored at the feet.
        scale = PIXEL_RUINS_ENTITY_SCALE / max(0.01, self.world_zoom)
        desired_size = (
            max(12, round(base_width * scale * PIXEL_RUINS_FOOTBOX_WIDTH_RATIO)),
            max(10, round(base_height * scale * PIXEL_RUINS_FOOTBOX_HEIGHT_RATIO)),
        )
        if entity.hurtbox.size != desired_size:
            feet = entity.hurtbox.midbottom
            entity.hurtbox.size = desired_size
            entity.hurtbox.midbottom = feet

    def _entity_is_in_tunnel(self, entity):
        """True only after the entity entered through a tunnel end line."""
        if self.selected_phase != 4 or not self.pixel_ruins_map or not hasattr(entity, 'hurtbox'):
            return False
        index = getattr(entity, '_phase4_tunnel_index', None)
        return isinstance(index, int) and 0 <= index < len(self.pixel_ruins_map.tunnel_zones) and self.pixel_ruins_map.tunnel_zones[index]['rect'].collidepoint(entity.hurtbox.center)

    def _entity_tunnel_side_walls(self, entity):
        if self.selected_phase != 4 or not self.pixel_ruins_map:
            return []
        index = getattr(entity, '_phase4_tunnel_index', None)
        if not isinstance(index, int):
            return []
        return self.pixel_ruins_map.tunnel_side_collision_rects(index)

    def _update_tunnel_traversal(self, entity, previous_hurtbox):
        """Toggle underpass state only when crossing a tunnel A/B line."""
        if self.selected_phase != 4 or not self.pixel_ruins_map or not hasattr(entity, 'hurtbox'):
            return
        index = self.pixel_ruins_map.tunnel_end_line_crossed(previous_hurtbox.center, entity.hurtbox.center)
        if index is not None:
            entity._phase4_tunnel_index = None if getattr(entity, '_phase4_tunnel_index', None) == index else index

    def _update_entity_region_floor(self, entity):
        """Record authored floor/tunnel membership for future map mechanics."""
        if self.selected_phase != 4 or not self.pixel_ruins_map or not hasattr(entity, 'hurtbox'):
            return
        floor = self.pixel_ruins_map.floor_at(entity.hurtbox.center)
        entity.map_region_floor = int(floor.get('floor', 0)) if floor else None
        tunnel_index = getattr(entity, '_phase4_tunnel_index', None)
        if isinstance(tunnel_index, int) and 0 <= tunnel_index < len(self.pixel_ruins_map.tunnel_zones):
            entity.map_region_floor = self.pixel_ruins_map.tunnel_zones[tunnel_index]['floor']

    def _update_player_stair_floor(self, player, previous_hurtbox):
        """Switch floor when a player crosses either end line of a stair box."""
        if self.selected_phase != 4 or not self.pixel_ruins_map:
            return
        reached = self.pixel_ruins_map.stair_end_line_crossed(
            previous_hurtbox.center, player.hurtbox.center,
        )
        if reached is not None:
            player.map_floor = reached['floor']
            player.map_floor_zoom = reached['zoom']

    def reload_pixel_ruins_layout(self):
        """Reload tuner-authored Phase 4 collider/floor/tunnel data in place."""
        if self.selected_phase != 4:
            return
        self.pixel_ruins_map = PixelRuinsMap(WIDTH, HEIGHT)
        self.map = self.pixel_ruins_map.surface
        self.world_width, self.world_height = self.map.get_size()
        self.map_collision_rects = list(self.pixel_ruins_map.wall_rects)
        self.world_render_map = pygame.transform.scale(
            self.map,
            (round(self.world_width * self.world_zoom), round(self.world_height * self.world_zoom)),
        )
        self._update_world_camera()

    def _update_world_camera(self):
        """Follow the players over the full Pixel Ruins world map."""
        if self.selected_phase != 4 or not hasattr(self, 'world_camera'):
            return
        living = [player for player in self.players if player.hp > 0]
        targets = living or list(self.players)
        if not targets:
            return
        target_x = sum(player.hurtbox.centerx for player in targets) / len(targets)
        target_y = sum(player.hurtbox.centery for player in targets) / len(targets)

        # Stair endpoints determine floors. The lead living player controls
        # the shared co-op camera so its floor number/zoom is unambiguous.
        camera_player = next((player for player in self.players if player.hp > 0), targets[0])
        active_floor = getattr(camera_player, 'map_floor', 1)
        requested_zoom = float(getattr(camera_player, 'map_floor_zoom', PIXEL_RUINS_CAMERA_ZOOM))
        requested_zoom = max(0.70, min(2.40, requested_zoom))
        if abs(requested_zoom - self.world_zoom) > 0.001:
            self.world_zoom = requested_zoom
            self.world_render_map = pygame.transform.scale(
                self.map,
                (round(self.world_width * self.world_zoom), round(self.world_height * self.world_zoom)),
            )
        self.current_floor = active_floor
        view_width = WIDTH / self.world_zoom
        view_height = HEIGHT / self.world_zoom
        max_x = max(0, self.world_width - view_width)
        max_y = max(0, self.world_height - view_height)
        self.world_camera.x = max(0, min(max_x, target_x - view_width / 2))
        self.world_camera.y = max(0, min(max_y, target_y - view_height / 2))

    def spawn_enemy(self):
        side = random.choice(['left', 'right'])
        if self.selected_phase == 4:
            y = random.randint(80, self.world_height - 80)
            x = 40 if side == 'left' else self.world_width - 40
        else:
            y = random.randint(MIN_Y + 50, MAX_Y - 30)
            x = -40 if side == 'left' else WIDTH + 40

        if self.selected_phase == 1:
            # Phase 1: 60% goblin warrior, 40% goblin spearman
            if random.random() < 0.6:
                enemy = GoblinWarrior(pos=(x, y))
            else:
                enemy = GoblinSpearman(pos=(x, y))
        elif self.selected_phase == 2:
            # Phase 2: 40% Lizardman, 30% Kobold, 20% Fireworm, 10% Cyclop
            rand = random.random()
            if rand < 0.4:
                enemy = Lizardman(pos=(x, y))
            elif rand < 0.7:
                enemy = Kobold(pos=(x, y))
            elif rand < 0.9:
                enemy = Fireworm(pos=(x, y))
            else:
                enemy = Cyclop(pos=(x, y))
        elif self.selected_phase == 4:
            # Pixel Ruins Arena: a varied non-boss encounter for the imported
            # top-down map. Keep heavy Cyclops rare so the arena remains fair.
            rand = random.random()
            if rand < 0.28:
                enemy = GoblinWarrior(pos=(x, y))
            elif rand < 0.48:
                enemy = GoblinSpearman(pos=(x, y))
            elif rand < 0.70:
                enemy = Lizardman(pos=(x, y))
            elif rand < 0.88:
                enemy = Kobold(pos=(x, y))
            elif rand < 0.96:
                enemy = Fireworm(pos=(x, y))
            else:
                enemy = Cyclop(pos=(x, y))
        else:
            # Phase 3: Handled in update loop manually
            return

        self.enemies.add(enemy)
        self.all_sprites.add(enemy)

    def spawn_miniboss(self):
        """Spawn the phase's miniboss from the right side."""
        y = (MIN_Y + MAX_Y) // 2
        x = WIDTH + 60
        boss = FatCultist(pos=(x, y))
        self.enemies.add(boss)
        self.all_sprites.add(boss)
        self.miniboss_spawned = True

    def spawn_boss(self):
        """Spawn the phase's boss from the right side."""
        y = (MIN_Y + MAX_Y) // 2  # center of the playable area
        x = WIDTH + 60
        if self.selected_phase == 1:
            boss = GoblinTank(pos=(x, y))
        elif self.selected_phase == 3:
            boss = DeathBringer(pos=(x, y))
        else:
            return  # No boss for phase 2 yet

        self.enemies.add(boss)
        self.all_sprites.add(boss)
        self.boss_spawned = True

    def trigger_camera_shake(self, intensity=None):
        """Start a camera shake effect."""
        self.shake_intensity = intensity or CAMERA_SHAKE_INTENSITY
        self.shake_timer = CAMERA_SHAKE_DURATION

    def update_camera_shake(self, dt):
        """Update camera shake offset, decaying over time."""
        if self.shake_timer > 0:
            self.shake_timer -= dt
            # Intensity decays linearly
            progress = max(0, self.shake_timer / CAMERA_SHAKE_DURATION)
            current_intensity = int(self.shake_intensity * progress)
            if current_intensity > 0:
                self.camera_offset[0] = random.randint(-current_intensity, current_intensity)
                self.camera_offset[1] = random.randint(-current_intensity, current_intensity)
            else:
                self.camera_offset = [0, 0]
        else:
            self.camera_offset = [0, 0]

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            if self.skill_ui_test_mode:
                self.events_skill_ui_test()
                self.draw_skill_ui_test()
                continue
            if self.state == "SELECT":
                self.events_select()
                self.update_select(dt)
                self.draw_select()
            elif self.state == "PHASE_SELECT":
                self.events_phase_select()
                self.draw_phase_select()
            else:
                self.events()
                if not self.paused:
                    self.update(dt)
                self.draw()
        pygame.quit()
        sys.exit()

    def _reload_skill_frame_assets(self):
        """Rebuild frame/target alignment after ratio-related changes."""
        self._skill_icon_cache.clear()
        self._skill_frame_img, self._skill_target_img = self._load_skill_ui_assets()

    def events_skill_ui_test(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type != pygame.KEYDOWN:
                continue

            k = event.key
            changed = False

            if k == pygame.K_ESCAPE:
                self.skill_ui_test_mode = False
                self.state = "SELECT"
                continue

            # Target cycling preview
            if k == pygame.K_1:
                self._skill_test_p1.target_skill_idx = (self._skill_test_p1.target_skill_idx + 1) % 3
            elif k == pygame.K_2:
                self._skill_test_p2.target_skill_idx = (self._skill_test_p2.target_skill_idx + 1) % 3

            # Icon size / offset
            elif k == pygame.K_q:
                self._skill_icon_ratio = min(0.95, round(self._skill_icon_ratio + 0.02, 2)); changed = True
            elif k == pygame.K_a:
                self._skill_icon_ratio = max(0.20, round(self._skill_icon_ratio - 0.02, 2)); changed = True
            elif k == pygame.K_w:
                self._skill_icon_offset_y -= 1; changed = True
            elif k == pygame.K_s:
                self._skill_icon_offset_y += 1; changed = True

            # Target size / offset
            elif k == pygame.K_e:
                self._skill_target_ratio = min(1.60, round(self._skill_target_ratio + 0.02, 2)); changed = True
            elif k == pygame.K_d:
                self._skill_target_ratio = max(0.30, round(self._skill_target_ratio - 0.02, 2)); changed = True
            elif k == pygame.K_r:
                self._skill_target_offset_x -= 1; changed = True
            elif k == pygame.K_f:
                self._skill_target_offset_x += 1; changed = True
            elif k == pygame.K_t:
                self._skill_target_offset_y -= 1; changed = True
            elif k == pygame.K_g:
                self._skill_target_offset_y += 1; changed = True

            # Whole bar scale / position
            elif k == pygame.K_y:
                self._skill_ui_scale = min(4, self._skill_ui_scale + 1); changed = True
            elif k == pygame.K_h:
                self._skill_ui_scale = max(1, self._skill_ui_scale - 1); changed = True
            elif k == pygame.K_u:
                self._skill_margin_x = max(0, self._skill_margin_x - 1); changed = True
            elif k == pygame.K_j:
                self._skill_margin_x += 1; changed = True
            elif k == pygame.K_i:
                self._skill_margin_y += 1; changed = True
            elif k == pygame.K_k:
                self._skill_margin_y = max(0, self._skill_margin_y - 1); changed = True

            # Print current tuning block for copy/paste
            elif k == pygame.K_p:
                print("[SKILL_UI_TUNE]",
                      f"icon_ratio={self._skill_icon_ratio},",
                      f"icon_offset_y={self._skill_icon_offset_y},",
                      f"target_ratio={self._skill_target_ratio},",
                      f"target_offset_x={self._skill_target_offset_x},",
                      f"target_offset_y={self._skill_target_offset_y},",
                      f"ui_scale={self._skill_ui_scale},",
                      f"margin_x={self._skill_margin_x},",
                      f"margin_y={self._skill_margin_y}")

            if changed:
                self._reload_skill_frame_assets()

    def draw_skill_ui_test(self):
        # Only show skill UI sandbox for fast iterative tuning.
        self.screen.fill((35, 44, 28))

        self._draw_player_skill_bar(
            self._skill_test_p1,
            x=self._skill_margin_x,
            y=HEIGHT // 2 - 55,
            reverse=False,
            label="P1 TEST"
        )
        # Draw a second bar on the same row for side-by-side comparison.
        native_h = max(self._skill_frame_img.get_height() + self._skill_frame_native_top,
                       self._skill_target_img.get_height())
        bar_w = int(self._skill_frame_img.get_width() * self._skill_ui_scale)
        bar_h = int(native_h * self._skill_ui_scale)
        x2 = WIDTH - bar_w - self._skill_margin_x
        y2 = HEIGHT // 2 - 55
        self._draw_player_skill_bar(
            self._skill_test_p2,
            x=x2,
            y=y2,
            reverse=True,
            label="P2 TEST"
        )

        font = pygame.font.SysFont('Consolas', 16, bold=True)
        help1 = "TEST MODE: only frame/target/icon | 1/2 cycle target | ESC back"
        help2 = "Q/A icon size  W/S icon Y  E/D target size  R/F target X  T/G target Y"
        help3 = "Y/H scale  U/J margin X  I/K margin Y  P print values"
        self.screen.blit(font.render(help1, True, (245, 245, 220)), (12, 14))
        self.screen.blit(font.render(help2, True, (210, 230, 255)), (12, 36))
        self.screen.blit(font.render(help3, True, (210, 255, 210)), (12, 58))

        live = (f"icon_ratio={self._skill_icon_ratio}  icon_offset_y={self._skill_icon_offset_y}  "
                f"target_ratio={self._skill_target_ratio}  target_offset_x={self._skill_target_offset_x}  "
                f"target_offset_y={self._skill_target_offset_y}  scale={self._skill_ui_scale}  "
                f"margin_x={self._skill_margin_x}  margin_y={self._skill_margin_y}")
        self.screen.blit(font.render(live, True, (255, 220, 170)), (12, HEIGHT - 28))

        pygame.display.flip()

    def events_select(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_1, pygame.K_2, pygame.K_3):
                    self.state = "PHASE_SELECT"

    def update_select(self, dt):
        self.knight_preview.update(dt, keys=None, groups=None)
        self.archer_preview.update(dt, keys=None, groups=None)

    def draw_select(self):
        self.screen.blit(self.map, (0, 0))

        font_title = pygame.font.SysFont('Arial', 48, bold=True)
        title = font_title.render("Co-op Beat'em Up", True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 100)))

        font_sub = pygame.font.SysFont('Arial', 28)
        font_small = pygame.font.SysFont('Arial', 22)

        panel = pygame.Surface((700, 260), pygame.SRCALPHA)
        panel.fill((20, 20, 25, 220))
        self.screen.blit(panel, (WIDTH // 2 - 350, HEIGHT // 2 - 100))

        player1 = font_sub.render("Player 1", True, (120, 220, 255))
        self.screen.blit(player1, player1.get_rect(center=(WIDTH // 2 - 180, HEIGHT // 2 - 40)))
        p1_lines = [
            "Move: A / S / D / W",
            "Attack: J",
            "Defend: K",
            "Ultimate: L"
        ]
        for idx, line in enumerate(p1_lines):
            text = font_small.render(line, True, (240, 240, 240))
            self.screen.blit(text, text.get_rect(center=(WIDTH // 2 - 180, HEIGHT // 2 + 10 + idx * 28)))

        player2 = font_sub.render("Player 2", True, (255, 190, 90))
        self.screen.blit(player2, player2.get_rect(center=(WIDTH // 2 + 180, HEIGHT // 2 - 40)))
        p2_lines = [
            "Move: Arrow keys",
            "Attack: NumPad 1 / 2",
            "Dash: NumPad 3 / 4",
            "Ultimate: NumPad 5 / 6",
            "Magic Arrow: NumPad 0"
        ]
        for idx, line in enumerate(p2_lines):
            text = font_small.render(line, True, (240, 240, 240))
            self.screen.blit(text, text.get_rect(center=(WIDTH // 2 + 180, HEIGHT // 2 + 10 + idx * 28)))

        hint = font_small.render("Press Enter or Space to choose a phase", True, (180, 255, 180))
        self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 120)))

        pygame.display.flip()

    # ── Phase Selection ──────────────────────────────────────────────

    def events_phase_select(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    self.selected_phase = 1
                    self.state = "PLAY"
                    self.load()
                elif event.key == pygame.K_2:
                    self.selected_phase = 2
                    self.state = "PLAY"
                    self.load()
                elif event.key == pygame.K_3:
                    self.selected_phase = 3
                    self.state = "PLAY"
                    self.load()
                elif event.key == pygame.K_4:
                    self.selected_phase = 4
                    self.state = "PLAY"
                    self.load()
                elif event.key == pygame.K_ESCAPE:
                    self.state = "SELECT"

    def draw_phase_select(self):
        self.screen.blit(self.map, (0, 0))

        # Semi-transparent overlay for readability
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        self.screen.blit(overlay, (0, 0))

        font_title = pygame.font.SysFont('Arial', 48, bold=True)
        title = font_title.render("Select Phase", True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 100)))

        font_sub = pygame.font.SysFont('Arial', 28)

        # Phase 1 description
        text_p1 = font_sub.render("Press 1 - Goblin Invasion", True, (150, 255, 150))
        desc_p1 = font_sub.render("Goblin Warriors, Spearmen & Tank Boss", True, (200, 200, 200))
        self.screen.blit(text_p1, text_p1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80)))
        self.screen.blit(desc_p1, desc_p1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40)))

        # Phase 2 description
        text_p2 = font_sub.render("Press 2 - The Menagerie", True, (255, 220, 150))
        desc_p2 = font_sub.render("Lizardmen, Kobolds, Fireworms & Cyclopes", True, (200, 200, 200))
        self.screen.blit(text_p2, text_p2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))
        self.screen.blit(desc_p2, desc_p2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 60)))

        # Phase 3 description
        text_p3 = font_sub.render("Press 3 - The Cult", True, (255, 150, 150))
        desc_p3 = font_sub.render("Fat Cultists & Death Bringer Boss", True, (200, 200, 200))
        self.screen.blit(text_p3, text_p3.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 120)))
        self.screen.blit(desc_p3, desc_p3.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 160)))

        # Phase 4 description — reconstructed Pygame arena from the Unity pack.
        text_p4 = font_sub.render("Press 4 - Pixel Ruins Arena", True, (150, 210, 255))
        desc_p4 = font_sub.render("Top-down pixel map with mixed enemy waves", True, (200, 200, 200))
        self.screen.blit(text_p4, text_p4.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 200)))
        self.screen.blit(desc_p4, desc_p4.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 230)))

        # Back hint
        font_hint = pygame.font.SysFont('Arial', 22)
        hint = font_hint.render("ESC to go back", True, (180, 180, 180))
        self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 28)))

        pygame.display.flip()

    # ── Main Gameplay ────────────────────────────────────────────────

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == self.spawn_event:
                if not self.paused and any(player.hp > 0 for player in self.players):
                    self.spawn_enemy()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                    continue

                if event.key == pygame.K_F5 and self.selected_phase == 4:
                    self.reload_pixel_ruins_layout()
                    continue

                if event.key == pygame.K_F3 and self.selected_phase == 4:
                    self.DEBUG_DRAW = not self.DEBUG_DRAW
                    continue

                if self.paused:
                    if len(self.players) > 0:
                        p1_upgrades = {
                            pygame.K_1: 'attack', pygame.K_2: 'armor', pygame.K_3: 'speed',
                        }
                        upgrade = p1_upgrades.get(event.key)
                        if upgrade:
                            self.upgrade_player_ability(self.players[0], upgrade)
                    if len(self.players) > 1:
                        p2_upgrades = {
                            pygame.K_7: 'attack', pygame.K_8: 'armor', pygame.K_9: 'speed',
                            pygame.K_KP7: 'attack', pygame.K_KP8: 'armor', pygame.K_KP9: 'speed',
                        }
                        upgrade = p2_upgrades.get(event.key)
                        if upgrade:
                            self.upgrade_player_ability(self.players[1], upgrade)
                    continue
                if event.key == pygame.K_r and all(player.hp <= 0 for player in self.players):
                    self.state = "SELECT"
                # Skill target/use controls
                if event.key in (pygame.K_0, pygame.K_KP0):
                    self.cycle_archer_arrow()
                    continue
                if len(self.players) > 0:
                    if event.key == pygame.K_n:
                        self.cycle_skill_target(self.players[0])
                    elif event.key == pygame.K_m:
                        self.use_target_skill(self.players[0])
                if len(self.players) > 1:
                    if event.key in (pygame.K_KP7, pygame.K_7):
                        # P2 bar is rendered from right-to-left.
                        self.cycle_skill_target(self.players[1], reverse=True)
                    elif event.key in (pygame.K_KP8, pygame.K_8):
                        self.use_target_skill(self.players[1])

    def update(self, dt):
        keys = pygame.key.get_pressed()
        self._update_player_passives(dt)
        # update players
        for player in self.players:
            self._fit_phase4_hurtbox(player)
            previous_rect = player.rect.copy()
            previous_hurtbox = player.hurtbox.copy()
            player.update(dt, keys, self.groups)
            self._fit_phase4_hurtbox(player)
            self._resolve_map_collision(player, previous_rect, previous_hurtbox)
            self._update_tunnel_traversal(player, previous_hurtbox)
            self._update_player_stair_floor(player, previous_hurtbox)
            self._update_entity_region_floor(player)

        # update enemies
        for e in list(self.enemies):
            living_players = [p for p in self.players if p.hp > 0]
            target = self._enemy_ai_target(e, living_players)
            if target is None:
                continue
            self._apply_enemy_status_effects(e)
            self._fit_phase4_hurtbox(e)
            previous_rect = e.rect.copy()
            previous_hurtbox = e.hurtbox.copy()
            e.update(dt, target, self.groups)
            self._fit_phase4_hurtbox(e)
            self._resolve_map_collision(e, previous_rect, previous_hurtbox)
            self._update_tunnel_traversal(e, previous_hurtbox)
            self._update_entity_region_floor(e)

        self._update_world_camera()

        # update enemy health bars (centralised so they tick every frame,
        # even when an enemy is in a hurt / attack / death state).
        for e in self.enemies:
            if getattr(e, 'health_bar', None) is not None:
                e.health_bar.update(dt)

        for player in self.players:
            self._ensure_player_resources(player)
            if player.hp > 0:
                mana_regen = float(PLAYER_RESOURCE_REGEN_PER_MS.get('mana', 0.010))
                armor_regen = float(PLAYER_RESOURCE_REGEN_PER_MS.get('armor', 0.003))
                player.mana = min(float(player.max_mana), float(player.mana) + dt * mana_regen)
                player.armor = min(float(player.max_armor), float(player.armor) + dt * armor_regen)

        # update attacks
        self.attacks.update(dt)
        self.enemy_attacks.update(dt)
        self.arrows.update(dt)
        self.water_projectiles.update(dt)
        self.water_blast_projectiles.update(dt)
        self.wind_projectiles.update(dt)
        self.light_projectiles.update(dt)
        self.dark_projectiles.update(dt)
        self.wood_projectiles.update(dt)
        self.acid_projectiles.update(dt)
        self.enemy_projectiles.update(dt)
        self.damage_numbers.update(dt)
        self.effects.update(dt)
        self.knight_shockwaves.update(dt)
        self.potions.update(dt)
        self.ability_vials.update(dt)
        self.berserk_vials.update(dt)
        self.skills.update(dt)
        self._update_enemy_dot_effects()

        # Boss spawn logic
        if self.selected_phase == 1 and not self.boss_spawned:
            elapsed = pygame.time.get_ticks() - self.phase_start_time
            if elapsed >= 10000 and any(player.hp > 0 for player in self.players):
                self.spawn_boss()
        elif self.selected_phase == 3:
            if not self.miniboss_spawned:
                # Spawn miniboss slightly after phase starts
                elapsed = pygame.time.get_ticks() - self.phase_start_time
                if elapsed >= 1000 and any(player.hp > 0 for player in self.players):
                    self.spawn_miniboss()
            elif not self.miniboss_defeated:
                if not any(isinstance(e, FatCultist) and e.hp > 0 for e in self.enemies):
                    self.miniboss_defeated = True
                    self.phase_start_time = pygame.time.get_ticks()
            elif not self.boss_spawned:
                elapsed = pygame.time.get_ticks() - self.phase_start_time
                if elapsed >= 3000 and any(player.hp > 0 for player in self.players):
                    self.spawn_boss()

        # Check for camera shake triggers from GoblinTank entities
        for e in self.enemies:
            if isinstance(e, GoblinTank) and getattr(e, 'camera_shake_triggered', False):
                self.trigger_camera_shake()
                e.camera_shake_triggered = False

        # Update camera shake
        self.update_camera_shake(dt)

        # ── Collision Resolution (Hitbox → Hurtbox) ───────────────────

        # 1. Player Attack Hitbox vs Enemy Hurtbox
        for hb in list(self.attacks):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if id(enemy) in hb.already_hit_targets:
                    continue
                # Phase 1 – Vertical depth filter (melee)
                if math.fabs(hb.owner.foot_y - enemy.foot_y) > 50:
                    continue
                # Phase 2 – 2D AABB collision
                if hb.rect.colliderect(enemy.hurtbox):
                    hb.already_hit_targets.add(id(enemy))
                    base_damage = self._passive_attack_damage(getattr(hb, 'owner', None), hb.damage, enemy)
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        continue
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=hb.owner.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        self._on_player_hit_enemy_passive(getattr(hb, 'owner', None), enemy, final_damage)
                        
                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)

        # 2. Arrow vs Enemy Hurtbox
        for arrow in list(self.arrows):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                # Phase 1 - Vertical depth filter (projectile)
                if math.fabs(arrow.floor_y - enemy.foot_y) > 50:
                    continue
                # Phase 2 - 2D AABB collision
                if arrow.rect.colliderect(enemy.hurtbox):
                    base_damage = self._passive_attack_damage(getattr(arrow, 'owner', None), arrow.damage, enemy)
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        arrow.kill()
                        break
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=arrow.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        self._apply_magic_arrow_effect(arrow, enemy, final_damage)
                        self._on_player_hit_enemy_passive(getattr(arrow, 'owner', None), enemy, final_damage)
                        
                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    arrow.kill()
                    break

        # 2a. Water Ball Projectile vs Enemy Hurtbox
        for proj in list(self.water_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if id(enemy) in proj.already_hit_targets:
                    continue
                if math.fabs(proj.floor_y - enemy.foot_y) > 55:
                    continue
                if proj.rect.colliderect(enemy.hurtbox):
                    proj.already_hit_targets.add(id(enemy))
                    base_damage = self._passive_attack_damage(getattr(proj, 'owner', None), proj.damage, enemy)
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        proj.kill()
                        break
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=proj.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        self._on_player_hit_enemy_passive(getattr(proj, 'owner', None), enemy, final_damage)

                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    self._spawn_skill_vfx('water_ball', enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(proj.owner, 'facing', 1) if getattr(proj, 'owner', None) else 1)
                    proj.kill()
                    break

        # 2a2. Dark Projectile vs Enemy Hurtbox
        for proj in list(self.light_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if id(enemy) in proj.already_hit_targets:
                    continue
                if math.fabs(proj.floor_y - enemy.foot_y) > 55:
                    continue
                if proj.rect.colliderect(enemy.hurtbox):
                    proj.already_hit_targets.add(id(enemy))
                    base_damage = self._passive_attack_damage(getattr(proj, 'owner', None), proj.damage, enemy)
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        proj.kill()
                        break
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=proj.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        self._on_player_hit_enemy_passive(getattr(proj, 'owner', None), enemy, final_damage)
                        self._spawn_skill_vfx('light', enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(proj.owner, 'facing', 1) if getattr(proj, 'owner', None) else 1)

                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)

                        splash_damage = max(1, int(final_damage * 0.55))
                        chained = 0
                        for other in self.enemies:
                            if chained >= 2:
                                break
                            if other is enemy or other.hp <= 0:
                                continue
                            if math.fabs(other.foot_y - enemy.foot_y) > 75:
                                continue
                            if abs(other.hurtbox.centerx - enemy.hurtbox.centerx) > 165:
                                continue
                            old_other_hp = other.hp
                            actual_splash = self._consume_entity_armor(other, splash_damage)
                            if actual_splash <= 0:
                                continue
                            other.take_damage(actual_splash, source_x=proj.rect.centerx, is_crit=False)
                            if other.hp < old_other_hp:
                                self.damage_numbers.add(
                                    DamageNumber(other.hurtbox.centerx, other.hurtbox.top, actual_splash, is_crit=False)
                                )
                                self._spawn_skill_vfx('light', other.hurtbox.centerx, other.hurtbox.centery, getattr(proj.owner, 'facing', 1) if getattr(proj, 'owner', None) else 1)
                                chained += 1
                    proj.kill()
                    break

        # 2a2. Dark Projectile vs Enemy Hurtbox
        for proj in list(self.water_blast_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if id(enemy) in proj.already_hit_targets:
                    continue
                if math.fabs(proj.floor_y - enemy.foot_y) > 60:
                    continue
                if proj.rect.colliderect(enemy.hurtbox):
                    proj.already_hit_targets.add(id(enemy))
                    base_damage = self._passive_attack_damage(getattr(proj, 'owner', None), proj.damage, enemy)
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        proj.kill()
                        break
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=proj.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        self._on_player_hit_enemy_passive(getattr(proj, 'owner', None), enemy, final_damage)
                        self._spawn_skill_vfx('water_blast', enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(proj.owner, 'facing', 1) if getattr(proj, 'owner', None) else 1)
                        enemy.slow_until = max(getattr(enemy, 'slow_until', 0), pygame.time.get_ticks() + 1100)
                        enemy.slow_mult = min(getattr(enemy, 'slow_mult', 0.74), 0.70)

                        splash_damage = max(1, int(final_damage * 0.5))
                        for other in self.enemies:
                            if other is enemy or other.hp <= 0:
                                continue
                            if math.fabs(other.foot_y - enemy.foot_y) > 90:
                                continue
                            if abs(other.hurtbox.centerx - enemy.hurtbox.centerx) > 130:
                                continue
                            old_other_hp = other.hp
                            actual_splash = self._consume_entity_armor(other, splash_damage)
                            if actual_splash <= 0:
                                continue
                            other.take_damage(actual_splash, source_x=proj.rect.centerx, is_crit=False)
                            if other.hp < old_other_hp:
                                self.damage_numbers.add(
                                    DamageNumber(other.hurtbox.centerx, other.hurtbox.top, actual_splash, is_crit=False)
                                )
                                self._spawn_skill_vfx('water_blast', other.hurtbox.centerx, other.hurtbox.centery, getattr(proj.owner, 'facing', 1) if getattr(proj, 'owner', None) else 1)

                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    proj.kill()
                    break

        # 2a2. Dark Projectile vs Enemy Hurtbox
        for proj in list(self.dark_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if not self._is_dark_eligible_enemy(enemy):
                    continue
                if id(enemy) in proj.already_hit_targets:
                    continue
                if math.fabs(proj.floor_y - enemy.foot_y) > 55:
                    continue
                if proj.rect.colliderect(enemy.hurtbox):
                    proj.already_hit_targets.add(id(enemy))
                    base_damage = self._passive_attack_damage(getattr(proj, 'owner', None), proj.damage, enemy)
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        proj.kill()
                        break
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=proj.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        self._on_player_hit_enemy_passive(getattr(proj, 'owner', None), enemy, final_damage)

                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    proj.kill()
                    break

        # 2a3. Wood Projectile vs Enemy Hurtbox
        for proj in list(self.wood_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if id(enemy) in proj.already_hit_targets:
                    continue
                if math.fabs(proj.floor_y - enemy.foot_y) > 55:
                    continue
                if proj.rect.colliderect(enemy.hurtbox):
                    proj.already_hit_targets.add(id(enemy))
                    base_damage = self._passive_attack_damage(getattr(proj, 'owner', None), proj.damage, enemy)
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        proj.kill()
                        break
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=proj.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        self._on_player_hit_enemy_passive(getattr(proj, 'owner', None), enemy, final_damage)

                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    proj.kill()
                    break

        # 2a4. Acid Projectile vs Enemy Hurtbox
        for proj in list(self.acid_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if id(enemy) in proj.already_hit_targets:
                    continue
                if math.fabs(proj.floor_y - enemy.foot_y) > 55:
                    continue
                if proj.rect.colliderect(enemy.hurtbox):
                    proj.already_hit_targets.add(id(enemy))
                    base_damage = self._passive_attack_damage(getattr(proj, 'owner', None), proj.damage, enemy)
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        proj.kill()
                        break
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=proj.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        self._on_player_hit_enemy_passive(getattr(proj, 'owner', None), enemy, final_damage)

                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    proj.kill()
                    break

        # 2b. Ultimate Beam vs Enemy Hurtbox (piercing)
        for beam in list(self.ultimate_beams):
            if not beam.alive():
                continue
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                # Vertical depth filter
                if math.fabs(beam.floor_y - enemy.foot_y) > 60:
                    continue
                if beam.rect.colliderect(enemy.hurtbox) and beam.can_hit(enemy):
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(beam.damage * CRIT_MULTIPLIER) if is_crit else beam.damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        beam.register_hit(enemy)
                        continue
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=beam.rect.centerx, is_crit=is_crit)
                    beam.register_hit(enemy)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        
                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)

        # 2a. Wind Projectile vs Enemy Hurtbox
        for proj in list(self.wind_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if id(enemy) in proj.already_hit_targets:
                    continue
                if math.fabs(proj.floor_y - enemy.foot_y) > 55:
                    continue
                if proj.rect.colliderect(enemy.hurtbox):
                    proj.already_hit_targets.add(id(enemy))
                    base_damage = self._passive_attack_damage(getattr(proj, 'owner', None), proj.damage, enemy)
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        proj.kill()
                        break
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=proj.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        self._on_player_hit_enemy_passive(getattr(proj, 'owner', None), enemy, final_damage)

                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    self._spawn_skill_vfx('wind', enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(proj.owner, 'facing', 1) if getattr(proj, 'owner', None) else 1)
                    proj.kill()
                    break

        # 2c. Knight Ultimate Shockwave vs Enemy Hurtbox (immense knockback, piercing)
        for shockwave in list(self.knight_shockwaves):
            if not shockwave.alive():
                continue
            shockwave_hit = False
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if shockwave.collides_with(enemy) and shockwave.can_hit(enemy):
                    is_crit = random.random() < CRIT_CHANCE
                    old_hp = enemy.hp
                    
                    # Determine if enemy is in the front or rear of the knight's ultimate
                    if shockwave.facing == 1:
                        is_front = enemy.hurtbox.centerx > shockwave.rect.centerx
                    else:
                        is_front = enemy.hurtbox.centerx < shockwave.rect.centerx
                    
                    if is_front:
                        final_damage = int(shockwave.damage * CRIT_MULTIPLIER) if is_crit else shockwave.damage
                    else:
                        base_dmg = shockwave.damage * 0.5
                        final_damage = int(base_dmg * CRIT_MULTIPLIER) if is_crit else int(base_dmg)

                    final_damage = self._consume_entity_armor(enemy, final_damage)
                    if final_damage <= 0:
                        shockwave.register_hit(enemy)
                        shockwave_hit = True
                        continue

                    enemy.take_damage(final_damage, source_x=shockwave.rect.centerx, is_crit=is_crit)
                    
                    # Apply knockback AFTER take_damage to prevent it from being overwritten
                    if is_front:
                        knockback_dir = shockwave.facing
                        enemy.vel.x = knockback_dir * shockwave.knockback
                        enemy.hurt_timer = max(getattr(enemy, 'hurt_timer', 0), 600)
                    else:
                        enemy.vel.x = 0  # No knockback for rear hits
                        enemy.hurt_timer = max(getattr(enemy, 'hurt_timer', 0), 300)

                    shockwave.register_hit(enemy)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        
                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    shockwave_hit = True
            # Trigger camera shake on impact
            if shockwave_hit:
                self.trigger_camera_shake(intensity=12)

        # 3. Enemy Attack Hitbox vs Player Hurtboxes
        for hb in list(self.enemy_attacks):
            owner = getattr(hb, 'owner', None)
            if owner is None:
                continue
            owner_source_x = getattr(getattr(owner, 'rect', None), 'centerx', hb.rect.centerx)
            owner_foot_y = getattr(owner, 'foot_y', hb.rect.bottom)
            for enemy in self.enemies:
                if not self._enemy_can_hit_enemy(owner, enemy):
                    continue
                if id(enemy) in hb.already_hit_targets:
                    continue
                if math.fabs(owner_foot_y - enemy.foot_y) > 50:
                    continue
                if not hb.rect.colliderect(enemy.hurtbox):
                    continue

                hb.already_hit_targets.add(id(enemy))
                dealt_damage = self._consume_entity_armor(enemy, hb.damage)
                if dealt_damage <= 0:
                    continue
                old_hp = enemy.hp
                enemy.take_damage(dealt_damage, source_x=owner_source_x, is_crit=False)
                if enemy.hp < old_hp:
                    self.damage_numbers.add(
                        DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, dealt_damage, is_crit=False)
                    )
                    self._spawn_skill_vfx('dark', enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(owner, 'facing', 1))

        for player in self.players:
            if player.hp > 0 and player.hurt_timer <= 0:
                for hb in list(self.enemy_attacks):
                    if self._is_enemy_zombie(getattr(hb, 'owner', None)):
                        continue
                    if id(player) in hb.already_hit_targets:
                        continue
                    if math.fabs(hb.owner.foot_y - player.foot_y) > 50:
                        continue
                    if hb.rect.colliderect(player.hurtbox):
                        hb.already_hit_targets.add(id(player))
                        incoming_damage = self._passive_defense_damage(player, hb.damage)
                        incoming_damage = self._consume_player_armor(player, incoming_damage)
                        if incoming_damage <= 0:
                            continue
                        old_hp = player.hp
                        player.take_damage(incoming_damage, source_x=hb.owner.rect.centerx)
                        if player.hp < old_hp:
                            defense_skill = self._active_passive(player)
                            if defense_skill in ('wood', 'holy', 'water_ball'):
                                self._spawn_skill_vfx(defense_skill, player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1))
                            if defense_skill == 'wood':
                                self._try_wood_reflect(player, hb.owner, incoming_damage)
                            dmg_num = DamageNumber(player.hurtbox.centerx, player.hurtbox.top, incoming_damage, is_crit=False)
                            self.damage_numbers.add(dmg_num)
                            vfx_type = "death" if player.hp <= 0 else "hit"
                            blood = BloodVFX(player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1), player.foot_y, vfx_type=vfx_type)
                            self.effects.add(blood)
                            hit_effect = HitVFX(player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1), player.foot_y)
                            self.effects.add(hit_effect)
                        break

        # 4. Enemy Projectile vs Player Hurtboxes
        for proj in list(self.enemy_projectiles):
            owner = getattr(proj, 'owner', None)
            if owner is None:
                continue
            owner_source_x = getattr(getattr(owner, 'rect', None), 'centerx', proj.rect.centerx)
            for enemy in self.enemies:
                if not self._enemy_can_hit_enemy(owner, enemy):
                    continue
                if math.fabs(proj.floor_y - enemy.foot_y) > 50:
                    continue
                if not proj.rect.colliderect(enemy.hurtbox):
                    continue

                dealt_damage = self._consume_entity_armor(enemy, proj.damage)
                if dealt_damage <= 0:
                    proj.kill()
                    break
                old_hp = enemy.hp
                enemy.take_damage(dealt_damage, source_x=owner_source_x, is_crit=False)
                if enemy.hp < old_hp:
                    self.damage_numbers.add(
                        DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, dealt_damage, is_crit=False)
                    )
                    self._spawn_skill_vfx('dark', enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(owner, 'facing', 1))
                proj.kill()
                break

        for player in self.players:
            if player.hp > 0 and player.hurt_timer <= 0:
                for proj in list(self.enemy_projectiles):
                    if self._is_enemy_zombie(getattr(proj, 'owner', None)):
                        continue
                    if math.fabs(proj.floor_y - player.foot_y) > 50:
                        continue
                    if proj.rect.colliderect(player.hurtbox):
                        incoming_damage = self._passive_defense_damage(player, proj.damage)
                        incoming_damage = self._consume_player_armor(player, incoming_damage)
                        if incoming_damage <= 0:
                            proj.kill()
                            continue
                        old_hp = player.hp
                        player.take_damage(incoming_damage, source_x=proj.rect.centerx)
                        if player.hp < old_hp:
                            defense_skill = self._active_passive(player)
                            if defense_skill in ('wood', 'holy', 'water_ball'):
                                self._spawn_skill_vfx(defense_skill, player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1))
                            if defense_skill == 'wood':
                                self._try_wood_reflect(player, getattr(proj, 'owner', None), incoming_damage)
                            dmg_num = DamageNumber(player.hurtbox.centerx, player.hurtbox.top, incoming_damage, is_crit=False)
                            self.damage_numbers.add(dmg_num)
                            vfx_type = "death" if player.hp <= 0 else "hit"
                            blood = BloodVFX(player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1), player.foot_y, vfx_type=vfx_type)
                            self.effects.add(blood)
                            hit_effect = HitVFX(player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1), player.foot_y)
                            self.effects.add(hit_effect)
                        proj.kill()

        # 5. Spawn potion
        for enemy in self.enemies:
            if enemy.hp <= 0 and not getattr(enemy, 'dropped_potion', False):
                enemy.dropped_potion = True
                if random.random() < 1:  # 15% rơi bình máu
                    potion = HealthPotion(enemy.hurtbox.centerx, enemy.foot_y)
                    self.potions.add(potion)
                    self.all_sprites.add(potion)

        # 5a. Poison Vials grant an ability point when picked up.
        for enemy in self.enemies:
            if enemy.hp <= 0 and not getattr(enemy, 'dropped_ability_vial', False):
                enemy.dropped_ability_vial = True
                if random.random() < ABILITY_VIAL_DROP_CHANCE:
                    vial = AbilityVial(enemy.hurtbox.centerx, enemy.foot_y)
                    self.ability_vials.add(vial)
                    self.all_sprites.add(vial)

        # 5aa. Red Berserk Vials: temporary attack buff with armor penalty.
        for enemy in self.enemies:
            if enemy.hp <= 0 and not getattr(enemy, 'dropped_berserk_vial', False):
                enemy.dropped_berserk_vial = True
                if random.random() < BERSERK_VIAL_DROP_CHANCE:
                    vial = BerserkVial(enemy.hurtbox.centerx + random.randint(-18, 18), enemy.foot_y)
                    self.berserk_vials.add(vial)
                    self.all_sprites.add(vial)
        
        # 5b. Spawn skills from enemies
        for enemy in self.enemies:
            if enemy.hp <= 0 and not getattr(enemy, 'dropped_skill', False):
                enemy.dropped_skill = True
                dropped_skills = self._roll_skill_drops_for_enemy(enemy)
                for skill_type in dropped_skills:
                    offset_x = random.randint(-30, 30)
                    skill = SkillIcon(enemy.hurtbox.centerx + offset_x, enemy.foot_y, skill_type)
                    self.skills.add(skill)
                    self.all_sprites.add(skill)

        # 6. Take potion
        for player in self.players:
            if player.hp > 0:
                for potion in list(self.potions):
                    if player.hurtbox.colliderect(potion.rect):
                        player.hp = min(player.max_hp, player.hp + potion.heal_amount)
                        potion.kill()

        # 6a. Pick up Poison Vials; spend their points from the pause menu.
        for player in self.players:
            if player.hp > 0:
                for vial in list(self.ability_vials):
                    if player.hurtbox.colliderect(vial.rect):
                        self._ensure_player_abilities(player)
                        player.ability_points += 1
                        vial.kill()

        # 6aa. Berserk effect refreshes on each pickup but does not stack.
        for player in self.players:
            if player.hp > 0:
                for vial in list(self.berserk_vials):
                    if player.hurtbox.colliderect(vial.rect):
                        player.berserk_until = pygame.time.get_ticks() + BERSERK_VIAL_DURATION_MS
                        vial.kill()
        
        # 6b. Pick up skills
        for player in self.players:
            if player.hp > 0:
                for skill in list(self.skills):
                    if player.hurtbox.colliderect(skill.rect):
                        # Max 3 stored skills per player.
                        if len(player.skills) < 3:
                            player.skills.append(skill.skill_type)
                            skill.kill()

    def _apply_magic_arrow_effect(self, arrow, enemy, dealt_damage):
        """Apply the selected Magic Arrow's utility after its direct hit."""
        cfg = ARCHER_ARROW_CONFIG.get(getattr(arrow, 'arrow_type', 'normal'), ARCHER_ARROW_CONFIG['normal'])
        effect = cfg.get('effect')
        if effect == 'burn':
            now = pygame.time.get_ticks()
            tick_ms = int(cfg['dot_tick_ms'])
            enemy.magic_arrow_burn_until = max(
                getattr(enemy, 'magic_arrow_burn_until', 0), now + int(cfg['dot_duration_ms'])
            )
            enemy.magic_arrow_burn_next_tick = min(
                getattr(enemy, 'magic_arrow_burn_next_tick', now + tick_ms), now + tick_ms
            )
            enemy.magic_arrow_burn_damage = int(cfg['dot_damage'])
            enemy.magic_arrow_burn_tick_ms = tick_ms
            enemy.magic_arrow_burn_source_x = arrow.rect.centerx
            self._spawn_skill_vfx('fire', enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(arrow, 'facing', 1))
        elif effect == 'slow':
            enemy.slow_until = max(
                getattr(enemy, 'slow_until', 0), pygame.time.get_ticks() + int(cfg['slow_duration_ms'])
            )
            enemy.slow_mult = min(getattr(enemy, 'slow_mult', 1.0), float(cfg['slow_mult']))
            self._spawn_skill_vfx('water_ball', enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(arrow, 'facing', 1))
        elif effect == 'chain':
            candidates = [
                other for other in self.enemies
                if other is not enemy and other.hp > 0
                and abs(other.hurtbox.centerx - enemy.hurtbox.centerx) <= int(cfg['chain_enemy_x_range'])
                and abs(other.foot_y - enemy.foot_y) <= int(cfg['chain_enemy_y_range'])
            ]
            if not candidates:
                return
            target = min(candidates, key=lambda other: abs(other.hurtbox.centerx - enemy.hurtbox.centerx))
            chain_damage = self._consume_entity_armor(target, max(1, int(dealt_damage * float(cfg['chain_damage_pct']))))
            if chain_damage <= 0:
                return
            old_hp = target.hp
            target.take_damage(chain_damage, source_x=enemy.hurtbox.centerx, is_crit=False)
            if target.hp < old_hp:
                self.damage_numbers.add(DamageNumber(target.hurtbox.centerx, target.hurtbox.top, chain_damage, is_crit=False))
                self._spawn_skill_vfx('light', target.hurtbox.centerx, target.hurtbox.centery, getattr(arrow, 'facing', 1))

    def draw(self):
        ox, oy = self.camera_offset
        world_mode = self.selected_phase == 4
        zoom = self.world_zoom if world_mode else 1.0
        entity_scale = PIXEL_RUINS_ENTITY_SCALE if world_mode else 1.0
        if world_mode:
            self.screen.blit(
                self.world_render_map,
                (round(ox - self.world_camera.x * zoom), round(oy - self.world_camera.y * zoom)),
            )
        else:
            self.screen.blit(self.map, (ox, oy))

        def world_to_screen(x, y):
            if not world_mode:
                return (round(x + ox), round(y + oy))
            return (
                round((x - self.world_camera.x) * zoom + ox),
                round((y - self.world_camera.y) * zoom + oy),
            )

        def world_rect_to_screen(rect):
            x, y = world_to_screen(rect.x, rect.y)
            return pygame.Rect(x, y, round(rect.width * zoom), round(rect.height * zoom))

        def scale_world_image(image):
            if entity_scale == 1.0:
                return image
            return pygame.transform.scale(
                image,
                (max(1, round(image.get_width() * entity_scale)), max(1, round(image.get_height() * entity_scale))),
            )

        def sprite_screen_position(sprite, image):
            """Place native-size sprites on a zoomed map without foot drift."""
            if not world_mode:
                return world_to_screen(sprite.rect.x, sprite.rect.y)

            if hasattr(sprite, 'hurtbox'):
                # Characters are visually anchored to their logical foot.  The
                # rect/hurtbox delta keeps custom animation pivots intact.
                hurtbox = sprite.hurtbox
                foot_x, foot_y = world_to_screen(hurtbox.centerx, hurtbox.bottom)
                x = round(foot_x + (sprite.rect.x - hurtbox.centerx) * entity_scale)
                y = round(foot_y + (sprite.rect.bottom - hurtbox.bottom) * entity_scale - image.get_height())
                return x, y

            # Projectiles/VFX retain their original size and stay centred on
            # their transformed world position.
            center_x, center_y = world_to_screen(sprite.rect.centerx, sprite.rect.centery)
            return (round(center_x - image.get_width() / 2), round(center_y - image.get_height() / 2))
        # Create a combined list of all entities that need Y-sorting
        render_list = (list(self.all_sprites) + list(self.arrows) +
                       list(self.water_projectiles) + list(self.water_blast_projectiles) + list(self.wind_projectiles) + list(self.light_projectiles) + list(self.dark_projectiles) +
                       list(self.wood_projectiles) + list(self.acid_projectiles) +
                       list(self.enemy_projectiles) + list(self.effects))

        def get_sort_y(s):
            if hasattr(s, 'foot_y'):
                return s.foot_y
            elif hasattr(s, 'floor_y'):
                return s.floor_y
            elif hasattr(s, 'hurtbox'):
                return s.hurtbox.bottom
            else:
                return s.rect.bottom - getattr(s, 'current_pdy', 0)

        sorted_sprites = sorted(render_list, key=get_sort_y)

        # ── Shadow pre-pass (drawn before sprites so shadows are always under) ──
        for sprite in sorted_sprites:
            # Only draw shadows for characters (skip arrows, spears, hitboxes)
            if not hasattr(sprite, 'hurtbox'):
                continue
            # Skip fully invisible sprites (alpha == 0 means corpse already gone)
            entity_alpha = getattr(sprite, 'alpha', 255)
            if entity_alpha <= 0:
                continue
            hurtbox = sprite.hurtbox
            # Scale shadow width to roughly match the entity's footprint
            target_w = max(20, int(hurtbox.width * 1.4 * entity_scale))
            if target_w not in self._shadow_cache:
                src_w, src_h = self._shadow_src.get_size()
                scaled_h = max(6, int(src_h * target_w / src_w))
                self._shadow_cache[target_w] = pygame.transform.scale(
                    self._shadow_src, (target_w, scaled_h)
                )
            shadow_surf = self._shadow_cache[target_w]
            # Fade the shadow in sync with the entity's death fade-out
            if entity_alpha < 255:
                shadow_surf = shadow_surf.copy()
                shadow_surf.fill((255, 255, 255, entity_alpha), special_flags=pygame.BLEND_RGBA_MULT)
            sx, sy = world_to_screen(hurtbox.centerx, hurtbox.bottom)
            sx -= shadow_surf.get_width() // 2
            sy -= shadow_surf.get_height() // 2
            self.screen.blit(shadow_surf, (sx, sy))

        for sprite in sorted_sprites:
            image = scale_world_image(sprite.image)
            if self._entity_is_in_tunnel(sprite):
                # Keep the original pixel art but let the map's upper layer
                # visually read through it, as if the character is below it.
                image = image.copy()
                image.set_alpha(min(getattr(sprite, 'alpha', 255), PIXEL_RUINS_TUNNEL_ENTITY_ALPHA))
            x, y = sprite_screen_position(sprite, image)
            self.screen.blit(image, (x, y))


        # Draw enemy health bars — always visible for living enemies
        for enemy in self.enemies:
            if getattr(enemy, 'health_bar', None) is not None and enemy.hp > 0:
                enemy.health_bar.draw(
                    self.screen,
                    enemy,
                    self.camera_offset,
                    world_camera=self.world_camera if world_mode else None,
                    zoom=zoom,
                )

        # --- DEBUG: Hitbox / Hurtbox visualization ---
        if self.DEBUG_DRAW:
            # Red transparent: zones authored in the tuner before tunnel cuts.
            if world_mode and self.pixel_ruins_map:
                for zone in self.pixel_ruins_map.collision_zones:
                    screen_zone = world_rect_to_screen(zone)
                    overlay = pygame.Surface(screen_zone.size, pygame.SRCALPHA)
                    overlay.fill((255, 65, 65, 42))
                    self.screen.blit(overlay, screen_zone.topleft)
                    pygame.draw.rect(self.screen, (255, 90, 90), screen_zone, 1)
                for floor in self.pixel_ruins_map.floors:
                    floor_rect = world_rect_to_screen(floor['rect'])
                    pygame.draw.rect(self.screen, (75, 185, 255), floor_rect, 2)
                    self.screen.blit(pygame.font.SysFont('Consolas', 14, bold=True).render(f"T{floor.get('floor', 0)}", True, (75, 185, 255)), (floor_rect.x + 3, floor_rect.y + 3))
                # Purple: tunnel regions that remove collision from red zones.
                for tunnel in self.pixel_ruins_map.tunnels:
                    pygame.draw.rect(self.screen, (190, 105, 255), world_rect_to_screen(tunnel), 2)
                for tunnel in self.pixel_ruins_map.tunnel_zones:
                    for line, color, label in ((tunnel['start_line'], (85, 255, 170), 'A'), (tunnel['end_line'], (255, 95, 145), 'B')):
                        start, end = world_to_screen(*line[0]), world_to_screen(*line[1])
                        pygame.draw.line(self.screen, color, start, end, 5)
                        self.screen.blit(pygame.font.SysFont('Consolas', 14, bold=True).render(label, True, (20, 20, 20)), (start[0] + 4, start[1] + 4))
                # Yellow: free-form boundary lines authored with mode 6.
                for start, end in self.pixel_ruins_map.map_boundaries:
                    pygame.draw.line(self.screen, (255, 230, 80), world_to_screen(*start), world_to_screen(*end), 3)
                # Orange: stair boxes. Entering one toggles between its two
                # configured floor/zoom pairs.
                debug_font = pygame.font.SysFont('Consolas', 14, bold=True)
                for stair in self.pixel_ruins_map.stairs:
                    rect = world_rect_to_screen(stair['rect'])
                    pygame.draw.rect(self.screen, (255, 165, 65), rect, 3)
                    text = debug_font.render(f"T{stair['from_floor']} -> T{stair['to_floor']}", True, (255, 165, 65))
                    self.screen.blit(text, (rect.x + 4, rect.y + 4))
                    for line, color, label in ((stair['start_line'], (85, 255, 170), 'A'), (stair['end_line'], (255, 95, 145), 'B')):
                        start, end = world_to_screen(*line[0]), world_to_screen(*line[1])
                        pygame.draw.line(self.screen, color, start, end, 5)
                        self.screen.blit(debug_font.render(label, True, (20, 20, 20)), (start[0] + 4, start[1] + 4))

            # Green: enemy hurtboxes; blue/orange: P1/P2 hurtboxes.
            for sprite in self.all_sprites:
                if hasattr(sprite, 'hurtbox') and getattr(sprite, 'hp', 0) > 0:
                    r = sprite.hurtbox
                    color = (0, 255, 0)
                    if sprite in self.players:
                        color = (70, 210, 255) if sprite is self.players[0] else (255, 180, 65)
                    pygame.draw.rect(self.screen, color, world_rect_to_screen(r), 2)
                    if hasattr(sprite, 'map_region_floor') and sprite.map_region_floor is not None:
                        label = pygame.font.SysFont('Consolas', 13, bold=True).render(f"T{sprite.map_region_floor}", True, color)
                        self.screen.blit(label, (world_rect_to_screen(r).x, world_rect_to_screen(r).y - 14))
            # Red: player attack hitboxes
            for hb in self.attacks:
                r = hb.rect
                pygame.draw.rect(self.screen, (255, 0, 0), world_rect_to_screen(r), 2)
            # Magenta: enemy attack hitboxes
            for hb in self.enemy_attacks:
                r = hb.rect
                pygame.draw.rect(self.screen, (255, 0, 255), world_rect_to_screen(r), 2)
            # Cyan: final active collision pieces used by the movement code.
            for wall in self.map_collision_rects:
                pygame.draw.rect(self.screen, (0, 220, 255), world_rect_to_screen(wall), 2)
            if world_mode:
                label = debug_font.render(
                    f'DEBUG MAP  F3: hide | Red: zone | Cyan: active | Purple: tunnel | Yellow: boundary | Orange: stairs | Floor T{self.current_floor} | F5: reload ({len(self.map_collision_rects)})',
                    True, (255, 255, 255),
                )
                panel = pygame.Surface((min(WIDTH - 20, label.get_width() + 16), 26), pygame.SRCALPHA)
                panel.fill((10, 15, 24, 205))
                self.screen.blit(panel, (10, HEIGHT - 32))
                self.screen.blit(label, (18, HEIGHT - 28))
        # -----------------------------------------------


        # Draw damage number popups on top of everything
        for dmg in self.damage_numbers:
            image = scale_world_image(dmg.image)
            if world_mode:
                center_x, center_y = world_to_screen(dmg.rect.centerx, dmg.rect.centery)
                x = round(center_x - image.get_width() / 2)
                y = round(center_y - image.get_height() / 2)
            else:
                x, y = world_to_screen(dmg.rect.x, dmg.rect.y)
            self.screen.blit(image, (x, y))

        # HUD: player HP (drawn without camera offset)
        for idx, player in enumerate(self.players):
            label = "P1" if idx == 0 else "P2"
            # P1 is left-aligned; P2 mirrors it against the right screen edge.
            offset = 0 if idx == 0 else WIDTH - 240
            self.draw_player_resource_bars(player, offset=offset, label=label)

        # HUD: Knight ultimate cooldown indicator
        if any(isinstance(player, Knight) and player.hp > 0 for player in self.players):
            self.draw_knight_ultimate_hud()
        self.draw_archer_arrow_hud()

        # Boss HP bar
        if self.selected_phase == 1 and self.boss_spawned:
            for e in self.enemies:
                if isinstance(e, GoblinTank) and e.hp > 0:
                    self.draw_boss_health_bar(e.hp, e.max_hp, "GOBLIN TANK")
                    break
        elif self.selected_phase == 3:
            for e in self.enemies:
                if isinstance(e, DeathBringer) and e.hp > 0:
                    self.draw_boss_health_bar(e.hp, e.max_hp, "DEATH BRINGER")
                    break
                elif isinstance(e, FatCultist) and e.hp > 0:
                    self.draw_boss_health_bar(e.hp, e.max_hp, "FAT CULTIST")
                    break

        # Skill frames UI (bottom corners)
        self.draw_skill_frames()

        # GAME OVER UI
        if all(player.hp <= 0 for player in self.players):
            font = pygame.font.SysFont('Arial', 64, bold=True)
            text = font.render("GAME OVER", True, (255, 0, 0))
            text_rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 50))
            self.screen.blit(text, text_rect)
            
            font_sub = pygame.font.SysFont('Arial', 32)
            sub_text = font_sub.render("Press 'R' to Restart", True, (255, 255, 255))
            sub_rect = sub_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))
            self.screen.blit(sub_text, sub_rect)

        if self.paused:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))

            font = pygame.font.SysFont('Arial', 56, bold=True)
            title = font.render("PAUSED", True, (255, 230, 120))
            self.screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 22)))

            hint_font = pygame.font.SysFont('Arial', 24)
            hint = hint_font.render("Press ESC to continue", True, (245, 245, 245))
            self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 34)))
            self.draw_pause_ability_panels()

        pygame.display.flip()

    def draw_pause_ability_panels(self):
        """Show each player's Poison Vial points and upgrade choices."""
        panel_w, panel_h = 410, 166
        panel_y = HEIGHT // 2 + 76
        title_font = pygame.font.SysFont('Arial', 20, bold=True)
        text_font = pygame.font.SysFont('Arial', 17)
        small_font = pygame.font.SysFont('Arial', 14)

        for index, player in enumerate(self.players[:2]):
            self._ensure_player_abilities(player)
            x = 34 if index == 0 else WIDTH - panel_w - 34
            panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            panel.fill((24, 35, 30, 235))
            pygame.draw.rect(panel, (95, 220, 115), panel.get_rect(), 2, border_radius=8)

            name = 'P1 KNIGHT' if index == 0 else 'P2 ARCHER'
            points = player.ability_points
            panel.blit(title_font.render(f"{name}  |  Poison Vials: {points}", True, (230, 255, 220)), (14, 12))
            panel.blit(small_font.render(f"Max level per stat: {ABILITY_MAX_LEVEL}", True, (180, 205, 180)), (14, 39))

            levels = player.ability_levels
            key_labels = ('1', '2', '3') if index == 0 else ('7', '8', '9')
            rows = [
                ('Attack', f"+{ABILITY_ATTACK_BONUS_PER_LEVEL} damage", 'attack'),
                ('Armor', f"+{ABILITY_ARMOR_BONUS_PER_LEVEL} max armor", 'armor'),
                ('Speed', f"+{ABILITY_SPEED_BONUS_PER_LEVEL:g} move speed", 'speed'),
            ]
            for row_index, (label, bonus, key) in enumerate(rows):
                level = levels[key]
                color = (255, 230, 130) if level < ABILITY_MAX_LEVEL else (145, 145, 145)
                line = f"[{key_labels[row_index]}] {label:<6} Lv.{level}/{ABILITY_MAX_LEVEL}  {bonus}"
                panel.blit(text_font.render(line, True, color), (16, 65 + row_index * 29))

            self.screen.blit(panel, (x, panel_y))

    def draw_health_bar(self, hp, max_hp, offset=0, label="P1"):
        w = 200
        h = 24
        x = 10 + offset
        y = 10
        ratio = max(0, hp) / max_hp
        font = pygame.font.SysFont('Arial', 16, bold=True)
        label_surf = font.render(label, True, (255, 255, 255))
        self.screen.blit(label_surf, (x, y + 30))
        pygame.draw.rect(self.screen, (60, 60, 60), (x - 2, y - 2, w + 4, h + 4))
        pygame.draw.rect(self.screen, (180, 40, 40), (x, y, w, h))
        pygame.draw.rect(self.screen, (60, 220, 90), (x, y, int(w * ratio), h))
        if hp <= 0:
            dead_surf = font.render("DEAD", True, (255, 80, 80))
            self.screen.blit(dead_surf, (x + 10, y + 2))

    def draw_player_resource_bars(self, player, offset=0, label="P1"):
        self._ensure_player_resources(player)
        x = 10 + offset
        y = 10
        w = 220
        h = 16

        font = pygame.font.SysFont('Arial', 14, bold=True)
        name = font.render(label, True, (255, 255, 255))
        self.screen.blit(name, (x, y - 2))

        def _draw_bar(by, ratio, bg, fg, text):
            pygame.draw.rect(self.screen, (45, 45, 45), (x - 2, by - 2, w + 4, h + 4))
            pygame.draw.rect(self.screen, bg, (x, by, w, h))
            pygame.draw.rect(self.screen, fg, (x, by, int(w * max(0.0, min(1.0, ratio))), h))
            txt = font.render(text, True, (235, 235, 235))
            self.screen.blit(txt, (x + 6, by + 1))

        hp_ratio = max(0.0, float(player.hp) / max(1.0, float(player.max_hp)))
        armor_ratio = max(0.0, float(player.armor) / max(1.0, float(player.max_armor)))
        mana_ratio = max(0.0, float(player.mana) / max(1.0, float(player.max_mana)))

        _draw_bar(y + 16, hp_ratio, (130, 32, 32), (62, 218, 110), f"HP {int(player.hp)}/{int(player.max_hp)}")
        _draw_bar(y + 36, armor_ratio, (35, 52, 70), (95, 165, 235), f"ARMOR {int(player.armor)}/{int(player.max_armor)}")
        _draw_bar(y + 56, mana_ratio, (35, 40, 90), (110, 120, 255), f"MANA {int(player.mana)}/{int(player.max_mana)}")

        if player.hp <= 0:
            dead_surf = font.render("DEAD", True, (255, 80, 80))
            self.screen.blit(dead_surf, (x + 8, y + 17))
        elif self._is_berserk_active(player):
            remaining = max(0.0, (player.berserk_until - pygame.time.get_ticks()) / 1000.0)
            ratio = max(0.0, min(1.0, remaining * 1000.0 / BERSERK_VIAL_DURATION_MS))
            buff_y = y + 78
            pygame.draw.rect(self.screen, (55, 25, 25), (x, buff_y, w, 11))
            pygame.draw.rect(self.screen, (225, 60, 45), (x, buff_y, int(w * ratio), 11))
            pygame.draw.rect(self.screen, (255, 145, 105), (x, buff_y, w, 11), 1)
            buff = font.render(f"BERSERK {remaining:.1f}s", True, (255, 225, 210))
            self.screen.blit(buff, (x + 6, buff_y - 2))

        if self._active_passive(player) == 'holy':
            remaining = max(0.0, (player.holy_effect_until - pygame.time.get_ticks()) / 1000.0)
            ratio = max(0.0, min(1.0, remaining * 1000.0 / HOLY_EFFECT_DURATION_MS))
            holy_y = y + (94 if self._is_berserk_active(player) else 78)
            pygame.draw.rect(self.screen, (55, 48, 18), (x, holy_y, w, 11))
            pygame.draw.rect(self.screen, (255, 210, 45), (x, holy_y, int(w * ratio), 11))
            pygame.draw.rect(self.screen, (255, 245, 170), (x, holy_y, w, 11), 1)
            holy = font.render(f"HOLY {remaining:.1f}s", True, (255, 255, 220))
            self.screen.blit(holy, (x + 6, holy_y - 2))

    def draw_knight_ultimate_hud(self):
        """Draw a golden circular ultimate-cooldown indicator for the Knight.

        Positioned just to the right of the HP bar.  When the ultimate is
        ready the ring glows bright gold; while on cooldown a grey arc shows
        the remaining wait time and a gold fill arc shows what has recharged.
        """
        from config import KNIGHT_ULTIMATE_COOLDOWN
        cx, cy = 240, 21   # centre of the indicator circle
        radius  = 18
        thickness = 4

        knight = next((player for player in self.players if isinstance(player, Knight)), None)
        if knight is None:
            return
        cd = max(0.0, getattr(knight, 'ultimate_cooldown', 0))
        ready = cd <= 0

        if ready:
            # Bright golden full ring + glow
            pygame.draw.circle(self.screen, (255, 200, 40), (cx, cy), radius + 3, 1)
            pygame.draw.circle(self.screen, (255, 200, 40), (cx, cy), radius, thickness + 1)
            pygame.draw.circle(self.screen, (255, 240, 120), (cx, cy), radius - thickness, 0)
        else:
            # Dark background disc
            pygame.draw.circle(self.screen, (40, 40, 40), (cx, cy), radius, 0)
            # Grey "empty" arc
            pygame.draw.circle(self.screen, (100, 100, 100), (cx, cy), radius, thickness)
            # Gold "filled" arc representing progress (drawn as a series of lines)
            progress = 1.0 - cd / KNIGHT_ULTIMATE_COOLDOWN
            import math as _m
            start_angle = -_m.pi / 2          # 12 o'clock
            sweep       = 2 * _m.pi * progress
            steps       = max(1, int(60 * progress))
            for i in range(steps + 1):
                angle = start_angle + sweep * i / max(1, steps)
                px = int(cx + radius * _m.cos(angle))
                py = int(cy + radius * _m.sin(angle))
                pygame.draw.circle(self.screen, (220, 160, 20), (px, py), thickness // 2 + 1)

        # Label
        font_ult = pygame.font.SysFont('Arial', 11, bold=True)
        label_color = (255, 230, 80) if ready else (160, 140, 60)
        lbl = font_ult.render("ULTIMATE [L]", True, label_color)
        self.screen.blit(lbl, lbl.get_rect(center=(cx, cy + radius + 9)))

    def draw_archer_arrow_hud(self):
        archer = next((player for player in self.players if isinstance(player, Archer)), None)
        if archer is None:
            return
        cfg = ARCHER_ARROW_CONFIG.get(getattr(archer, 'arrow_type', 'normal'), ARCHER_ARROW_CONFIG['normal'])
        font = pygame.font.SysFont('Arial', 15, bold=True)
        text = font.render(f"P2 ARROW: {cfg['label']}  [0] Change", True, cfg['hud_color'])
        self.screen.blit(text, (510, 12))

    def draw_boss_health_bar(self, hp, max_hp, boss_name="BOSS"):
        """Draw a large boss health bar at the bottom of the screen."""
        bar_w = 400
        bar_h = 14
        x = (WIDTH - bar_w) // 2
        y = HEIGHT - 40
        ratio = max(0, hp) / max_hp

        # Label
        font = pygame.font.SysFont('Arial', 18, bold=True)
        label = font.render(boss_name, True, (255, 200, 100))
        self.screen.blit(label, label.get_rect(center=(WIDTH // 2, y - 14)))

        # Bar background
        pygame.draw.rect(self.screen, (40, 40, 40), (x - 2, y - 2, bar_w + 4, bar_h + 4))
        # Red base
        pygame.draw.rect(self.screen, (180, 30, 30), (x, y, bar_w, bar_h))
        # Orange fill
        pygame.draw.rect(self.screen, (220, 120, 20), (x, y, int(bar_w * ratio), bar_h))

    def draw_skill_frames(self):
        """Draw 3-slot skill bars using prebuilt bar frame + target overlay assets."""
        native_h = max(self._skill_frame_img.get_height() + self._skill_frame_native_top,
                       self._skill_target_img.get_height())
        bar_w = int(self._skill_frame_img.get_width() * self._skill_ui_scale)
        bar_h = int(native_h * self._skill_ui_scale)
        margin_x = self._skill_margin_x
        margin_y = self._skill_margin_y
        y = HEIGHT - bar_h - margin_y

        if len(self.players) > 0:
            self._draw_player_skill_bar(
                self.players[0],
                x=margin_x,
                y=y,
                bar_key='p1',
                label="P1 N:Target M:Use"
            )

        if len(self.players) > 1:
            self._draw_player_skill_bar(
                self.players[1],
                x=WIDTH - bar_w - margin_x,
                y=y,
                bar_key='p2',
                label="P2 7:Target 8:Use"
            )

    def _draw_player_skill_bar(self, player, x, y, bar_key, label):
        skills = getattr(player, 'skills', [])[:3]
        if skills:
            player.target_skill_idx = max(0, min(player.target_skill_idx, len(skills) - 1))
        else:
            player.target_skill_idx = 0

        bar_cfg = self._skill_bar_cfg.get(bar_key, self._skill_bar_cfg['p1'])
        reverse = bool(bar_cfg.get('reverse', False))

        native_w = self._skill_frame_img.get_width()
        native_h = max(self._skill_frame_img.get_height() + self._skill_frame_native_top,
                       self._skill_target_img.get_height())
        native_bar = pygame.Surface((native_w, native_h), pygame.SRCALPHA)

        # Draw the complete frame block first at original ratio.
        native_bar.blit(self._skill_frame_img, (0, self._skill_frame_native_top))

        for display_slot_idx in range(3):
            inv_idx = (2 - display_slot_idx) if reverse else display_slot_idx
            if inv_idx >= len(skills):
                continue

            slot_cx = self._skill_slot_centers[display_slot_idx]
            slot_cy = self._skill_slot_center_y

            icon_scale = bar_cfg.get('icon_scales', [1.0, 1.0, 1.0])[inv_idx]
            icon_size = max(1, int(self._skill_slot_pitch * self._skill_icon_ratio * icon_scale))
            icon = self._get_skill_icon(skills[inv_idx], icon_size=icon_size)
            icon_off = bar_cfg.get('icon_offsets', [[0, 0], [0, 0], [0, 0]])[inv_idx]
            ix = slot_cx - icon.get_width() // 2
            iy = slot_cy - icon.get_height() // 2 + int(icon_off[1])
            ix += int(icon_off[0])
            native_bar.blit(icon, (ix, iy))

            if inv_idx == player.target_skill_idx:
                target_scale = bar_cfg.get('target_scales', [1.0, 1.0, 1.0])[inv_idx]
                tw = max(1, int(round(self._skill_target_img.get_width() * target_scale)))
                th = max(1, int(round(self._skill_target_img.get_height() * target_scale)))
                target_img = pygame.transform.scale(self._skill_target_img, (tw, th))
                target_off = bar_cfg.get('target_offsets', [[0, 0], [0, 0], [0, 0]])[inv_idx]
                tx = slot_cx - target_img.get_width() // 2 + int(target_off[0])
                ty = int(target_off[1])
                native_bar.blit(target_img, (tx, ty))

        scaled_w = int(native_w * self._skill_ui_scale)
        scaled_h = int(native_h * self._skill_ui_scale)
        scaled_bar = pygame.transform.scale(native_bar, (scaled_w, scaled_h))
        self.screen.blit(scaled_bar, (x, y))

        font = pygame.font.SysFont('Arial', 12, bold=True)
        info = font.render(label, True, (230, 230, 230))
        self.screen.blit(info, (x, y - 15))

        active = self._active_passive(player) or "none"
        active_font = pygame.font.SysFont('Arial', 11)
        active_txt = active_font.render(f"Active: {active}", True, (220, 210, 180))
        self.screen.blit(active_txt, (x, y + self._skill_frame_img.get_height() + 2))
