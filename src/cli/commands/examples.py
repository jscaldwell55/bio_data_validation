"""Examples command implementation"""

import click


@click.command('examples')
def examples():
    """
    Show usage examples.

    Displays common usage patterns and examples for validating different data types.
    """
    click.echo()
    click.echo("╔" + "=" * 58 + "╗")
    click.echo("║" + " " * 15 + "VALIDATE-BIO USAGE EXAMPLES" + " " * 16 + "║")
    click.echo("╚" + "=" * 58 + "╝")
    click.echo()

    examples_list = [
        {
            "title": "1️⃣  Basic Validation (Auto-detect type)",
            "commands": [
                "validate-bio validate mydata.csv"
            ],
            "description": "Automatically detects data type and validates with defaults"
        },
        {
            "title": "2️⃣  RNA-seq Expression Data",
            "commands": [
                "validate-bio validate rnaseq_counts.csv \\",
                "    --type expression \\",
                "    --organism human \\",
                "    --missing-threshold 0.10"
            ],
            "description": "Validate RNA-seq data with custom missing value threshold"
        },
        {
            "title": "3️⃣  CRISPR Dependency Screen",
            "commands": [
                "validate-bio validate crispr_deps.csv \\",
                "    --type crispr \\",
                "    --allow-negative \\",
                "    --missing-threshold 0.05"
            ],
            "description": "CRISPR screens have negative values (dependency scores)"
        },
        {
            "title": "4️⃣  Quick QC (Fast, No Gene Validation)",
            "commands": [
                "validate-bio validate large_dataset.csv --quick"
            ],
            "description": "⚡ Runs in ~0.1s vs 30+s with full validation"
        },
        {
            "title": "5️⃣  Save Report to File",
            "commands": [
                "validate-bio validate mydata.csv \\",
                "    --output report.json \\",
                "    --format json"
            ],
            "description": "Save validation report in JSON format"
        },
        {
            "title": "6️⃣  Batch Processing",
            "commands": [
                "for file in data/*.csv; do",
                "    validate-bio validate \"$file\" --quick",
                "done"
            ],
            "description": "Validate multiple files in a loop"
        },
        {
            "title": "7️⃣  Pipeline Integration (Bash)",
            "commands": [
                "#!/bin/bash",
                "if validate-bio validate counts.csv; then",
                "    echo \"✅ Data valid, running analysis...\"",
                "    python analyze.py",
                "else",
                "    echo \"❌ Data has issues, stopping pipeline\"",
                "    exit 1",
                "fi"
            ],
            "description": "Use exit codes to control pipeline flow"
        },
        {
            "title": "8️⃣  Compact Output for Logging",
            "commands": [
                "validate-bio validate data.csv --format compact"
            ],
            "description": "Single-line output suitable for logs"
        }
    ]

    for i, example in enumerate(examples_list):
        click.echo(example["title"])
        click.echo("-" * 60)

        for cmd in example["commands"]:
            click.echo(f"$ {cmd}")

        if example.get("description"):
            click.echo()
            click.echo(example["description"])

        click.echo()

    # Tips
    click.echo("💡 TIPS")
    click.echo("-" * 60)
    click.echo("• Run 'validate-bio setup' to configure NCBI API key for 3x faster")
    click.echo("  validation")
    click.echo("• Use '--help' on any command for detailed options")
    click.echo("• Exit codes: 0=pass, 1=fail (for pipeline integration)")
    click.echo()
