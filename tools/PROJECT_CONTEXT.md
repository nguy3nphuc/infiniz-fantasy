# Infiniiz Fantasy — Project Context

> Đọc file này trước khi sửa code. Nó tóm tắt kiến trúc và trạng thái hiện tại
> của đồ án để không cần quét lại toàn bộ repository.

## Mục tiêu

Game beat-'em-up 2D viết bằng Python + Pygame, theo hướng lập trình hướng đối
tượng. Game có hai người chơi cùng màn hình, nhiều phase quái, boss, combo,
ultimate, loot skill và hiệu ứng hình ảnh.

## Chạy project

```bash
pip install -r requirements.txt
python main.py
```

Dependency hiện tại: `pygame>=2.0`.

## Luồng chạy

```text
main.py
  └─ Game.run()                         # game.py
       ├─ SELECT                         # màn giới thiệu controls
       ├─ PHASE_SELECT                   # chọn phase 1 / 2 / 3
       └─ PLAY
            ├─ Game.load()               # map, players, sprite groups
            ├─ Game.events()             # input / spawn event
            ├─ Game.update(dt)           # AI, status, va chạm, loot
            └─ Game.draw()               # Y-sort, HUD, VFX
```

`dt` luôn dùng đơn vị milliseconds, nhận từ `clock.tick(FPS)`.

## File và trách nhiệm

| File | Vai trò |
| --- | --- |
| `main.py` | Entry point; tạo `Game` rồi gọi `run()`. |
| `game.py` | State machine, map/phase, sprite groups, combat collision, loot, skill, HUD, render. |
| `entities.py` | Player, enemy, boss, projectile, hitbox, item và VFX entity. |
| `sprites.py` | `SpriteSheet`, `Animator`, đọc metadata animation và xử lý pivot. |
| `config.py` | Hằng số gameplay/tuning và cấu hình effect/combat/drop của skill. |
| `assets/animation_metadata.json` | Nguồn dữ liệu animation: file, frame, duration, pivot, hit-frame, hitbox/hurtbox. |
| `assets/skills/ui_tune.json` | Căn chỉnh riêng từng slot UI skill bar. |
| `box_tool.py` | Editor hurtbox/hitbox, lưu vào animation metadata. |
| `pivot_tool.py` | Editor pivot animation, lưu vào animation metadata. |
| `skill_ui_tuner.py` | Sandbox chỉnh UI skill bar. |
| `skill_effects_demo.py` | Sandbox test VFX/projectile skill. |
| `test.py` | Test khởi tạo co-op/phase cơ bản; cần môi trường có Pygame. |

## Kiến trúc OOP

### Nền tảng

- Phần lớn đối tượng hiển thị kế thừa `pygame.sprite.Sprite`.
- `HealthMixin` cung cấp HP, armor, mana, reduction và `take_damage()`.
- `EnemyHealthBar` là object composition trong `HealthMixin`, không phải sprite group.
- `Animator` chuyển animation state, frame, hit frame và pivot delta.
- Mỗi character có `rect` (khung ảnh) và `hurtbox` (vùng va chạm logic).
  Khi sửa vị trí/animation phải giữ hurtbox đồng bộ theo pivot.

### Players

| Lớp | Đặc điểm |
| --- | --- |
| `Knight` | P1, melee combo 3 đòn, defend theo hướng nhận đòn, ultimate shockwave. |
| `Archer` | P2, bắn tên combo, dash có bất tử, ultimate beam. |

Mỗi player có inventory `skills` tối đa 3 skill, `target_skill_idx` và
`active_skill`. `active_skill` vừa là skill vừa cast gần nhất, vừa là passive
đang áp dụng cho đòn đánh/phòng thủ.

### Enemy

| Phase | Lớp | Hành vi chính |
| --- | --- | --- |
| 1 | `GoblinWarrior` | Melee combo 2 hit. |
| 1 | `GoblinSpearman` | Ném `Spear`. |
| 1 | `GoblinTank` | Boss, combo/heavy attack và camera shake. |
| 2 | `Lizardman` | Melee combo 2 hit. |
| 2 | `Kobold` | Combo 3 hit, dash xuyên qua/ra sau player. |
| 2 | `Fireworm` | Ranged, bắn `Fireball`. |
| 2 | `Cyclop` | Heavy melee; special attack có cooldown. |
| 3 | `FatCultist` | Miniboss. |
| 3 | `DeathBringer` | Boss melee + `DeathBringerSpell`. |

Phần lớn quái có state AI `chase`, `idle`, `wait`, attack/hurt/death. Sau chết
chúng chơi death animation rồi fade-out trước khi bị `kill()`.

## Sprite groups quan trọng

`Game.load()` tạo và truyền dictionary `self.groups` cho entity:

- `all`: entity cần render cơ bản.
- `enemies`, `potions`, `skills`: quái và loot trên bản đồ.
- `attacks`, `enemy_attacks`: melee hitbox.
- `arrows`, `enemy_projectiles`: projectile cơ bản.
- Các group projectile skill: `wind_projectiles`, `water_projectiles`,
  `water_blast_projectiles`, `light_projectiles`, `dark_projectiles`,
  `wood_projectiles`, `acid_projectiles`.
- `effects`, `damage_numbers`, `ultimate_beams`, `knight_shockwaves`: VFX và
  hitbox ultimate.

Đừng thêm sprite có update/render riêng vào sai group, vì `Game.update()` và
`Game.draw()` cập nhật/render từng group theo danh sách rõ ràng.

## Combat và va chạm

- Melee dùng `AttackHitbox`; mỗi hitbox có `already_hit_targets` để một mục
  tiêu chỉ nhận một lần damage.
- Va chạm có lọc theo chiều sâu đường đi bằng `foot_y` trước, rồi AABB
  (`rect.colliderect(hurtbox)`).
- Damage cuối cùng thường đi qua `Game._consume_entity_armor()`.
- Crit, damage number, blood/hit VFX được resolve tập trung trong `Game.update()`.
- `DEBUG_DRAW = True` trong `Game.__init__` để xem hurtbox/hitbox.
- Y-sort render dựa trên `foot_y`/`floor_y`; sprite mới nên cung cấp một trong
  hai property này nếu cần nằm đúng lớp sâu.

## Resources và skill

Các bảng cần chỉnh trước tiên nằm trong `config.py`:

- `PLAYER_RESOURCE_PRESETS`, `PLAYER_RESOURCE_REGEN_PER_MS`.
- `SKILL_MANA_COST`, `SKILL_TYPES`.
- `SKILL_DROP_CONFIG`: tier theo class quái và weighted drop table.
- `SKILL_EFFECT_CONFIG`: spritesheet VFX cho mỗi skill.
- `SKILL_COMBAT_CONFIG`: damage/multiplier/status cho mỗi skill.
- `ABILITY_*`: tỉ lệ rơi Poison Vial và mức tăng Attack/Armor/Speed.
- `BERSERK_*`: tỉ lệ rơi và chỉ số buff của bình đỏ Berserk.

Skill cast có handler riêng trong `Game.use_target_skill()`.

| Skill | Tác dụng chính |
| --- | --- |
| `fire` | Burst, tăng attack, DOT và splash. |
| `water_ball` | Projectile, slow và splash. |
| `wind` | Projectile, tăng speed, bleed/bonus damage. |
| `holy` | Heal on hit, regen aura. |
| `dark` | Lifesteal, bonus damage, biến **quái tier `normal`** thành zombie tạm thời; không tác động elite/miniboss/boss. |
| `wood` | Giảm damage phẳng, regen và phản damage. |
| `acid` | Projectile + DOT dài. |
| `shield` | Giảm damage. |
| `earth` | Ground spike/burst. |
| `light` | Projectile, chain và slow. |
| `smoke` | VFX/passive hiện có; chưa có projectile riêng. |
| `thunder` | Cast damage. |
| `water_blast` | Projectile diện rộng, slow/splash. |

## Controls thực tế

| Người chơi | Di chuyển | Attack | Phòng thủ/Dash | Ultimate | Skill |
| --- | --- | --- | --- | --- | --- |
| P1 Knight | WASD | J | K (defend) | L | N chọn, M dùng |
| P2 Archer | Arrow keys | Numpad 1/4 | Numpad 2/5 (dash) | Numpad 3/6 | 7 chọn, 8 dùng |

Archer nhấn `Numpad 0` (hoặc `0`) để đổi Magic Arrow: Normal (damage chuẩn),
Red/Burn (damage thấp + DOT), Blue/Slow (damage thấp + slow), Purple/Chain
(damage thấp + lan một mục tiêu gần). Thông số cân bằng nằm trong
`ARCHER_ARROW_CONFIG` của `config.py`.

Holy là aura có thời lượng 8 giây sau khi dùng. Thanh vàng `HOLY` bên dưới HUD
hiển thị thời gian còn lại; thời lượng chỉnh bằng `HOLY_EFFECT_DURATION_MS`.

Trong gameplay, nhấn `Esc` để pause/resume. Khi pause, update (AI, combat,
spawn và timer) dừng hoàn toàn; menu chọn phase vẫn dùng `Esc` để quay lại.

Quái chết có thể rơi **Poison Vial** màu xanh. Player nhặt vial nhận 1 ability
point. Khi pause, P1 dùng `1/2/3`, P2 dùng `7/8/9` (hoặc numpad `7/8/9`) để
nâng lần lượt Attack, Armor hoặc Speed; mỗi stat có giới hạn level trong
`config.py`.

Bình đỏ **Berserk Vial** kích hoạt ngay khi nhặt: +25% damage trong 8 giây,
đổi lại armor chỉ hấp thụ được 85% hiệu quả bình thường trong thời gian buff.

Lưu ý: README cũ nói chọn Knight/Archer, nhưng code hiện tại luôn tạo cả hai
player trong `Game.load()`.

## Phase và spawn hiện tại

- Phase 1: spawn Goblin Warrior/Spearman; sau khoảng 10 giây spawn Goblin Tank.
- Phase 2: spawn Lizardman/Kobold/Fireworm/Cyclop; **chưa có boss**.
- Phase 3: Fat Cultist spawn sau khoảng 1 giây; khi chết, đợi khoảng 3 giây rồi
  spawn Death Bringer.
- Phase 4: **Pixel Ruins Arena**, dựng cho Pygame từ
  `assets/maps/Pixel Art Top Down - Basic v1.2.3/Scene Overview.png`. PNG được
  giữ nguyên pixel 1:1 rồi crop giữa để phủ viewport 960×640; không dùng
  runtime Unity hay `.unitypackage`. Arena có wave quái hỗn hợp, không có boss.
  `pixel_ruins_map.py` render overview + `assets/maps/pixel_ruins_layout.json`.
  Dùng `python pixel_ruins_tuner.py` để đặt texture atlas (wall, struct, props,
  plant, grass, stone, shadow) và đánh dấu collider; nhấn `S` để xuất JSON.

## Quy ước khi sửa code

1. Tuning damage/range/cooldown nên đặt ở `config.py`, không hard-code thêm nếu
   không cần thiết.
2. Thông tin animation/hitbox/pivot nên nằm trong `assets/animation_metadata.json`.
3. Khi thêm quái mới cần tối thiểu: class entity, metadata animation, import ở
   `game.py`, spawn rule, drop tier (nếu cần), collision compatibility và asset.
4. Khi thêm skill: icon, VFX config, combat config, cast branch trong
   `use_target_skill()`, projectile/collision nếu skill có đạn.
5. `entities.py` và `game.py` đang lớn và có nhiều logic lặp lại giữa enemy;
   ưu tiên sửa có phạm vi hẹp để tránh regression.
6. Asset load thường có fallback surface để game không crash ngay, nhưng cần
   kiểm tra đường dẫn thật trước khi coi feature đã hoàn thành.

## Kiểm tra nhanh

```bash
python -m py_compile main.py game.py entities.py sprites.py config.py
python -m unittest test.py
```

Nếu test báo `ModuleNotFoundError: pygame`, hãy cài dependency vào đúng Python
environment đang chạy test.

## Cập nhật file này

Mỗi khi thay đổi đáng kể về kiến trúc, controls, phase, class mới, skill mới
hoặc đường dẫn asset, hãy cập nhật `PROJECT_CONTEXT.md` trong cùng commit với
thay đổi đó.
