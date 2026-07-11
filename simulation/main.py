"""Entry point: builds the demo scenario and runs it.

Usage:
    python main.py                        # all six agent types (default)
    python main.py uav                    # only UAVs
    python main.py uav ugv rocket         # only the listed types
    python main.py --headless             # no GUI, print final stats
    python main.py rocket --headless --plot out.png   # save trajectory plot
"""
from __future__ import annotations

import argparse

from src.coordination import (
    ArtificialPotentialField,
    PredictiveArtificialPotentialField,
)
from src.engine import SimulationEngine
from src.scenario import AGENT_TYPES, build_demo_scenario


def print_stats(engine: SimulationEngine) -> None:
    stats = engine.stats()
    print(f"\n--- Simulation finished ({stats.sim_time:.1f} s, {stats.ticks} ticks) ---")
    print(f"Goals reached  : {stats.goals_reached}/{stats.total_agents}")
    print(f"Total distance : {stats.total_distance:.1f} m")
    print(f"Total cost     : ${stats.total_cost:.2f}")
    for type_name, entry in stats.per_type.items():
        print(f"  {type_name}: {entry['reached']}/{entry['count']} at goal, "
              f"{entry['distance']:.1f} m travelled")


def save_plot(engine: SimulationEngine, path: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {
        "UAV": "#4287f5", "UGV": "#2ea043", "AMR": "#f08c28",
        "USV": "#00c3dc", "UUV": "#a05ff0", "ROCKET": "#eb50a0",
    }
    fig, ax = plt.subplots(figsize=(8, 8))
    env = engine.environment
    for obstacle in env.obstacles:
        alpha = 0.35 if obstacle.base < 0 else 0.7  # underwater obstacles fainter
        circle = plt.Circle(obstacle.center, obstacle.radius, color="#777", alpha=alpha)
        ax.add_patch(circle)
    seen = set()
    for agent in engine.agents:
        xs = [p[0] for p in agent.trail]
        ys = [p[1] for p in agent.trail]
        label = agent.TYPE_NAME if agent.TYPE_NAME not in seen else None
        seen.add(agent.TYPE_NAME)
        ax.plot(xs, ys, color=colors[agent.TYPE_NAME], alpha=0.8, label=label)
        if agent.goal is not None:
            ax.scatter([agent.goal[0]], [agent.goal[1]], marker="x", color="#e63c50")
    ax.set_xlim(0, env.width)
    ax.set_ylim(0, env.height)
    ax.set_aspect("equal")
    ax.set_title("Heterogeneous Swarm — APF Trajectories (top-down)")
    ax.legend()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    print(f"Trajectory plot saved: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Heterogeneous swarm simulation (UAV / UGV / AMR / USV / UUV / underwater rocket)"
    )
    parser.add_argument(
        "types",
        nargs="*",
        metavar="TYPE",
        help=f"agent types to simulate (default: all). Choices: {', '.join(AGENT_TYPES)}. "
             "Example: python main.py uav rocket",
    )
    parser.add_argument(
        "--algo",
        choices=["apf", "papf"],
        default="papf",
        help="coordination algorithm: apf (classic) or papf (predictive, default)",
    )
    parser.add_argument(
        "--d",
        type=float,
        default=PredictiveArtificialPotentialField.DEFAULT_STEP_LENGTH,
        help="PAPF virtual step length in meters (default: "
             f"{PredictiveArtificialPotentialField.DEFAULT_STEP_LENGTH}). Example: --d=10",
    )
    parser.add_argument("--headless", action="store_true", help="run without GUI")
    parser.add_argument("--ticks", type=int, default=4000, help="maximum tick count")
    parser.add_argument("--plot", type=str, default=None, help="save trajectory PNG to this path")
    args = parser.parse_args()

    if args.algo == "papf":
        strategy = PredictiveArtificialPotentialField(step_length=args.d)
        algo_desc = f"PAPF (d={args.d} m)"
    else:
        strategy = ArtificialPotentialField()
        algo_desc = "APF"

    try:
        engine = build_demo_scenario(args.types or None, strategy=strategy)
    except ValueError as exc:
        parser.error(str(exc))
        return

    selected = ", ".join(sorted({a.TYPE_NAME for a in engine.agents}))
    print(f"Simulating {len(engine.agents)} agents with {algo_desc}: {selected}")

    if args.headless:
        engine.run(max_ticks=args.ticks)
        print_stats(engine)
        if args.plot:
            save_plot(engine, args.plot)
    else:
        from src.visualizer import Visualizer

        Visualizer(engine).run(max_ticks=args.ticks)
        print_stats(engine)


if __name__ == "__main__":
    main()
