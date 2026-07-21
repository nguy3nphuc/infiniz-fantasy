import pygame
import math
from config import (ABILITY_MAX_LEVEL, ABILITY_ATTACK_BONUS_PER_LEVEL,
                    ABILITY_ARMOR_BONUS_PER_LEVEL, ABILITY_SPEED_BONUS_PER_LEVEL)

class HealthPotion(pygame.sprite.Sprite):
    def __init__(self, x, y, heal_amount=30, lifetime=10000):
        super().__init__()
        self.heal_amount = heal_amount
        self.lifetime = lifetime
        self.spawn_time = pygame.time.get_ticks()

        # Load image
        try:
            raw_img = pygame.image.load("assets/items/potions/blue.png").convert_alpha()
            self.image = pygame.transform.scale(raw_img, (24,24))
        except Exception:
            self.image = pygame.Surface((20,24))
            self.image.fill((50,255,50))

        self.rect = self.image.get_rect(midbottom=(x,y))
        self.base_y = float(self.rect.y)
        self.float_timer = 0

    @property
    def foot_y(self):
        return self.rect.bottom
    
    def update(self, dt):
        # Auto destroy
        if pygame.time.get_ticks() - self.spawn_time > self.lifetime:
            self.kill()
            return

        # Floating effects
        self.float_timer += dt * 0.005
        self.rect.y = int(self.base_y + math.sin(self.float_timer) * 5)


class AbilityVial(pygame.sprite.Sprite):
    """Green Poison Vial dropped by enemies; grants one ability point."""

    def __init__(self, x, y, lifetime=15000):
        super().__init__()
        self.lifetime = lifetime
        self.spawn_time = pygame.time.get_ticks()
        try:
            raw_img = pygame.image.load("assets/items/potions/green.png").convert_alpha()
            self.image = pygame.transform.scale(raw_img, (26, 26))
        except Exception:
            self.image = pygame.Surface((22, 26), pygame.SRCALPHA)
            self.image.fill((80, 230, 90, 230))

        self.rect = self.image.get_rect(midbottom=(x, y))
        self.base_y = float(self.rect.y)
        self.float_timer = 0

    @property
    def foot_y(self):
        return self.rect.bottom

    def update(self, dt):
        if pygame.time.get_ticks() - self.spawn_time > self.lifetime:
            self.kill()
            return
        self.float_timer += dt * 0.005
        self.rect.y = int(self.base_y + math.sin(self.float_timer) * 7)


class BerserkVial(pygame.sprite.Sprite):
    """Red pickup that temporarily increases damage at an armor cost."""

    def __init__(self, x, y, lifetime=12000):
        super().__init__()
        self.lifetime = lifetime
        self.spawn_time = pygame.time.get_ticks()
        try:
            raw_img = pygame.image.load("assets/items/potions/red.png").convert_alpha()
            self.image = pygame.transform.scale(raw_img, (26, 26))
        except Exception:
            self.image = pygame.Surface((22, 26), pygame.SRCALPHA)
            self.image.fill((245, 75, 65, 230))

        self.rect = self.image.get_rect(midbottom=(x, y))
        self.base_y = float(self.rect.y)
        self.float_timer = 0

    @property
    def foot_y(self):
        return self.rect.bottom

    def update(self, dt):
        if pygame.time.get_ticks() - self.spawn_time > self.lifetime:
            self.kill()
            return
        self.float_timer += dt * 0.006
        self.rect.y = int(self.base_y + math.sin(self.float_timer) * 7)


class SkillIcon(pygame.sprite.Sprite):
    """Skill icon that drops from enemies when they die.
    Can be picked up by the player to add to their skill inventory."""
    
    SKILL_TYPES = {
        'fire': 'assets/skills/icons/fire.png',
        'water_ball': 'assets/skills/icons/water_ball.png',
        'ice': 'assets/skills/icons/water_ball.png',
        'wind': 'assets/skills/icons/wind.png',
        'holy': 'assets/skills/icons/holy.png',
        'light': 'assets/skills/icons/light.png',
        'dark': 'assets/skills/icons/dark.png',
        'smoke': 'assets/skills/icons/smoke.png',
        'wood': 'assets/skills/icons/wood.png',
        'earth': 'assets/skills/icons/earth.png',
        'acid': 'assets/skills/icons/acid.png',
        'shield': 'assets/skills/icons/shield.png',
        'thunder': 'assets/skills/icons/thunder.png',
        'water_blast': 'assets/skills/icons/water_blast.png',
    }
    
    def __init__(self, x, y, skill_type='fire', lifetime=15000):
        super().__init__()
        if skill_type == 'ice':
            skill_type = 'water_ball'
        self.skill_type = skill_type
        self.lifetime = lifetime
        self.spawn_time = pygame.time.get_ticks()
        
        # Load image
        try:
            icon_path = self.SKILL_TYPES.get(skill_type, self.SKILL_TYPES['fire'])
            raw_img = pygame.image.load(icon_path).convert_alpha()
            self.image = pygame.transform.scale(raw_img, (32, 32))
        except Exception:
            self.image = pygame.Surface((32, 32), pygame.SRCALPHA)
            self.image.fill((255, 100, 100, 200))
        
        self.rect = self.image.get_rect(midbottom=(x, y))
        self.base_y = float(self.rect.y)
        self.float_timer = 0
        self.rotation = 0
    
    @property
    def foot_y(self):
        return self.rect.bottom
    
    def update(self, dt):
        # Auto destroy
        if pygame.time.get_ticks() - self.spawn_time > self.lifetime:
            self.kill()
            return
        
        # Floating and rotation effects
        self.float_timer += dt * 0.005
        self.rect.y = int(self.base_y + math.sin(self.float_timer) * 8)
        self.rotation = (self.rotation + dt * 0.3) % 360
        
class BloodVFX(pygame.sprite.Sprite):
    """Spawns blood effects when an enemy is hit or dies."""
    
    _hit_cache = None
    _death_cache = None
    
    def __init__(self, x, y, facing, foot_y, vfx_type="hit"):
        super().__init__()
        self.frame_duration = 50
        self.timer = 0
        self.frame_index = 0
        self._custom_floor_y = foot_y + 10  # Force it to draw in front of the entity
        
        if vfx_type == "death":
            frames = self._get_death_frames()
        else:
            frames = self._get_hit_frames()
            
        if not frames:
            self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
            self._frames = []
        else:
            self._frames = frames
            # Reverse if facing == 1 per user request
            if facing == 1:
                self._frames = [pygame.transform.flip(f, True, False) for f in frames]
                
            self.image = self._frames[0]
            
        # Move the blood effect slightly to the back of the entity
        x_offset = -facing * 40
        self.rect = self.image.get_rect(center=(x + x_offset, y))

    @property
    def floor_y(self):
        return self._custom_floor_y

    @classmethod
    def _get_hit_frames(cls):
        if cls._hit_cache is not None:
            return cls._hit_cache
        try:
            sheet = pygame.image.load("assets/vfx/hit_blood_vfx.png").convert_alpha()
            frames = [sheet.subsurface((i * 110, 0, 110, 93)) for i in range(5)]
            # Scale up the blood
            cls._hit_cache = [pygame.transform.scale(f, (int(f.get_width() * 1.5), int(f.get_height() * 1.5))) for f in frames]
        except Exception:
            cls._hit_cache = []
        return cls._hit_cache

    @classmethod
    def _get_death_frames(cls):
        if cls._death_cache is not None:
            return cls._death_cache
        try:
            sheet = pygame.image.load("assets/vfx/death_blood_vfx.png").convert_alpha()
            frames = [sheet.subsurface((i * 110, 0, 110, 93)) for i in range(9)]
            # Scale up the blood
            cls._death_cache = [pygame.transform.scale(f, (int(f.get_width() * 1.5), int(f.get_height() * 1.5))) for f in frames]
        except Exception:
            cls._death_cache = []
        return cls._death_cache
        
    def update(self, dt):
        if not self._frames:
            self.kill()
            return
            
        self.timer += dt
        if self.timer >= self.frame_duration:
            self.timer -= self.frame_duration
            self.frame_index += 1
            if self.frame_index >= len(self._frames):
                self.kill()
            else:
                self.image = self._frames[self.frame_index]

class HitVFX(pygame.sprite.Sprite):
    """Spawns generic hit flash effects when an entity is struck."""
    
    _frames_cache = None
    
    def __init__(self, x, y, facing, foot_y):
        super().__init__()
        self.frame_duration = 40
        self.timer = 0
        self.frame_index = 0
        self._custom_floor_y = foot_y + 12  # Force it to draw in front
        
        frames = self._get_frames()
        if not frames:
            self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
            self._frames = []
        else:
            self._frames = frames
            # Reverse if facing == 1 per user request
            if facing == 1:
                self._frames = [pygame.transform.flip(f, True, False) for f in frames]
            self.image = self._frames[0]
            
        self.rect = self.image.get_rect(center=(x, y))

    @property
    def floor_y(self):
        return self._custom_floor_y

    @classmethod
    def _get_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache
        try:
            sheet = pygame.image.load("assets/vfx/hit_vfx.png").convert_alpha()
            # 336x48 -> 7 frames of 48x48
            frames = [sheet.subsurface((i * 48, 0, 48, 48)) for i in range(7)]
            # Scale it up
            cls._frames_cache = [pygame.transform.scale(f, (int(f.get_width() * 1.5), int(f.get_height() * 1.5))) for f in frames]
        except Exception:
            cls._frames_cache = []
        return cls._frames_cache
        
    def update(self, dt):
        if not self._frames:
            self.kill()
            return
            
        self.timer += dt
        if self.timer >= self.frame_duration:
            self.timer -= self.frame_duration
            self.frame_index += 1
            if self.frame_index >= len(self._frames):
                self.kill()
            else:
                self.image = self._frames[self.frame_index]
