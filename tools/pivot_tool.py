#!/usr/bin/env python3
"""
Pivot Point Editor - Visual tool for setting per-animation pivot points.

Pivots define where the character's feet touch the ground in each animation
frame canvas.  The game engine uses these to keep feet locked to the same
screen position when switching between animation states with different
canvas sizes.

Usage:  python pivot_tool.py

Controls:
    Left / Right   Navigate animation states
    Up / Down      Navigate characters
    Left-click     Set pivot on the zoomed frame view
    Space          Play / Pause animation preview
    R              Reset current pivot to default (frame midbottom)
    S              Save all pivots to animation_metadata.json
    Esc            Quit
"""

import pygame
import json
import os
import sys
import copy

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
METADATA_PATH = os.path.join(_SCRIPT_DIR, "assets", "animation_metadata.json")

# ---------------------------------------------------------------------------
# Layout & Colors
# ---------------------------------------------------------------------------
WIN_W, WIN_H = 1400, 900

BG           = (25, 25, 30)
PANEL_BG     = (35, 35, 42)
GRID_COL     = (55, 55, 65)
TEXT_COL     = (210, 210, 210)
DIM_COL      = (120, 120, 140)
HIGHLIGHT    = (255, 200, 50)
MODIFIED_COL = (255, 90, 90)
PIVOT_COL    = (255, 50, 50)
DEFAULT_COL  = (80, 180, 80)
GROUND_COL   = (70, 70, 80)

ZOOM_X, ZOOM_Y     = 30, 100        # top-left of the zoomed frame panel
MAX_ZOOM_W          = 550            # max pixel-width for zoomed view
MAX_ZOOM_H          = 650            # max pixel-height for zoomed view
RIGHT_X             = 650            # x-start of the right preview panels
LIST_X              = WIN_W - 200    # x-start of character/state lists


# ═══════════════════════════════════════════════════════════════════════════
# Helper: load metadata
# ═══════════════════════════════════════════════════════════════════════════
def _load_metadata():
    with open(METADATA_PATH, "r") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════
# Main editor class
# ═══════════════════════════════════════════════════════════════════════════
class PivotEditor:
    """Interactive pivot-point editor for 2-D spritesheets."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Pivot Point Editor")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_lg = pygame.font.SysFont("Consolas", 20, bold=True)
        self.font    = pygame.font.SysFont("Consolas", 15)
        self.font_sm = pygame.font.SysFont("Consolas", 12)

        # Metadata
        self.metadata   = _load_metadata()
        self.char_names = list(self.metadata.keys())
        self.char_idx   = 0
        self.state_idx  = 0

        # ── Pre-load all spritesheets ────────────────────────────────
        self.frames_cache = {}     # (char, state) -> [Surface …]
        self.dims_cache   = {}     # (char, state) -> (fw, fh) unscaled

        for cn, cd in self.metadata.items():
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

        # ── Initialize pivot data ────────────────────────────────────
        # pivots[(char, state)] = (pivot_x, pivot_y) in unscaled pixels
        self.pivots    = {}
        self.is_custom = {}        # True if manually set or loaded from JSON

        for cn in self.char_names:
            for sn in self.metadata[cn].get("animations", {}).keys():
                ai = self.metadata[cn]["animations"][sn]
                fw, fh = self.dims_cache[(cn, sn)]
                if "pivot_x" in ai and "pivot_y" in ai:
                    self.pivots[(cn, sn)]    = (ai["pivot_x"], ai["pivot_y"])
                    self.is_custom[(cn, sn)] = True
                else:
                    self.pivots[(cn, sn)]    = (fw // 2, fh)
                    self.is_custom[(cn, sn)] = False

        # Animation playback state
        self.playing    = True
        self.anim_time  = 0
        self.anim_frame = 0
        self.dirty      = False     # unsaved changes flag

    # ─── Property helpers ────────────────────────────────────────────
    @property
    def char(self):
        return self.char_names[self.char_idx]

    @property
    def states(self):
        return list(self.metadata[self.char].get("animations", {}).keys())

    @property
    def state(self):
        ss = self.states
        self.state_idx %= max(1, len(ss))
        return ss[self.state_idx]

    @property
    def scale(self):
        return self.metadata[self.char].get("scale", 1.0)

    @property
    def pivot(self):
        return self.pivots[(self.char, self.state)]

    @pivot.setter
    def pivot(self, val):
        self.pivots[(self.char, self.state)]    = val
        self.is_custom[(self.char, self.state)] = True
        self.dirty = True

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

    # ─── Pivot delta math (same formula as the game engine) ──────────
    def _pivot_delta(self, cn, sn):
        """Compute the rect offset this state needs after midbottom anchoring."""
        idle_fw, idle_fh = self.dims_cache.get((cn, "idle"), (1, 1))
        idle_px, idle_py = self.pivots.get((cn, "idle"), (idle_fw // 2, idle_fh))
        st_fw, st_fh     = self.dims_cache.get((cn, sn), (1, 1))
        st_px, st_py     = self.pivots.get((cn, sn), (st_fw // 2, st_fh))
        sc = self.metadata[cn].get("scale", 1.0)

        idle_ox = (idle_px - idle_fw / 2) * sc
        idle_oy = (idle_py - idle_fh)     * sc
        st_ox   = (st_px   - st_fw  / 2) * sc
        st_oy   = (st_py   - st_fh)      * sc
        return (round(idle_ox - st_ox), round(idle_oy - st_oy))

    # ═══════════════════════════════════════════════════════════════════
    # Main loop
    # ═══════════════════════════════════════════════════════════════════
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
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    self._on_click(ev.pos)

            if self.playing:
                self._tick_anim(dt)
            self._draw()
            pygame.display.flip()
        pygame.quit()

    # ─── Input ───────────────────────────────────────────────────────
    def _on_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.dirty:
                print("[!] Unsaved changes — press S to save first.")
                return True
            return False
        elif key == pygame.K_RIGHT:
            self.state_idx = (self.state_idx + 1) % len(self.states)
            self.anim_frame = self.anim_time = 0
        elif key == pygame.K_LEFT:
            self.state_idx = (self.state_idx - 1) % len(self.states)
            self.anim_frame = self.anim_time = 0
        elif key == pygame.K_DOWN:
            self.char_idx = (self.char_idx + 1) % len(self.char_names)
            self.state_idx = 0
            self.anim_frame = self.anim_time = 0
        elif key == pygame.K_UP:
            self.char_idx = (self.char_idx - 1) % len(self.char_names)
            self.state_idx = 0
            self.anim_frame = self.anim_time = 0
        elif key == pygame.K_SPACE:
            self.playing = not self.playing
        elif key == pygame.K_r:
            fw, fh = self._dims()
            self.pivots[(self.char, self.state)]    = (fw // 2, fh)
            self.is_custom[(self.char, self.state)] = False
            self.dirty = True
        elif key == pygame.K_s:
            self._save()
        return True

    def _on_click(self, pos):
        frms = self._frames()
        if not frms:
            return
        fw, fh = self._dims()
        z  = self._zoom()
        zw = fw * z
        zh = fh * z
        mx, my = pos
        if ZOOM_X <= mx <= ZOOM_X + zw and ZOOM_Y <= my <= ZOOM_Y + zh:
            px = max(0, min(fw, round((mx - ZOOM_X) / z)))
            py = max(0, min(fh, round((my - ZOOM_Y) / z)))
            self.pivot = (px, py)

    def _tick_anim(self, dt):
        frms = self._frames()
        if len(frms) <= 1:
            return
        dur = self._ainfo().get("duration", 100)
        self.anim_time += dt
        while self.anim_time >= dur:
            self.anim_time -= dur
            self.anim_frame = (self.anim_frame + 1) % len(frms)

    # ─── Save ────────────────────────────────────────────────────────
    def _save(self):
        out = copy.deepcopy(self.metadata)
        for cn in self.char_names:
            for sn in out[cn].get("animations", {}).keys():
                px, py = self.pivots[(cn, sn)]
                out[cn]["animations"][sn]["pivot_x"] = px
                out[cn]["animations"][sn]["pivot_y"] = py
        with open(METADATA_PATH, "w") as f:
            json.dump(out, f, indent=4)
        self.metadata = out
        self.dirty = False
        print(f"[OK] Saved pivot data to {METADATA_PATH}")

    # ═══════════════════════════════════════════════════════════════════
    # Drawing
    # ═══════════════════════════════════════════════════════════════════
    def _txt(self, text, x, y, font=None, col=TEXT_COL):
        surf = (font or self.font).render(str(text), True, col)
        self.screen.blit(surf, (x, y))

    def _draw(self):
        self.screen.fill(BG)

        fw, fh   = self._dims()
        px, py   = self.pivot
        z        = self._zoom()
        frms     = self._frames()
        custom   = self.is_custom.get((self.char, self.state), False)
        delta    = self._pivot_delta(self.char, self.state)

        # ── Header ───────────────────────────────────────────────────
        self._txt(self.char, 30, 10, self.font_lg, HIGHLIGHT)
        self._txt(f"{self.state}  [{self.state_idx+1}/{len(self.states)}]",
                  300, 12, self.font_lg)

        info = f"Frame {fw}\u00d7{fh}   Pivot ({px}, {py})   Zoom {z}x   Scale {self.scale}x"
        tag  = "  [CUSTOM]" if custom else "  [DEFAULT: midbottom]"
        self._txt(info + tag, 30, 48,
                  col=MODIFIED_COL if custom else DEFAULT_COL)
        self._txt(f"Pivot delta (scaled): ({delta[0]}, {delta[1]}) px",
                  30, 70, self.font_sm, DIM_COL)

        if self.dirty:
            self._txt("\u25cf UNSAVED", WIN_W - 160, 12, self.font, MODIFIED_COL)

        # ── Zoomed frame view (left) ────────────────────────────────
        self._draw_zoomed(z, fw, fh, px, py, frms, custom)

        # ── Alignment preview (right-top) ───────────────────────────
        self._txt("ALIGNMENT PREVIEW  (idle ghost + current frame)",
                  RIGHT_X, 88, self.font_sm, DIM_COL)
        self._draw_alignment(RIGHT_X, 110, frms)

        # ── Animation playback (right-bottom) ───────────────────────
        play_y  = 530
        status  = "\u25b6 PLAYING" if self.playing else "\u23f8 PAUSED"
        self._txt(f"ANIMATION PLAYBACK   {status}",
                  RIGHT_X, play_y - 18, self.font_sm, DIM_COL)
        self._draw_playback(RIGHT_X, play_y, frms)

        # ── Character / state navigation lists (far-right) ──────────
        self._draw_lists()

        # ── Controls footer ─────────────────────────────────────────
        self._txt("\u2190/\u2192 Anim   \u2191/\u2193 Char   Click: Set Pivot   "
                  "Space: Play/Pause   R: Reset   S: Save   Esc: Quit",
                  30, WIN_H - 35, self.font_sm, DIM_COL)

    # ─────────────────────────────────────────────────────────────────
    def _draw_zoomed(self, z, fw, fh, px, py, frms, custom):
        zw, zh = fw * z, fh * z
        pad = 8

        # Panel background
        pygame.draw.rect(self.screen, PANEL_BG,
                         (ZOOM_X - pad, ZOOM_Y - pad,
                          zw + pad * 2, zh + pad * 2),
                         border_radius=4)

        # Zoomed first frame
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

        # Pivot crosshair
        cx = ZOOM_X + px * z
        cy = ZOOM_Y + py * z
        col = PIVOT_COL if custom else DEFAULT_COL
        pygame.draw.line(self.screen, col,
                         (ZOOM_X, cy), (ZOOM_X + zw, cy), 2)
        pygame.draw.line(self.screen, col,
                         (cx, ZOOM_Y), (cx, ZOOM_Y + zh), 2)
        pygame.draw.circle(self.screen, (255, 255, 0), (int(cx), int(cy)), 5)

        # Show default-midbottom marker when pivot has been customized
        if custom:
            dx = ZOOM_X + (fw // 2) * z
            dy = ZOOM_Y + fh * z
            pygame.draw.circle(self.screen, DEFAULT_COL, (dx, dy), 4)
            self._txt("\u25cf default", dx + 6, dy - 10, self.font_sm, DEFAULT_COL)

    # ─────────────────────────────────────────────────────────────────
    def _draw_alignment(self, x, y, cur_frames):
        """Idle frame (ghosted) + current animation frame, both anchored at
        their respective pivot points.  If pivots are correct the character's
        body overlaps perfectly."""
        sc = self.scale
        ref_x = x + 200
        ref_y = y + 350

        # Ground line
        pygame.draw.line(self.screen, GROUND_COL,
                         (x, ref_y), (x + 420, ref_y), 1)
        self._txt("ground", x + 425, ref_y - 8, self.font_sm, GROUND_COL)

        # ── Idle ghost ──
        idle_frms = self.frames_cache.get((self.char, "idle"), [])
        if idle_frms:
            ifw, ifh = self.dims_cache[(self.char, "idle")]
            ipx, ipy = self.pivots.get((self.char, "idle"), (ifw // 2, ifh))
            sw = int(ifw * sc)
            sh = int(ifh * sc)
            ghost = pygame.transform.scale(idle_frms[0], (sw, sh))
            ghost.fill((255, 255, 255, 70),
                       special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(ghost,
                             (ref_x - int(ipx * sc),
                              ref_y - int(ipy * sc)))

        # ── Current frame ──
        if cur_frames and self.anim_frame < len(cur_frames):
            cfw, cfh = self._dims()
            cpx, cpy = self.pivot
            sw = int(cfw * sc)
            sh = int(cfh * sc)
            cur = pygame.transform.scale(cur_frames[self.anim_frame],
                                         (sw, sh))
            self.screen.blit(cur,
                             (ref_x - int(cpx * sc),
                              ref_y - int(cpy * sc)))

        # Pivot marker
        pygame.draw.circle(self.screen, (255, 255, 0), (ref_x, ref_y), 4)
        self._txt("pivot", ref_x + 6, ref_y - 10, self.font_sm,
                  (255, 255, 0))

    # ─────────────────────────────────────────────────────────────────
    def _draw_playback(self, x, y, frms):
        if not frms:
            return
        fi       = self.anim_frame % len(frms)
        fw, fh   = self._dims()
        sc       = self.scale
        px, py   = self.pivot
        sw, sh   = int(fw * sc), int(fh * sc)
        ref_x    = x + 200
        ref_y    = y + 220

        # Ground line
        pygame.draw.line(self.screen, GROUND_COL,
                         (x, ref_y), (x + 420, ref_y), 1)

        scaled = pygame.transform.scale(frms[fi], (sw, sh))
        self.screen.blit(scaled,
                         (ref_x - int(px * sc),
                          ref_y - int(py * sc)))
        pygame.draw.circle(self.screen, PIVOT_COL, (ref_x, ref_y), 3)

        self._txt(f"Frame {fi + 1}/{len(frms)}", x, y + 240,
                  self.font_sm, DIM_COL)

    # ─────────────────────────────────────────────────────────────────
    def _draw_lists(self):
        # ── Characters ──
        self._txt("CHARACTERS", LIST_X, 88, self.font_sm, DIM_COL)
        for i, cn in enumerate(self.char_names):
            mc = sum(1 for sn in self.metadata[cn].get("animations", {})
                     if self.is_custom.get((cn, sn), False))
            tc = len(self.metadata[cn].get("animations", {}))
            pre = "\u25b6 " if i == self.char_idx else "  "
            col = HIGHLIGHT if i == self.char_idx else DIM_COL
            self._txt(f"{pre}{cn} ({mc}/{tc})",
                      LIST_X, 108 + i * 22, self.font_sm, col)

        # ── Animations ──
        ay = 108 + len(self.char_names) * 22 + 16
        self._txt("ANIMATIONS", LIST_X, ay, self.font_sm, DIM_COL)
        for i, sn in enumerate(self.states):
            pre = "\u25b6 " if i == self.state_idx else "  "
            col = HIGHLIGHT if i == self.state_idx else DIM_COL
            mk  = "\u2713" if self.is_custom.get((self.char, sn), False) else " "
            self._txt(f"{pre}[{mk}] {sn}",
                      LIST_X, ay + 20 + i * 20, self.font_sm, col)


# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    PivotEditor().run()
