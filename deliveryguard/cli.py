import argparse
import json
from pathlib import Path

from deliveryguard.config import settings


def main():
    parser = argparse.ArgumentParser(prog="deliveryguard")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="Generate explicitly synthetic CSV")
    gen.add_argument("--output", default="examples/synthetic.csv")
    gen.add_argument("--rows", type=int, default=1500)
    gen.add_argument("--seed", type=int, default=42)
    sub.add_parser("migrate")
    worker = sub.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    imp = sub.add_parser("import")
    imp.add_argument("file")
    imp.add_argument("--mapping")
    imp.add_argument("--update", action="store_true")
    imp.add_argument("--correction-code", default="")
    sub.add_parser("smoke")
    args = parser.parse_args()
    if args.command == "generate":
        from deliveryguard.synthetic import generate

        if not 1 <= args.rows <= 20000:
            parser.error("--rows must be between 1 and 20000")
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(generate(args.rows, args.seed))
        print(f"Synthetic dataset: {path} ({args.rows} rows, seed={args.seed})")
        return
    settings().validate_security()
    if args.command == "migrate":
        from alembic import command
        from alembic.config import Config

        command.upgrade(Config("alembic.ini"), "head")
    elif args.command == "worker":
        from deliveryguard.ml import work_once, worker

        print(json.dumps({"processed": work_once()})) if args.once else worker()
    elif args.command == "import":
        from deliveryguard.service import import_csv

        mapping = json.loads(Path(args.mapping).read_text()) if args.mapping else None
        print(
            json.dumps(
                import_csv(
                    Path(args.file).read_bytes(),
                    mapping,
                    args.update,
                    correction_code=args.correction_code,
                ),
                ensure_ascii=False,
            )
        )
    elif args.command == "smoke":
        from deliveryguard.smoke import smoke

        smoke()


if __name__ == "__main__":
    main()
