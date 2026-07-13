"""Top-down 2D visualization with pygame (all UI text in English).

Agents are drawn as emojis when an emoji-capable font is available
(Noto Color Emoji / Segoe UI Emoji / Apple Color Emoji):

    ✈️ = UAV     (altitude label, e.g. "20m")
    🚗 = UGV
    🤖 = AMR
    🚤 = USV
    🤿 = UUV     (depth label, e.g. "-12m")
    🚀 = Rocket  (high-altitude, e.g. "35m")

If no emoji font is found, the visualizer falls back to colored geometric
shapes (triangle/square/circle/diamond/hexagon/dart) so it works everywhere.

Obstacles are gray disks; a "z:-30..-8m" label marks underwater obstacles.
Goals are red crosses; faint trails show path history.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pygame

from .agents import AMR, UAV, UGV, USV, UUV, BaseAgent, Rocket
from .engine import SimulationEngine

EMOJI = {
    "UAV": "✈️",
    "UGV": "🚗",
    "AMR": "🤖",
    "USV": "🚤",
    "UUV": "🤿",
    "ROCKET": "🚀",
}
#: font families that can render color emoji, in preference order
EMOJI_FONTS = ["notocoloremoji", "segoeuiemoji", "applecoloremoji", "twemojimozilla"]
EMOJI_SIZE = 26  # rendered emoji height in pixels

COLORS = {
    "UAV": (66, 135, 245),
    "UGV": (46, 160, 67),
    "AMR": (240, 140, 40),
    "USV": (0, 195, 220),
    "UUV": (160, 95, 240),
    "ROCKET": (235, 80, 160),
}
LEGEND = [
    ("UAV", "UAV (aerial drone)"),
    ("UGV", "UGV (ground vehicle)"),
    ("AMR", "AMR (indoor robot)"),
    ("USV", "USV (surface vessel)"),
    ("UUV", "UUV (underwater)"),
    ("ROCKET", "Rocket (high-altitude)"),
]
#: fallback legend text when drawing geometric shapes instead of emojis
SHAPE_NAMES = {
    "UAV": "blue triangle",
    "UGV": "green square",
    "AMR": "orange circle",
    "USV": "cyan diamond",
    "UUV": "purple hexagon",
    "ROCKET": "pink dart",
}
BG = (18, 20, 26)
GRID = (34, 38, 48)
OBSTACLE = (95, 100, 112)
GOAL = (230, 60, 80)
TEXT = (220, 224, 232)
PANEL = (28, 31, 40)


class Visualizer:
    def __init__(self, engine: SimulationEngine, window_size: int = 800, fps: int = 60):
        pygame.init()
        self.engine = engine
        self.fps = fps
        env = engine.environment
        self.scale = window_size / max(env.width, env.height)
        self.size = (int(env.width * self.scale), int(env.height * self.scale))
        self.screen = pygame.display.set_mode(self.size)
        pygame.display.set_caption(
            "Heterogeneous Swarm Simulation — UAV / UGV / AMR / USV / UUV / Rocket"
        )
        self.font = pygame.font.SysFont("consolas", 14)
        self.clock = pygame.time.Clock()
        self.emoji_cache: dict[str, pygame.Surface] = self._build_emoji_cache()

    # ----------------------------------------------------------------- emoji
    def _build_emoji_cache(self) -> dict[str, pygame.Surface]:
        """Pre-render each agent emoji once, scaled to EMOJI_SIZE.

        Color-emoji fonts (e.g. Noto Color Emoji) are bitmap fonts that render
        at a fixed large size, so we render big and smooth-scale down. Returns
        an empty dict if no emoji font is available -> shape fallback.
        """
        path: Optional[str] = None
        for family in EMOJI_FONTS:
            path = pygame.font.match_font(family)
            if path:
                break
        if not path:
            print("Note: no emoji font found — falling back to geometric shapes.")
            return {}
        try:
            font = pygame.font.Font(path, 48)
            cache: dict[str, pygame.Surface] = {}
            for type_name, emoji in EMOJI.items():
                surface = font.render(emoji, True, (255, 255, 255))
                if surface.get_bounding_rect().width < 4:  # tofu/empty glyph
                    raise ValueError(f"font cannot render {emoji}")
                ratio = EMOJI_SIZE / surface.get_height()
                size = (max(1, int(surface.get_width() * ratio)), EMOJI_SIZE)
                cache[type_name] = pygame.transform.smoothscale(surface, size)
            return cache
        except Exception as exc:  # pragma: no cover - depends on system fonts
            print(f"Note: emoji rendering unavailable ({exc}) — using shapes.")
            return {}

    @property
    def uses_emoji(self) -> bool:
        return bool(self.emoji_cache)

    # ------------------------------------------------------------ transforms
    def to_px(self, position: np.ndarray) -> tuple[int, int]:
        # Flip y so the world's +y points up on screen.
        return (
            int(position[0] * self.scale),
            int(self.size[1] - position[1] * self.scale),
        )

    # ------------------------------------------------- fallback shape drawing
    def _triangle(self, pos, color, heading, size=9):
        pts = []
        for angle, r in ((0.0, size), (2.5, size * 0.66), (-2.5, size * 0.66)):
            a = heading + angle
            pts.append((pos[0] + r * math.cos(a), pos[1] - r * math.sin(a)))
        pygame.draw.polygon(self.screen, color, pts)

    def _square(self, pos, color, size=6):
        pygame.draw.rect(
            self.screen, color, pygame.Rect(pos[0] - size, pos[1] - size, 2 * size, 2 * size)
        )

    def _circle(self, pos, color, size=6):
        pygame.draw.circle(self.screen, color, pos, size)

    def _diamond(self, pos, color, size=8):
        pts = [(pos[0], pos[1] - size), (pos[0] + size, pos[1]),
               (pos[0], pos[1] + size), (pos[0] - size, pos[1])]
        pygame.draw.polygon(self.screen, color, pts)

    def _hexagon(self, pos, color, size=7):
        pts = [
            (pos[0] + size * math.cos(math.pi / 3 * i),
             pos[1] + size * math.sin(math.pi / 3 * i))
            for i in range(6)
        ]
        pygame.draw.polygon(self.screen, color, pts)

    def _dart(self, pos, color, heading, size=13):
        pts = []
        for angle, r in ((0.0, size), (2.9, size * 0.5), (math.pi, size * 0.25), (-2.9, size * 0.5)):
            a = heading + angle
            pts.append((pos[0] + r * math.cos(a), pos[1] - r * math.sin(a)))
        pygame.draw.polygon(self.screen, color, pts)

    def _shape_for(self, agent: BaseAgent, pos, color) -> None:
        heading = math.atan2(agent.velocity[1], agent.velocity[0]) if agent.speed > 0.1 else 0.0
        if isinstance(agent, Rocket):
            self._dart(pos, color, heading)
        elif isinstance(agent, UAV):
            self._triangle(pos, color, heading)
        elif isinstance(agent, UGV):
            self._square(pos, color)
        elif isinstance(agent, AMR):
            self._circle(pos, color)
        elif isinstance(agent, USV):
            self._diamond(pos, color)
        elif isinstance(agent, UUV):
            self._hexagon(pos, color)
        else:  # pragma: no cover - future types
            self._circle(pos, color)

    def _draw_body(self, agent: BaseAgent, pos) -> None:
        """Emoji when available, geometric shape otherwise."""
        emoji = self.emoji_cache.get(agent.TYPE_NAME)
        if emoji is not None:
            self.screen.blit(
                emoji, (pos[0] - emoji.get_width() // 2, pos[1] - emoji.get_height() // 2)
            )
        else:
            self._shape_for(agent, pos, COLORS.get(agent.TYPE_NAME, (200, 200, 200)))

    # ------------------------------------------------------------------ draw
    def draw_grid(self, step: float = 10.0) -> None:
        env = self.engine.environment
        x = 0.0
        while x <= env.width:
            px = int(x * self.scale)
            pygame.draw.line(self.screen, GRID, (px, 0), (px, self.size[1]))
            x += step
        y = 0.0
        while y <= env.height:
            py = int(self.size[1] - y * self.scale)
            pygame.draw.line(self.screen, GRID, (0, py), (self.size[0], py))
            y += step

    def draw_obstacles(self) -> None:
        for obstacle in self.engine.environment.obstacles:
            center = self.to_px(np.array([*obstacle.center, 0.0]))
            radius = int(obstacle.radius * self.scale)
            pygame.draw.circle(self.screen, OBSTACLE, center, radius)
            if math.isfinite(obstacle.height):
                if obstacle.base < 0:
                    text = f"z:{obstacle.base:.0f}..{obstacle.top:.0f}m"
                else:
                    text = f"h={obstacle.height:.0f}m"
                label = self.font.render(text, True, TEXT)
                self.screen.blit(label, (center[0] - label.get_width() // 2, center[1] - 8))

    def draw_agent(self, agent: BaseAgent) -> None:
        color = COLORS.get(agent.TYPE_NAME, (200, 200, 200))
        pos = self.to_px(agent.position)

        # trail
        if len(agent.trail) > 2:
            points = [self.to_px(p) for p in agent.trail[-250:]]
            pygame.draw.lines(self.screen, tuple(c // 2 for c in color), False, points, 1)

        # goal
        if agent.goal is not None:
            g = self.to_px(agent.goal)
            pygame.draw.line(self.screen, GOAL, (g[0] - 5, g[1] - 5), (g[0] + 5, g[1] + 5), 2)
            pygame.draw.line(self.screen, GOAL, (g[0] - 5, g[1] + 5), (g[0] + 5, g[1] - 5), 2)

        # body (emoji or fallback shape)
        self._draw_body(agent, pos)

        # altitude/depth label for all agents
        z = agent.position[2]
        label = self.font.render(f"{z:.0f}m", True, color)
        self.screen.blit(label, (pos[0] + 12, pos[1] - 20))

    def draw_hud(self) -> None:
        stats = self.engine.stats()
        lines = [
            f"t={stats.sim_time:6.1f}s  tick={stats.ticks}",
            f"goals reached: {stats.goals_reached}/{stats.total_agents}",
            f"total distance: {stats.total_distance:7.1f} m   cost: ${stats.total_cost:.2f}",
            "press ESC to quit",
        ]
        for i, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, TEXT), (10, 10 + 18 * i))

    def draw_legend(self) -> None:
        """Bottom-left panel explaining which marker means which robot."""
        present = {a.TYPE_NAME for a in self.engine.agents}
        entries = [(t, text) for t, text in LEGEND if t in present]
        if not entries:
            return
        line_h = 24 if self.uses_emoji else 20
        panel_w = 250 if self.uses_emoji else 285
        panel_h = 12 + line_h * len(entries)
        x0, y0 = 8, self.size[1] - panel_h - 8
        panel = pygame.Surface((panel_w, panel_h))
        panel.set_alpha(215)
        panel.fill(PANEL)
        self.screen.blit(panel, (x0, y0))

        for i, (type_name, text) in enumerate(entries):
            cy = y0 + 10 + i * line_h
            emoji = self.emoji_cache.get(type_name)
            if emoji is not None:
                icon = pygame.transform.smoothscale(
                    emoji,
                    (max(1, int(emoji.get_width() * 18 / emoji.get_height())), 18),
                )
                self.screen.blit(icon, (x0 + 8, cy))
                label = f"= {text}"
            else:
                icon_pos = (x0 + 16, cy + 8)
                color = COLORS[type_name]
                if type_name == "UAV":
                    self._triangle(icon_pos, color, math.pi / 2, size=7)
                elif type_name == "UGV":
                    self._square(icon_pos, color, size=5)
                elif type_name == "AMR":
                    self._circle(icon_pos, color, size=5)
                elif type_name == "USV":
                    self._diamond(icon_pos, color, size=6)
                elif type_name == "UUV":
                    self._hexagon(icon_pos, color, size=6)
                elif type_name == "ROCKET":
                    self._dart(icon_pos, color, 0.0, size=10)
                label = f"{SHAPE_NAMES[type_name]} = {text}"
            self.screen.blit(self.font.render(label, True, TEXT), (x0 + 34, cy + 2))

    # ------------------------------------------------------------------- run
    def run(self, max_ticks: int = 5000) -> None:
        running = True
        while running and self.engine.ticks < max_ticks:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            if not self.engine.all_goals_reached():
                self.engine.tick()

            self.screen.fill(BG)
            self.draw_grid()
            self.draw_obstacles()
            for agent in self.engine.agents:
                self.draw_agent(agent)
            self.draw_hud()
            self.draw_legend()
            pygame.display.flip()
            self.clock.tick(self.fps)
        pygame.quit()
