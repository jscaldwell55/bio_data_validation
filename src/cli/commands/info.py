"""Info command implementation"""

import click
import sys
from pathlib import Path
from src.cli.config import Config


@click.command('info')
@click.pass_context
def info(ctx):
    """
    Show system status and configuration.

    Displays version, configuration, cache status, and supported features.
    """
    config = ctx.obj

    click.echo()
    click.echo("Bio-Data Validation System")
    click.echo("=" * 60)
    click.echo("Version: 0.1.0")
    click.echo(f"Python: {sys.version.split()[0]}")
    click.echo()

    # Configuration
    click.echo("Configuration")
    click.echo("-" * 60)
    click.echo(f"Config file: {config.config_path}")

    # API Key
    if config.has_api_key():
        click.echo("NCBI API key: ✅ Configured")
    else:
        click.echo("NCBI API key: ❌ Not configured (run 'validate-bio setup')")

    # Cache
    cache_enabled = config.is_cache_enabled()
    click.echo(f"Cache enabled: {'✅ Yes' if cache_enabled else '❌ No'}")

    if cache_enabled:
        cache_path = config.get_cache_path()
        click.echo(f"Cache location: {cache_path}")

        if cache_path.exists():
            size_mb = cache_path.stat().st_size / 1024 / 1024
            click.echo(f"Cache size: {size_mb:.2f} MB")
        else:
            click.echo("Cache file: Not created yet")

    click.echo()

    # Supported organisms
    click.echo("Supported Organisms")
    click.echo("-" * 60)
    organisms = [
        ("human", "Homo sapiens"),
        ("mouse", "Mus musculus"),
        ("rat", "Rattus norvegicus"),
        ("zebrafish", "Danio rerio"),
        ("fly", "Drosophila melanogaster"),
        ("worm", "Caenorhabditis elegans"),
        ("yeast", "Saccharomyces cerevisiae"),
    ]

    for short_name, full_name in organisms:
        click.echo(f"✅ {short_name} ({full_name})")

    click.echo()

    # Supported data types
    click.echo("Supported Data Types")
    click.echo("-" * 60)
    data_types = [
        "RNA-seq expression matrices",
        "CRISPR dependency screens",
        "Proteomics quantification",
        "Any gene × sample matrix"
    ]

    for dt in data_types:
        click.echo(f"✅ {dt}")

    click.echo()

    # Quick tips
    click.echo("Quick Tips")
    click.echo("-" * 60)
    click.echo("• Run 'validate-bio setup' to configure NCBI API key (3x faster)")
    click.echo("• Use '--quick' for fast QC without gene validation")
    click.echo("• Use '--help' on any command for detailed usage")
    click.echo("• Run 'validate-bio examples' to see usage examples")
    click.echo()
