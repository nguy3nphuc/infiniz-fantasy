#!/usr/bin/env python3
"""
Hitbox / Hurtbox Editor — Visual tool for setting per-character hurtboxes
and per-animation attack hitboxes.

The tool mirrors the design of pivot_tool.py:
  • Left panel   – zoomed sprite view with colour-coded box overlays
  • Right panel  – live preview at game scale

Box data is stored in assets/animation_metadata.json:
  Character-level  : hurtbox_w, hurtbox_h, hurtbox_offset_x
  Animation-level  : hitbox_w, hitbox_h, hitbox_offset_x, hitbox_offset_y
                     (only on states that have an attack hitbox)

Usage:  python box_tool.py

Controls:
    ←  /  →        Navigate animation states
    ↑  /  ↓        Navigate characters
    H               Edit Hurtbox
    B               Edit attack Hitbox (only when the state has one)
    Left-click      Place / drag box corner or edge on the zoomed view
    Right-click     Remove attack hitbox from current state
    R               Reset active box to default
    S               Save all boxes to animation_metadata.json
    Space           Play / Pause animation preview
    Esc             Quit
"""

import pygame
import json
import os
import sys
import copy

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
METADATA_PATH = os.path.join(_SCRIPT_DIR, "assets", "animation_metadata.json")

# ---------------------------------------------------------------------------
# Layout & Colours
# ---------------------------------------------------------------------------
WIN_W, WIN_H = 1400, 900

BG           = (18, 18, 24)
PANEL_BG     = (30, 30, 38)
GRID_COL     = (50, 50, 62)
TEXT_COL     = (210, 210, 210)
DIM_COL      = (110, 110, 130)
HIGHLIGHT    = (255, 200, 50)
MODIFIED_COL = (255, 90, 90)

HURTBOX_COL   = (130, 80, 255)    # purple
HURTBOX_FILL  = (130, 80, 255, 40)
HITBOX_COL    = (255, 60, 60)     # red
HITBOX_FILL   = (255, 60, 60, 40)
ACTIVE_COL    = (255, 220, 0)     # gold outline when box is selected

ZOOM_X, ZOOM_Y    = 30, 100
MAX_ZOOM_W         = 550
MAX_ZOOM_H         = 640
RIGHT_X            = 650
LIST_X             = WIN_W - 200

HANDLE_RADIUS = 6   # px radius of corner / edge drag handles

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_metadata():
    with open(METADATA_PATH, "r") as f:
        return json.load(f)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ============================================================================
# Main editor
# ============================================================================
class BoxEditor:
    """Interactive hurtbox + hitbox editor for 2-D spritesheets."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Hitbox / Hurtbox Editor")
        self.clock = pygame.time.Clock()

        self.font_lg = pygame.font.SysFont("Consolas", 20, bold=True)
        self.font    = pygame.font.SysFont("Consolas", 15)
        self.font_sm = pygame.font.SysFont("Consolas", 12)

        self.metadata   = _load_metadata()
        # Filter to only characters that have a "folder" (skip effect-only entries)
        self.char_names = [
            cn for cn, cd in self.metadata.items()
            if "folder" in cd and "animations" in cd
        ]
        self.char_idx  = 0
        self.state_idx = 0

        # ── Pre-load all spritesheets ─────────────────────────────────
        self.frames_cache = {}  # (char, state) -> [Surface …]
        self.dims_cache   = {}  # (char, state) -> (fw, fh) unscaled

        for cn in self.char_names:
            cd = self.metadata[cn]
            folder = cd.get("folder", "")
            for sn, ai in cd.get("animations", {}).items():
                fp = os.path.join(_SCRIPT_DIR, folder, ai["file"])
                fc = ai.get("frames", 1)
                if not os.path.isfile(fp):
                    self.frames_cache[(cn, sn)] = []
                    self.dims_cache[(cn, sn)]   = (32, 32)
                    continue
                sheet = pygame.image.load(fp).convert_alpha()
                sw, sh = sheet.get_size()
                fw = sw // fc
                self.dims_cache[(cn, sn)] = (fw, sh)
                frms = []
                for i in range(fc):
                    sub = pygame.Surface((fw, sh), pygame.SRCALPHA)
                    sub.blit(sheet, (0, 0), (i * fw, 0, fw, sh))
                    frms.append(sub)
                self.frames_cache[(cn, sn)] = frms

        # ── Hurtbox data: (w, h, offset_x) per character ─────────────
        # Stored as unscaled pixels; displayed in the zoomed view.
        self.hurtboxes     = {}  # char -> [w, h, offset_x]
        self.hb_modified   = {}  # char -> bool

        for cn in self.char_names:
            cd = self.metadata[cn]
            # Use idle frame to derive defaults
            idle_ai    = cd.get("animations", {}).get("idle", {})
            ifw, ifh   = self.dims_cache.get((cn, "idle"), (32, 32))
            default_w  = max(1, ifw // 2)
            default_h  = max(1, ifh)
            self.hurtboxes[cn]   = [
                cd.get("hurtbox_w",        default_w),
                cd.get("hurtbox_h",        default_h),
                cd.get("hurtbox_offset_x", 0),
            ]
            self.hb_modified[cn] = (
                "hurtbox_w" in cd or "hurtbox_h" in cd or "hurtbox_offset_x" in cd
            )

        # ── Hitbox data: (w, h, offset_x, offset_y) per (char, state) ─
        # Only stored for attack states.
        ATTACK_KEYWORDS = ("attack", "dash_special")
        RANGED_CHARS    = ("archer", "fireworm", "goblin_spearman")
        self.hitboxes    = {}   # (char, state) -> [w, h, offset_x, offset_y] or None
        self.hx_modified = {}   # (char, state) -> bool

        for cn in self.char_names:
            for sn, ai in self.metadata[cn].get("animations", {}).items():
                key = (cn, sn)
                if "hitbox_w" in ai:
                    self.hitboxes[key]    = [
                        ai["hitbox_w"],
                        ai["hitbox_h"],
                        ai.get("hitbox_offset_x", 0),
                        ai.get("hitbox_offset_y", 0),
                    ]
                    self.hx_modified[key] = True
                elif cn not in RANGED_CHARS and any(k in sn for k in ATTACK_KEYWORDS):
                    # Provide sensible defaults so user can start editing
                    fw, fh = self.dims_cache.get(key, (32, 32))
                    sc     = self.metadata[cn].get("scale", 1.0)
                    self.hitboxes[key]    = [
                        max(1, int(fw * 0.8)),
                        max(1, int(fh * 0.5)),
                        0, 0,
                    ]
                    self.hx_modified[key] = False
                else:
                    self.hitboxes[key]    = None
                    self.hx_modified[key] = False

        # ── Pivot data (read-only, needed for alignment preview) ──────
        self.pivots = {}
        for cn in self.char_names:
            for sn, ai in self.metadata[cn].get("animations", {}).items():
                fw, fh = self.dims_cache.get((cn, sn), (32, 32))
                self.pivots[(cn, sn)] = (
                    ai.get("pivot_x", fw // 2),
                    ai.get("pivot_y", fh),
                )

        # ── Editor state ──────────────────────────────────────────────
        self.active_box  = "hurtbox"  # "hurtbox" | "hitbox"
        self.playing     = True
        self.anim_time   = 0
        self.anim_frame  = 0
        self.dirty       = False

        # Drag state
        self._drag_handle  = None   # None or (side, axis) description string
        self._drag_start   = None   # mouse pos when drag began
        self._drag_box_start = None # box list snapshot when drag began

    # ── Property helpers ──────────────────────────────────────────────
    @property
    def char(self):
        return self.char_names[self.char_idx]

    @property
    def states(self):
        return list(self.metadata[self.char].get("animations", {}).keys())

    @property
    def state(self):
        self.state_idx %= max(1, len(self.states))
        return self.states[self.state_idx]

    @property
    def scale(self):
        return self.metadata[self.char].get("scale", 1.0)

    def _frames(self):
        return self.frames_cache.get((self.char, self.state), [])

    def _dims(self):
        return self.dims_cache.get((self.char, self.state), (32, 32))

    def _ainfo(self):
        return self.metadata[self.char]["animations"][self.state]

    def _zoom(self):
        fw, fh = self._dims()
        z = min(14, MAX_ZOOM_W // max(1, fw), MAX_ZOOM_H // max(1, fh))
        return max(2, z)

    # Return mutable box list for current selection (may be None for hitbox)
    def _hurtbox(self):
        return self.hurtboxes[self.char]

    def _hitbox(self):
        return self.hitboxes.get((self.char, self.state))

    def _current_box(self):
        if self.active_box == "hurtbox":
            return self._hurtbox()
        return self._hitbox()

    def _has_hitbox(self):
        """True if the current state has / can have an attack hitbox."""
        return self.hitboxes.get((self.char, self.state)) is not None

    # ══════════════════════════════════════════════════════════════════
    # Main loop
    # ══════════════════════════════════════════════════════════════════
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    if not self._on_key(ev.key):
                        running = False
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    if ev.button == 1:
                        self._begin_drag(ev.pos)
                    elif ev.button == 3:
                        self._remove_hitbox()
                elif ev.type == pygame.MOUSEMOTION:
                    if self._drag_handle is not None:
                        self._update_drag(ev.pos)
                elif ev.type == pygame.MOUSEBUTTONUP:
                    if ev.button == 1:
                        self._end_drag()

            if self.playing:
                self._tick_anim(dt)
            self._draw()
            pygame.display.flip()
        pygame.quit()

    # ── Input ─────────────────────────────────────────────────────────
    def _on_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.dirty:
                print("[!] Unsaved changes — press S to save first.")
                return True
            return False
        elif key == pygame.K_RIGHT:
            self.state_idx = (self.state_idx + 1) % len(self.states)
            self.anim_frame = self.anim_time = 0
            # Auto-switch active box when entering a non-attack state
            if not self._has_hitbox():
                self.active_box = "hurtbox"
        elif key == pygame.K_LEFT:
            self.state_idx = (self.state_idx - 1) % len(self.states)
            self.anim_frame = self.anim_time = 0
            if not self._has_hitbox():
                self.active_box = "hurtbox"
        elif key == pygame.K_DOWN:
            self.char_idx  = (self.char_idx + 1) % len(self.char_names)
            self.state_idx = 0
            self.anim_frame = self.anim_time = 0
            self.active_box = "hurtbox"
        elif key == pygame.K_UP:
            self.char_idx  = (self.char_idx - 1) % len(self.char_names)
            self.state_idx = 0
            self.anim_frame = self.anim_time = 0
            self.active_box = "hurtbox"
        elif key == pygame.K_h:
            self.active_box = "hurtbox"
        elif key == pygame.K_b:
            if self._has_hitbox():
                self.active_box = "hitbox"
            else:
                print("[!] This state has no attack hitbox.  "
                      "Right-click would remove, but nothing is set.")
        elif key == pygame.K_SPACE:
            self.playing = not self.playing
        elif key == pygame.K_r:
            self._reset_active_box()
        elif key == pygame.K_s:
            self._save()
        return True

    # ── Drag handles ──────────────────────────────────────────────────
    # Box format:  [w, h, offset_x, offset_y]
    # Hurtbox:     [w, h, offset_x]  (no offset_y — always midbottom of pivot)
    # In the zoomed view the hurtbox is anchored at the pivot point of the
    # idle frame (centre-bottom of the canvas), and the hitbox is placed
    # right of / left of that anchor.

    def _box_screen_rect(self, z, fw, fh):
        """Return (x, y, w, h) in screen coordinates for the active box
        in the zoomed frame view (facing right / +x direction)."""
        px, py = self.pivots.get((self.char, self.state),
                                 (fw // 2, fh))
        pivot_sx = ZOOM_X + px * z
        pivot_sy = ZOOM_Y + py * z

        if self.active_box == "hurtbox":
            box = self._hurtbox()
            bw, bh, box_ox = box[0], box[1], box[2]
            # hurtbox is centred on the pivot with an x offset
            left = pivot_sx + box_ox * z - (bw * z) // 2
            top  = pivot_sy - bh * z
            return (left, top, bw * z, bh * z)
        else:
            box = self._hitbox()
            if box is None:
                return None
            bw, bh, box_ox, box_oy = box
            # hitbox placed to the right of the pivot (facing == 1)
            left = pivot_sx + box_ox * z
            top  = pivot_sy - (bh * z) // 2 + box_oy * z
            return (left, top, bw * z, bh * z)

    def _handles(self, rect):
        """Return list of (name, pygame.Rect) for the 8 drag handles."""
        x, y, w, h = rect
        cx, cy = x + w // 2, y + h // 2
        r = HANDLE_RADIUS
        return [
            ("top-left",     pygame.Rect(x - r,      y - r,      r*2, r*2)),
            ("top-mid",      pygame.Rect(cx - r,     y - r,      r*2, r*2)),
            ("top-right",    pygame.Rect(x + w - r,  y - r,      r*2, r*2)),
            ("mid-left",     pygame.Rect(x - r,      cy - r,     r*2, r*2)),
            ("mid-right",    pygame.Rect(x + w - r,  cy - r,     r*2, r*2)),
            ("bot-left",     pygame.Rect(x - r,      y + h - r,  r*2, r*2)),
            ("bot-mid",      pygame.Rect(cx - r,     y + h - r,  r*2, r*2)),
            ("bot-right",    pygame.Rect(x + w - r,  y + h - r,  r*2, r*2)),
        ]

    def _begin_drag(self, pos):
        frms = self._frames()
        if not frms:
            return
        fw, fh = self._dims()
        z = self._zoom()
        brect = self._box_screen_rect(z, fw, fh)
        if brect is None:
            return

        mx, my = pos
        # Check handle hit first
        for name, hrect in self._handles(brect):
            if hrect.collidepoint(mx, my):
                self._drag_handle = name
                self._drag_start  = pos
                box = self._current_box()
                self._drag_box_start = list(box) if box else None
                return

        # Inside the box body — move the entire box (offset_x / offset_y)
        bx, by, bw, bh = brect
        if bx <= mx <= bx + bw and by <= my <= by + bh:
            self._drag_handle = "move"
            self._drag_start  = pos
            box = self._current_box()
            self._drag_box_start = list(box) if box else None

    def _update_drag(self, pos):
        if self._drag_handle is None or self._drag_box_start is None:
            return
        fw, fh = self._dims()
        z = self._zoom()
        dx_px = (pos[0] - self._drag_start[0]) / z   # unscaled pixels
        dy_px = (pos[1] - self._drag_start[1]) / z

        box  = self._current_box()
        base = self._drag_box_start
        h    = self._drag_handle

        if self.active_box == "hurtbox":
            bw, bh, box_ox = base[0], base[1], base[2]
            if h == "move":
                box[2] = round(box_ox + dx_px)
            elif "left" in h:
                new_w = max(2, round(bw - dx_px))
                box[0] = new_w
                box[2] = round(box_ox + (bw - new_w) / 2)
            elif "right" in h:
                box[0] = max(2, round(bw + dx_px))
            if "top" in h:
                new_h = max(2, round(bh - dy_px))
                box[1] = new_h
            elif "bot" in h:
                box[1] = max(2, round(bh + dy_px))
            self.hb_modified[self.char] = True
        else:
            bw, bh, box_ox, box_oy = base[0], base[1], base[2], base[3]
            if h == "move":
                box[2] = round(box_ox + dx_px)
                box[3] = round(box_oy + dy_px)
            elif "left" in h:
                new_w = max(2, round(bw - dx_px))
                box[0] = new_w
                box[2] = round(box_ox + (bw - new_w))
            elif "right" in h:
                box[0] = max(2, round(bw + dx_px))
            if "top" in h:
                new_h = max(2, round(bh - dy_px))
                box[1] = new_h
                box[3] = round(box_oy + (bh - new_h))
            elif "bot" in h:
                box[1] = max(2, round(bh + dy_px))
            self.hx_modified[(self.char, self.state)] = True

        self.dirty = True

    def _end_drag(self):
        self._drag_handle    = None
        self._drag_start     = None
        self._drag_box_start = None

    def _remove_hitbox(self):
        """Right-click removes the hitbox from the current attack state."""
        key = (self.char, self.state)
        if self.hitboxes.get(key) is not None:
            self.hitboxes[key]    = None
            self.hx_modified[key] = False
            self.dirty            = True

    def _reset_active_box(self):
        fw, fh = self._dims()
        if self.active_box == "hurtbox":
            self.hurtboxes[self.char]   = [fw // 2, fh, 0]
            self.hb_modified[self.char] = False
            self.dirty = True
        else:
            key = (self.char, self.state)
            self.hitboxes[key]    = [max(1, fw // 2), max(1, fh // 2), 0, 0]
            self.hx_modified[key] = True
            self.dirty = True

    def _tick_anim(self, dt):
        frms = self._frames()
        if len(frms) <= 1:
            return
        dur = self._ainfo().get("duration", 100)
        self.anim_time += dt
        while self.anim_time >= dur:
            self.anim_time -= dur
            self.anim_frame = (self.anim_frame + 1) % len(frms)

    # ── Save ──────────────────────────────────────────────────────────
    def _save(self):
        out = copy.deepcopy(self.metadata)
        for cn in self.char_names:
            hb = self.hurtboxes[cn]
            out[cn]["hurtbox_w"]        = hb[0]
            out[cn]["hurtbox_h"]        = hb[1]
            out[cn]["hurtbox_offset_x"] = hb[2]
            for sn in out[cn].get("animations", {}).keys():
                hx = self.hitboxes.get((cn, sn))
                if hx is not None:
                    out[cn]["animations"][sn]["hitbox_w"]        = hx[0]
                    out[cn]["animations"][sn]["hitbox_h"]        = hx[1]
                    out[cn]["animations"][sn]["hitbox_offset_x"] = hx[2]
                    out[cn]["animations"][sn]["hitbox_offset_y"] = hx[3]
                else:
                    # Remove stale hitbox fields
                    for k in ("hitbox_w", "hitbox_h", "hitbox_offset_x", "hitbox_offset_y"):
                        out[cn]["animations"][sn].pop(k, None)
        with open(METADATA_PATH, "w") as f:
            json.dump(out, f, indent=4)
        self.metadata = out
        self.dirty    = False
        print(f"[OK] Saved box data to {METADATA_PATH}")

    # ══════════════════════════════════════════════════════════════════
    # Drawing
    # ══════════════════════════════════════════════════════════════════
    def _txt(self, text, x, y, font=None, col=TEXT_COL):
        surf = (font or self.font).render(str(text), True, col)
        self.screen.blit(surf, (x, y))

    def _draw(self):
        self.screen.fill(BG)
        fw, fh = self._dims()
        z      = self._zoom()
        frms   = self._frames()

        # ── Header ───────────────────────────────────────────────────
        self._txt(self.char, 30, 10, self.font_lg, HIGHLIGHT)
        self._txt(f"{self.state}  [{self.state_idx+1}/{len(self.states)}]",
                  300, 12, self.font_lg)

        mode_str = f"  [Editing: {'HURTBOX (H)' if self.active_box=='hurtbox' else 'HITBOX (B)'}]"
        self._txt(mode_str, 30, 48,
                  col=HURTBOX_COL if self.active_box == "hurtbox" else HITBOX_COL)

        hb  = self._hurtbox()
        hbx = self._hitbox()
        hb_str = f"Hurtbox  {hb[0]}×{hb[1]}  off_x={hb[2]}"
        hx_str = (f"Hitbox  {hbx[0]}×{hbx[1]}  off_x={hbx[2]}  off_y={hbx[3]}"
                  if hbx else "Hitbox  —")
        self._txt(hb_str, 30, 70,  font=self.font_sm, col=HURTBOX_COL)
        self._txt(hx_str, 300, 70, font=self.font_sm, col=HITBOX_COL)
        self._txt(f"Frame {fw}×{fh}   Zoom {z}x   Scale {self.scale}x",
                  700, 70, font=self.font_sm, col=DIM_COL)

        if self.dirty:
            self._txt("● UNSAVED", WIN_W - 160, 12, self.font, MODIFIED_COL)

        # ── Zoomed frame view ─────────────────────────────────────────
        self._draw_zoomed(z, fw, fh, frms)

        # ── Game-scale preview ────────────────────────────────────────
        self._txt("PREVIEW (game scale, facing right)",
                  RIGHT_X, 88, self.font_sm, DIM_COL)
        self._draw_preview(RIGHT_X, 110, frms)

        # ── Playback ──────────────────────────────────────────────────
        play_y  = 530
        status  = "▶ PLAYING" if self.playing else "⏸ PAUSED"
        self._txt(f"ANIMATION PLAYBACK   {status}",
                  RIGHT_X, play_y - 18, self.font_sm, DIM_COL)
        self._draw_playback(RIGHT_X, play_y, frms, fw, fh, z)

        # ── Navigation lists ──────────────────────────────────────────
        self._draw_lists()

        # ── Footer ───────────────────────────────────────────────────
        self._txt(
            "←/→ Anim   ↑/↓ Char   H: Hurtbox   B: Hitbox   "
            "Drag: resize/move   RClick: remove hitbox   R: Reset   S: Save   Esc: Quit",
            30, WIN_H - 35, self.font_sm, DIM_COL)

    # ─────────────────────────────────────────────────────────────────
    def _draw_zoomed(self, z, fw, fh, frms):
        zw, zh = fw * z, fh * z
        pad = 8

        pygame.draw.rect(self.screen, PANEL_BG,
                         (ZOOM_X - pad, ZOOM_Y - pad,
                          zw + pad * 2, zh + pad * 2),
                         border_radius=4)

        # Sprite frame
        if frms:
            zoomed = pygame.transform.scale(frms[0], (zw, zh))
            self.screen.blit(zoomed, (ZOOM_X, ZOOM_Y))

        # Pixel grid
        for gx in range(fw + 1):
            lx = ZOOM_X + gx * z
            pygame.draw.line(self.screen, GRID_COL,
                             (lx, ZOOM_Y), (lx, ZOOM_Y + zh))
        for gy in range(fh + 1):
            ly = ZOOM_Y + gy * z
            pygame.draw.line(self.screen, GRID_COL,
                             (ZOOM_X, ly), (ZOOM_X + zw, ly))

        px, py = self.pivots.get((self.char, self.state), (fw // 2, fh))
        pivot_sx = ZOOM_X + px * z
        pivot_sy = ZOOM_Y + py * z

        # Draw hurtbox
        hb  = self._hurtbox()
        hbw_s, hbh_s, hbox_s = hb[0] * z, hb[1] * z, hb[2] * z
        hb_left = pivot_sx + hbox_s - hbw_s // 2
        hb_top  = pivot_sy - hbh_s
        self._draw_box_overlay(hb_left, hb_top, hbw_s, hbh_s,
                               HURTBOX_COL, HURTBOX_FILL,
                               active=(self.active_box == "hurtbox"))

        # Draw attack hitbox (if any)
        hx = self._hitbox()
        if hx is not None:
            hxw_s = hx[0] * z
            hxh_s = hx[1] * z
            hx_left = pivot_sx + hx[2] * z
            hx_top  = pivot_sy - hxh_s // 2 + hx[3] * z
            self._draw_box_overlay(hx_left, hx_top, hxw_s, hxh_s,
                                   HITBOX_COL, HITBOX_FILL,
                                   active=(self.active_box == "hitbox"))

        # Pivot marker
        pygame.draw.circle(self.screen, (255, 255, 0),
                           (int(pivot_sx), int(pivot_sy)), 4)
        self._txt("pivot", int(pivot_sx) + 6, int(pivot_sy) - 10,
                  self.font_sm, (255, 255, 0))

    def _draw_box_overlay(self, x, y, w, h, col, fill_col, active=False):
        """Draw a semi-transparent filled rect + solid border + handles."""
        fill_surf = pygame.Surface((max(1, int(w)), max(1, int(h))), pygame.SRCALPHA)
        fill_surf.fill(fill_col)
        self.screen.blit(fill_surf, (int(x), int(y)))

        border_col = ACTIVE_COL if active else col
        border_w   = 3 if active else 2
        pygame.draw.rect(self.screen, border_col,
                         (int(x), int(y), int(w), int(h)), border_w)

        if active:
            rect = (int(x), int(y), int(w), int(h))
            for _name, hrect in self._handles(rect):
                pygame.draw.rect(self.screen, ACTIVE_COL, hrect)
                pygame.draw.rect(self.screen, (0, 0, 0), hrect, 1)

    # ─────────────────────────────────────────────────────────────────
    def _draw_preview(self, x, y, cur_frames):
        """Game-scale preview with hurtbox (purple) and hitbox (red) overlaid."""
        sc     = self.scale
        ref_x  = x + 200
        ref_y  = y + 350

        # Ground line
        pygame.draw.line(self.screen, (55, 55, 70),
                         (x, ref_y), (x + 420, ref_y), 1)

        if cur_frames and self.anim_frame < len(cur_frames):
            fw, fh = self._dims()
            px, py = self.pivots.get((self.char, self.state), (fw // 2, fh))
            sw, sh = int(fw * sc), int(fh * sc)
            cur = pygame.transform.scale(cur_frames[self.anim_frame], (sw, sh))
            self.screen.blit(cur,
                             (ref_x - int(px * sc),
                              ref_y - int(py * sc)))

        # Hurtbox overlay
        hb = self._hurtbox()
        hb_w_s = int(hb[0] * sc)
        hb_h_s = int(hb[1] * sc)
        hb_ox_s = int(hb[2] * sc)
        hbx = ref_x + hb_ox_s - hb_w_s // 2
        hby = ref_y - hb_h_s
        self._draw_box_overlay(hbx, hby, hb_w_s, hb_h_s,
                               HURTBOX_COL, HURTBOX_FILL,
                               active=(self.active_box == "hurtbox"))

        # Hitbox overlay
        hx = self._hitbox()
        if hx is not None:
            hx_w_s  = int(hx[0] * sc)
            hx_h_s  = int(hx[1] * sc)
            hx_ox_s = int(hx[2] * sc)
            hx_oy_s = int(hx[3] * sc)
            hxx = ref_x + hx_ox_s
            hxy = ref_y - hx_h_s // 2 + hx_oy_s
            self._draw_box_overlay(hxx, hxy, hx_w_s, hx_h_s,
                                   HITBOX_COL, HITBOX_FILL,
                                   active=(self.active_box == "hitbox"))

        pygame.draw.circle(self.screen, (255, 255, 0), (ref_x, ref_y), 4)
        self._txt("pivot", ref_x + 6, ref_y - 10, self.font_sm, (255, 255, 0))

    # ─────────────────────────────────────────────────────────────────
    def _draw_playback(self, x, y, frms, fw, fh, z):
        if not frms:
            return
        fi     = self.anim_frame % len(frms)
        sc     = self.scale
        ref_x  = x + 200
        ref_y  = y + 220
        px, py = self.pivots.get((self.char, self.state), (fw // 2, fh))
        sw, sh = int(fw * sc), int(fh * sc)

        pygame.draw.line(self.screen, (55, 55, 70),
                         (x, ref_y), (x + 420, ref_y), 1)

        scaled = pygame.transform.scale(frms[fi], (sw, sh))
        self.screen.blit(scaled,
                         (ref_x - int(px * sc),
                          ref_y - int(py * sc)))

        # Hurtbox on playback
        hb    = self._hurtbox()
        hb_ws = int(hb[0] * sc)
        hb_hs = int(hb[1] * sc)
        hb_os = int(hb[2] * sc)
        pygame.draw.rect(self.screen, HURTBOX_COL,
                         (ref_x + hb_os - hb_ws // 2, ref_y - hb_hs, hb_ws, hb_hs), 2)

        hx = self._hitbox()
        if hx is not None:
            hx_ws  = int(hx[0] * sc)
            hx_hs  = int(hx[1] * sc)
            hx_oys = int(hx[3] * sc)
            pygame.draw.rect(self.screen, HITBOX_COL,
                             (ref_x + int(hx[2] * sc),
                              ref_y - hx_hs // 2 + hx_oys,
                              hx_ws, hx_hs), 2)

        pygame.draw.circle(self.screen, (255, 60, 60), (ref_x, ref_y), 3)
        self._txt(f"Frame {fi+1}/{len(frms)}", x, y + 240, self.font_sm, DIM_COL)

    # ─────────────────────────────────────────────────────────────────
    def _draw_lists(self):
        # Characters
        self._txt("CHARACTERS", LIST_X, 88, self.font_sm, DIM_COL)
        for i, cn in enumerate(self.char_names):
            pre = "▶ " if i == self.char_idx else "  "
            col = HIGHLIGHT if i == self.char_idx else DIM_COL
            self._txt(f"{pre}{cn}", LIST_X, 108 + i * 22, self.font_sm, col)

        # States
        ay = 108 + len(self.char_names) * 22 + 16
        self._txt("ANIMATIONS", LIST_X, ay, self.font_sm, DIM_COL)
        for i, sn in enumerate(self.states):
            pre = "▶ " if i == self.state_idx else "  "
            col = HIGHLIGHT if i == self.state_idx else DIM_COL
            has_hx = "🟥" if self.hitboxes.get((self.char, sn)) is not None else "  "
            self._txt(f"{pre}{has_hx} {sn}",
                      LIST_X, ay + 20 + i * 20, self.font_sm, col)


# ============================================================================
if __name__ == "__main__":
    BoxEditor().run()
