"""`hestia serve` runs the gateway; `hestia check` validates the registry file."""

import argparse
import sys

from hestia.core.config import Settings
from hestia.services.registry import Registry, RegistryError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hestia")
    sub = parser.add_subparsers(dest="cmd")
    serve = sub.add_parser("serve", help="run the gateway (default)")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    sub.add_parser("check", help="validate the registry file and exit")
    args = parser.parse_args(argv)

    settings = Settings()
    try:
        registry = Registry.load(settings.config_path)
    except RegistryError as e:
        print(f"hestia: {e}", file=sys.stderr)
        return 2

    if args.cmd == "check":
        ids = ", ".join(s.id for s in registry.all()) or "(none)"
        print(f"{settings.config_path}: ok — services: {ids}")
        return 0

    import uvicorn

    from hestia.main import create_app

    uvicorn.run(
        create_app(settings, registry),
        host=getattr(args, "host", None) or settings.host,
        port=getattr(args, "port", None) or settings.port,
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
