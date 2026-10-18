"""Allow ``python -m flakeguard`` to work like the ``flakeguard`` script."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
