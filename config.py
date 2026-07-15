# Basic configuration for the test beat-em-up
WIDTH = 960
HEIGHT = 640
FPS = 60

# Asset paths (adjust names to match your files)
MAP_IMAGE = "assets/maps/map1.jpeg"
PLAYER_SPRITESHEET = "assets/hero/knight/spritesheet.png"
EFFECT_SPRITESHEET = "assets/effects/effects.png"
ARCHER_DIR = "assets/hero/archer"
ARROW_IMAGE = "assets/hero/archer/arrow.png"

# Archer Magic Arrows.  Their lower direct damage compensates for utility so
# no choice is strictly stronger than the standard 20-damage arrow.
ARCHER_ARROW_CONFIG = {
    'normal': {
        'label': 'Normal', 'path': ARROW_IMAGE, 'damage': 20,
        'hud_color': (235, 235, 235), 'effect': None,
    },
    'fire': {
        'label': 'Red: Burn', 'path': 'assets/projectiles/arrows/MagickArrow/red/1_0.png', 'damage': 14,
        'hud_color': (255, 105, 80), 'effect': 'burn',
        'dot_damage': 2, 'dot_duration_ms': 1800, 'dot_tick_ms': 450,
    },
    'frost': {
        'label': 'Blue: Slow', 'path': 'assets/projectiles/arrows/MagickArrow/blue/1_0.png', 'damage': 16,
        'hud_color': (105, 185, 255), 'effect': 'slow',
        'slow_duration_ms': 1200, 'slow_mult': 0.72,
    },
    'chain': {
        'label': 'Purple: Chain', 'path': 'assets/projectiles/arrows/MagickArrow/purple/1_0.png', 'damage': 14,
        'hud_color': (205, 125, 255), 'effect': 'chain',
        'chain_damage_pct': 0.50, 'chain_enemy_x_range': 135, 'chain_enemy_y_range': 70,
    },
}

# Goblin Asset Paths
GOBLIN_TANK_DIR = "assets/monsters/goblin_tank"
GOBLIN_WARRIOR_DIR = "assets/monsters/goblin_warrior"
GOBLIN_SPEARMAN_DIR = "assets/monsters/goblin_spearman"
SPEAR_IMAGE = "assets/monsters/goblin_spearman/spear.png"

# Moveable area boundaries (these are rect.bottom values, i.e. where feet land)
# Adjust these to match the dirt road area on your map
MIN_Y = 190   # top of the dirt road (below the back grass/bushes)
MAX_Y = 530   # bottom of the dirt road (above the foreground grass)
MIN_X = 0
MAX_X = WIDTH

# Player Settings

# Enemy Attack Settings (shared offset)
ENEMY_ATTACK_OFFSET_Y = 0      # vertical offset for enemy melee attack boxes

# Goblin Tank Attack Settings (boss)
GOBLIN_TANK_ATTACK_RANGE_X = 80
GOBLIN_TANK_ATTACK_RANGE_Y = 40
GOBLIN_TANK_ATTACK_2_RANGE_X = 120
GOBLIN_TANK_ATTACK_2_RANGE_Y = 60

# Goblin Warrior Attack Settings
GOBLIN_WARRIOR_ATTACK_RANGE_X = 55
GOBLIN_WARRIOR_ATTACK_RANGE_Y = 30

# Goblin Spearman Attack Settings
GOBLIN_SPEARMAN_ATTACK_RANGE_X = 65
GOBLIN_SPEARMAN_ATTACK_RANGE_Y = 30

# ── Phase 1 New Monsters ─────────────────────────────────────────────────────

# Lizardman (standard 2-hit melee)
LIZARDMAN_ATTACK_RANGE_X = 75
LIZARDMAN_ATTACK_RANGE_Y = 40

# Cyclop (heavy hitter with special attack2 on cooldown)
CYCLOP_ATTACK_RANGE_X = 90
CYCLOP_ATTACK_RANGE_Y = 45
CYCLOP_SPECIAL_COOLDOWN = 5000   # ms between attack2 uses

# Kobold (assassin — dash special + normal combo)
KOBOLD_ATTACK_RANGE_X = 60
KOBOLD_ATTACK_RANGE_Y = 35
KOBOLD_DASH_RANGE_X = 150        # horizontal range that triggers the dash
KOBOLD_DASH_RANGE_Y = 40
KOBOLD_DASH_COOLDOWN = 6000      # ms cooldown between dash special attacks

# ── Phase 3 New Monsters (Map 3) ─────────────────────────────────────────────

# Fat Cultist (miniboss, similar to tank)
FAT_CULTIST_ATTACK_RANGE_X = 80
FAT_CULTIST_ATTACK_RANGE_Y = 40
FAT_CULTIST_ATTACK_2_RANGE_X = 120
FAT_CULTIST_ATTACK_2_RANGE_Y = 60

# Death Bringer (boss)
DEATH_BRINGER_ATTACK_RANGE_X = 70
DEATH_BRINGER_ATTACK_RANGE_Y = 40
DEATH_BRINGER_CAST_RANGE_X = 350
DEATH_BRINGER_CAST_RANGE_Y = 150
DEATH_BRINGER_SPELL_COOLDOWN = 7000

# Fireworm (ranged, shorter range than spearman)
FIREWORM_ATTACK_RANGE = 320      # ~WIDTH/3, must close more than spearman (WIDTH/2)
FIREBALL_SPEED = 8               # pixels per frame

# Camera Shake Settings
CAMERA_SHAKE_INTENSITY = 6     # max pixel offset per shake event
CAMERA_SHAKE_DURATION = 200    # ms per shake event

# Death fade-out settings
DEATH_FADE_DELAY = 500         # ms to wait after death anim finishes before fading
DEATH_FADE_DURATION = 1000     # ms for the fade-out effect

# Archer Ultimate Skill Settings
ARCHER_ULTIMATE_DAMAGE = 40        # damage per hit of the ultimate beam
ARCHER_ULTIMATE_SPEED = 18         # pixels per frame the beam travels
ARCHER_ULTIMATE_COOLDOWN = 8000    # ms cooldown between ultimates
ARCHER_ULTIMATE_CAST_FRAME = 12    # animation frame at which the beam is spawned (0-indexed)
DASH_SMOKE_IMAGE = "assets/hero/archer/dash_smoke.png"
ULTIMATE_EFFECT_IMAGE = "assets/hero/archer/archer_ultimate_effect.png"

# Knight Ultimate Skill Settings
KNIGHT_ULTIMATE_DAMAGE = 80            # base damage of the shockwave slam
KNIGHT_ULTIMATE_KNOCKBACK = 28         # pixel velocity knocked back per hit (immense)
KNIGHT_ULTIMATE_COOLDOWN = 10000       # ms cooldown between knight ultimates
KNIGHT_ULTIMATE_CAST_FRAME = 34        # animation frame at which the shockwave is spawned (0-indexed)

# Font
DAMAGE_FONT_PATH = "assets/font/BoldPixels.ttf"

# Critical Hit Settings
CRIT_CHANCE = 0.20             # 20% chance to land a critical hit
CRIT_MULTIPLIER = 2.0          # critical hits deal 2x damage

# Damage Number Settings
DAMAGE_NUMBER_FONT_SIZE = 32           # base font size for normal hits
DAMAGE_NUMBER_CRIT_FONT_SIZE = 40      # font size for critical hits
DAMAGE_NUMBER_RISE_SPEED = 1.5         # pixels per frame the number floats up
DAMAGE_NUMBER_DURATION = 800           # ms before the number disappears
DAMAGE_NUMBER_COLOR = (255, 50, 50)            # red for normal damage
DAMAGE_NUMBER_CRIT_COLOR = (255, 20, 20)       # deeper red for critical hits

# ── Resource System Tuning (Armor / Mana) ───────────────────────────────────

# Generic defaults applied by HealthMixin when an entity does not provide
# explicit values.
RESOURCE_DEFAULT_ARMOR_RATIO = 0.35
RESOURCE_DEFAULT_MANA_RATIO = 0.45
RESOURCE_MAX_ARMOR_CAP = 120
RESOURCE_MAX_MANA_CAP = 140
DEFAULT_ARMOR_REDUCTION_PCT = 0.25

# Player presets keyed by class identifier.
PLAYER_RESOURCE_PRESETS = {
	'knight': {
		'max_armor': 70,
		'max_mana': 10000,
		'armor_reduction_pct': 0.40,
	},
	'archer': {
		'max_armor': 45,
		'max_mana': 120,
		'armor_reduction_pct': 0.30,
	},
}

# Passive regen rates in units per millisecond.
PLAYER_RESOURCE_REGEN_PER_MS = {
	'mana': 0.010,
	'armor': 0.003,
}

# Skill mana costs for active casts.
SKILL_MANA_COST = {
	'fire': 10,
	'water_ball': 12,
	'wind': 10,
	'holy': 12,
	'dark': 14,
	'wood': 11,
	'acid': 13,
	'shield': 9,
	'earth': 12,
	'light': 15,
	'smoke': 10,
	'thunder': 16,
	'water_blast': 18,
}

# Canonical skill ordering for UI/demo cycles.
SKILL_TYPES = [
	'fire',
	'water_ball',
	'wind',
	'holy',
	'dark',
	'wood',
	'acid',
	'shield',
	'earth',
	'light',
	'smoke',
	'thunder',
	'water_blast',
]

# Random drop pool when enemies drop skill icons.
SKILL_DROP_POOL = list(SKILL_TYPES)

# ── Ability upgrades / Poison Vials ─────────────────────────────────────────

# Every slain enemy can drop a green Poison Vial.  Picking it up grants one
# ability point, which can be spent only while the game is paused.
ABILITY_VIAL_DROP_CHANCE = 0.35
ABILITY_MAX_LEVEL = 5
ABILITY_ATTACK_BONUS_PER_LEVEL = 3
ABILITY_ARMOR_BONUS_PER_LEVEL = 12
ABILITY_SPEED_BONUS_PER_LEVEL = 0.35

# Red Berserk Vial: a temporary offensive pickup with a meaningful defensive
# trade-off.  Armor penalty reduces how much incoming damage armor can absorb.
BERSERK_VIAL_DROP_CHANCE = 0.18
BERSERK_VIAL_DURATION_MS = 8000
BERSERK_DAMAGE_MULTIPLIER = 1.25
BERSERK_ARMOR_EFFECTIVENESS_MULTIPLIER = 0.85

# Holy is a timed aura: healing-on-hit and regeneration remain active only
# while this duration bar is running.
HOLY_EFFECT_DURATION_MS = 8000

# Visual zoom used only by the scrollable Pixel Ruins world map.
PIXEL_RUINS_CAMERA_ZOOM = 1.3
# Native combat sprites were authored for the old beat-'em-up background.
# Scale them down only in the larger top-down Pixel Ruins world.
PIXEL_RUINS_ENTITY_SCALE = 0.68
# Characters inside a tuner-authored tunnel are drawn beneath the upper map
# layer by fading them, creating a simple underpass effect.
PIXEL_RUINS_TUNNEL_ENTITY_ALPHA = 115
# Phase 4 map collision uses a compact footprint at character feet instead of
# the full combat hurtbox, which keeps top-down wall movement natural.
PIXEL_RUINS_FOOTBOX_WIDTH_RATIO = 0.70
PIXEL_RUINS_FOOTBOX_HEIGHT_RATIO = 0.28


# Skill drop tuning by enemy tier.
# - enemy_tiers maps class names from entities.py to a drop tier.
# - each tier defines chance, count range, and weighted skill table.
SKILL_DROP_CONFIG = {
	'enemy_tiers': {
		'GoblinWarrior': 'normal',
		'GoblinSpearman': 'normal',
		'Lizardman': 'normal',
		'Kobold': 'normal',
		'Fireworm': 'normal',
		'Cyclop': 'elite',
		'FatCultist': 'miniboss',
		'GoblinTank': 'boss',
		'DeathBringer': 'boss',
	},
	'tiers': {
		'normal': {
			'chance': 1,
			'count_min': 1,
			'count_max': 1,
			'weights': {
				'fire': 10,
				'water_ball': 10,
				'wind': 10,
				'shield': 9,
				'holy': 8,
				'wood': 8,
				'acid': 7,
				'dark': 6,
				'earth': 4,
				'smoke': 4,
				'light': 3,
				'thunder': 2,
				'water_blast': 2,
			},
		},
		'elite': {
			'chance': 0.65,
			'count_min': 1,
			'count_max': 1,
			'weights': {
				'fire': 8,
				'water_ball': 8,
				'wind': 8,
				'shield': 7,
				'holy': 7,
				'wood': 7,
				'acid': 7,
				'dark': 7,
				'earth': 6,
				'smoke': 6,
				'light': 5,
				'thunder': 4,
				'water_blast': 4,
			},
		},
		'miniboss': {
			'chance': 0.90,
			'count_min': 1,
			'count_max': 1,
			'weights': {
				'fire': 6,
				'water_ball': 6,
				'wind': 6,
				'shield': 6,
				'holy': 6,
				'wood': 6,
				'acid': 6,
				'dark': 6,
				'earth': 7,
				'smoke': 7,
				'light': 7,
				'thunder': 6,
				'water_blast': 6,
			},
		},
		'boss': {
			'chance': 1.00,
			'count_min': 1,
			'count_max': 1,
			'weights': {
				'fire': 5,
				'water_ball': 5,
				'wind': 5,
				'shield': 5,
				'holy': 5,
				'wood': 5,
				'acid': 5,
				'dark': 5,
				'earth': 7,
				'smoke': 7,
				'light': 8,
				'thunder': 8,
				'water_blast': 8,
			},
		},
	},
}

# Shared one-shot VFX sheet config used by SkillEffect.
SKILL_EFFECT_CONFIG = {
	'fire': {
		'path': 'assets/skills/effects/Explosion SpriteSheet.png',
		'frame_w': 64, 'frame_h': 64, 'frame_ms': 42, 'scale': 1.4,
	},
	'water_ball': {
		'path': 'assets/skills/effects/Water Ball - Spritesheet/WaterBall - Impact.png',
		'frame_w': 64, 'frame_h': 64, 'frame_ms': 45, 'scale': 1.3,
	},
	'wind': {
		'path': 'assets/skills/effects/Wind Effect 01/Wind Hit Effect.png',
		'frame_w': 32, 'frame_h': 32, 'frame_ms': 45, 'scale': 1.9,
	},
	'wind_breath': {
		'path': 'assets/skills/effects/Wind Effect 01/Wind Breath.png',
		'frame_w': 32, 'frame_h': 32, 'frame_ms': 36, 'scale': 1.6,
	},
	'holy': {
		'path': 'assets/skills/effects/Holy VFX 02.png',
		'frame_w': 48, 'frame_h': 48, 'frame_ms': 48, 'scale': 1.5,
	},
	'light': {
		'path': 'assets/skills/effects/Holy VFX 01/Holy VFX 01 Impact.png',
		'frame_w': 32, 'frame_h': 32, 'frame_ms': 42, 'scale': 2.0,
	},
	'dark': {
		'path': 'assets/skills/effects/Dark VFX 2/Dark VFX 2 (48x64).png',
		'frame_w': 48, 'frame_h': 64, 'frame_ms': 42, 'scale': 1.2,
	},
	'earth': {
		'path': 'assets/skills/effects/Earth Wall.png',
		'frame_w': 32, 'frame_h': 32, 'frame_ms': 120, 'scale': 2.0,
		'row_start': 2, 'row_count': 1,
		'col_start': 0, 'col_count': 1,
		'anchor_bottom': True,
	},
	'wood': {
		'path': 'assets/skills/effects/Wood VFX 01/Wood VFX 01 Hit.png',
		'frame_w': 32, 'frame_h': 32, 'frame_ms': 45, 'scale': 1.8,
	},
	'smoke': {
		'path': 'assets/skills/effects/SmokeNDust P03 VFX 1.png',
		'frame_w': 48, 'frame_h': 64, 'frame_ms': 40, 'scale': 1.25,
	},
	'thunder': {
		'path': 'assets/skills/effects/Thunder Effect 02/Thunder Strike/Thunderstrike wo blur.png',
		'frame_w': 64, 'frame_h': 64, 'frame_ms': 38, 'scale': 1.35,
	},
	'water_blast': {
		'path': 'assets/skills/effects/Water Blast - Spritesheet/Water Blast - End.png',
		'frame_w': 128, 'frame_h': 128, 'frame_ms': 50, 'scale': 1.05,
		'row_start': 0, 'row_count': 2,
		'col_start': 0, 'col_count': 3,
	},
	'acid': {
		'path': 'assets/skills/effects/Acid VFX 2/Acid VFX 02Ending.png',
		'frame_w': 56, 'frame_h': 64, 'frame_ms': 48, 'scale': 1.1,
		'vertical': True,
		'src_y': 0,
		'src_h': 32,
	},
	'shield': {
		'path': 'assets/skills/effects/shields/pipo-btleffect207_480.png',
		'frame_w': 480, 'frame_h': 480, 'frame_ms': 45, 'scale': 0.34,
	},
}

# Per-skill combat tuning used by game logic.
SKILL_COMBAT_CONFIG = {
	'fire': {
		'attack_multiplier': 1.30,
		'cast_damage': 16,
		'cast_enemy_x_range': 210,
		'cast_enemy_y_range': 85,
		'fire_dot_duration_ms': 2200,
		'fire_dot_tick_ms': 450,
		'fire_dot_damage': 3,
		'splash_proc_chance': 0.20,
		'splash_damage_pct': 0.30,
		'splash_enemy_y_range': 60,
		'splash_enemy_x_range': 95,
	},
	'water_ball': {
		'attack_multiplier': 1.06,
		'defense_multiplier': 0.88,
		'slow_duration_ms': 1300,
		'slow_mult': 0.72,
		'splash_damage_pct': 0.35,
		'splash_enemy_y_range': 70,
		'splash_enemy_x_range': 110,
	},
	'wind': {
		'attack_multiplier': 1.12,
		'bonus_proc_chance': 0.30,
		'bonus_damage_pct': 0.25,
		'bleed_duration_ms': 2200,
		'bleed_tick_ms': 450,
		'bleed_damage': 3,
	},
	'holy': {
		'attack_multiplier': 1.05,
		'defense_multiplier': 0.90,
		'heal_on_hit': 1,
	},
	'dark': {
		'attack_multiplier': 1.18,
		'lifesteal_pct': 0.18,
		'bonus_proc_chance': 0.22,
		'bonus_damage_pct': 0.32,
		'zombie_proc_chance': 1.00,
		'zombie_duration_ms': 8000,
		'zombie_attack_damage': 9,
		'zombie_attack_interval_ms': 850,
		'zombie_attack_x_range': 66,
		'zombie_attack_y_range': 60,
		'zombie_move_multiplier': 0.90,
	},
	'wood': {
		'defense_flat_reduce': 4,
	},
	'acid': {
		'attack_multiplier': 1.10,
		'acid_dot_duration_ms': 4500,
		'acid_dot_tick_ms': 600,
		'acid_dot_damage': 4,
	},
	'shield': {
		'defense_multiplier': 0.58,
	},
	'earth': {
		'cast_damage': 18,
		'cast_range_y': 90,
	},
	'light': {
		'cast_damage': 18,
		'chain_damage': 10,
		'chain_damage_pct': 0.55,
		'chain_count': 2,
		'chain_enemy_x_range': 165,
		'chain_enemy_y_range': 75,
		'slow_duration_ms': 850,
		'slow_mult': 0.78,
		'chain_slow_duration_ms': 550,
		'chain_slow_mult': 0.84,
	},
	'smoke': {
		'windup_multiplier': 1.0,
	},
	'thunder': {
		'cast_damage': 26,
	},
	'water_blast': {
		'cast_damage': 20,
		'slow_duration_ms': 1100,
		'slow_mult': 0.70,
		'splash_damage_pct': 0.50,
		'splash_enemy_x_range': 130,
		'splash_enemy_y_range': 90,
	},
}
