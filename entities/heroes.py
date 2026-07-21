import pygame
import random
from sprites import Animator, load_character_animations
from config import (MIN_X, MAX_X, MIN_Y, MAX_Y,
                    KNIGHT_ULTIMATE_DAMAGE, KNIGHT_ULTIMATE_KNOCKBACK,
                    KNIGHT_ULTIMATE_COOLDOWN, KNIGHT_ULTIMATE_CAST_FRAME,
                    ARCHER_ULTIMATE_DAMAGE, ARCHER_ULTIMATE_SPEED,
                    ARCHER_ULTIMATE_COOLDOWN, ARCHER_ULTIMATE_CAST_FRAME,
                    PLAYER_RESOURCE_PRESETS, ARCHER_ARROW_CONFIG,
                    DASH_SMOKE_IMAGE, ULTIMATE_EFFECT_IMAGE)
from .core import HealthMixin, _hurtbox_from_config, AttackHitbox

class KnightUltimateShockwave(pygame.sprite.Sprite):
    """A massive ground shockwave spawned at the peak of the Knight's ultimate.

    The shockwave covers a wide area in the knight's facing direction and deals
    KNIGHT_ULTIMATE_DAMAGE.  Every enemy struck receives an enormous knockback
    (KNIGHT_ULTIMATE_KNOCKBACK) so they are blasted far across the screen.
    The hitbox lives for 250 ms — long enough to catch enemies stepping into it.

    Collision tracking (already_hit_targets) ensures each enemy is damaged only
    once per shockwave.  The game.py loop uses the 'knight_shockwaves' group to
    drive collision resolution.
    """

    DURATION = 250   # ms the hitbox stays alive

    def __init__(self, owner_hurtbox, facing, damage, knockback):
        super().__init__()
        self.damage   = damage
        self.knockback = knockback
        self.facing   = facing
        self.spawn_time = pygame.time.get_ticks()
        self.already_hit_targets: set = set()

        # Massive oval range around the knight (flat on the ground)
        w = 500
        h = 180

        # Place the shockwave centered on the knight's feet
        hb_x = owner_hurtbox.centerx - w // 2
        hb_y = owner_hurtbox.bottom - h // 2

        self.rect = pygame.Rect(hb_x, hb_y, w, h)

        # Visual: a translucent golden-white flash
        self.image = pygame.Surface((w, h), pygame.SRCALPHA)
        # Draw a radial-style glow — bright centre, fades to edges
        centre_color  = (255, 240, 120, 200)
        edge_color    = (255, 160,  40,   0)
        mid_x, mid_y  = w // 2, h // 2
        
        # Draw concentric ellipses fading outward
        steps = 50
        for i in range(steps, 0, -1):
            t = i / steps
            alpha = int(edge_color[3] + (centre_color[3] - edge_color[3]) * (1 - t))
            cr = int(edge_color[0] + (centre_color[0] - edge_color[0]) * (1 - t))
            cg = int(edge_color[1] + (centre_color[1] - edge_color[1]) * (1 - t))
            cb = int(edge_color[2] + (centre_color[2] - edge_color[2]) * (1 - t))
            
            ew = int(w * t)
            eh = int(h * t)
            if ew <= 0 or eh <= 0:
                continue
                
            ex = mid_x - ew // 2
            ey = mid_y - eh // 2
            
            pygame.draw.ellipse(self.image, (cr, cg, cb, alpha), (ex, ey, ew, eh))
            
        # Draw a sharp, visible boundary outline so the player can clearly see the oval edge
        pygame.draw.ellipse(self.image, (255, 200, 50, 180), (0, 0, w, h), max(3, w//150))

    @property
    def floor_y(self):
        return self.rect.centery

    def can_hit(self, enemy):
        return id(enemy) not in self.already_hit_targets

    def collides_with(self, enemy):
        """Check if enemy's hurtbox center is within the shockwave's ellipse."""
        # Check bounding rect first for efficiency
        if not self.rect.colliderect(enemy.hurtbox):
            return False
            
        cx, cy = self.rect.center
        a = self.rect.width / 2
        b = self.rect.height / 2
        
        if a <= 0 or b <= 0:
            return False
            
        ex, ey = enemy.hurtbox.center
        dx = ex - cx
        dy = ey - cy
        
        return (dx * dx) / (a * a) + (dy * dy) / (b * b) <= 1.0

    def register_hit(self, enemy):
        self.already_hit_targets.add(id(enemy))

    def update(self, dt):
        elapsed = pygame.time.get_ticks() - self.spawn_time
        # Fade out the visual as the hitbox expires
        ratio = max(0.0, 1.0 - elapsed / self.DURATION)
        alpha = int(255 * ratio)
        self.image.set_alpha(alpha)
        if elapsed >= self.DURATION:
            self.kill()

class Knight(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(200, 300)):
        pygame.sprite.Sprite.__init__(self)
        _preset = PLAYER_RESOURCE_PRESETS.get('knight', {})
        HealthMixin.__init__(
            self,
            max_hp=1000000000,
            max_armor=_preset.get('max_armor', 70),
            max_mana=_preset.get('max_mana', 100),
            armor_reduction_pct=_preset.get('armor_reduction_pct', 0.40),
        )
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 4
        self.facing = 1
        self.on_ground = True
        self.controls = {
            'left': [pygame.K_a],
            'right': [pygame.K_d],
            'up': [pygame.K_w],
            'down': [pygame.K_s],
            'attack': [pygame.K_j, pygame.K_u],
            'defend': [pygame.K_k, pygame.K_i],
            'ultimate': [pygame.K_l, pygame.K_o],
        }
        self.attack_cooldown = 0
        self.hurt_timer = 0
        self.combo_step = 0
        self.combo_buffered = False
        self.exceeded_combo = False
        self.combo_break_timer = 0
        self.attack_pressed_last = False
        self.has_attacked = False # flag to ensure damage is dealt only once at midpoint
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config,
            default_w=50, default_h=85, default_ox=20)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

        # -- Ultimate --
        self.ultimate_cooldown = 0
        self.ultimate_pressed_last = False
        self._ultimate_shockwave_spawned = False
        
        # -- Skills Inventory --
        self.skills = []  # List of skill types that have been picked up
        self.active_skill = None  # Currently selected skill (if any)
        self.target_skill_idx = 0  # Selected skill slot index (0..2)

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def _is_control_pressed(self, control_name, keys):
        for key in self.controls.get(control_name, []):
            if keys[key]:
                return True
        return False

    def load_assets(self):
        anim_config = load_character_animations('knight')

        # --- Split run into start (frame 0) and loop (frames 1-N) ---
        # Frame 0 is the start-run pose; it plays once then hands off to
        # run_loop which loops frames 1-N continuously.
        if 'run' in anim_config:
            run_info = anim_config.pop('run')
            run_frames = run_info['frames']
            run_dur = run_info.get('duration', 100)
            if len(run_frames) > 1:
                anim_config['run_start'] = {
                    'frames': run_frames[:1], 'duration': run_dur, 'loop': False
                }
                anim_config['run_loop'] = {
                    'frames': run_frames[1:], 'duration': run_dur, 'loop': True
                }
            else:
                anim_config['run_start'] = {
                    'frames': run_frames, 'duration': run_dur, 'loop': True
                }
                anim_config['run_loop'] = {
                    'frames': run_frames, 'duration': run_dur, 'loop': True
                }

        # --- Split defend (11 frames) into four sub-states ---
        # Layout:
        #   Frames  0-4  (5 frames) : startup / enter-defend sequence
        #   Frame   4    (hold)     : defend_idle holds on this frame
        #   Frames  5-8  (4 frames) : block-impact reaction
        #   Frames  9-10 (2 frames) : return to idle
        if 'defend' in anim_config:
            defend_info = anim_config.pop('defend')
            defend_frames = defend_info['frames']
            defend_dur = defend_info.get('duration', 120)
            n = len(defend_frames)
            # defend_start  — frames 0..4  (5 startup frames)
            start_end = min(5, n)
            anim_config['defend_start'] = {
                'frames': defend_frames[:start_end], 'duration': defend_dur, 'loop': False
            }
            # defend_idle   — frame 4 only, loops as a 1-frame hold
            hold_idx = min(4, n - 1)
            anim_config['defend_idle'] = {
                'frames': [defend_frames[hold_idx]], 'duration': defend_dur, 'loop': True
            }
            # defend_hit    — frames 5..8  (4 block-impact frames)
            hit_start = min(5, n)
            hit_end   = min(9, n)
            anim_config['defend_hit'] = {
                'frames': defend_frames[hit_start:hit_end] if hit_start < n else [defend_frames[hold_idx]],
                'duration': 80, 'loop': False
            }
            # defend_return — frames 9..10  (2 return frames)
            ret_start = min(9, n)
            anim_config['defend_return'] = {
                'frames': defend_frames[ret_start:] if ret_start < n else [defend_frames[-1]],
                'duration': defend_dur, 'loop': False
            }

        self.animator = Animator.from_config(anim_config)

    def _apply_frame(self):
        """Apply current animation frame with pivot alignment correction."""
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

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return

        # Invincible during the ultimate slam animation
        if getattr(self, 'animator', None) is not None and self.animator.state == 'ultimate':
            return
            
        # Block is active during the entire defend sequence.
        is_defending = getattr(self, 'animator', None) is not None and self.animator.state in ('defend_start', 'defend_idle', 'defend_hit')
        hit_from_front = False
        
        if is_defending and source_x is not None:
            if self.facing == 1 and source_x > self.rect.centerx:
                hit_from_front = True
            elif self.facing == -1 and source_x < self.rect.centerx:
                hit_from_front = True
                
        if hit_from_front:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('defend_hit', reset=True)
            self.vel.x = -self.facing * 1
            return
            
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            self.vel.x = -self.facing * 3
            self.hurt_timer = 300
            self.combo_step = 0
            self.combo_buffered = False
            self.exceeded_combo = False

    def update(self, dt, keys=None, groups=None):
        if keys is None or groups is None:
            return

        # check if dead
        if self.hp <= 0:
            if getattr(self, 'animator', None) is not None:
                self.animator.update(dt)
                self._apply_frame()
            return

        # handle timers
        if self.combo_break_timer > 0:
            self.combo_break_timer -= dt

        if self.ultimate_cooldown > 0:
            self.ultimate_cooldown -= dt

        # ULTIMATE block — Knight is locked in the 44-frame slam animation
        if getattr(self, 'animator', None) is not None and self.animator.state == 'ultimate':
            fi = self.animator.frame_index
            # Spawn the shockwave at the designated cast frame
            if fi >= KNIGHT_ULTIMATE_CAST_FRAME and not self._ultimate_shockwave_spawned:
                self._spawn_ultimate_shockwave(groups)
                self._ultimate_shockwave_spawned = True
            if self.animator.is_finished():
                self.animator.set_state('idle', reset=False)
            self.animator.update(dt)
            self._apply_frame()
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            # Clamp by the logical foot (hurtbox.bottom) not rect.bottom.
            # rect.bottom includes the raw pivot offset pdy, which can push it
            # well beyond MAX_Y for tall animation canvases — clamping rect.bottom
            # directly would pull the whole sprite up.
            clamped_foot = max(MIN_Y, min(MAX_Y, self.hurtbox.bottom))
            foot_shift = clamped_foot - self.hurtbox.bottom
            if foot_shift != 0:
                self.rect.y += foot_shift
                self.hurtbox.y += foot_shift
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            
            if self.hurt_timer <= 0:
                if getattr(self, 'animator', None) is not None:
                    self.animator.set_state('idle', reset=False)
            else:
                if getattr(self, 'animator', None) is not None:
                    self.animator.update(dt)
                    self._apply_frame()
                return

        self.handle_input(keys, groups)

        # Yield immediately if handle_input started the ultimate
        if getattr(self, 'animator', None) is not None and self.animator.state == 'ultimate':
            self.animator.update(dt)
            self._apply_frame()
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            clamped_foot = max(MIN_Y, min(MAX_Y, self.hurtbox.bottom))
            foot_shift = clamped_foot - self.hurtbox.bottom
            if foot_shift != 0:
                self.rect.y += foot_shift
                self.hurtbox.y += foot_shift
            return
        
        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)

        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        # choose animation state
        if getattr(self, 'animator', None) is not None:
            if self.animator.state in ('attack1', 'attack2', 'attack3'):
                # Check for the designated hit frame to spawn hitbox
                if self.animator.is_at_hit_frame() and not self.has_attacked:
                    self.spawn_attack_hitbox(groups)
                    self.has_attacked = True

                if self.animator.is_finished():
                    if self.combo_step == 1 and self.combo_buffered:
                        self.start_combo_step(2, groups)
                    elif self.combo_step == 2 and self.combo_buffered:
                        self.start_combo_step(3, groups)
                    else:
                        if self.combo_step == 3 or getattr(self, 'exceeded_combo', False):
                            self.combo_break_timer = 800
                        self.combo_step = 0
                        self.combo_buffered = False
                        self.exceeded_combo = False
                        self.animator.set_state('idle', reset=False)

            # --- Run start (frame 0, plays once) → loop transition ---
            # Bug fix: run_start has only 1 frame so Animator.update() returns
            # early without ever setting finished=True. Check len<=1 as well.
            elif self.animator.state == 'run_start':
                run_start_frames = self.animator.states.get('run_start', [])
                if self._is_control_pressed('defend', keys):
                    # Defend can always interrupt the start frame
                    self.animator.set_state('defend_start', reset=True)
                    self.vel.x = 0
                    self.vel.y = 0
                elif self.animator.is_finished() or len(run_start_frames) <= 1:
                    # 1-frame start: transition immediately on the next tick
                    if abs(self.vel.x) > 0 or abs(self.vel.y) > 0:
                        self.animator.set_state('run_loop', reset=True)
                    else:
                        self.animator.set_state('idle', reset=False)

            # --- Run loop (frames 1-N, loops) ---
            elif self.animator.state == 'run_loop':
                if self._is_control_pressed('defend', keys):
                    self.animator.set_state('defend_start', reset=True)
                    self.vel.x = 0
                    self.vel.y = 0
                elif not (abs(self.vel.x) > 0 or abs(self.vel.y) > 0):
                    self.animator.set_state('idle', reset=False)

            # --- Defend sub-state machine ---
            elif self.animator.state == 'defend_start':
                # Play startup; then hold in defend_idle while key held
                if self.animator.is_finished():
                    if self._is_control_pressed('defend', keys):
                        self.animator.set_state('defend_idle', reset=True)
                    else:
                        self.animator.set_state('defend_return', reset=True)

            elif self.animator.state == 'defend_idle':
                # Loop the hold frame; break out when key released
                if not self._is_control_pressed('defend', keys):
                    self.animator.set_state('defend_return', reset=True)

            elif self.animator.state == 'defend_hit':
                if self.animator.is_finished():
                    if self._is_control_pressed('defend', keys):
                        self.animator.set_state('defend_idle', reset=True)
                    else:
                        self.animator.set_state('defend_return', reset=True)

            elif self.animator.state == 'defend_return':
                if self.animator.is_finished():
                    self.animator.set_state('idle', reset=False)

            else:
                # Idle / any other state
                if self._is_control_pressed('defend', keys):
                    self.animator.set_state('defend_start', reset=True)
                    self.vel.x = 0
                    self.vel.y = 0
                elif abs(self.vel.x) > 0 or abs(self.vel.y) > 0:
                    self.animator.set_state('run_start', reset=True)
                else:
                    self.animator.set_state('idle', reset=False)
            self.animator.update(dt)
            self._apply_frame()

        # Clamp position AFTER animation rect update so bounds are always enforced.
        # Clamp the logical foot (hurtbox.bottom) not rect.bottom — rect.bottom
        # includes the pivot offset pdy and clamping it directly would shift the
        # sprite up when the character stands near the bottom boundary.
        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        clamped_foot = max(MIN_Y, min(MAX_Y, self.hurtbox.bottom))
        foot_shift = clamped_foot - self.hurtbox.bottom
        if foot_shift != 0:
            self.rect.y += foot_shift
            self.hurtbox.y += foot_shift

    def handle_input(self, keys, groups):
        self.vel.x = 0
        self.vel.y = 0
        
        attack_pressed   = self._is_control_pressed('attack', keys)
        ultimate_pressed = self._is_control_pressed('ultimate', keys)
        just_pressed_attack   = attack_pressed   and not getattr(self, 'attack_pressed_last', False)
        just_pressed_ultimate = ultimate_pressed and not getattr(self, 'ultimate_pressed_last', False)
        self.attack_pressed_last   = attack_pressed
        self.ultimate_pressed_last = ultimate_pressed

        is_attacking = self.animator.state in ('attack1', 'attack2', 'attack3')
        is_defending = getattr(self, 'animator', None) is not None and self.animator.state in ('defend_start', 'defend_idle', 'defend_hit', 'defend_return')

        # Ultimate (L) — highest offensive priority
        if just_pressed_ultimate and self.ultimate_cooldown <= 0 and not is_attacking and not is_defending:
            self.animator.set_state('ultimate', reset=True)
            self.ultimate_cooldown = KNIGHT_ULTIMATE_COOLDOWN
            self._ultimate_shockwave_spawned = False
            self.combo_step = 0
            self.combo_buffered = False
            self.vel.x = 0
            self.vel.y = 0
            return

        if just_pressed_attack and self.combo_break_timer <= 0:
            if not is_attacking and not is_defending:
                self.start_combo_step(1, groups)
            elif is_attacking:
                if self.animator.state == 'attack1' and self.combo_step == 1:
                    self.combo_buffered = True
                elif self.animator.state == 'attack2' and self.combo_step == 2:
                    self.combo_buffered = True
                elif self.animator.state == 'attack3' and self.combo_step == 3:
                    self.exceeded_combo = True

        if is_attacking or is_defending:
            return

        if self._is_control_pressed('defend', keys):
            return

        if self._is_control_pressed('left', keys):
            self.vel.x = -self.speed
            self.facing = -1
        if self._is_control_pressed('right', keys):
            self.vel.x = self.speed
            self.facing = 1
        if self._is_control_pressed('up', keys):
            self.vel.y = -self.speed
        if self._is_control_pressed('down', keys):
            self.vel.y = self.speed

    def start_combo_step(self, step, groups):
        self.combo_step = step
        self.combo_buffered = False
        self.has_attacked = False
        
        state_name = f'attack{step}'
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state(state_name, reset=True)

    def spawn_attack_hitbox(self, groups):
        """Spawn a melee attack hitbox, reading size/offset from animation metadata."""
        step = self.combo_step
        damage = 15 + step * 5
        state_name = f'attack{step}'
        # Read hitbox dimensions from the metadata-driven config (fall back to
        # the old config.py values so nothing breaks if metadata is missing).
        anim_entry = self.animator.states_config.get(state_name, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w        = anim_entry.get('hitbox_w',        150)
        h        = anim_entry.get('hitbox_h',         20)
        offset_x = anim_entry.get('hitbox_offset_x', -35)
        offset_y = anim_entry.get('hitbox_offset_y',  -5)

        pivot_x, pivot_y = self._get_true_pivot()

        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y

        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['attacks'].add(hitbox)

    def _spawn_ultimate_shockwave(self, groups):
        """Spawn the ground shockwave hitbox at the peak of the slam animation."""
        shockwave = KnightUltimateShockwave(
            owner_hurtbox=self.hurtbox,
            facing=self.facing,
            damage=KNIGHT_ULTIMATE_DAMAGE,
            knockback=KNIGHT_ULTIMATE_KNOCKBACK,
        )
        if 'effects' in groups:
            groups['effects'].add(shockwave)
        if 'knight_shockwaves' in groups:
            groups['knight_shockwaves'].add(shockwave)

    def on_death(self):
        print('Player died')
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0

class Arrow(pygame.sprite.Sprite):
    ARROW_SCALE = 2.5  # match the archer's sprite scale

    def __init__(self, x, y, facing, damage=15, owner=None, arrow_type='normal'):
        super().__init__()
        self.arrow_type = arrow_type if arrow_type in ARCHER_ARROW_CONFIG else 'normal'
        arrow_cfg = ARCHER_ARROW_CONFIG[self.arrow_type]
        try:
            raw = pygame.image.load(arrow_cfg['path']).convert_alpha()
            # Magic Arrow artwork has a larger canvas than the standard arrow.
            # Keep every arrow within the same readable projectile footprint.
            scale = self.ARROW_SCALE if self.arrow_type == 'normal' else min(1.0, 56 / max(raw.get_width(), raw.get_height()))
            aw = max(1, int(raw.get_width() * scale))
            ah = max(1, int(raw.get_height() * scale))
            self.image = pygame.transform.scale(raw, (aw, ah))
        except Exception:
            self.image = pygame.Surface((65, 8))
            self.image.fill(arrow_cfg.get('hud_color', (200, 200, 200)))

        if facing == -1:
            self.image = pygame.transform.flip(self.image, True, False)

        self.rect = self.image.get_rect(center=(x, y))
        self.facing = facing
        self.speed = 20
        self.damage = damage
        self.owner = owner

    @property
    def y(self):
        """Vertical screen position of the projectile centre."""
        return self.rect.centery

    @property
    def floor_y(self):
        """Ground-plane projection: the Y row this arrow travels on."""
        return self.rect.centery + 25

    def update(self, dt):
        self.rect.x += self.speed * self.facing
        if self.rect.right < 0 or self.rect.left > MAX_X:
            self.kill()

class DashSmoke(pygame.sprite.Sprite):
    """One-shot dash smoke puff left behind the archer when she dashes.

    Loaded dynamically from animation_metadata.json (dash_smoke).
    Renders in Y-sorted order via *floor_y* but has no hurtbox, so no shadow
    is drawn beneath it.
    """
    _frames_cache = None  # class-level cache so the strip is sliced only once

    @classmethod
    def _get_meta(cls):
        from sprites import _ANIMATION_METADATA
        return _ANIMATION_METADATA.get('archer', {}).get('animations', {}).get('dash_smoke', {})

    def __init__(self, x, y, facing):
        super().__init__()
        meta = self._get_meta()
        self.frame_duration = meta.get('duration', 55)

        # You can adjust the offset of the smoke in assets/animation_metadata.json 
        # using the "offset_x" and "offset_y" variables under "dash_smoke".
        # positive offset_x moves smoke RIGHT (flips automatically with facing direction)
        # positive offset_y moves smoke DOWN
        self.offset_x = meta.get('offset_x', 0)
        self.offset_y = meta.get('offset_y', 0)

        frames = self._load_frames()
        if not frames:
            # Fallback invisible surface
            self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
            self._frames = []
        else:
            self._frames = frames
            if facing == -1:
                self._frames = [pygame.transform.flip(f, True, False) for f in frames]
            self.image = self._frames[0]

        final_x = x + (self.offset_x * facing)
        final_y = y + self.offset_y
        self.rect = self.image.get_rect(center=(final_x, final_y))
        
        self._frame_index = 0
        self._time = 0
        self._finished = False

    @property
    def floor_y(self):
        """Used by the Y-sort in draw() to place smoke at the right depth."""
        return self.rect.bottom

    @classmethod
    def _load_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache
        meta = cls._get_meta()
        try:
            from sprites import SpriteSheet
            ss = SpriteSheet(DASH_SMOKE_IMAGE)
            frame_count = meta.get('frames', 9)
            scale = meta.get('scale', 1.5)
            cls._frames_cache = ss.load_horizontal_strip(frame_count, scale=scale)
        except Exception as e:
            print(f"[WARNING] DashSmoke: failed to load {DASH_SMOKE_IMAGE}: {e}")
            cls._frames_cache = []
        return cls._frames_cache

    def update(self, dt):
        if self._finished or not self._frames:
            self.kill()
            return
        self._time += dt
        while self._time >= self.frame_duration:
            self._time -= self.frame_duration
            self._frame_index += 1
            if self._frame_index >= len(self._frames):
                self._finished = True
                self.kill()
                return
        self.image = self._frames[self._frame_index]
        self.rect = self.image.get_rect(center=self.rect.center)

class UltimateEffect(pygame.sprite.Sprite):
    """Animated stretching beam fired during the archer's ultimate.

    Loaded dynamically from animation_metadata.json (ultimate_effect).
    Stays fixed at the spawn position — the animation itself stretches
    outward as a beam.  Damages every enemy whose hurtbox overlaps the
    beam rect, hitting each enemy only ONCE for the duration of the cast.
    Removes itself when the animation finishes.
    """
    _frames_cache_right = None
    _frames_cache_left  = None

    @classmethod
    def _get_meta(cls):
        from sprites import _ANIMATION_METADATA
        return _ANIMATION_METADATA.get('archer', {}).get('animations', {}).get('ultimate_effect', {})

    def __init__(self, x, y, facing):
        super().__init__()
        meta = self._get_meta()
        self.frame_duration = meta.get('duration', 80)
        self.facing = facing
        self.damage = ARCHER_ULTIMATE_DAMAGE
        # Each enemy may be hit only once per beam cast
        self.already_hit_targets: set = set()
        
        self.offset_x = meta.get('offset_x', 0)
        self.offset_y = meta.get('offset_y', 0)

        frames = self._load_frames(facing)
        if not frames:
            self.image = pygame.Surface((80, 16), pygame.SRCALPHA)
            self._frames = []
        else:
            self._frames = frames
            self.image = self._frames[0]

        # Anchor beam to the side of the archer's hurtbox, then apply offset
        final_x = x + (self.offset_x * facing)
        final_y = y + self.offset_y
        if facing == 1:
            self.rect = self.image.get_rect(midleft=(final_x, final_y))
        else:
            self.rect = self.image.get_rect(midright=(final_x, final_y))
        self._frame_index = 0
        self._time = 0

    @property
    def floor_y(self):
        return self.rect.centery + 20

    @classmethod
    def _load_frames(cls, facing):
        if facing == 1:
            if cls._frames_cache_right is not None:
                return cls._frames_cache_right
        else:
            if cls._frames_cache_left is not None:
                return cls._frames_cache_left

        meta = cls._get_meta()
        try:
            from sprites import SpriteSheet
            ss = SpriteSheet(ULTIMATE_EFFECT_IMAGE)
            frame_count = meta.get('frames', 7)
            scale = meta.get('scale', 2.5)
            base = ss.load_horizontal_strip(frame_count, scale=scale)
        except Exception as e:
            print(f"[WARNING] UltimateEffect: failed to load {ULTIMATE_EFFECT_IMAGE}: {e}")
            base = []

        cls._frames_cache_right = base
        cls._frames_cache_left  = [pygame.transform.flip(f, True, False) for f in base] if base else []
        return cls._frames_cache_right if facing == 1 else cls._frames_cache_left

    def update(self, dt):
        # Advance animation (non-looping — kill when finished)
        if self._frames:
            self._time += dt
            while self._time >= self.frame_duration:
                self._time -= self.frame_duration
                self._frame_index += 1
                if self._frame_index >= len(self._frames):
                    self.kill()
                    return
            self.image = self._frames[self._frame_index]
        else:
            self.kill()

    def can_hit(self, enemy):
        """Returns True if this enemy has not yet been hit by this beam."""
        return id(enemy) not in self.already_hit_targets

    def register_hit(self, enemy):
        """Mark this enemy as hit — prevents hitting them again this cast."""
        self.already_hit_targets.add(id(enemy))

class Archer(pygame.sprite.Sprite, HealthMixin):

    def __init__(self, pos=(200, 300)):
        pygame.sprite.Sprite.__init__(self)
        _preset = PLAYER_RESOURCE_PRESETS.get('archer', {})
        HealthMixin.__init__(
            self,
            max_hp=80,
            max_armor=_preset.get('max_armor', 45),
            max_mana=_preset.get('max_mana', 120),
            armor_reduction_pct=_preset.get('armor_reduction_pct', 0.30),
        )
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 5
        self.facing = 1
        self.on_ground = True
        self.controls = {
            'left': [pygame.K_LEFT],
            'right': [pygame.K_RIGHT],
            'up': [pygame.K_UP],
            'down': [pygame.K_DOWN],
            'attack': [pygame.K_KP1, pygame.K_KP4],
            'dash': [pygame.K_KP2, pygame.K_KP5],
            'ultimate': [pygame.K_KP3, pygame.K_KP6],
        }

        self.hurt_timer = 0

        # -- Attack / Combo --
        # combo_step: 0 = none, 1 = 'attack', 2 = 'attack_combo'
        self.combo_step = 0
        self.combo_buffered = False
        self.attack_pressed_last = False
        # Per-frame arrow spawn guards
        self._arrow_shot_f5  = False   # 'attack'       frame 5
        self._arrow_shot_f11 = False   # 'attack_combo' frame 11
        self._arrow_shot_f14 = False   # 'attack_combo' frame 14

        # -- Dash --
        self.dash_cooldown = 0
        self.dash_dx = 0
        self.dash_dy = 0
        self.dashing = False

        # -- Ultimate --
        self.ultimate_cooldown = 0
        self.ultimate_pressed_last = False
        self._ultimate_beam_spawned = False
        
        # -- Skills Inventory --
        self.skills = []  # List of skill types that have been picked up
        self.active_skill = None  # Currently selected skill (if any)
        self.target_skill_idx = 0  # Selected skill slot index (0..2)

        # Magic Arrow selection. Numpad 0 cycles this list during gameplay.
        self.arrow_types = list(ARCHER_ARROW_CONFIG.keys())
        self.arrow_type_index = 0
        self.arrow_type = self.arrow_types[self.arrow_type_index]

        # -- Hurtbox --
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=40, default_h=80, default_ox=-5)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def _is_control_pressed(self, control_name, keys):
        for key in self.controls.get(control_name, []):
            if keys[key]:
                return True
        return False

    def load_assets(self):
        anim_config = load_character_animations('archer')
        self.animator = Animator.from_config(anim_config)

    def _apply_frame(self):
        """Apply current animation frame with pivot alignment correction."""
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

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _clamp_position(self):
        self.rect.left   = max(MIN_X, self.rect.left)
        self.rect.right  = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

    def take_damage(self, amount, source_x=None, is_crit=False):
        # Invincibility during dash and ultimate
        if self.hp <= 0 or self.dashing or self.animator.state == 'ultimate':
            return

        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            self.vel.x = -self.facing * 3
            self.hurt_timer = 300
            self.combo_step = 0
            self.combo_buffered = False

    def update(self, dt, keys=None, groups=None):
        if keys is None or groups is None:
            return

        # Dead: play death animation only
        if self.hp <= 0:
            if getattr(self, 'animator', None) is not None:
                self.animator.update(dt)
                self._apply_frame()
            return

        # Cooldown timers
        if self.dash_cooldown > 0:
            self.dash_cooldown -= dt
        if self.ultimate_cooldown > 0:
            self.ultimate_cooldown -= dt

        # DASH block
        if self.dashing:
            self.animator.update(dt)
            dash_speed = 8   # pixels per frame - new 5-frame dash moves every frame
            self.rect.x += int(self.dash_dx * dash_speed)
            self.rect.y += int(self.dash_dy * dash_speed)
            if self.animator.is_finished():
                self.dashing = False
                self.vel.x = 0
                self.vel.y = 0
                self.animator.set_state('idle', reset=False)
            self._apply_frame()
            self._clamp_position()
            return

        # HURT block
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
            self.animator.update(dt)
            self._apply_frame()
            self._clamp_position()
            return

        # ULTIMATE block
        if self.animator.state == 'ultimate':
            self.animator.update(dt)
            fi = self.animator.frame_index
            if fi >= ARCHER_ULTIMATE_CAST_FRAME and not self._ultimate_beam_spawned:
                self._spawn_ultimate_beam(groups)
                self._ultimate_beam_spawned = True
            if self.animator.is_finished():
                self.animator.set_state('idle', reset=False)
            self._apply_frame()
            self._clamp_position()
            return

        # Normal input
        self.handle_input(keys, groups)

        # Yield to dash/ultimate if handle_input started them
        if self.dashing or self.animator.state == 'ultimate':
            self.animator.update(dt)
            self._apply_frame()
            self._clamp_position()
            return

        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)

        # Attack state machine
        state = self.animator.state

        if state == 'attack':
            fi = self.animator.frame_index
            # Shoot at frame 5
            if fi == 5 and not self._arrow_shot_f5:
                self.spawn_arrow(groups)
                self._arrow_shot_f5 = True
            if fi != 5:
                self._arrow_shot_f5 = False

            if self.animator.is_finished():
                if self.combo_buffered:
                    self.combo_buffered = False
                    self._arrow_shot_f5 = False
                    if self.combo_step < 2:
                        # Play the second basic attack
                        self.combo_step += 1
                        self.animator.set_state('attack', reset=True)
                    else:
                        # Two basic attacks done — fire the combo
                        self.combo_step = 3
                        self.animator.set_state('attack_combo', reset=True)
                        self._arrow_shot_f11 = False
                        self._arrow_shot_f14 = False
                else:
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)

        elif state == 'attack_combo':
            fi = self.animator.frame_index
            # First shot at frame 11
            if fi == 11 and not self._arrow_shot_f11:
                self.spawn_arrow(groups)
                self._arrow_shot_f11 = True
            if fi != 11:
                self._arrow_shot_f11 = False
            # Second shot at frame 14
            if fi == 14 and not self._arrow_shot_f14:
                self.spawn_arrow(groups)
                self._arrow_shot_f14 = True
            if fi != 14:
                self._arrow_shot_f14 = False

            if self.animator.is_finished():
                self.combo_step = 0
                self.animator.set_state('idle', reset=False)

        else:
            if abs(self.vel.x) > 0 or abs(self.vel.y) > 0:
                self.animator.set_state('run', reset=False)
            else:
                self.animator.set_state('idle', reset=False)

        self.animator.update(dt)
        self._apply_frame()
        self._clamp_position()

    def handle_input(self, keys, groups):
        self.vel.x = 0
        self.vel.y = 0

        attack_pressed   = self._is_control_pressed('attack', keys)
        ultimate_pressed = self._is_control_pressed('ultimate', keys)
        just_pressed_attack   = attack_pressed   and not self.attack_pressed_last
        just_pressed_ultimate = ultimate_pressed and not self.ultimate_pressed_last
        self.attack_pressed_last   = attack_pressed
        self.ultimate_pressed_last = ultimate_pressed

        state = self.animator.state
        is_attacking = state in ('attack', 'attack_combo', 'ultimate')

        # Dash (K) - highest priority
        if self._is_control_pressed('dash', keys) and self.dash_cooldown <= 0 and not is_attacking:
            self.dash_dx = 0
            self.dash_dy = 0
            if self._is_control_pressed('left', keys):
                self.dash_dx = -1
            if self._is_control_pressed('right', keys):
                self.dash_dx = 1
            if self._is_control_pressed('up', keys):
                self.dash_dy = -1
            if self._is_control_pressed('down', keys):
                self.dash_dy = 1
            if self.dash_dx == 0 and self.dash_dy == 0:
                self.dash_dx = self.facing
            if self.dash_dx != 0:
                self.facing = self.dash_dx

            # Spawn smoke trail behind the archer (facing = dash direction, smoke faces opposite)
            smoke_x = self.hurtbox.centerx - (self.facing * 10)
            smoke_y = self.hurtbox.bottom - 10
            smoke = DashSmoke(smoke_x, smoke_y, self.facing)
            if 'effects' in groups:
                groups['effects'].add(smoke)

            self.animator.set_state('dash', reset=True)
            self.dashing = True
            self.dash_cooldown = 1500
            return

        # Ultimate (L)
        if just_pressed_ultimate and self.ultimate_cooldown <= 0 and not is_attacking:
            self.animator.set_state('ultimate', reset=True)
            self.ultimate_cooldown = ARCHER_ULTIMATE_COOLDOWN
            self._ultimate_beam_spawned = False
            self.vel.x = 0
            self.vel.y = 0
            return

        # Attack (J)
        if just_pressed_attack:
            if state not in ('attack', 'attack_combo', 'ultimate'):
                self.combo_step = 1
                self.animator.set_state('attack', reset=True)
                self._arrow_shot_f5 = False
            elif state == 'attack' and not self.combo_buffered:
                # Buffer the next step (2nd attack, or combo if already on step 2)
                self.combo_buffered = True

        if is_attacking:
            return

        if self._is_control_pressed('left', keys):
            self.vel.x = -self.speed
            self.facing = -1
        if self._is_control_pressed('right', keys):
            self.vel.x = self.speed
            self.facing = 1
        if self._is_control_pressed('up', keys):
            self.vel.y = -self.speed
        if self._is_control_pressed('down', keys):
            self.vel.y = self.speed

    def spawn_arrow(self, groups):
        spawn_y = self.rect.bottom - 6 - self.rect.height // 2
        spawn_x = self.rect.centerx + (20 * self.facing)
        arrow_cfg = ARCHER_ARROW_CONFIG.get(self.arrow_type, ARCHER_ARROW_CONFIG['normal'])
        arrow = Arrow(spawn_x, spawn_y, self.facing, damage=arrow_cfg['damage'], owner=self, arrow_type=self.arrow_type)
        groups['arrows'].add(arrow)

    def cycle_arrow_type(self):
        self.arrow_type_index = (self.arrow_type_index + 1) % len(self.arrow_types)
        self.arrow_type = self.arrow_types[self.arrow_type_index]

    def _spawn_ultimate_beam(self, groups):
        """Spawn the UltimateEffect beam at the archer's chest position."""
        spawn_x = self.hurtbox.right if self.facing == 1 else self.hurtbox.left
        spawn_y = self.hurtbox.centery - 10
        beam = UltimateEffect(spawn_x, spawn_y, self.facing)
        if 'effects' in groups:
            groups['effects'].add(beam)
        if 'ultimate_beams' in groups:
            groups['ultimate_beams'].add(beam)

    def on_death(self):
        print('Archer died')
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0


