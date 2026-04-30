"""Create a local app user (bcrypt password) with a membership tier."""

from __future__ import annotations

import argparse
import sys

from backend.repositories import user_repository
from backend.repositories.user_repository import UserAlreadyExistsError


def main() -> int:
    p = argparse.ArgumentParser(description="Create an invest-researcher app user.")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument(
        "--tier",
        choices=("none", "basic", "premium"),
        default="none",
        help="Membership tier: none=10 reports/day, basic=50/day, premium=unlimited + valuation screen",
    )
    p.add_argument(
        "--admin",
        action="store_true",
        help="Grant admin (user management API)",
    )
    args = p.parse_args()
    try:
        uid = user_repository.create_user(
            args.username,
            args.password,
            is_admin=args.admin,
            membership_tier=args.tier,
        )
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    except UserAlreadyExistsError as e:
        print(f"Username already exists: {e}", file=sys.stderr)
        return 1
    print(f"Created user id={uid} tier={args.tier} admin={args.admin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
