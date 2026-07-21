import pygame
import random
import math
from sprites import Animator, load_character_animations
from config import (ENEMY_ATTACK_OFFSET_Y,
                    FAT_CULTIST_ATTACK_RANGE_X, FAT_CULTIST_ATTACK_RANGE_Y,
                    FAT_CULTIST_ATTACK_2_RANGE_X, FAT_CULTIST_ATTACK_2_RANGE_Y,
                    DEATH_BRINGER_ATTACK_RANGE_X, DEATH_BRINGER_ATTACK_RANGE_Y,
                    DEATH_BRINGER_CAST_RANGE_X, DEATH_BRINGER_CAST_RANGE_Y,
                    DEATH_BRINGER_SPELL_COOLDOWN)
from .core import HealthMixin, _hurtbox_from_config, AttackHitbox

class FatCultist(pygame.sprite.Sprite, HealthMixin):
    """Miniboss for Phase 3. Slow movement, high HP, 2 attack animations."""
    is_boss = True  # Boss enemies are immune to knight ultimate knockback
    def __init__(self, pos):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=500)
        
        self.animator = Animator.from_config(load_character_animations('fat_cultist'))
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        
        self.hurtbox_w, self.hurtbox_h, self.hurtbox_offset_x = _hurtbox_from_config(self.animator.states_config)
        self.hurtbox = pygame.Rect(0, 0, self.hurtbox_w, self.hurtbox_h)
        
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 1.0
        self.facing = -1
        
        self._update_hurtbox()
        
        self.hurt_timer = 0
        self.has_attacked = False
        
        # State machine
        self.is_attacking = False
        self.combo_step = 0
        self.attack_timer = 0      # cooldown between combo sequences
        self.ai_state = 'chase'    # 'chase' | 'wait'
        self.ai_timer = 0          # ms remaining in wait state

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def _get_true_pivot(self):
        if not hasattr(self, 'rect'): return (0, 0)
        foot_x = self.rect.midbottom[0] - getattr(self, 'current_pdx', 0)
        foot_y = self.rect.midbottom[1] - getattr(self, 'current_pdy', 0)
        animator = getattr(self, 'animator', None)
        if not animator: return (foot_x, foot_y)
        sn = getattr(animator, 'state', None)
        entry = getattr(animator, 'states_config', {}).get(sn, {})
        idle_mb_ox = entry.get('idle_mb_ox', 0)
        idle_mb_oy = entry.get('idle_mb_oy', 0)
        if getattr(self, 'facing', 1) == 1:
            return foot_x + idle_mb_ox, foot_y + idle_mb_oy
        else:
            return foot_x - idle_mb_ox, foot_y + idle_mb_oy

    def update(self, dt, player, groups):
        if self.hp <= 0:
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            self.animator.update(dt)
            if self.animator.is_finished():
                self.kill()
            self._update_visuals()  # must call to update self.image with death frames
            return
            
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.animator.update(dt)
            if self.animator.is_finished():
                self.hurt_timer = 0
                self.animator.set_state('idle', reset=False)
        else:
            self._update_ai(dt, player, groups)
            self.animator.update(dt)
            
        self.rect.x += self.vel.x
        self.rect.y += self.vel.y
        self._update_visuals()

    def _update_ai(self, dt, player, groups):
        # Use hurtbox for accurate distance measurement
        target_x = player.hurtbox.centerx
        target_y = player.foot_y
        dist_x = target_x - self.hurtbox.centerx
        dist_y = target_y - self.hurtbox.bottom

        # --- wait state after a combo finishes ---
        if self.ai_state == 'wait':
            self.ai_timer -= dt
            self.animator.set_state('idle', reset=False)
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
            return

        if not self.is_attacking:
            self.facing = 1 if dist_x > 0 else -1

            in_range_attack1 = abs(dist_x) <= FAT_CULTIST_ATTACK_RANGE_X and abs(dist_y) <= FAT_CULTIST_ATTACK_RANGE_Y
            in_range_attack2 = abs(dist_x) <= FAT_CULTIST_ATTACK_2_RANGE_X and abs(dist_y) <= FAT_CULTIST_ATTACK_2_RANGE_Y

            now = pygame.time.get_ticks()
            attack_ready = (now - self.attack_timer) > 1200  # min delay between combos

            if attack_ready and (in_range_attack1 or in_range_attack2):
                self.vel.x = 0
                self.vel.y = 0
                self.is_attacking = True
                self.has_attacked = False
                # Always start with attack1 if in range, else attack2
                if in_range_attack1:
                    self.animator.set_state('attack1', reset=True)
                    self.combo_step = 1
                else:
                    self.animator.set_state('attack2', reset=True)
                    self.combo_step = 2
                self.attack_timer = now
            else:
                self.animator.set_state('run', reset=False)  # reset=False prevents frame-0 lock
                dist = math.hypot(dist_x, dist_y)
                if dist > 0:
                    self.vel.x = (dist_x / dist) * self.speed
                    self.vel.y = (dist_y / dist) * self.speed
        else:
            self.vel.x = 0
            self.vel.y = 0

            sn = self.animator.state
            entry = self.animator.states_config.get(sn, {})
            hit_frames = entry.get('hit_frame', [6])
            if not isinstance(hit_frames, list):
                hit_frames = [hit_frames]

            if self.animator.frame_index in hit_frames and not self.has_attacked:
                damage = 35 if self.combo_step == 2 else 20
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True

            if self.animator.frame_index not in hit_frames:
                self.has_attacked = False

            if self.animator.is_finished():
                if self.combo_step == 1:
                    # Check if still in range to chain into attack2
                    cur_dist_x = player.hurtbox.centerx - self.hurtbox.centerx
                    cur_dist_y = player.foot_y - self.hurtbox.bottom
                    in_range2 = abs(cur_dist_x) <= FAT_CULTIST_ATTACK_2_RANGE_X and abs(cur_dist_y) <= FAT_CULTIST_ATTACK_2_RANGE_Y
                    if in_range2:
                        # Chain combo to attack2
                        self.combo_step = 2
                        self.animator.set_state('attack2', reset=True)
                        self.has_attacked = False
                        return
                # Combo fully done
                self.is_attacking = False
                self.combo_step = 0
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'wait'
                self.ai_timer = random.randint(600, 1200)

    def _spawn_enemy_attack_hitbox(self, groups, damage):
        sn = self.animator.state
        entry = self.animator.states_config.get(sn, {})
        w = entry.get('hitbox_w', 60)
        h = entry.get('hitbox_h', 40)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        if self.facing == 1: hb_x = pivot_x + offset_x
        else: hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def _update_visuals(self):
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
        if self.hp <= 0: return
        super().take_damage(amount, source_x, is_crit)
        if self.hp > 0 and not self.is_attacking:
            self.animator.set_state('hit', reset=True)
            self.hurt_timer = self.animator.states_config['hit']['duration'] * len(self.animator.states_config['hit']['frames'])
            self.vel.x = 0
            self.vel.y = 0

    def on_death(self):
        if self.animator: self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0


class DeathBringerSpell(pygame.sprite.Sprite):
    def __init__(self, x, y, damage, groups):
        pygame.sprite.Sprite.__init__(self)
        self.groups = groups
        self.animator = Animator.from_config(load_character_animations('death_bringer_spell'))
        self.animator.set_state('spell')
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(center=(x, y))
        self.damage = damage
        self.has_hit = False
        
    def update(self, dt):
        self.animator.update(dt)
        self.image = self.animator.get_frame()
        
        sn = self.animator.state
        entry = self.animator.states_config.get(sn, {})
        hit_frame = entry.get('hit_frame', 4)
        
        if self.animator.frame_index == hit_frame and not self.has_hit:
            self.has_hit = True
            w = entry.get('hitbox_w', 80)
            h = entry.get('hitbox_h', 120)
            ox = entry.get('hitbox_offset_x', -40)
            oy = entry.get('hitbox_offset_y', -100)
            
            # Since this effect has no facing, the hitbox is just applied at the center of the effect
            hb_x = self.rect.centerx + ox
            hb_y = self.rect.centery + oy
            
            # We must pass an owner for knockback. The spell itself isn't a character, so we pass self (which doesn't have foot_y or hurtbox).
            # We'll mock it for the collision system.
            self.foot_y = self.rect.bottom
            self.owner = self
            hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=self.damage, duration=100)
            self.groups['enemy_attacks'].add(hitbox)
            
        if self.animator.is_finished():
            self.kill()


class DeathBringer(pygame.sprite.Sprite, HealthMixin):
    """Final Boss for Phase 3. Has standard melee attack, and a spell attack that spawns a spell effect."""
    is_boss = True  # Boss enemies are immune to knight ultimate knockback
    def __init__(self, pos):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=1000)
        
        self.animator = Animator.from_config(load_character_animations('bringer_of_death'))
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        
        self.hurtbox_w, self.hurtbox_h, self.hurtbox_offset_x = _hurtbox_from_config(self.animator.states_config)
        self.hurtbox = pygame.Rect(0, 0, self.hurtbox_w, self.hurtbox_h)
        
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 1.2
        self.facing = -1
        
        self._update_hurtbox()
        
        self.hurt_timer = 0
        self.has_attacked = False
        
        self.is_attacking = False
        self.last_spell_time = pygame.time.get_ticks() - DEATH_BRINGER_SPELL_COOLDOWN

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def _get_true_pivot(self):
        if not hasattr(self, 'rect'): return (0, 0)
        foot_x = self.rect.midbottom[0] - getattr(self, 'current_pdx', 0)
        foot_y = self.rect.midbottom[1] - getattr(self, 'current_pdy', 0)
        animator = getattr(self, 'animator', None)
        if not animator: return (foot_x, foot_y)
        sn = getattr(animator, 'state', None)
        entry = getattr(animator, 'states_config', {}).get(sn, {})
        idle_mb_ox = entry.get('idle_mb_ox', 0)
        idle_mb_oy = entry.get('idle_mb_oy', 0)
        if getattr(self, 'facing', 1) == 1:
            return foot_x + idle_mb_ox, foot_y + idle_mb_oy
        else:
            return foot_x - idle_mb_ox, foot_y + idle_mb_oy

    def update(self, dt, player, groups):
        if self.hp <= 0:
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            self.animator.update(dt)
            if self.animator.is_finished():
                self.kill()
            self._update_visuals()  # must call to update self.image with death frames
            return
            
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.animator.update(dt)
            if self.animator.is_finished():
                self.hurt_timer = 0
                self.animator.set_state('idle', reset=False)
        else:
            self._update_ai(dt, player, groups)
            self.animator.update(dt)
            
        self.rect.x += self.vel.x
        self.rect.y += self.vel.y
        self._update_visuals()

    def _update_ai(self, dt, player, groups):
        target_x = player.hurtbox.centerx
        target_y = player.foot_y
        dist_x = target_x - self.rect.centerx
        dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
        real_dist_x = player.hurtbox.centerx - self.rect.centerx
        real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
        
        now = pygame.time.get_ticks()
        can_spell = (now - self.last_spell_time > DEATH_BRINGER_SPELL_COOLDOWN)
        
        if not self.is_attacking:
            self.facing = 1 if dist_x > 0 else -1
            
            in_melee = abs(dist_x) <= DEATH_BRINGER_ATTACK_RANGE_X and abs(dist_y) <= DEATH_BRINGER_ATTACK_RANGE_Y
            in_spell_range = abs(dist_x) <= DEATH_BRINGER_CAST_RANGE_X and abs(dist_y) <= DEATH_BRINGER_CAST_RANGE_Y
            
            if can_spell and in_spell_range:
                self.vel.x = 0
                self.vel.y = 0
                self.is_attacking = True
                self.has_attacked = False
                self.animator.set_state('cast', reset=True)
                self.last_spell_time = now
            elif in_melee:
                self.vel.x = 0
                self.vel.y = 0
                self.is_attacking = True
                self.has_attacked = False
                self.animator.set_state('attack', reset=True)
            else:
                self.animator.set_state('run', reset=False)  # reset=False prevents frame-0 lock
                dist = math.hypot(dist_x, dist_y)
                if dist > 0:
                    self.vel.x = (dist_x / dist) * self.speed
                    self.vel.y = (dist_y / dist) * self.speed
        else:
            self.vel.x = 0
            self.vel.y = 0
            
            if self.animator.state == 'attack':
                hit_frame = self.animator.states_config.get('attack', {}).get('hit_frame', 7)
                if self.animator.frame_index == hit_frame and not self.has_attacked:
                    self._spawn_enemy_attack_hitbox(groups, damage=40)
                    self.has_attacked = True
                    
            elif self.animator.state == 'cast':
                if self.animator.frame_index == 3 and not self.has_attacked:
                    # Spawn the spell effect centered on the player's hurtbox so it hits them reliably
                    spell_x = player.hurtbox.centerx
                    spell_y = player.hurtbox.centery  # align to hurtbox center, not feet
                    spell = DeathBringerSpell(spell_x, spell_y, damage=50, groups=groups)
                    groups['effects'].add(spell)
                    self.has_attacked = True
                    
            if self.animator.is_finished():
                self.is_attacking = False
                self.animator.set_state('idle')

    def _spawn_enemy_attack_hitbox(self, groups, damage):
        sn = self.animator.state
        entry = self.animator.states_config.get(sn, {})
        w = entry.get('hitbox_w', 80)
        h = entry.get('hitbox_h', 60)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        if self.facing == 1: hb_x = pivot_x + offset_x
        else: hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def _update_visuals(self):
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
        if self.hp <= 0: return
        super().take_damage(amount, source_x, is_crit)
        # Boss does not flinch to normal attacks while attacking, only flinches in idle/run
        if self.hp > 0 and not self.is_attacking:
            self.animator.set_state('hit', reset=True)
            self.hurt_timer = self.animator.states_config['hit']['duration'] * len(self.animator.states_config['hit']['frames'])
            self.vel.x = 0
            self.vel.y = 0

    def on_death(self):
        if self.animator: self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0

