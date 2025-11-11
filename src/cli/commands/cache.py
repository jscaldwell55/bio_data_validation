"""Cache management commands"""

import click
from pathlib import Path
from src.utils.cache_manager import GeneCacheManager
from src.cli.config import Config


@click.group('cache')
@click.pass_context
def cache(ctx):
    """
    Manage gene symbol cache.

    The cache stores validated gene symbols to speed up repeated validations.
    """
    pass


@cache.command('stats')
@click.pass_context
def stats(ctx):
    """Show cache statistics"""
    config = ctx.obj
    cache_path = config.get_cache_path()

    if not cache_path.exists():
        click.echo("No cache database found")
        click.echo(f"Expected location: {cache_path}")
        return

    try:
        cache_mgr = GeneCacheManager(
            cache_path=str(cache_path),
            enable_cache=True
        )

        stats = cache_mgr.get_stats()

        click.echo()
        click.echo("Cache Statistics")
        click.echo("=" * 60)
        click.echo(f"Location: {cache_path}")
        click.echo(f"Size: {stats.get('cache_size_bytes', 0) / 1024 / 1024:.2f} MB")
        click.echo(f"Entries: {stats.get('cached_entries', 0):,} genes")

        if stats.get('total_requests', 0) > 0:
            click.echo(f"Hit rate: {stats.get('hit_rate', 0) * 100:.1f}%")
            click.echo(f"Total hits: {stats.get('hits', 0):,}")
            click.echo(f"Total misses: {stats.get('misses', 0):,}")

        # Provider breakdown
        by_provider = stats.get('by_provider', {})
        if by_provider:
            click.echo()
            click.echo("By provider:")
            for provider, count in by_provider.items():
                click.echo(f"  {provider}: {count:,} genes")

        click.echo()

    except Exception as e:
        click.echo(f"❌ Error reading cache: {e}", err=True)


@cache.command('clear')
@click.option('--expired-only', is_flag=True, help='Clear only expired entries')
@click.confirmation_option(prompt='Are you sure you want to clear the cache?')
@click.pass_context
def clear(ctx, expired_only):
    """Clear cache entries"""
    config = ctx.obj
    cache_path = config.get_cache_path()

    if not cache_path.exists():
        click.echo("No cache database found")
        return

    try:
        cache_mgr = GeneCacheManager(
            cache_path=str(cache_path),
            enable_cache=True
        )

        if expired_only:
            removed = cache_mgr.clear_expired()
            click.echo(f"✅ Cleared {removed} expired entries")
        else:
            cache_mgr.clear_all()
            click.echo("✅ Cache cleared")

    except Exception as e:
        click.echo(f"❌ Error clearing cache: {e}", err=True)


@cache.command('info')
@click.argument('gene')
@click.option('--organism', '-o', default='human', help='Organism name')
@click.pass_context
def info(ctx, gene, organism):
    """Show cache info for a specific gene"""
    config = ctx.obj
    cache_path = config.get_cache_path()

    if not cache_path.exists():
        click.echo("No cache database found")
        return

    try:
        cache_mgr = GeneCacheManager(
            cache_path=str(cache_path),
            enable_cache=True
        )

        result = cache_mgr.get(organism, gene)

        if result:
            click.echo(f"\n✅ Gene '{gene}' found in cache (organism: {organism})")
            click.echo(f"Provider: {result.get('cached_provider', 'unknown')}")
            click.echo(f"Valid: {result.get('is_valid', 'unknown')}")
        else:
            click.echo(f"\n❌ Gene '{gene}' not found in cache (organism: {organism})")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
