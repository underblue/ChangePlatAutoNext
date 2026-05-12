"""Command-line interface for ChangePlatAutoNext."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from change_plate_next.application.workflow import ChangePlateWorkflow
from change_plate_next.domain.errors import ChangePlateError
from change_plate_next.domain.models import PlateChangeRecipe
from change_plate_next.domain.policies import InsertionStrategy
from change_plate_next.resources.defaults import load_default_change_gcode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="change-plate-next")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="Inspect sliced 3MF plates.")
    inspect.add_argument("inputs", nargs="+", type=Path)
    inspect.add_argument("--json", action="store_true", help="Output JSON.")

    merge = sub.add_parser("merge", help="Merge all plates from input 3MF files.")
    merge.add_argument("inputs", nargs="+", type=Path)
    merge.add_argument("--output", "-o", required=True, type=Path)
    merge.add_argument("--change-gcode", type=Path, help="Path to plate-change G-code snippet.")
    merge.add_argument("--sound-gcode", type=Path, help="Path to finish sound G-code snippet.")
    merge.add_argument("--pre-plate-gcode", type=Path, help="Path to G-code prepended before every plate.")
    merge.add_argument("--post-plate-gcode", type=Path, help="Path to G-code appended after every plate.")
    merge.add_argument("--copies", type=int, default=1)
    merge.add_argument("--append-if-marker-missing", action="store_true")
    merge.add_argument("--no-start-fix", action="store_true")
    merge.add_argument("--m73-plate-number", action="store_true")
    merge.add_argument("--wait-hotbed-cool", action="store_true", help="Add M190 before plate-change G-code.")
    merge.add_argument("--hotbed-temp", type=int, default=40, help="Target bed temperature for --wait-hotbed-cool.")
    merge.add_argument("--wait-before-next-plate", action="store_true", help="Add dwell time after plate-change G-code.")
    merge.add_argument("--wait-seconds", type=int, default=120, help="Seconds to wait when --wait-before-next-plate is enabled.")
    merge.add_argument("--sound-tip-when-waiting", action="store_true", help="Loop sound G-code during the wait.")
    merge.add_argument("--sound-tip-count", type=int, default=10, help="Number of sound loops during the wait.")
    return parser


def default_change_gcode() -> str:
    return load_default_change_gcode()


def read_optional(path: Path | None, fallback: str = "") -> str:
    return path.read_text(encoding="utf-8-sig") if path else fallback


def inspect_command(args: argparse.Namespace) -> int:
    workflow = ChangePlateWorkflow.create_default()
    results = []
    for path in args.inputs:
        plates = workflow.inspect_package(path)
        for plate in plates:
            results.append(
                {
                    "source": str(plate.source_package),
                    "plate": plate.source_index,
                    "prediction_seconds": plate.prediction_seconds,
                    "weight_g": plate.weight_g,
                    "filaments": [
                        {
                            "local_id": int(fil.local_id),
                            "color": fil.signature.color,
                            "material": fil.signature.material,
                            "used_g": fil.used_g,
                        }
                        for fil in plate.filaments
                    ],
                }
            )
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print(f"{Path(item['source']).name} plate_{item['plate']}: {item['weight_g']:.2f}g")
    return 0


def merge_command(args: argparse.Namespace) -> int:
    workflow = ChangePlateWorkflow.create_default()
    queue = workflow.build_queue_from_packages(args.inputs, copies=args.copies, auto_map=True)
    recipe = PlateChangeRecipe(
        change_gcode=read_optional(args.change_gcode, default_change_gcode()),
        sound_gcode=read_optional(args.sound_gcode, ""),
        pre_plate_gcode=read_optional(args.pre_plate_gcode, ""),
        post_plate_gcode=read_optional(args.post_plate_gcode, ""),
        insertion_strategy=InsertionStrategy.APPEND_WITH_WARNING if args.append_if_marker_missing else InsertionStrategy.BEFORE_FINISH_SOUND_BLOCK,
        wait_hotbed_cool=args.wait_hotbed_cool,
        hotbed_temp=args.hotbed_temp,
        wait_before_next_plate=args.wait_before_next_plate,
        wait_seconds=args.wait_seconds,
        sound_tip_when_waiting=args.sound_tip_when_waiting,
        sound_tip_count=args.sound_tip_count,
        apply_start_position_fix=not args.no_start_fix,
        encode_plate_number_in_m73=args.m73_plate_number,
    )
    result = workflow.export_queue(queue, recipe, args.output)
    print(f"Exported: {result.output_path}")
    print(f"Plates: {result.total_printed_plates}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            return inspect_command(args)
        if args.command == "merge":
            return merge_command(args)
    except ChangePlateError as exc:
        print(f"Error: {exc.detail.message}", file=sys.stderr)
        if exc.detail.suggestion:
            print(f"Suggestion: {exc.detail.suggestion}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
