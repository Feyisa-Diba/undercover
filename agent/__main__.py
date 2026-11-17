"""Work the queue with the UnderCover Agent: uv run -m agent [--cap 5 | CLM-1001]"""

import argparse
import sys

from agent import api
from agent.harness import work_claim, work_queue


def main(args: list[str]) -> None:
    """Work the claim named on the command line, or the queue up to a cap."""
    parser = argparse.ArgumentParser(
        prog="uv run -m agent", description="Work claims with the UnderCover Agent."
    )
    parser.add_argument("claim_id", nargs="?", help="work this one claim")
    parser.add_argument("--cap", type=int, help="the most claims the run may work")
    options = parser.parse_args(args)
    if not options.claim_id:
        work_queue(options.cap)
        return
    try:
        print(work_claim(options.claim_id))
    except api.Refused as refusal:
        sys.exit(refusal.detail)


if __name__ == "__main__":
    main(sys.argv[1:])
