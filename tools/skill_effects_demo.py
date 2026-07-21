import math
import random
import sys

import pygame

from config import FPS, HEIGHT, WIDTH
from config import SKILL_TYPES
from game import SkillEffect, WindStreamEffect, WaterBallProjectile, WaterBlastProjectile, LightProjectile, DarkProjectile, WoodProjectile, AcidProjectile


SKILLS = list(SKILL_TYPES)


class DemoUnit:
    def __init__(self, x, y, color, name, max_hp=200):
        self.x = x
        self.y = y
        self.color = color
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.slow_until = 0
        self.slow_mult = 1.0
        self.fire_dot_until = 0
        self.fire_dot_next_tick = 0
        self.acid_dot_until = 0
        self.acid_dot_next_tick = 0

    def center(self):
        return int(self.x), int(self.y)


class FloatingText(pygame.sprite.Sprite):
    def __init__(self, x, y, text, color):
        super().__init__()
        self.font = pygame.font.SysFont("consolas", 18, bold=True)
        self.image = self.font.render(str(text), True, color)
        self.rect = self.image.get_rect(center=(x, y))
        self.life_ms = 650

    def update(self, dt):
        self.life_ms -= dt
        self.rect.y -= max(1, int(80 * dt / 1000.0))
        if self.life_ms <= 0:
            self.kill()


class SkillEffectsDemo:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Skill Effects Demo")
        self.clock = pygame.time.Clock()
        self.running = True

        self.effects = pygame.sprite.Group()
        self.float_texts = pygame.sprite.Group()
        self.water_projectiles = pygame.sprite.Group()
        self.water_blast_projectiles = pygame.sprite.Group()
        self.light_projectiles = pygame.sprite.Group()
        self.dark_projectiles = pygame.sprite.Group()
        self.wood_projectiles = pygame.sprite.Group()
        self.acid_projectiles = pygame.sprite.Group()

        self.font = pygame.font.SysFont("consolas", 20)
        self.font_small = pygame.font.SysFont("consolas", 16)

        cy = HEIGHT // 2
        self.player = DemoUnit(WIDTH * 0.27, cy, (90, 210, 255), "PLAYER", max_hp=240)
        self.enemy = DemoUnit(WIDTH * 0.70, cy, (255, 100, 90), "ENEMY", max_hp=3200)
        self.enemy2 = DemoUnit(WIDTH * 0.80, cy - 55, (250, 145, 100), "ENEMY B", max_hp=2600)
        self.enemy3 = DemoUnit(WIDTH * 0.80, cy + 55, (250, 145, 100), "ENEMY C", max_hp=2600)
        self.enemies = [self.enemy, self.enemy2, self.enemy3]

        self.auto_demo = False
        self.auto_timer = 0
        self.auto_idx = 0
        self.aura_timer = 0

        self.last_skill = "-"
        self.last_hint_ms = 0
        self.aim_dir = pygame.math.Vector2(1, 0)

    def spawn_vfx(self, skill_name, x, y, facing=1):
        self.effects.add(SkillEffect(skill_name, x, y, facing=facing))

    def pop_text(self, unit, amount, color=(255, 240, 140), prefix=""):
        text = f"{prefix}{amount}"
        self.float_texts.add(FloatingText(unit.center()[0], unit.center()[1] - 40, text, color))

    def apply_damage(self, unit, amount, skill_name=None):
        if amount <= 0 or unit.hp <= 0:
            return
        unit.hp = max(0, unit.hp - int(amount))
        self.pop_text(unit, int(amount), (255, 170, 120), "-")
        if skill_name:
            self.spawn_vfx(skill_name, unit.center()[0], unit.center()[1], facing=1)

    def apply_heal(self, unit, amount):
        if amount <= 0 or unit.hp <= 0:
            return
        unit.hp = min(unit.max_hp, unit.hp + int(amount))
        self.pop_text(unit, int(amount), (120, 255, 180), "+")

    def trigger_skill(self, skill_name):
        self.last_skill = skill_name
        self.last_hint_ms = 900

        if skill_name == "fire":
            self.apply_damage(self.enemy, 20, "fire")
            now = pygame.time.get_ticks()
            self.enemy.fire_dot_until = max(self.enemy.fire_dot_until, now + 2200)
            self.enemy.fire_dot_next_tick = now + 350
            if random.random() < 0.6:
                for other in (self.enemy2, self.enemy3):
                    self.apply_damage(other, 8, "fire")

        elif skill_name == "water_ball":
            self.spawn_waterball_projectile(self.aim_dir.x, self.aim_dir.y)

        elif skill_name == "wind":
            self.spawn_wind_stream(self.aim_dir.x, self.aim_dir.y)

        elif skill_name == "holy":
            self.spawn_vfx("holy", self.player.center()[0], self.player.center()[1], 1)
            self.apply_heal(self.player, 15)

        elif skill_name == "dark":
            self.spawn_dark_projectile(self.aim_dir.x, self.aim_dir.y)

        elif skill_name == "wood":
            self.spawn_wood_projectile(self.aim_dir.x, self.aim_dir.y)

        elif skill_name == "acid":
            self.spawn_acid_projectile(self.aim_dir.x, self.aim_dir.y)

        elif skill_name == "shield":
            self.spawn_vfx("shield", self.player.center()[0], self.player.center()[1], 1)
            self.apply_heal(self.player, 4)

        elif skill_name == "earth":
            ex, ey = self.enemy.center()
            self.spawn_vfx("earth", ex, ey + 30, 1)
            self.apply_damage(self.enemy, 18)

        elif skill_name == "light":
            self.spawn_light_projectile(self.aim_dir.x, self.aim_dir.y)

        elif skill_name == "smoke":
            px, py = self.player.center()
            self.spawn_vfx("smoke", px, py, 1)
            now = pygame.time.get_ticks()
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                ex, ey = enemy.center()
                if abs(ex - px) <= 180 and abs(ey - py) <= 90:
                    enemy.slow_until = max(enemy.slow_until, now + 1400)
                    enemy.slow_mult = min(enemy.slow_mult, 0.65)

        elif skill_name == "thunder":
            ex, ey = self.enemy.center()
            self.spawn_vfx("thunder", ex, ey, 1)
            self.apply_damage(self.enemy, 26)

        elif skill_name == "water_blast":
            self.spawn_water_blast_projectile(self.aim_dir.x, self.aim_dir.y)

    def reset_demo(self):
        self.effects.empty()
        self.float_texts.empty()
        self.water_projectiles.empty()
        self.water_blast_projectiles.empty()
        self.light_projectiles.empty()
        self.dark_projectiles.empty()
        self.wood_projectiles.empty()
        self.acid_projectiles.empty()
        for unit in [self.player, self.enemy, self.enemy2, self.enemy3]:
            unit.hp = unit.max_hp
            unit.slow_until = 0
            unit.slow_mult = 1.0
            unit.fire_dot_until = 0
            unit.fire_dot_next_tick = 0
            unit.acid_dot_until = 0
            unit.acid_dot_next_tick = 0

    def handle_status_ticks(self):
        now = pygame.time.get_ticks()
        for target in self.enemies:
            if target.hp <= 0:
                continue

            if now < target.slow_until:
                # Visual-only status in this demo.
                pass
            else:
                target.slow_mult = 1.0

            while target.fire_dot_until > now and now >= target.fire_dot_next_tick:
                target.fire_dot_next_tick += 350
                self.apply_damage(target, 3, "fire")

            while target.acid_dot_until > now and now >= target.acid_dot_next_tick:
                target.acid_dot_next_tick += 550
                self.apply_damage(target, 4)

        # Auto aura preview disabled: holy/shield are now only shown on explicit skill cast.

    def spawn_wind_stream(self, dir_x, dir_y):
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px, py = self.player.center()
        # Cast breath VFX (separate asset from projectile and hit).
        self.spawn_vfx("wind_breath", px, py, -1 if vec.x < 0 else 1)
        for i in range(4):
            sx = px + int(vec.x * i * 22)
            sy = py + int(vec.y * i * 22)
            self.effects.add(
                WindStreamEffect(sx, sy, vec.x, vec.y, speed_px_per_ms=0.95, life_ms=320 + i * 35)
            )

    def _update_aim_direction(self, keys):
        dir_x = 0.0
        dir_y = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dir_x -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dir_x += 1.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dir_y -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dir_y += 1.0

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() > 0:
            self.aim_dir = vec.normalize()

    def _apply_wind_collisions(self):
        now = pygame.time.get_ticks()
        for fx in self.effects:
            if not isinstance(fx, WindStreamEffect):
                continue
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                ex, ey = enemy.center()
                if abs(fx.rect.centerx - ex) <= 28 and abs(fx.rect.centery - ey) <= 28:
                    stamp = getattr(enemy, '_wind_hit_ms', 0)
                    if now - stamp < 120:
                        continue
                    enemy._wind_hit_ms = now
                    self.apply_damage(enemy, 3)
                    self.spawn_vfx("wind", ex, ey, -1 if fx.vel.x < 0 else 1)
                    enemy.slow_until = max(enemy.slow_until, now + 1000)
                    enemy.slow_mult = min(enemy.slow_mult, 0.80)
                    fx.kill()

    def spawn_waterball_projectile(self, dir_x, dir_y):
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px, py = self.player.center()
        proj = WaterBallProjectile(px, py, vec.x, vec.y, damage=14, speed_px_per_ms=0.78, life_ms=760)
        self.water_projectiles.add(proj)

    def _apply_waterball_collisions(self):
        now = pygame.time.get_ticks()
        for proj in list(self.water_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                ex, ey = enemy.center()
                if abs(proj.rect.centerx - ex) <= 36 and abs(proj.rect.centery - ey) <= 36:
                    self.apply_damage(enemy, 14)
                    self.spawn_vfx("water_ball", ex, ey, -1 if proj.vel.x < 0 else 1)
                    enemy.slow_until = max(enemy.slow_until, now + 1500)
                    enemy.slow_mult = min(enemy.slow_mult, 0.68)

                    # Splash preview on nearby enemies.
                    for other in self.enemies:
                        if other is enemy or other.hp <= 0:
                            continue
                        ox, oy = other.center()
                        if abs(ox - ex) <= 120 and abs(oy - ey) <= 80:
                            self.apply_damage(other, 6)
                            self.spawn_vfx("water_ball", ox, oy, -1 if proj.vel.x < 0 else 1)

                    proj.kill()
                    break

    def spawn_light_projectile(self, dir_x, dir_y):
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px, py = self.player.center()
        proj = LightProjectile(px, py, vec.x, vec.y, damage=18, speed_px_per_ms=0.88, life_ms=760)
        self.light_projectiles.add(proj)

    def spawn_water_blast_projectile(self, dir_x, dir_y):
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px, py = self.player.center()
        proj = WaterBlastProjectile(px, py, vec.x, vec.y, damage=20, speed_px_per_ms=0.76, life_ms=840)
        self.water_blast_projectiles.add(proj)

    def _apply_water_blast_collisions(self):
        now = pygame.time.get_ticks()
        for proj in list(self.water_blast_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                ex, ey = enemy.center()
                if abs(proj.rect.centerx - ex) <= 44 and abs(proj.rect.centery - ey) <= 44:
                    self.apply_damage(enemy, 20)
                    self.spawn_vfx("water_blast", ex, ey, -1 if proj.vel.x < 0 else 1)
                    enemy.slow_until = max(enemy.slow_until, now + 1100)
                    enemy.slow_mult = min(enemy.slow_mult, 0.70)

                    for other in self.enemies:
                        if other is enemy or other.hp <= 0:
                            continue
                        ox, oy = other.center()
                        if abs(ox - ex) <= 130 and abs(oy - ey) <= 90:
                            self.apply_damage(other, 10)
                            self.spawn_vfx("water_blast", ox, oy, -1 if proj.vel.x < 0 else 1)

                    proj.kill()
                    break

    def _apply_light_collisions(self):
        now = pygame.time.get_ticks()
        for proj in list(self.light_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                ex, ey = enemy.center()
                if abs(proj.rect.centerx - ex) <= 36 and abs(proj.rect.centery - ey) <= 36:
                    self.apply_damage(enemy, 18)
                    self.spawn_vfx("light", ex, ey, -1 if proj.vel.x < 0 else 1)
                    enemy.slow_until = max(enemy.slow_until, now + 900)
                    enemy.slow_mult = min(enemy.slow_mult, 0.80)

                    chained = 0
                    for other in self.enemies:
                        if chained >= 2:
                            break
                        if other is enemy or other.hp <= 0:
                            continue
                        ox, oy = other.center()
                        if abs(ox - ex) > 165 or abs(oy - ey) > 75:
                            continue
                        self.apply_damage(other, 10)
                        self.spawn_vfx("light", ox, oy, -1 if proj.vel.x < 0 else 1)
                        other.slow_until = max(other.slow_until, now + 600)
                        other.slow_mult = min(other.slow_mult, 0.85)
                        chained += 1

                    proj.kill()
                    break

    def spawn_dark_projectile(self, dir_x, dir_y):
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px, py = self.player.center()
        proj = DarkProjectile(px, py, vec.x, vec.y, damage=16, speed_px_per_ms=0.92, life_ms=700)
        self.dark_projectiles.add(proj)

    def _apply_dark_collisions(self):
        for proj in list(self.dark_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                ex, ey = enemy.center()
                if abs(proj.rect.centerx - ex) <= 36 and abs(proj.rect.centery - ey) <= 36:
                    self.apply_damage(enemy, 16)
                    self.spawn_vfx("dark", ex, ey, -1 if proj.vel.x < 0 else 1)

                    # Lifesteal preview.
                    self.apply_heal(self.player, 8)

                    if random.random() < 0.65:
                        self.apply_damage(enemy, 6)
                        self.spawn_vfx("dark", ex, ey, -1 if proj.vel.x < 0 else 1)

                    proj.kill()
                    break

    def spawn_wood_projectile(self, dir_x, dir_y):
        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px, py = self.player.center()
        proj = WoodProjectile(px, py, vec.x, vec.y, damage=12, speed_px_per_ms=0.76, life_ms=760)
        self.wood_projectiles.add(proj)

    def _apply_wood_collisions(self):
        for proj in list(self.wood_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                ex, ey = enemy.center()
                if abs(proj.rect.centerx - ex) <= 36 and abs(proj.rect.centery - ey) <= 36:
                    self.apply_damage(enemy, 12)
                    self.spawn_vfx("wood", ex, ey, -1 if proj.vel.x < 0 else 1)
                    self.apply_heal(self.player, 5)
                    proj.kill()
                    break

    def spawn_acid_projectile(self, dir_x, dir_y):
        for p in list(self.acid_projectiles):
            p.kill()

        vec = pygame.math.Vector2(dir_x, dir_y)
        if vec.length_squared() <= 0:
            vec = pygame.math.Vector2(1, 0)
        vec = vec.normalize()

        px, py = self.player.center()
        proj = AcidProjectile(px, py, vec.x, vec.y, damage=12, speed_px_per_ms=0.72, life_ms=820)
        self.acid_projectiles.add(proj)

    def _apply_acid_collisions(self):
        now = pygame.time.get_ticks()
        for proj in list(self.acid_projectiles):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                ex, ey = enemy.center()
                if abs(proj.rect.centerx - ex) <= 36 and abs(proj.rect.centery - ey) <= 36:
                    self.apply_damage(enemy, 12)
                    self.spawn_vfx("acid", ex, ey, -1 if proj.vel.x < 0 else 1)
                    enemy.acid_dot_until = max(enemy.acid_dot_until, now + 5000)
                    enemy.acid_dot_next_tick = now + 550
                    proj.kill()
                    break

    def draw_unit(self, unit):
        x, y = unit.center()
        radius = 30

        status_slow = pygame.time.get_ticks() < unit.slow_until
        body_color = unit.color
        if status_slow:
            body_color = (110, 170, 255)

        pygame.draw.circle(self.screen, body_color, (x, y), radius)
        pygame.draw.circle(self.screen, (20, 20, 20), (x, y), radius, 2)

        # HP bar
        bw, bh = 110, 12
        bx = x - bw // 2
        by = y - 48
        pygame.draw.rect(self.screen, (40, 40, 40), (bx, by, bw, bh), border_radius=4)
        fill = int(bw * (unit.hp / max(1, unit.max_hp)))
        pygame.draw.rect(self.screen, (220, 70, 70), (bx, by, fill, bh), border_radius=4)

        name = self.font_small.render(f"{unit.name} {unit.hp}/{unit.max_hp}", True, (235, 235, 235))
        self.screen.blit(name, (bx, by - 18))

        flags = []
        now = pygame.time.get_ticks()
        if now < unit.slow_until:
            flags.append(f"SLOW x{unit.slow_mult:.2f}")
        if now < unit.fire_dot_until:
            flags.append("BURN")
        if now < unit.acid_dot_until:
            flags.append("ACID")
        if flags:
            line = self.font_small.render(" | ".join(flags), True, (255, 220, 140))
            self.screen.blit(line, (bx, y + 36))

    def draw_hud(self):
        title = self.font.render("SKILL EFFECTS DEMO (outside main game)", True, (255, 255, 255))
        self.screen.blit(title, (20, 12))

        tips = [
            "1 fire   2 water_ball   3 wind   4 holy",
            "5 dark   6 wood         7 acid   8 shield",
            "9 earth  0 light        Q smoke  E thunder  F water_blast",
            "WASD / Arrow: aim wind direction",
            "TAB auto-demo on/off   R reset HP/status   ESC quit",
        ]
        for i, line in enumerate(tips):
            surf = self.font_small.render(line, True, (220, 220, 220))
            self.screen.blit(surf, (20, 42 + i * 22))

        state = "ON" if self.auto_demo else "OFF"
        info = self.font_small.render(f"Auto demo: {state} | Last skill: {self.last_skill}", True, (180, 255, 180))
        self.screen.blit(info, (20, 112))

        aim_txt = self.font_small.render(
            f"Wind aim: ({self.aim_dir.x:+.2f}, {self.aim_dir.y:+.2f})",
            True,
            (180, 220, 255),
        )
        self.screen.blit(aim_txt, (20, 134))

        if self.last_hint_ms > 0:
            hint = self.font.render(f"TRIGGER: {self.last_skill.upper()}", True, (255, 245, 135))
            self.screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, 16))

    def update(self):
        keys = pygame.key.get_pressed()
        self._update_aim_direction(keys)
        self.effects.update(self.dt)
        self.water_projectiles.update(self.dt)
        self.water_blast_projectiles.update(self.dt)
        self.light_projectiles.update(self.dt)
        self.dark_projectiles.update(self.dt)
        self.wood_projectiles.update(self.dt)
        self.acid_projectiles.update(self.dt)
        self.float_texts.update(self.dt)
        self._apply_wind_collisions()
        self._apply_waterball_collisions()
        self._apply_water_blast_collisions()
        self._apply_light_collisions()
        self._apply_dark_collisions()
        self._apply_wood_collisions()
        self._apply_acid_collisions()
        self.handle_status_ticks()

        if self.auto_demo:
            self.auto_timer += self.dt
            if self.auto_timer >= 900:
                self.auto_timer = 0
                self.trigger_skill(SKILLS[self.auto_idx])
                self.auto_idx = (self.auto_idx + 1) % len(SKILLS)

        self.last_hint_ms = max(0, self.last_hint_ms - self.dt)

    def draw(self):
        self.screen.fill((22, 24, 30))

        pygame.draw.rect(self.screen, (32, 36, 45), (0, HEIGHT // 2 + 60, WIDTH, 4))

        for unit in [self.player, self.enemy, self.enemy2, self.enemy3]:
            self.draw_unit(unit)

        self.water_projectiles.draw(self.screen)
        self.water_blast_projectiles.draw(self.screen)
        self.light_projectiles.draw(self.screen)
        self.dark_projectiles.draw(self.screen)
        self.wood_projectiles.draw(self.screen)
        self.acid_projectiles.draw(self.screen)
        self.effects.draw(self.screen)
        self.float_texts.draw(self.screen)
        self.draw_hud()

        pygame.display.flip()

    def run(self):
        key_to_skill = {
            pygame.K_1: "fire",
            pygame.K_2: "water_ball",
            pygame.K_3: "wind",
            pygame.K_4: "holy",
            pygame.K_5: "dark",
            pygame.K_6: "wood",
            pygame.K_7: "acid",
            pygame.K_8: "shield",
            pygame.K_9: "earth",
            pygame.K_0: "light",
            pygame.K_q: "smoke",
            pygame.K_e: "thunder",
            pygame.K_f: "water_blast",
        }

        while self.running:
            self.dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_TAB:
                        self.auto_demo = not self.auto_demo
                    elif event.key == pygame.K_r:
                        self.reset_demo()
                    elif event.key in key_to_skill:
                        self.trigger_skill(key_to_skill[event.key])

            self.update()
            self.draw()

        pygame.quit()


def main():
    demo = SkillEffectsDemo()
    demo.run()
    sys.exit()


if __name__ == "__main__":
    main()
