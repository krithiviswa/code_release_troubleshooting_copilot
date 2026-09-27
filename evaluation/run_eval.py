"""Command-line entry point for the synthetic benchmark."""
import argparse
import asyncio
import json

from evaluation.evaluator import run_benchmark


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the synthetic troubleshooting benchmark.")
    parser.add_argument("--max-cases", type=int, default=None, help="Run only the first N cases.")
    parser.add_argument("--no-llm-judge", action="store_true", help="Run deterministic metrics only.")
    args = parser.parse_args()

    result = asyncio.run(
        run_benchmark(
            max_cases=args.max_cases,
            use_llm_judge=not args.no_llm_judge,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
