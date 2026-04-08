import argparse
from pathlib import Path

from src.orchestrator.coordinator import run_war_room


def main() -> None:
    parser = argparse.ArgumentParser(description="Assessment 1 - War Room Multi-Agent Simulation")
    parser.add_argument(
        "--scenario",
        choices=["baseline", "optimistic", "critical"],
        default="baseline",
        help="Dataset scenario to run",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    result = run_war_room(project_root=project_root, scenario=args.scenario)

    print("Run complete.")
    print(f"Decision: {result['decision']}")
    print(f"Confidence: {result['confidence_score']}")
    print(f"JSON output: {result['_meta']['json_path']}")
    print(f"YAML output: {result['_meta']['yaml_path']}")
    print(f"Trace log: {result['_meta']['trace_path']}")


if __name__ == "__main__":
    main()
