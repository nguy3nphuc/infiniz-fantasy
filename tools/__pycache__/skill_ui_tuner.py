import json
import os
import pygame

from entities.core import SkillIcon

WIDTH = 1200
HEIGHT = 680
FPS = 60

BASE_DIR = os.path.dirname(__file__)
FRAME_PATH = os.path.join(BASE_DIR, "assets", "skills", "frames", "skill_frame.png")
TARGET_PATH = os.path.join(BASE_DIR, "assets", "skills", "frames", "target_skill.png")
OUTPUT_JSON = os.path.join(BASE_DIR, "assets", "skills", "ui_tune.json")

SKILLS_PREVIEW = ["water_ball", "fire", "wind"]


def load_image(path, fallback_size):
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception:
        surf = pygame.Surface(fallback_size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (255, 0, 0), surf.get_rect(), 2)
        return surf


def default_slot_centers(frame_img):
    bbox = frame_img.get_bounding_rect()
    pitch = bbox.width / 3.0
    return [
        [int(round(bbox.x + pitch * 0.5)), int(round(bbox.centery))],
        [int(round(bbox.x + pitch * 1.5)), int(round(bbox.centery))],
        [int(round(bbox.x + pitch * 2.5)), int(round(bbox.centery))],
    ]


def default_config(frame_img, target_img):
    frame_h = frame_img.get_height()
    target_h = target_img.get_height()
    frame_top = max(0, target_h - frame_h)

    return {
        "ui_scale": 3,
        "margin_x": 24,
        "margin_y": 18,
        "frame_top": frame_top,
        "slot_centers": default_slot_centers(frame_img),
        "bars": {
            "p1": {
                "reverse": False,
                "icon_offsets": [[0, 0], [0, 0], [0, 0]],
                "icon_scales": [1.0, 1.0, 1.0],
                "target_offsets": [[0, 0], [0, 0], [0, 0]],
                "target_scales": [0.82, 0.82, 0.82],
            },
            "p2": {
                "reverse": True,
                "icon_offsets": [[0, 0], [0, 0], [0, 0]],
                "icon_scales": [1.0, 1.0, 1.0],
                "target_offsets": [[0, 0], [0, 0], [0, 0]],
                "target_scales": [0.82, 0.82, 0.82],
            },
        },
    }


def load_config(frame_img, target_img):
    if not os.path.exists(OUTPUT_JSON):
        return default_config(frame_img, target_img)
    try:
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg
    except Exception:
        return default_config(frame_img, target_img)


def save_config(cfg):
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def get_icon(skill_type):
    icon_path = SkillIcon.SKILL_TYPES.get(skill_type, SkillIcon.SKILL_TYPES["fire"])
    return load_image(os.path.join(BASE_DIR, icon_path), (32, 32))


def scaled(surface, factor):
    w = max(1, int(round(surface.get_width() * factor)))
    h = max(1, int(round(surface.get_height() * factor)))
    return pygame.transform.scale(surface, (w, h))


def draw_bar(dst, x, y, frame_img, target_img, cfg, bar_key):
    bar_cfg = cfg["bars"][bar_key]
    slot_centers = cfg["slot_centers"]
    frame_top = cfg["frame_top"]
    skills = SKILLS_PREVIEW

    native_w = frame_img.get_width()
    native_h = max(frame_img.get_height() + frame_top, target_img.get_height())
    bar_native = pygame.Surface((native_w, native_h), pygame.SRCALPHA)
    bar_native.blit(frame_img, (0, frame_top))

    for display_idx in range(3):
        inv_idx = (2 - display_idx) if bar_cfg["reverse"] else display_idx
        if inv_idx >= len(skills):
            continue

        cx, cy = slot_centers[display_idx]

        icon = get_icon(skills[inv_idx])
        icon_scale = bar_cfg["icon_scales"][inv_idx]
        icon = scaled(icon, icon_scale)
        ox, oy = bar_cfg["icon_offsets"][inv_idx]
        ix = cx - icon.get_width() // 2 + ox
        iy = cy - icon.get_height() // 2 + oy
        bar_native.blit(icon, (ix, iy))

        t_scale = bar_cfg["target_scales"][inv_idx]
        target = scaled(target_img, t_scale)
        tx_off, ty_off = bar_cfg["target_offsets"][inv_idx]
        tx = cx - target.get_width() // 2 + tx_off
        ty = ty_off
        bar_native.blit(target, (tx, ty))

    ui_scale = max(1, int(cfg["ui_scale"]))
    bar_final = pygame.transform.scale(bar_native, (native_w * ui_scale, native_h * ui_scale))
    dst.blit(bar_final, (x, y))
    return bar_final.get_size()


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Skill UI Tuner")
    clock = pygame.time.Clock()

    frame_img = load_image(FRAME_PATH, (151, 36))
    target_img = load_image(TARGET_PATH, (40, 59))
    cfg = load_config(frame_img, target_img)

    selected_bar = "p1"
    selected_slot = 0
    selected_item = "icon"  # icon | target | center
    running = True

    while running:
        dt = clock.tick(FPS)
        _ = dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type != pygame.KEYDOWN:
                continue

            k = event.key
            if k == pygame.K_ESCAPE:
                running = False

            elif k == pygame.K_TAB:
                selected_bar = "p2" if selected_bar == "p1" else "p1"

            elif k in (pygame.K_1, pygame.K_2, pygame.K_3):
                selected_slot = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2}[k]

            elif k == pygame.K_i:
                selected_item = "icon"
            elif k == pygame.K_t:
                selected_item = "target"
            elif k == pygame.K_c:
                selected_item = "center"

            elif k == pygame.K_EQUALS:
                cfg["ui_scale"] = min(8, int(cfg["ui_scale"]) + 1)
            elif k == pygame.K_MINUS:
                cfg["ui_scale"] = max(1, int(cfg["ui_scale"]) - 1)

            elif k == pygame.K_LEFT:
                if selected_item == "icon":
                    cfg["bars"][selected_bar]["icon_offsets"][selected_slot][0] -= 1
                elif selected_item == "target":
                    cfg["bars"][selected_bar]["target_offsets"][selected_slot][0] -= 1
                else:
                    cfg["slot_centers"][selected_slot][0] -= 1

            elif k == pygame.K_RIGHT:
                if selected_item == "icon":
                    cfg["bars"][selected_bar]["icon_offsets"][selected_slot][0] += 1
                elif selected_item == "target":
                    cfg["bars"][selected_bar]["target_offsets"][selected_slot][0] += 1
                else:
                    cfg["slot_centers"][selected_slot][0] += 1

            elif k == pygame.K_UP:
                if selected_item == "icon":
                    cfg["bars"][selected_bar]["icon_offsets"][selected_slot][1] -= 1
                elif selected_item == "target":
                    cfg["bars"][selected_bar]["target_offsets"][selected_slot][1] -= 1
                else:
                    cfg["slot_centers"][selected_slot][1] -= 1

            elif k == pygame.K_DOWN:
                if selected_item == "icon":
                    cfg["bars"][selected_bar]["icon_offsets"][selected_slot][1] += 1
                elif selected_item == "target":
                    cfg["bars"][selected_bar]["target_offsets"][selected_slot][1] += 1
                else:
                    cfg["slot_centers"][selected_slot][1] += 1

            elif k == pygame.K_RIGHTBRACKET:
                if selected_item == "icon":
                    s = cfg["bars"][selected_bar]["icon_scales"][selected_slot]
                    cfg["bars"][selected_bar]["icon_scales"][selected_slot] = round(min(2.0, s + 0.02), 2)
                elif selected_item == "target":
                    s = cfg["bars"][selected_bar]["target_scales"][selected_slot]
                    cfg["bars"][selected_bar]["target_scales"][selected_slot] = round(min(2.0, s + 0.02), 2)

            elif k == pygame.K_LEFTBRACKET:
                if selected_item == "icon":
                    s = cfg["bars"][selected_bar]["icon_scales"][selected_slot]
                    cfg["bars"][selected_bar]["icon_scales"][selected_slot] = round(max(0.1, s - 0.02), 2)
                elif selected_item == "target":
                    s = cfg["bars"][selected_bar]["target_scales"][selected_slot]
                    cfg["bars"][selected_bar]["target_scales"][selected_slot] = round(max(0.1, s - 0.02), 2)

            elif k == pygame.K_u:
                cfg["margin_x"] = max(0, cfg["margin_x"] - 1)
            elif k == pygame.K_j:
                cfg["margin_x"] += 1
            elif k == pygame.K_k:
                cfg["margin_y"] = max(0, cfg["margin_y"] - 1)
            elif k == pygame.K_m:
                cfg["margin_y"] += 1

            elif k == pygame.K_s:
                save_config(cfg)
                print("Saved:", OUTPUT_JSON)

            elif k == pygame.K_p:
                print(json.dumps(cfg, indent=2))

        screen.fill((28, 42, 28))

        # Draw bars with the same config but independent per-slot parameters.
        x_left = cfg["margin_x"]
        y = HEIGHT // 2 - 50
        bar_size = draw_bar(screen, x_left, y, frame_img, target_img, cfg, "p1")
        x_right = WIDTH - cfg["margin_x"] - bar_size[0]
        draw_bar(screen, x_right, y, frame_img, target_img, cfg, "p2")

        font = pygame.font.SysFont("Consolas", 16, bold=True)
        small = pygame.font.SysFont("Consolas", 14)

        title = "Skill UI Tuner (standalone)"
        help1 = "TAB bar | 1/2/3 slot | I icon | T target | C center"
        help2 = "Arrows move selected | [ ] scale selected | = - ui scale"
        help3 = "U/J margin X | K/M margin Y | S save JSON | P print | ESC quit"

        info = (
            f"bar={selected_bar} slot={selected_slot + 1} item={selected_item} "
            f"ui_scale={cfg['ui_scale']} margin=({cfg['margin_x']},{cfg['margin_y']})"
        )

        screen.blit(font.render(title, True, (255, 245, 210)), (12, 12))
        screen.blit(small.render(help1, True, (215, 230, 255)), (12, 40))
        screen.blit(small.render(help2, True, (215, 230, 255)), (12, 60))
        screen.blit(small.render(help3, True, (215, 230, 255)), (12, 80))
        screen.blit(small.render(info, True, (255, 220, 150)), (12, HEIGHT - 28))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
