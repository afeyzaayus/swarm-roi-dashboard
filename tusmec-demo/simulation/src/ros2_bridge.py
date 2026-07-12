"""[BONUS] ROS2 wrapper node: runs the simulation engine inside an rclpy node
and publishes the swarm state for RViz.

Agents are rendered as 3D COLLADA models (Marker.MESH_RESOURCE) loaded from
<project_root>/dae/, oriented along their direction of motion. Mesh lookup is
tolerant: file names are matched case-insensitively against the type keyword
(uav, ugv, amr, usv, uuv, rocket) with any of the .dae/.stl/.obj extensions,
so "UGV.dae", "ugv.DAE" or "rocket_v2.dae" all resolve. Types without a mesh
fall back to primitive shapes (and say so in the startup log).

Every MarkerArray starts with a DELETEALL action, so markers left over from a
previous run (e.g. old primitive cubes) are wiped from RViz each frame.

Published topics:
    /swarm/markers  (visualization_msgs/MarkerArray)  — agent meshes + obstacles
    /swarm/poses    (geometry_msgs/PoseArray)         — raw agent positions

Usage (on a machine with ROS2 sourced, e.g. Humble/Jazzy):
    source /opt/ros/humble/setup.bash
    python -m src.ros2_bridge                       # all types, PAPF (default)
    python -m src.ros2_bridge --algo apf            # classic APF
    python -m src.ros2_bridge --d=10                # PAPF, virtual step 10 m
    python -m src.ros2_bridge uav rocket --d=12     # same flags as main.py
    python -m src.ros2_bridge --mesh-scale=0.01     # shrink oversized models
    python -m src.ros2_bridge --tint                # solid colors, no materials
    python -m src.ros2_bridge --no-mesh             # primitives (old behavior)

RViz setup: set Fixed Frame to "map", add a MarkerArray display on
/swarm/markers (and optionally a PoseArray display on /swarm/poses).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Optional

try:
    import rclpy
    from geometry_msgs.msg import Pose, PoseArray
    from rclpy.node import Node
    from std_msgs.msg import ColorRGBA
    from visualization_msgs.msg import Marker, MarkerArray
except ImportError:  # pragma: no cover - requires a ROS2 installation
    raise SystemExit(
        "ROS2 (rclpy) not found. Source your ROS2 installation first, e.g.\n"
        "    source /opt/ros/humble/setup.bash\n"
        "then run:  python -m src.ros2_bridge [types...]"
    )

from .agents import BaseAgent
from .coordination import (
    ArtificialPotentialField,
    PredictiveArtificialPotentialField,
)
from .engine import SimulationEngine
from .scenario import build_demo_scenario

#: <project_root>/dae — 3D models, one per agent type
MESH_DIR = Path(__file__).resolve().parent.parent / "dae"

#: extensions RViz can load via mesh_resource
MESH_EXTENSIONS = {".dae", ".stl", ".obj"}

#: Per-type mesh tuning. `scale` multiplies the model uniformly (tune per
#: model since export units differ); `yaw_offset` (radians) corrects models
#: whose nose doesn't point along +X.
MESH_CONFIG = {
    "UAV": {"keyword": "uav", "scale": 1.0, "yaw_offset": 0.0},
    "UGV": {"keyword": "ugv", "scale": 5.0, "yaw_offset": 0.0},
    "AMR": {"keyword": "amr", "scale": 1.0, "yaw_offset": 0.0},
    "USV": {"keyword": "usv", "scale": 0.05, "yaw_offset": 0.0},
    "UUV": {"keyword": "uuv", "scale": 30.0, "yaw_offset": 0.0},
    "ROCKET": {"keyword": "rocket", "scale": 0.5, "yaw_offset": 0.0},
}

#: RViz color (r, g, b) per agent type — matches the pygame visualizer
TYPE_COLORS = {
    "UAV": (0.26, 0.53, 0.96),
    "UGV": (0.18, 0.63, 0.26),
    "AMR": (0.94, 0.55, 0.16),
    "USV": (0.00, 0.76, 0.86),
    "UUV": (0.63, 0.37, 0.94),
    "ROCKET": (0.92, 0.31, 0.63),
}
#: RViz primitive per agent type (fallback when no mesh is found)
TYPE_SHAPES = {
    "UAV": Marker.SPHERE,
    "UGV": Marker.CUBE,
    "AMR": Marker.CYLINDER,
    "USV": Marker.CUBE,
    "UUV": Marker.SPHERE,
    "ROCKET": Marker.ARROW,
}


def discover_meshes(mesh_dir: Path = MESH_DIR) -> dict[str, Path]:
    """Scan the dae/ folder (and subfolders) once and map TYPE_NAME -> mesh file.

    Matching is case-insensitive on the file *stem*: exact match with the
    type keyword wins; otherwise a stem that starts with the keyword is
    accepted (e.g. "rocket_v2.dae"). Only .dae/.stl/.obj files are considered.
    """
    found: dict[str, Path] = {}
    if not mesh_dir.is_dir():
        return found
    files = [
        p for p in mesh_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in MESH_EXTENSIONS
    ]
    for type_name, cfg in MESH_CONFIG.items():
        keyword = cfg["keyword"]
        exact = [p for p in files if p.stem.lower() == keyword]
        prefix = [p for p in files if p.stem.lower().startswith(keyword)]
        candidates = exact or prefix
        if candidates:
            found[type_name] = sorted(candidates)[0]
    return found


class SwarmBridge(Node):  # pragma: no cover - requires a ROS2 installation
    """Ticks the engine on a ROS timer and republishes the world state."""

    def __init__(
        self,
        engine: SimulationEngine,
        use_meshes: bool = True,
        mesh_scale: float = 1.0,
        tint: bool = False,
    ) -> None:
        super().__init__("swarm_sim")
        self.engine = engine
        self.use_meshes = use_meshes
        self.mesh_scale = mesh_scale
        self.tint = tint
        self.meshes: dict[str, Path] = discover_meshes() if use_meshes else {}
        self.marker_pub = self.create_publisher(MarkerArray, "swarm/markers", 10)
        self.pose_pub = self.create_publisher(PoseArray, "swarm/poses", 10)
        self.timer = self.create_timer(engine.dt, self.step)
        self.get_logger().info(
            f"Swarm bridge up: {len(engine.agents)} agents, dt={engine.dt}s"
        )
        self._report_meshes()

    def _report_meshes(self) -> None:
        """Log exactly which agent types use which mesh file."""
        if not self.use_meshes:
            self.get_logger().info("Meshes disabled (--no-mesh): using primitives.")
            return
        if not MESH_DIR.is_dir():
            self.get_logger().warning(
                f"Mesh folder not found: {MESH_DIR} — all agents use primitives."
            )
            return
        present = {a.TYPE_NAME for a in self.engine.agents}
        for type_name in sorted(present):
            path = self.meshes.get(type_name)
            if path is not None:
                self.get_logger().info(f"{type_name}: mesh {path.name} ({path})")
            else:
                self.get_logger().warning(
                    f"{type_name}: no mesh matching '{MESH_CONFIG[type_name]['keyword']}"
                    f".dae/.stl/.obj' in {MESH_DIR} — using primitive shape."
                )

    # ------------------------------------------------------------------ tick
    def step(self) -> None:
        if not self.engine.all_goals_reached():
            self.engine.tick()
        self.publish_markers()
        self.publish_poses()

    # -------------------------------------------------------------- messages
    @staticmethod
    def _yaw_to_quaternion(yaw: float) -> tuple[float, float, float, float]:
        """(x, y, z, w) quaternion for a rotation of `yaw` around the z axis."""
        return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))

    def _agent_marker(self, agent: BaseAgent, marker_id: int) -> Marker:
        m = Marker()
        m.header.frame_id = "map"
        m.header.stamp = self.get_clock().now().to_msg()
        m.ns = agent.TYPE_NAME
        m.id = marker_id
        m.action = Marker.ADD
        m.pose.position.x = float(agent.position[0])
        m.pose.position.y = float(agent.position[1])
        m.pose.position.z = float(agent.position[2])

        # face the direction of motion
        cfg = MESH_CONFIG.get(agent.TYPE_NAME, {})
        yaw = 0.0
        if agent.speed > 0.1:
            yaw = math.atan2(float(agent.velocity[1]), float(agent.velocity[0]))
        yaw += cfg.get("yaw_offset", 0.0)
        qx, qy, qz, qw = self._yaw_to_quaternion(yaw)
        m.pose.orientation.x = qx
        m.pose.orientation.y = qy
        m.pose.orientation.z = qz
        m.pose.orientation.w = qw

        mesh_path: Optional[Path] = self.meshes.get(agent.TYPE_NAME)
        r, g, b = TYPE_COLORS.get(agent.TYPE_NAME, (0.8, 0.8, 0.8))
        if mesh_path is not None:
            m.type = Marker.MESH_RESOURCE
            m.mesh_resource = mesh_path.as_uri()  # file:///abs/path/to/x.dae
            scale = cfg.get("scale", 1.0) * self.mesh_scale
            m.scale.x = m.scale.y = m.scale.z = scale
            if self.tint:
                # solid type color (useful when the DAE has no materials)
                m.mesh_use_embedded_materials = False
                m.color = ColorRGBA(r=r, g=g, b=b, a=1.0)
            else:
                # all-zero color = use the model's own materials/textures
                m.mesh_use_embedded_materials = True
                m.color = ColorRGBA(r=0.0, g=0.0, b=0.0, a=0.0)
        else:
            m.type = TYPE_SHAPES.get(agent.TYPE_NAME, Marker.SPHERE)
            m.scale.x, m.scale.y, m.scale.z = 2.0, 2.0, 1.0
            m.color = ColorRGBA(r=r, g=g, b=b, a=1.0)
        return m

    def _obstacle_marker(self, index: int) -> Marker:
        obstacle = self.engine.environment.obstacles[index]
        m = Marker()
        m.header.frame_id = "map"
        m.header.stamp = self.get_clock().now().to_msg()
        m.ns = "obstacles"
        m.id = index
        m.type = Marker.CYLINDER
        m.action = Marker.ADD
        height = obstacle.height if obstacle.height != float("inf") else 60.0
        m.pose.position.x = float(obstacle.center[0])
        m.pose.position.y = float(obstacle.center[1])
        m.pose.position.z = float(obstacle.base + height / 2.0)
        m.pose.orientation.w = 1.0
        m.scale.x = m.scale.y = obstacle.radius * 2.0
        m.scale.z = height
        m.color = ColorRGBA(r=0.45, g=0.47, b=0.52, a=0.6)
        return m

    def publish_markers(self) -> None:
        markers = MarkerArray()

        # Wipe everything first: clears stale markers from previous runs
        # (old primitive cubes, agents from a different type filter, ...).
        # DELETEALL + ADDs in one message are applied atomically, no flicker.
        wipe = Marker()
        wipe.header.frame_id = "map"
        wipe.action = Marker.DELETEALL
        markers.markers.append(wipe)

        for i, agent in enumerate(self.engine.agents):
            markers.markers.append(self._agent_marker(agent, i))
        for i in range(len(self.engine.environment.obstacles)):
            markers.markers.append(self._obstacle_marker(i))
        self.marker_pub.publish(markers)

    def publish_poses(self) -> None:
        msg = PoseArray()
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        for agent in self.engine.agents:
            pose = Pose()
            pose.position.x = float(agent.position[0])
            pose.position.y = float(agent.position[1])
            pose.position.z = float(agent.position[2])
            pose.orientation.w = 1.0
            msg.poses.append(pose)
        self.pose_pub.publish(msg)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        description="ROS2 bridge for the heterogeneous swarm simulation"
    )
    parser.add_argument(
        "types",
        nargs="*",
        metavar="TYPE",
        help="agent types to simulate (default: all): uav, ugv, amr, usv, uuv, rocket",
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
    parser.add_argument(
        "--no-mesh",
        action="store_true",
        help="publish primitive shapes instead of the dae/ 3D meshes",
    )
    parser.add_argument(
        "--mesh-scale",
        type=float,
        default=1.0,
        help="uniform scale multiplier for all meshes (default: 1.0). "
             "Use this if models appear too big/small in RViz, e.g. --mesh-scale=0.01",
    )
    parser.add_argument(
        "--tint",
        action="store_true",
        help="paint meshes in solid type colors instead of their embedded "
             "materials (useful if a DAE has no materials and renders white/invisible)",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.algo == "papf":
        strategy = PredictiveArtificialPotentialField(step_length=args.d)
    else:
        strategy = ArtificialPotentialField()

    try:
        engine = build_demo_scenario(args.types or None, strategy=strategy)
    except ValueError as exc:
        parser.error(str(exc))
        return

    rclpy.init()
    node = SwarmBridge(
        engine,
        use_meshes=not args.no_mesh,
        mesh_scale=args.mesh_scale,
        tint=args.tint,
    )
    node.get_logger().info(
        f"Coordination: {args.algo.upper()}"
        + (f" (d={args.d} m)" if args.algo == "papf" else "")
    )
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":  # pragma: no cover
    main()