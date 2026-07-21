import pygame
import random
import math
from sprites import Animator, load_character_animations
from config import (MIN_X, MAX_X, MIN_Y, MAX_Y, ENEMY_ATTACK_OFFSET_Y,
                    DEATH_FADE_DELAY, DEATH_FADE_DURATION,
                    LIZARDMAN_ATTACK_RANGE_X, LIZARDMAN_ATTACK_RANGE_Y,
                    CYCLOP_ATTACK_RANGE_X, CYCLOP_ATTACK_RANGE_Y, CYCLOP_SPECIAL_COOLDOWN,
                    KOBOLD_ATTACK_RANGE_X, KOBOLD_ATTACK_RANGE_Y,
                    KOBOLD_DASH_RANGE_X, KOBOLD_DASH_RANGE_Y, KOBOLD_DASH_COOLDOWN,
                    FIREWORM_ATTACK_RANGE, FIREBALL_SPEED)
from .core import HealthMixin, _hurtbox_from_config, AttackHitbox

class Lizardman(pygame.sprite.Sprite, HealthMixin):
    """Standard 2-hit melee combo enemy. Same pattern as GoblinWarrior."""

    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=50)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 1.3
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.combo_step = 0
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=32, default_h=90, default_ox=0)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('lizardman')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            knockback_dir = 1 if (source_x is not None and self.rect.centerx > source_x) else -1
            self.vel.x = knockback_dir * 1.8
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        current_attack = self.animator.state
        if current_attack in ('attack1', 'attack2'):
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                damage = {1: 8, 2: 12}.get(self.combo_step, 8)
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True
            self.update_animation(dt)
            if self.animator.is_finished():
                dist_x = player.hurtbox.centerx - self.hurtbox.centerx
                dist_y = player.hurtbox.bottom - self.hurtbox.bottom
                in_range = abs(dist_x) <= LIZARDMAN_ATTACK_RANGE_X and abs(dist_y) <= LIZARDMAN_ATTACK_RANGE_Y
                if in_range and self.combo_step < 2:
                    self.combo_step += 1
                    self.animator.set_state(f'attack{self.combo_step}', reset=True)
                    self.has_attacked = False
                else:
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)
                    self.ai_state = 'wait'
                    self.ai_timer = random.randint(500, 1000)
            return

        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
                self.target_offset = pygame.math.Vector2(random.randint(-50, 50), random.randint(-25, 25))
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        if self.ai_state == 'idle':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            target_x = player.rect.centerx + self.target_offset.x
            target_y = player.rect.bottom + self.target_offset.y
            dist_x = target_x - self.rect.centerx
            dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
            real_dist_x = player.rect.centerx - self.rect.centerx
            real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)

            if abs(real_dist_x) > LIZARDMAN_ATTACK_RANGE_X or abs(real_dist_y) > LIZARDMAN_ATTACK_RANGE_Y:
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    self.rect.y += self.speed if dist_y > 0 else -self.speed
                    moving = True
                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                if pygame.time.get_ticks() - self.attack_timer > 1500:
                    self.combo_step = 1
                    self.animator.set_state('attack1', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack1', 'attack2', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _spawn_enemy_attack_hitbox(self, groups, damage, w=None, h=None, state=None):
        """Spawn an enemy melee attack hitbox, reading size from metadata when possible."""
        sn = state or getattr(self.animator, 'state', None)
        entry = self.animator.states_config.get(sn, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w = entry.get('hitbox_w', w or 50)
        h = entry.get('hitbox_h', h or 46)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        
        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0
        self.combo_step = 0


# ── Phase 1 New Monster: Cyclop ───────────────────────────────────────────────

class Cyclop(pygame.sprite.Sprite, HealthMixin):
    """Heavy melee enemy. attack1 is the normal attack. attack2 is a powerful
    special attack gated behind CYCLOP_SPECIAL_COOLDOWN. Stun-immune during
    attack2 and triggers a camera shake."""

    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=120)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 0.8
        self.facing = -1
        self.attack_timer = 0
        self.special_attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.combo_step = 0
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=44, default_h=110, default_ox=0)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox
        self.camera_shake_triggered = False

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('cyclop')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if self.animator.state == 'attack2':
                if self.health_bar is not None:
                    self.health_bar.notify_damage(self.hp)
                return
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            knockback_dir = 1 if (source_x is not None and self.rect.centerx > source_x) else -1
            self.vel.x = knockback_dir * 1.0
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.85
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        current_attack = self.animator.state
        if current_attack in ('attack1', 'attack2'):
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                if current_attack == 'attack2':
                    damage = 25
                    self.camera_shake_triggered = True
                else:
                    damage = 15
                    self.camera_shake_triggered = False
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True
            else:
                self.camera_shake_triggered = False
            self.update_animation(dt)
            if self.animator.is_finished():
                self.combo_step = 0
                self.camera_shake_triggered = False
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'wait'
                self.ai_timer = random.randint(800, 1500)
            return

        self.camera_shake_triggered = False
        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
                self.target_offset = pygame.math.Vector2(random.randint(-50, 50), random.randint(-25, 25))
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        if self.ai_state == 'idle':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            target_x = player.rect.centerx + self.target_offset.x
            target_y = player.rect.bottom + self.target_offset.y
            dist_x = target_x - self.rect.centerx
            dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
            real_dist_x = player.rect.centerx - self.rect.centerx
            real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)

            if abs(real_dist_x) > CYCLOP_ATTACK_RANGE_X or abs(real_dist_y) > CYCLOP_ATTACK_RANGE_Y:
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    self.rect.y += self.speed if dist_y > 0 else -self.speed
                    moving = True
                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                now = pygame.time.get_ticks()
                if now - self.attack_timer > 2000:
                    special_ready = (now - self.special_attack_timer) > CYCLOP_SPECIAL_COOLDOWN
                    use_special = special_ready and random.random() < 0.35
                    if use_special:
                        self.animator.set_state('attack2', reset=True)
                        self.special_attack_timer = now
                    else:
                        self.animator.set_state('attack1', reset=True)
                    self.has_attacked = False
                    self.attack_timer = now

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack1', 'attack2', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _spawn_enemy_attack_hitbox(self, groups, damage, w=None, h=None, state=None):
        """Spawn an enemy melee attack hitbox, reading size from metadata when possible."""
        sn = state or getattr(self.animator, 'state', None)
        entry = self.animator.states_config.get(sn, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w = entry.get('hitbox_w', w or 60)
        h = entry.get('hitbox_h', h or 55)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        
        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0
        self.combo_step = 0


# ── Phase 1 New Monster: Kobold (Assassin) ────────────────────────────────────

class Kobold(pygame.sprite.Sprite, HealthMixin):
    """Assassin enemy with a cooldown-gated dash special attack.
    AI states:
      'chase'         -- walk toward player
      'dash_special'  -- lunge animation + hitbox, moves toward player during frames
      'jump_escape'   -- jump animation, moves away to reset distance
      'attack'        -- 3-hit normal melee combo (attack1 -> attack2 -> attack3)
      'wait'/'idle'   -- brief pause after attacks
    """

    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=35)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 2.0
        self.facing = -1
        self.attack_timer = 0
        self.dash_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-20, 20), random.randint(-10, 10))
        self.has_attacked = False
        self.combo_step = 0
        self.dash_exact_x = 0.0
        self.dash_exact_y = 0.0
        self.dash_dx = 0.0
        self.dash_dy = 0.0
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=26, default_h=72, default_ox=0)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('kobold')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if self.animator.state in ('dash', 'dash_special', 'jump'):
                self.ai_state = 'chase'
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            knockback_dir = 1 if (source_x is not None and self.rect.centerx > source_x) else -1
            self.vel.x = knockback_dir * 2.5
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'chase'
            self.update_animation(dt)
            return

        current_state = self.animator.state

        # Dash movement
        if current_state == 'dash':
            # move towards player during dash animation
            self.dash_exact_x += self.dash_dx * (dt / 16.666)
            self.dash_exact_y += self.dash_dy * (dt / 16.666)
            int_x = int(self.dash_exact_x)
            int_y = int(self.dash_exact_y)
            self.rect.x += int_x
            self.rect.y += int_y
            self.dash_exact_x -= int_x
            self.dash_exact_y -= int_y

            self.update_animation(dt)
            if self.animator.is_finished():
                self.animator.set_state('dash_special', reset=True)
                self.has_attacked = False
                self.dash_exact_x = 0.0
                self.dash_exact_y = 0.0
                # turn around to attack the player
                if player is not None:
                    dist_to_player = player.rect.centerx - self.rect.centerx
                    self.facing = 1 if dist_to_player > 0 else -1
                else:
                    self.facing = -self.facing
            return

        # Dash special attack (no movement, just the strike)
        if current_state == 'dash_special':
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                self._spawn_enemy_attack_hitbox(groups, 18)
                self.has_attacked = True

            self.update_animation(dt)
            if self.animator.is_finished():
                self.ai_state = 'jump_escape'
                self.animator.set_state('jump', reset=True)
                self.dash_exact_x = 0.0
                self.dash_exact_y = 0.0
                self.dash_dx = -self.facing * 3.5
                self.dash_dy = 0.0
            return

        # Jump escape
        if current_state == 'jump' and self.ai_state == 'jump_escape':
            self.dash_exact_x += self.dash_dx * (dt / 16.666)
            int_x = int(self.dash_exact_x)
            self.rect.x += int_x
            self.dash_exact_x -= int_x
            self.update_animation(dt)
            if self.animator.is_finished():
                self.ai_state = 'wait'
                self.ai_timer = random.randint(400, 800)
                self.animator.set_state('idle', reset=False)
            return

        # Normal melee combo
        if current_state in ('attack1', 'attack2', 'attack3'):
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                damage = {1: 8, 2: 10, 3: 12}.get(self.combo_step, 8)
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True
            self.update_animation(dt)
            if self.animator.is_finished():
                dist_x = player.hurtbox.centerx - self.hurtbox.centerx
                dist_y = player.hurtbox.bottom - self.hurtbox.bottom
                in_range = abs(dist_x) <= KOBOLD_ATTACK_RANGE_X and abs(dist_y) <= KOBOLD_ATTACK_RANGE_Y
                if in_range and self.combo_step < 3:
                    self.combo_step += 1
                    self.animator.set_state(f'attack{self.combo_step}', reset=True)
                    self.has_attacked = False
                else:
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)
                    self.ai_state = 'wait'
                    self.ai_timer = random.randint(400, 800)
            return

        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
                self.target_offset = pygame.math.Vector2(random.randint(-20, 20), random.randint(-10, 10))
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        if self.ai_state == 'idle':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            real_dist_x = player.rect.centerx - self.rect.centerx
            real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
            target_x = player.rect.centerx + self.target_offset.x
            target_y = player.rect.bottom + self.target_offset.y
            dist_x = target_x - self.rect.centerx
            dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
            now = pygame.time.get_ticks()

            # Melee range - normal combo
            if abs(real_dist_x) <= KOBOLD_ATTACK_RANGE_X and abs(real_dist_y) <= KOBOLD_ATTACK_RANGE_Y:
                if now - self.attack_timer > 1200:
                    self.combo_step = 1
                    self.animator.set_state('attack1', reset=True)
                    self.has_attacked = False
                    self.attack_timer = now

            # Dash range - dash special if cooldown ready
            elif abs(real_dist_x) <= KOBOLD_DASH_RANGE_X and abs(real_dist_y) <= KOBOLD_DASH_RANGE_Y:
                if (now - self.dash_timer) > KOBOLD_DASH_COOLDOWN:
                    # Dash EXACTLY behind the player based on PLAYER's facing
                    player_facing = getattr(player, 'facing', 1)
                    overshoot = 100
                    target_x = player.rect.centerx - (player_facing * overshoot)
                    target_dist_x = target_x - self.rect.centerx
                    
                    self.facing = 1 if target_dist_x > 0 else -1
                    self.dash_exact_x = 0.0
                    self.dash_exact_y = 0.0
                    
                    total_frames_approx = len(self.animator.states.get('dash', [1]))
                    duration_ms = self.animator.durations.get('dash', 100)
                    total_time_ms = max(total_frames_approx * duration_ms, 1)
                    total_ticks = total_time_ms / 16.666
                    
                    self.dash_dx = target_dist_x / total_ticks
                    self.dash_dy = real_dist_y / total_ticks
                    self.animator.set_state('dash', reset=True)
                    self.has_attacked = False
                    self.dash_timer = now
                    self.ai_timer = 0
                else:
                    # Dash on cooldown - walk toward player
                    if abs(dist_x) > 5:
                        if dist_x < 0:
                            self.rect.x -= self.speed
                            self.facing = -1
                        else:
                            self.rect.x += self.speed
                            self.facing = 1
                        moving = True
                    if abs(dist_y) > 5:
                        self.rect.y += self.speed if dist_y > 0 else -self.speed
                        moving = True
            else:
                # Out of dash range - just chase
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    self.rect.y += self.speed if dist_y > 0 else -self.speed
                    moving = True
                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(800, 1500)

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack1', 'attack2', 'attack3',
                                            'dash', 'dash_special', 'jump', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _spawn_enemy_attack_hitbox(self, groups, damage, w=None, h=None, state=None):
        """Spawn an enemy melee attack hitbox, reading size from metadata when possible."""
        sn = state or getattr(self.animator, 'state', None)
        entry = self.animator.states_config.get(sn, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w = entry.get('hitbox_w', w or 45)
        h = entry.get('hitbox_h', h or 42)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        
        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0
        self.combo_step = 0


# ── Phase 1 New Monster: Fireworm (Ranged) ────────────────────────────────────

class Fireworm(pygame.sprite.Sprite, HealthMixin):
    """Ranged enemy that throws fireballs. Same logic as GoblinSpearman but
    uses FIREWORM_ATTACK_RANGE (shorter) and spawns animated Fireball."""

    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=30)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 1.0
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=30, default_h=70, default_ox=0)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox
        self._fireball_frame = 12

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('fireworm')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            knockback_dir = 1 if (source_x is not None and self.rect.centerx > source_x) else -1
            self.vel.x = knockback_dir * 2.0
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        if self.animator.state == 'attack':
            if self.animator.frame_index == self._fireball_frame and not self.has_attacked:
                fb = Fireball(self.rect.centerx, self.rect.centery,
                              player.rect.centerx, player.rect.centery)
                fb.owner = self
                if 'enemy_projectiles' in groups:
                    groups['enemy_projectiles'].add(fb)
                self.has_attacked = True
            self.update_animation(dt)
            if self.animator.is_finished():
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'wait'
                self.ai_timer = random.randint(1000, 2000)
            return

        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
                self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        if self.ai_state == 'idle':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            dist = math.hypot(dx, dy)

            if dist > FIREWORM_ATTACK_RANGE:
                target_x = player.rect.centerx + self.target_offset.x
                target_y = player.rect.bottom + self.target_offset.y
                dist_x = target_x - self.rect.centerx
                dist_y = target_y - self.rect.bottom
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    self.rect.y += self.speed if dist_y > 0 else -self.speed
                    moving = True
                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                if pygame.time.get_ticks() - self.attack_timer > 2500:
                    self.animator.set_state('attack', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0


# ── Fireball animated projectile ─────────────────────────────────────────────

class Fireball(pygame.sprite.Sprite):
    """Animated fireball projectile spawned by Fireworm.
    Plays the 'move' animation loop while travelling, and 'explosion'
    on impact (handled externally; this sprite self-kills off-screen)."""

    def __init__(self, x, y, target_x, target_y, damage=12):
        super().__init__()
        anim_config = load_character_animations('fireball')
        self.animator = Animator.from_config(anim_config)
        self.animator.set_state('move', reset=True)
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(center=(x, y))
        self.damage = damage

        direction = pygame.math.Vector2(target_x - x, target_y - y)
        if direction.length() > 0:
            direction = direction.normalize()
        else:
            direction = pygame.math.Vector2(1, 0)
        self.vel = direction * FIREBALL_SPEED
        self.facing = 1 if direction.x >= 0 else -1

    @property
    def y(self):
        return self.rect.centery

    @property
    def floor_y(self):
        return self.rect.centery + 20

    def update(self, dt):
        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)
        self.animator.update(dt)
        frame = self.animator.get_frame()
        if self.facing == -1:
            frame = pygame.transform.flip(frame, True, False)
        center = self.rect.center
        self.image = frame
        self.rect = self.image.get_rect(center=center)
        from config import WIDTH, HEIGHT
        if self.rect.right < 0 or self.rect.left > WIDTH or self.rect.bottom < 0 or self.rect.top > HEIGHT:
            self.kill()
