"""CLI for GUI Action Coordinate Grounder."""
import argparse
import json
from .core import CoordinateGrounder, DisplayMonitor, Insets


def main() -> None:
    parser = argparse.ArgumentParser(description="Ground [0..1000] VLM coords to desktop pixels")
    parser.add_argument("--x", type=float, default=500.0)
    parser.add_argument("--y", type=float, default=500.0)
    parser.add_argument("--dpi", type=float, default=2.0)
    args = parser.parse_args()

    grounder = CoordinateGrounder([
        DisplayMonitor("main", 0, 0, 3840, 2160, dpi_scale=args.dpi, insets=Insets(bottom=80), is_primary=True)
    ])
    pt = grounder.ground_point(args.x, args.y)
    print(json.dumps({
        "physical": [pt.physical_x, pt.physical_y],
        "logical": [pt.logical_x, pt.logical_y],
        "clamped": pt.clamped,
    }, indent=2))


if __name__ == "__main__":
    main()
