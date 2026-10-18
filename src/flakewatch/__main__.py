"""Allow ``python -m flakewatch`` to work like the ``flakewatch`` script."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
