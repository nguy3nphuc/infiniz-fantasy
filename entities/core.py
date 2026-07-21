import pygame
import os
import random
from config import (DAMAGE_FONT_PATH, DAMAGE_NUMBER_DURATION, DAMAGE_NUMBER_RISE_SPEED,
                    DAMAGE_NUMBER_CRIT_FONT_SIZE, DAMAGE_NUMBER_FONT_SIZE,
                    RESOURCE_MAX_ARMOR_CAP, RESOURCE_MAX_MANA_CAP,
                    RESOURCE_DEFAULT_ARMOR_RATIO, RESOURCE_DEFAULT_MANA_RATIO,
                    DEFAULT_ARMOR_REDUCTION_PCT)

def _hurtbox_from_config(anim_config, default_w=40, default_h=80, default_ox=0):
    """Extract hurtbox dimensions from the metadata-driven animation config.

    ``load_character_animations`` stamps ``hurtbox_w``, ``hurtbox_h``, and
    ``hurtbox_offset_x`` onto every animation entry from the character-level
    metadata.  We read them from the first available state here so entities
    don't need to hard-code these values.
    """
    for entry in anim_config.values():
        if isinstance(entry, dict) and 'hurtbox_w' in entry:
            return (entry['hurtbox_w'],
                    entry['hurtbox_h'],
                    entry.get('hurtbox_offset_x', default_ox))
    return (default_w, default_h, default_ox)


class HealthMixin:
    def __init__(self, max_hp, max_armor=None, max_mana=None, armor_reduction_pct=0.25):
        self.max_hp = max_hp
        self.hp = max_hp

        # Shared resource fields for all entities (players + enemies).
        if max_armor is None:
            max_armor = max(0, min(RESOURCE_MAX_ARMOR_CAP, int(max_hp * RESOURCE_DEFAULT_ARMOR_RATIO)))
        if max_mana is None:
            max_mana = max(0, min(RESOURCE_MAX_MANA_CAP, int(max_hp * RESOURCE_DEFAULT_MANA_RATIO)))

        self.max_armor = int(max_armor)
        self.armor = float(self.max_armor)
        self.armor_reduction_pct = max(0.0, min(0.9, float(armor_reduction_pct if armor_reduction_pct is not None else DEFAULT_ARMOR_REDUCTION_PCT)))
        self.max_mana = int(max_mana)
        self.mana = float(self.max_mana)

        # EnemyHealthBar is defined later in this module but is always available
        # at runtime when enemy instances are created.
        self.health_bar = EnemyHealthBar(max_hp)

    def _ensure_health_bar(self):
        """No-op kept for compatibility; bar is now created in __init__."""
        pass

    def take_damage(self, amount, source_x=None, is_crit=False):
        # ignore damage if already dead
        if self.hp <= 0:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        # Notify the health bar about the new HP so catchup resets properly.
        # We call this even on death so the bar reflects 0 before fade-out.
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def on_death(self):
        self.kill()

    def _get_true_pivot(self):
        """Returns the true visual pivot point (x, y) of the character on screen."""
        if not hasattr(self, 'rect'):
            return (0, 0)
        foot_x = self.rect.midbottom[0] - getattr(self, 'current_pdx', 0)
        foot_y = self.rect.midbottom[1] - getattr(self, 'current_pdy', 0)
        
        animator = getattr(self, 'animator', None)
        if not animator:
            return (foot_x, foot_y)
            
        sn = getattr(animator, 'state', None)
        entry = getattr(animator, 'states_config', {}).get(sn, {})
        idle_mb_ox = entry.get('idle_mb_ox', 0)
        idle_mb_oy = entry.get('idle_mb_oy', 0)
        
        if getattr(self, 'facing', 1) == 1:
            return foot_x + idle_mb_ox, foot_y + idle_mb_oy
        else:
            return foot_x - idle_mb_ox, foot_y + idle_mb_oy

base_dir = os.path.dirname(os.path.dirname(__file__))
_HEALTH_BAR_DIR = os.path.join(base_dir, 'assets', 'monster_health_bar')

class EnemyHealthBar:
    """Sprite-based health bar with a smooth delayed catch-up animation.

    Layer order (bottom → top):
        1. no_health.png  – empty bar background
        2. health_catchup.png  – orange catch-up indicator
        3. health.png  – actual current HP (red)

    Usage::

        # In enemy update():
        if self.health_bar:
            self.health_bar.update(dt)

        # In the draw loop:
        if enemy.health_bar:
            enemy.health_bar.draw(surface, enemy, camera_offset)
    """

    # Vertical distance above the hurtbox top where the bar is centred.
    VERTICAL_OFFSET = 30  # pixels above hurtbox.top

    # How long (ms) after a hit before the catch-up bar starts shrinking.
    CATCHUP_DELAY = 200  # ms

    # Speed at which catchup_ratio moves toward current_ratio each ms.
    # Expressed as a fraction per ms (e.g. 0.004 = 0.4 % per ms).
    CATCHUP_SPEED = 0.004  # ratio/ms  → full drain in ~250 ms

    def __init__(self, max_hp: int):
        self.max_hp = max_hp
        self.current_hp: float = float(max_hp)

        # Displayed ratios  (0.0 – 1.0)
        self.display_ratio: float = 1.0   # health bar width
        self.catchup_ratio: float = 1.0   # catch-up bar width

        # Catch-up delay countdown (counts down from CATCHUP_DELAY to 0 in ms)
        self.catchup_timer: float = 0.0

        # Load and cache images (class-level cache to avoid re-loading per enemy)
        self._bg, self._catchup, self._health = self._load_images()

        # Natural width of the bar sprites (they should all be identical)
        self._bar_width: int = self._bg.get_width()
        self._bar_height: int = self._bg.get_height()

    # ── Class-level image cache ────────────────────────────────────────────────

    _image_cache: dict = {}

    @classmethod
    def _load_images(cls):
        if cls._image_cache:
            return cls._image_cache['bg'], cls._image_cache['catchup'], cls._image_cache['health']

        def _load(name):
            path = os.path.join(_HEALTH_BAR_DIR, name)
            try:
                return pygame.image.load(path).convert_alpha()
            except Exception:
                # Fallback 1px solid colour strip if asset is missing
                surf = pygame.Surface((80, 8), pygame.SRCALPHA)
                colour = {'health.png': (200, 0, 0),
                          'health_catchup.png': (230, 140, 0),
                          'no_health.png': (40, 40, 40)}.get(name, (80, 80, 80))
                surf.fill(colour)
                return surf

        cls._image_cache['bg']      = _load('no_health.png')
        cls._image_cache['catchup'] = _load('health_catchup.png')
        cls._image_cache['health']  = _load('health.png')
        return cls._image_cache['bg'], cls._image_cache['catchup'], cls._image_cache['health']

    # ── Public API ─────────────────────────────────────────────────────────────

    def notify_damage(self, new_hp: float):
        """Called immediately when the enemy's HP changes.

        Updates display_ratio instantly; resets the catch-up delay so the
        orange bar holds for CATCHUP_DELAY ms before chasing.
        The catch-up bar's *current visual position* is never snapped —
        it continues smoothly from wherever it currently is.
        """
        self.current_hp = max(0.0, float(new_hp))
        self.display_ratio = self.current_hp / self.max_hp if self.max_hp > 0 else 0.0
        # Reset delay so the player sees the orange segment for a moment.
        self.catchup_timer = self.CATCHUP_DELAY

    def update(self, dt: float):
        """Advance catch-up animation.  Call every frame with dt in ms."""
        if self.catchup_timer > 0:
            self.catchup_timer -= dt
            return  # hold — do not shrink yet

        # Once the delay expires, lerp catchup_ratio toward display_ratio.
        target = self.display_ratio
        if self.catchup_ratio > target:
            step = self.CATCHUP_SPEED * dt
            self.catchup_ratio = max(target, self.catchup_ratio - step)
        else:
            self.catchup_ratio = target  # snap if somehow overshot

    def draw(self, surface: pygame.Surface, enemy, camera_offset=(0, 0)):
        """Render the three-layer health bar above the enemy.

        Anchored to enemy.hurtbox.  Falls back to enemy.rect if no hurtbox.
        """
        hurtbox = getattr(enemy, 'hurtbox', enemy.rect)
        ox, oy = camera_offset

        bar_x = hurtbox.centerx - self._bar_width // 2 + ox
        bar_y = hurtbox.top - self.VERTICAL_OFFSET + oy

        # 1. Background (full width, always)
        surface.blit(self._bg, (bar_x, bar_y))

        # 2. Catch-up bar (cropped to catchup_ratio)
        catchup_w = int(self._bar_width * max(0.0, self.catchup_ratio))
        if catchup_w > 0:
            src_rect = pygame.Rect(0, 0, catchup_w, self._bar_height)
            surface.blit(self._catchup, (bar_x, bar_y), src_rect)

        # 3. Current HP bar (cropped to display_ratio)
        health_w = int(self._bar_width * max(0.0, self.display_ratio))
        if health_w > 0:
            src_rect = pygame.Rect(0, 0, health_w, self._bar_height)
            surface.blit(self._health, (bar_x, bar_y), src_rect)

class AttackHitbox(pygame.sprite.Sprite):
    def __init__(self, owner, rect, damage=10, duration=150):
        super().__init__()
        self.owner = owner
        self.image = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        self.image.fill((255, 0, 0, 80))
        self.rect = pygame.Rect(rect)
        self.damage = damage
        self.spawn_time = pygame.time.get_ticks()
        self.duration = duration
        self.already_hit_targets = set()

    def update(self, dt):
        if pygame.time.get_ticks() - self.spawn_time > self.duration:
            self.kill()

class DamageNumber(pygame.sprite.Sprite):
    """Floating damage number that pops up when an enemy takes damage.
    Normal hits: red, standard size.
    Critical hits: red, larger font with a brief scale-up pop effect.
    """
    _font_cache = {}  # class-level cache so the font is only loaded once per size

    @classmethod
    def _get_font(cls, size):
        if size not in cls._font_cache:
            try:
                cls._font_cache[size] = pygame.font.Font(DAMAGE_FONT_PATH, size)
            except Exception:
                cls._font_cache[size] = pygame.font.SysFont('Arial', size, bold=True)
        return cls._font_cache[size]

    def __init__(self, x, y, damage, is_crit=False):
        super().__init__()
        self.is_crit = is_crit
        self.elapsed = 0
        self.duration = DAMAGE_NUMBER_DURATION
        self.rise_speed = DAMAGE_NUMBER_RISE_SPEED
        self.float_x = float(x + random.randint(-10, 10))
        self.float_y = float(y - 20)

        # Choose font size and text
        if is_crit:
            font_size = DAMAGE_NUMBER_CRIT_FONT_SIZE
            self.text = str(damage) + "!"
            top_color = (180, 0, 0)
            bottom_color = (255, 80, 80)
        else:
            font_size = DAMAGE_NUMBER_FONT_SIZE
            self.text = str(damage)
            top_color = (130, 0, 0)
            bottom_color = (255, 120, 120)

        self.font = self._get_font(font_size)
        
        # Pre-render the decorated text surface
        text_mask = self.font.render(self.text, True, (255, 255, 255))
        w, h = text_mask.get_size()
        
        # Gradient
        grad_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for yy in range(h):
            ratio = yy / max(1, h - 1)
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
            pygame.draw.line(grad_surf, (r, g, b, 255), (0, yy), (w, yy))
        
        # Multiply gradient by the text's alpha mask
        grad_surf.blit(text_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        
        # Shadow
        shadow_offset = 1

        shadow = self.font.render(self.text, True, (30, 30, 30))
        shadow.set_alpha(120)

        self.base_image = pygame.Surface(
            (w + shadow_offset, h + shadow_offset),
            pygame.SRCALPHA
        )

        # Shadow phía dưới bên phải
        self.base_image.blit(shadow, (shadow_offset, shadow_offset))

        # Text chính
        self.base_image.blit(grad_surf, (0, 0))

        # Pop scale animation for crits: starts bigger, shrinks to 1.0
        self.scale = 1.6 if is_crit else 1.0
        self.target_scale = 1.0

        self._render()

    def _render(self):
        """Render the text surface with current scale and alpha."""
        base = self.base_image
        if self.scale != 1.0:
            w = max(1, int(base.get_width() * self.scale))
            h = max(1, int(base.get_height() * self.scale))
            base = pygame.transform.scale(base, (w, h))

        # Apply fade-out and shrink animation
        progress = self.elapsed / self.duration
        # Start fading at 50% of duration
        if progress > 0.5:
            fade_progress = (progress - 0.5) / 0.5
            alpha = max(0, int(255 * (1.0 - fade_progress)))
            self.scale = max(0.1, self.target_scale * (1.0 - fade_progress * 0.8))
        else:
            alpha = 255

        if alpha < 255:
            base = base.copy()
            base.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)

        self.image = base
        self.rect = self.image.get_rect(center=(int(self.float_x), int(self.float_y)))

    def update(self, dt):
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.kill()
            return

        # Float upward initially, but float down when phasing out
        progress = self.elapsed / self.duration
        if progress > 0.5:
            self.float_y += self.rise_speed * 1.5
        else:
            self.float_y -= self.rise_speed

        # Ease scale back to 1.0 for crit pop effect
        if self.scale > self.target_scale:
            self.scale = max(self.target_scale, self.scale - 0.04)

        self._render()

