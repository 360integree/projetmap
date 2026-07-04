"""Projetmap — Knowledge graph generator for codebases."""
import sys


def main():
    # Check for MCP subcommand before importing heavy CLI modules
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        from projetmap.server import main as mcp_main
        # Remove 'mcp' from argv so argparse in server doesn't see it
        sys.argv.pop(1)
        mcp_main()
    else:
        from projetmap.cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
