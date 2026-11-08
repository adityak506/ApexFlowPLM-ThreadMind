"""Executable module entry point for plm_mcp."""

from plm_mcp.server import run


def main() -> None:
    """CLI entrypoint."""
    run()


if __name__ == "__main__":
    main()

