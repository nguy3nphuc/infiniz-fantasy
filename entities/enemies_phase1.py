import pygame
import random
import math
from sprites import Animator, load_character_animations
from config import (MIN_X, MAX_X, MIN_Y, MAX_Y, ENEMY_ATTACK_OFFSET_Y,
                    DEATH_FADE_DELAY, DEATH_FADE_DURATION,
                    GOBLIN_WARRIOR_ATTACK_RANGE_X, GOBLIN_WARRIOR_ATTACK_RANGE_Y,
                    GOBLIN_SPEARMAN_ATTACK_RANGE_X, GOBLIN_SPEARMAN_ATTACK_RANGE_Y,
                    GOBLIN_TANK_ATTACK_RANGE_X, GOBLIN_TANK_ATTACK_RANGE_Y,
                    GOBLIN_TANK_ATTACK_2_RANGE_X, GOBLIN_TANK_ATTACK_2_RANGE_Y, SPEAR_IMAGE)
from .core import HealthMixin, _hurtbox_from_config, AttackHitbox

class Spear(pygame.sprite.Sprite):
    SPEAR_SCALE = 2.0

    def __init__(self, x, y, target_x, target_y, damage=10):
        super().__init__()
        try:
            raw = pygame.image.load(SPEAR_IMAGE).convert_alpha()
            sw = int(raw.get_width() * self.SPEAR_SCALE)
            sh = int(raw.get_height() * self.SPEAR_SCALE)
            self.image = pygame.transform.scale(raw, (sw, sh))
        except Exception:
            self.image = pygame.Surface((40, 6))
            self.image.fill((150, 150, 150))

        direction = pygame.math.Vector2(target_x - x, target_y - y)
        if direction.length() > 0:
            direction = direction.normalize()
        else:
            direction = pygame.math.Vector2(1, 0)
        self.vel = direction * 10
        
        angle = math.degrees(math.atan2(-direction.y, direction.x))
        self.image = pygame.transform.rotate(self.image, angle)
        self.rect = self.image.get_rect(center=(x, y))
        self.damage = damage

    @property
    def y(self):
        """Vertical screen position of the projectile centre."""
        return self.rect.centery

    @property
    def floor_y(self):
        """Ground-plane projection: the Y row this spear travels on."""
        return self.rect.centery + 25

    def update(self, dt):
        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)
        from config import WIDTH, HEIGHT
        if self.rect.right < 0 or self.rect.left > WIDTH or self.rect.bottom < 0 or self.rect.top > HEIGHT:
            self.kill()



class GoblinWarrior(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=50)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 1.5
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.combo_step = 0
        # Death fade-out state
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=30, default_h=96, default_ox=10)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('goblin_warrior')
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
            # Knock back away from the damage source
            if source_x is not None:
                knockback_dir = 1 if self.rect.centerx > source_x else -1
            else:
                knockback_dir = -self.facing
            self.vel.x = knockback_dir * 1.8
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0  # getting hit breaks the combo
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        # Handle death state first
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

        # Handle hurt timer
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

            if self.hurt_timer <= 0:
                if getattr(self, 'animator', None) is not None:
                    self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        # Handle combo attack states
        current_attack = self.animator.state
        if current_attack in ('attack1', 'attack2'):
            # Spawn attack hitbox at the designated hit frame
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                damage = {1: 8, 2: 12}.get(self.combo_step, 8)
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True

            self.update_animation(dt)
            if self.animator.is_finished():
                # Check if player is still in range for combo continuation
                dist_x = player.hurtbox.centerx - self.hurtbox.centerx
                dist_y = player.hurtbox.bottom - self.hurtbox.bottom
                in_range = abs(dist_x) <= GOBLIN_WARRIOR_ATTACK_RANGE_X and abs(dist_y) <= GOBLIN_WARRIOR_ATTACK_RANGE_Y

                if in_range and self.combo_step < 2:
                    # Chain to next combo step
                    self.combo_step += 1
                    state_name = f'attack{self.combo_step}'
                    self.animator.set_state(state_name, reset=True)
                    self.has_attacked = False
                else:
                    # Combo finished or player moved away
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)
                    self.ai_state = 'wait'
                    self.ai_timer = random.randint(500, 1000)
            return

        # AI Behavior State Machine
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

        # CHASE state logic
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

            range_x = GOBLIN_WARRIOR_ATTACK_RANGE_X
            range_y = GOBLIN_WARRIOR_ATTACK_RANGE_Y

            if abs(real_dist_x) > range_x or abs(real_dist_y) > range_y:
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    if dist_y < 0:
                        self.rect.y -= self.speed
                    else:
                        self.rect.y += self.speed
                    moving = True

                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                # In range to attack — start combo
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

        # Clamp position
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


class GoblinSpearman(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=40)
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
        # Death fade-out state
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=28, default_h=96, default_ox=-15)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('goblin_spearman')
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
            # Knock back away from the damage source
            if source_x is not None:
                knockback_dir = 1 if self.rect.centerx > source_x else -1
            else:
                knockback_dir = -self.facing
            self.vel.x = knockback_dir * 2.0
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        # Handle death state first
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

        # Handle hurt timer
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

            if self.hurt_timer <= 0:
                if getattr(self, 'animator', None) is not None:
                    self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        # Handle attack state
        if self.animator.state == 'attack':
            # Spawn spear at frame 6
            if self.animator.frame_index == 6 and not self.has_attacked:
                spear = Spear(self.rect.centerx, self.rect.centery, player.rect.centerx, player.rect.centery)
                spear.owner = self
                if 'enemy_projectiles' in groups:
                    groups['enemy_projectiles'].add(spear)
                self.has_attacked = True

            self.update_animation(dt)
            if self.animator.is_finished():
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'wait'
                self.ai_timer = random.randint(800, 1500)
            return

        # AI Behavior State Machine
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

        # CHASE state logic
        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            from config import WIDTH
            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            dist = math.hypot(dx, dy)
            
            in_range = False
            if dist <= WIDTH / 2:
                angle = math.degrees(math.atan2(dy, dx))
                facing_angle = 0 if self.facing == 1 else 180
                diff = (angle - facing_angle + 180) % 360 - 180
                if abs(diff) <= 60:
                    in_range = True

            if not in_range:
                # Move toward player
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
                    if dist_y < 0:
                        self.rect.y -= self.speed
                    else:
                        self.rect.y += self.speed
                    moving = True

                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                # In range to attack
                if pygame.time.get_ticks() - self.attack_timer > 2000:
                    self.animator.set_state('attack', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        # Clamp position
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


class GoblinTank(pygame.sprite.Sprite, HealthMixin):
    is_boss = True  # Boss enemies are immune to knight ultimate knockback
    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=250)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 0.6
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.combo_step = 0
        self.jump_dx = 0
        self.jump_dy = 0
        self.jump_exact_x = 0.0
        self.jump_exact_y = 0.0
        # Death fade-out state
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=44, default_h=128, default_ox=10)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox
        # Camera shake state
        self.camera_shake_triggered = False
        self._last_shake_frame = -1
        self.shake_frames = {
            'attack2': {4, 9},
            'death': {3, 6, 9, 14},
            'jump': {2, 10},
            'run': {1, 5, 7},
        }

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('goblin_tank')

        # Truncate run to 8 frames: frames 0-7 are the run loop, 8+ is stopping
        if 'run' in anim_config and len(anim_config['run']['frames']) > 8:
            anim_config['run']['frames'] = anim_config['run']['frames'][:8]

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
            stun_immune = False
            current_state = self.animator.state if getattr(self, 'animator', None) is not None else None
            
            if current_state in ('jump', 'attack1', 'attack2'):
                stun_immune = True
            elif current_state == 'idle':
                if not is_crit:
                    stun_immune = True
                    
            if stun_immune:
                # Still notify bar even if animation stun is skipped
                if self.health_bar is not None:
                    self.health_bar.notify_damage(self.hp)
                return

            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            # Knock back away from the damage source
            if source_x is not None:
                knockback_dir = 1 if self.rect.centerx > source_x else -1
            else:
                knockback_dir = -self.facing
            self.vel.x = knockback_dir * 1.0  # very heavy, minimal knockback
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0  # getting hit breaks the combo
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        # Handle death state first
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

        # Handle hurt timer
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.85  # heavier, slower decel
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

            if self.hurt_timer <= 0:
                if getattr(self, 'animator', None) is not None:
                    self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        # Handle attack and jump states
        current_state = self.animator.state
        if current_state == 'jump':
            frame = self.animator.frame_index
            if 3 <= frame <= 9:
                self.jump_exact_x += self.jump_dx * (dt / 16.666)
                self.jump_exact_y += self.jump_dy * (dt / 16.666)
                int_x = int(self.jump_exact_x)
                int_y = int(self.jump_exact_y)
                self.rect.x += int_x
                self.rect.y += int_y
                self.jump_exact_x -= int_x
                self.jump_exact_y -= int_y
            self.update_animation(dt)
            if self.animator.is_finished():
                self.combo_step = 1
                self.animator.set_state('attack1', reset=True)
                self.has_attacked = False
                self.attack_timer = pygame.time.get_ticks()
            return

        if current_state in ('attack1', 'attack2'):
            if current_state == 'attack2':
                frame = self.animator.frame_index
                if 4 <= frame <= 8:
                    self.jump_exact_x += self.jump_dx * (dt / 16.666)
                    self.jump_exact_y += self.jump_dy * (dt / 16.666)
                    int_x = int(self.jump_exact_x)
                    int_y = int(self.jump_exact_y)
                    self.rect.x += int_x
                    self.rect.y += int_y
                    self.jump_exact_x -= int_x
                    self.jump_exact_y -= int_y

            # Spawn attack hitbox at the designated hit frame(s)
            if self.animator.is_at_hit_frame():
                if not self.has_attacked:
                    damage = 25 if current_state == 'attack2' else 15
                    self._spawn_enemy_attack_hitbox(groups, damage)
                    self.has_attacked = True
            else:
                self.has_attacked = False

            self.update_animation(dt)
            if self.animator.is_finished():
                # Check if player is still in range for combo continuation
                dist_x = player.hurtbox.centerx - self.hurtbox.centerx
                dist_y = player.hurtbox.bottom - self.hurtbox.bottom
                # Use base range to determine if we should chain into attack2
                in_range = abs(dist_x) <= GOBLIN_TANK_ATTACK_RANGE_X and abs(dist_y) <= GOBLIN_TANK_ATTACK_RANGE_Y

                if in_range and self.combo_step < 2 and current_state == 'attack1':
                    # Chain to next combo step
                    self.combo_step += 1
                    state_name = f'attack{self.combo_step}'
                    self.animator.set_state(state_name, reset=True)
                    self.has_attacked = False
                    self.jump_dx = 0
                    self.jump_dy = 0
                else:
                    # Combo finished or player moved away
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)
                    self.ai_state = 'wait'
                    self.ai_timer = random.randint(1000, 2000)
            return

        # AI Behavior State Machine
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

        # CHASE state logic
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

            range_x = GOBLIN_TANK_ATTACK_RANGE_X
            range_y = GOBLIN_TANK_ATTACK_RANGE_Y

            is_out_of_range = (real_dist_x**2) / (range_x**2) + (real_dist_y**2) / (range_y**2) > 1
            
            jump_range_x = range_x * 3
            jump_range_y = range_y * 3
            is_within_jump_range = (real_dist_x**2) / (jump_range_x**2) + (real_dist_y**2) / (jump_range_y**2) <= 1

            if is_out_of_range:
                if is_within_jump_range and pygame.time.get_ticks() - self.attack_timer > 3000:
                    choice = random.choice(['jump', 'jump_slam'])
                    self.attack_timer = pygame.time.get_ticks()
                    self.has_attacked = False
                    self.facing = 1 if real_dist_x > 0 else -1
                    self.jump_exact_x = 0.0
                    self.jump_exact_y = 0.0
                    
                    if choice == 'jump':
                        self.animator.set_state('jump', reset=True)
                        self.jump_dx = real_dist_x / 40.0
                        self.jump_dy = real_dist_y / 40.0
                    else:
                        self.combo_step = 2
                        self.animator.set_state('attack2', reset=True)
                        self.jump_dx = real_dist_x / 30.0
                        self.jump_dy = real_dist_y / 30.0
                else:
                    if abs(dist_x) > 5:
                        if dist_x < 0:
                            self.rect.x -= self.speed
                            self.facing = -1
                        else:
                            self.rect.x += self.speed
                            self.facing = 1
                        moving = True
                    if abs(dist_y) > 5:
                        if dist_y < 0:
                            self.rect.y -= self.speed
                        else:
                            self.rect.y += self.speed
                        moving = True

                    if random.random() < 0.005:
                        self.ai_state = 'idle'
                        self.ai_timer = random.randint(1000, 2000)
            else:
                # In range to attack — start combo
                if pygame.time.get_ticks() - self.attack_timer > 2500:
                    self.combo_step = 1
                    self.animator.set_state('attack1', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack1', 'attack2', 'jump', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        # Clamp position
        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)

            # Check for camera shake trigger
            self.camera_shake_triggered = False
            current_state = self.animator.state
            current_frame = self.animator.frame_index
            if current_state in self.shake_frames:
                if current_frame in self.shake_frames[current_state] and current_frame != self._last_shake_frame:
                    self.camera_shake_triggered = True
                    self._last_shake_frame = current_frame
                elif current_frame != self._last_shake_frame:
                    self._last_shake_frame = current_frame

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
        w = entry.get('hitbox_w', w or 70)
        h = entry.get('hitbox_h', h or 60)
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

