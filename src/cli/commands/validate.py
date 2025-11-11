"""Validate command implementation"""

import sys
import asyncio
import pandas as pd
import click
from pathlib import Path
from typing import Optional

from src.validators.matrix_validator import MatrixValidator
from src.cli.formatters.text import TextFormatter, CompactTextFormatter
from src.cli.formatters.json_formatter import JSONFormatter
from src.cli.config import Config


def detect_data_type(df: pd.DataFrame, verbose: bool = False) -> str:
    """
    Auto-detect data type from dataframe.

    Args:
        df: Input dataframe
        verbose: Whether to log detection process

    Returns:
        Detected data type: 'expression', 'crispr', or 'proteomics'
    """
    # Convert to numeric
    df_numeric = df.apply(pd.to_numeric, errors='coerce')

    # Check column names for hints
    columns_str = ' '.join(str(col).lower() for col in df.columns)

    if 'dependency_score' in columns_str or 'crispr' in columns_str:
        if verbose:
            click.echo("Auto-detected: CRISPR (based on column names)", err=True)
        return 'crispr'

    if 'tpm' in columns_str or 'fpkm' in columns_str or 'expression' in columns_str:
        if verbose:
            click.echo("Auto-detected: Expression (based on column names)", err=True)
        return 'expression'

    # Check for negative values
    if df_numeric.size > 0:
        negative_count = (df_numeric < 0).sum().sum()
        negative_pct = (negative_count / df_numeric.size) * 100 if df_numeric.size > 0 else 0

        if negative_pct > 30:
            if verbose:
                click.echo(f"Auto-detected: CRISPR ({negative_pct:.1f}% negative values)", err=True)
            return 'crispr'

    # Default to expression
    if verbose:
        click.echo("Auto-detected: Expression (default)", err=True)
    return 'expression'


@click.command('validate')
@click.argument('filepath', type=click.Path(exists=True))
@click.option('--type', '-t', 'data_type',
              type=click.Choice(['expression', 'crispr', 'proteomics', 'auto']),
              default='auto',
              help='Data type (auto-detected if not specified)')
@click.option('--organism', '-o', default='human',
              help='Organism name (default: human)')
@click.option('--quick', '-q', is_flag=True,
              help='Quick QC mode (skip gene validation)')
@click.option('--output', '-O', type=click.Path(),
              help='Output file path (default: stdout)')
@click.option('--format', '-f', 'output_format',
              type=click.Choice(['text', 'json', 'compact']),
              default='text',
              help='Output format (default: text)')
@click.option('--verbose', '-V', is_flag=True,
              help='Verbose output with progress')
@click.option('--silent', '-s', is_flag=True,
              help='Silent mode (only errors)')
@click.option('--missing-threshold', type=float,
              help='Maximum missing value rate (0.0-1.0)')
@click.option('--outlier-threshold', type=float,
              help='Outlier detection sensitivity (default: 5.0)')
@click.option('--allow-negative', is_flag=True,
              help='Allow negative values')
@click.option('--no-gene-validation', is_flag=True,
              help='Skip gene symbol validation')
@click.pass_context
def validate(ctx, filepath, data_type, organism, quick, output, output_format,
             verbose, silent, missing_threshold, outlier_threshold,
             allow_negative, no_gene_validation):
    """
    Validate a gene × sample matrix.

    Examples:

      \b
      # Basic validation (auto-detect type)
      validate-bio validate mydata.csv

      \b
      # RNA-seq expression data
      validate-bio validate rnaseq.csv --type expression --organism human

      \b
      # CRISPR dependency screen
      validate-bio validate crispr.csv --type crispr --allow-negative

      \b
      # Quick QC (skip gene validation)
      validate-bio validate large_dataset.csv --quick

      \b
      # Save report to file
      validate-bio validate mydata.csv --output report.json --format json
    """
    config = ctx.obj

    try:
        # Load data
        if verbose and not silent:
            click.echo(f"Loading data from {filepath}...", err=True)

        try:
            df = pd.read_csv(filepath, index_col=0)
        except Exception as e:
            click.echo(f"❌ Error loading file: {e}", err=True)
            sys.exit(3)

        if verbose and not silent:
            click.echo(f"✅ Loaded: {df.shape[0]:,} genes × {df.shape[1]} samples", err=True)

        # Auto-detect data type
        if data_type == 'auto':
            data_type = detect_data_type(df, verbose=verbose and not silent)

        # Set allow_negative based on data type if not explicitly set
        if allow_negative is None:
            allow_negative = (data_type == 'crispr')

        # Get config values or use defaults
        if missing_threshold is None:
            missing_threshold = config.get('validation', 'default_missing_threshold', default=0.10)

        if outlier_threshold is None:
            outlier_threshold = config.get('validation', 'default_outlier_threshold', default=5.0)

        # Determine if gene validation should be skipped
        skip_gene_validation = quick or no_gene_validation

        # Configure validator
        validator = MatrixValidator(
            organism=organism,
            validate_genes=not skip_gene_validation,
            missing_threshold=missing_threshold,
            outlier_threshold=outlier_threshold,
            allow_negative=allow_negative
        )

        # Run validation
        if verbose and not silent:
            click.echo(f"🔬 Running validation (type: {data_type})...", err=True)

        result = asyncio.run(validator.validate(df, experiment_type=data_type))

        if verbose and not silent:
            click.echo(f"✅ Validation complete", err=True)

        # Format output
        if output_format == 'text':
            formatter = TextFormatter(use_color=not output and sys.stdout.isatty())
        elif output_format == 'compact':
            formatter = CompactTextFormatter(use_color=not output and sys.stdout.isatty())
        else:  # json
            formatter = JSONFormatter(pretty=True)

        output_text = formatter.format(result)

        # Write or print
        if output:
            output_path = Path(output)
            output_path.write_text(output_text)
            if not silent:
                click.echo(f"✅ Report saved to: {output}", err=True)
        else:
            click.echo(output_text)

        # Exit with proper code
        exit_code = 0 if result.passed else 1
        sys.exit(exit_code)

    except KeyboardInterrupt:
        click.echo("\n\n⚠️  Validation interrupted by user", err=True)
        sys.exit(130)

    except Exception as e:
        click.echo(f"❌ Validation error: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        sys.exit(2)
