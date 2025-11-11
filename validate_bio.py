#!/usr/bin/env python3
"""
validate-bio: Command-line interface for biological data validation

A production-grade CLI for validating gene expression matrices, CRISPR screens,
proteomics data, and other biological datasets.
"""

import sys
import click
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.cli.config import load_config
from src.cli.commands.validate import validate
from src.cli.commands.setup import setup
from src.cli.commands.cache import cache
from src.cli.commands.info import info
from src.cli.commands.examples import examples

__version__ = "0.1.0"


@click.group()
@click.version_option(__version__)
@click.pass_context
def cli(ctx):
    """
    validate-bio: Automated data quality validation for bioinformatics

    Validate gene × sample matrices (RNA-seq, CRISPR, proteomics) with
    comprehensive quality checks.

    \b
    Quick Start:
      validate-bio validate mydata.csv
      validate-bio setup
      validate-bio examples

    \b
    For help on a specific command:
      validate-bio COMMAND --help

    \b
    Exit codes:
      0 = Validation passed
      1 = Validation failed
      2 = Invalid arguments
      3 = File not found
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Load config and store in context
    config = load_config()
    ctx.obj = config


# Register subcommands
cli.add_command(validate)
cli.add_command(setup)
cli.add_command(cache)
cli.add_command(info)
cli.add_command(examples)


def main():
    """Main entry point"""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
