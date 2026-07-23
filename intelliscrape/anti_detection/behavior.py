"""Human-like behavioral simulation for anti-detection."""

from __future__ import annotations

import math
import random
import time
from typing import List, Tuple


class HumanBehavior:
    """Simulates human-like mouse movements, scrolls, and timing."""

    @staticmethod
    def bezier_curve(
        start: Tuple[float, float],
        end: Tuple[float, float],
        control: Tuple[float, float],
        steps: int = 50,
    ) -> List[Tuple[float, float]]:
        """Generate a Bezier curve path between two points."""
        points = []
        for i in range(steps + 1):
            t = i / steps
            x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t ** 2 * end[0]
            y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t ** 2 * end[1]
            points.append((x, y))
        return points

    @staticmethod
    def human_mouse_path(
        start: Tuple[float, float],
        end: Tuple[float, float],
    ) -> List[Tuple[float, float]]:
        """Generate a human-like mouse path between two points."""
        # Add slight randomness to control point
        mid_x = (start[0] + end[0]) / 2 + random.uniform(-50, 50)
        mid_y = (start[1] + end[1]) / 2 + random.uniform(-30, 30)
        control = (mid_x, mid_y)

        # Variable steps based on distance
        distance = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
        steps = max(20, min(100, int(distance / 10)))

        path = HumanBehavior.bezier_curve(start, end, control, steps)

        # Add micro-jitter to simulate hand tremor
        jittered = []
        for x, y in path:
            jittered.append((
                x + random.gauss(0, 0.5),
                y + random.gauss(0, 0.5),
            ))

        return jittered

    @staticmethod
    def human_delay(action: str = "click") -> float:
        """Generate a human-like delay in seconds.

        Parameters
        ----------
        action : str
            Type of action: "click", "scroll", "type", "navigate", "think"
        """
        delays = {
            "click": (0.05, 0.3),        # Time between clicks
            "scroll": (0.3, 1.5),        # Time between scrolls
            "type": (0.03, 0.15),        # Time between keystrokes
            "navigate": (1.0, 4.0),      # Time after page load
            "think": (0.5, 3.0),         # Thinking time
            "read": (2.0, 8.0),          # Reading time
            "idle": (5.0, 30.0),         # Idle time
        }

        min_d, max_d = delays.get(action, (0.5, 2.0))
        # Gaussian distribution for more natural timing
        delay = random.gauss((min_d + max_d) / 2, (max_d - min_d) / 4)
        return max(min_d, min(max_d, delay))

    @staticmethod
    def human_scroll_pattern(
        total_height: int = 5000,
        viewport_height: int = 900,
    ) -> List[Tuple[int, float]]:
        """Generate a human-like scroll pattern.

        Returns list of (scroll_y, delay) tuples.
        """
        scrolls = []
        current = 0

        while current < total_height:
            # Variable scroll distance
            scroll_amount = random.randint(100, min(400, viewport_height - 100))

            # Sometimes scroll back up slightly
            if random.random() < 0.15:
                scroll_amount = -random.randint(30, 100)

            current = max(0, current + scroll_amount)
            delay = HumanBehavior.human_delay("scroll")

            scrolls.append((current, delay))

            # Occasional longer pause (reading)
            if random.random() < 0.2:
                scrolls.append((current, random.uniform(2.0, 5.0)))

        return scrolls

    @staticmethod
    def random_mouse_positions(count: int = 5) -> List[Tuple[float, float]]:
        """Generate random realistic mouse positions on a page."""
        positions = []
        for _ in range(count):
            x = random.gauss(960, 400)  # Center-biased distribution
            y = random.gauss(400, 250)
            x = max(0, min(1920, x))
            y = max(0, min(1080, y))
            positions.append((x, y))
        return positions

    @staticmethod
    async def simulate_page_interaction(page, duration: float = 3.0):
        """Simulate realistic page interaction.

        Parameters
        ----------
        page : playwright.Page
            The page to interact with.
        duration : float
            Duration of interaction in seconds.
        """
        import asyncio

        start = time.time()

        while time.time() - start < duration:
            action = random.choice(["move", "scroll", "pause"])

            if action == "move":
                pos = HumanBehavior.random_mouse_positions(1)[0]
                try:
                    await page.mouse.move(pos[0], pos[1])
                except Exception:
                    pass
                await asyncio.sleep(HumanBehavior.human_delay("click"))

            elif action == "scroll":
                scroll_y = random.randint(100, 500)
                try:
                    await page.mouse.wheel(0, scroll_y)
                except Exception:
                    pass
                await asyncio.sleep(HumanBehavior.human_delay("scroll"))

            else:
                await asyncio.sleep(HumanBehavior.human_delay("think"))
