"""Setup command implementation"""

import click
from pathlib import Path
from src.cli.config import Config


@click.command('setup')
@click.option('--api-key', help='NCBI API key')
@click.option('--warm-cache', is_flag=True, help='Pre-populate cache with common genes')
@click.pass_context
def setup(ctx, api_key, warm_cache):
    """
    Configure validate-bio settings.

    Interactive setup wizard to configure NCBI API key and other settings.

    Examples:

      \b
      # Interactive setup
      validate-bio setup

      \b
      # Non-interactive with API key
      validate-bio setup --api-key YOUR_KEY_HERE

      \b
      # Setup with cache warming
      validate-bio setup --api-key YOUR_KEY --warm-cache
    """
    config = ctx.obj

    click.echo("=" * 60)
    click.echo("Bio-Data Validation System - Setup Wizard")
    click.echo("=" * 60)
    click.echo()

    # API Key configuration
    if api_key:
        # Non-interactive mode
        config.set('api', 'ncbi', 'key', api_key)
        click.echo("✅ NCBI API key saved")
    else:
        # Interactive mode
        click.echo("Configure NCBI API Key (3x faster validation)")
        click.echo("Get free key: https://www.ncbi.nlm.nih.gov/account/")
        click.echo()

        current_key = config.get('api', 'ncbi', 'key')
        if current_key:
            click.echo(f"Current key: {current_key[:8]}..." if len(current_key) > 8 else "***")

        new_key = click.prompt("Enter NCBI API key (or press Enter to skip)", default="", show_default=False)

        if new_key:
            config.set('api', 'ncbi', 'key', new_key)
            click.echo("✅ API key saved to ~/.validate-bio/config.yml")
            click.echo("✅ Validation will now be 3x faster")
        else:
            click.echo("⚠️  Skipping API key configuration")

    click.echo()

    # Cache warming
    if warm_cache or (not api_key and click.confirm("Warm cache with common genes?", default=False)):
        click.echo()
        click.echo("Warming cache with common genes...")
        click.echo("  (This would download top 1000 genes: BRCA1, TP53, etc.)")
        click.echo("  [Not implemented in this version]")
        # TODO: Implement cache warming

    click.echo()
    click.echo("=" * 60)
    click.echo("✅ Setup complete!")
    click.echo("=" * 60)
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Try validating a dataset: validate-bio validate mydata.csv")
    click.echo("  2. View examples: validate-bio examples")
    click.echo("  3. Check system info: validate-bio info")
