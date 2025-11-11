# Validate-Bio: Automated Data Quality Assessment for Biological Datasets

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

`validate-bio` is a command-line tool and Python library for automated quality control of biological omics datasets. The tool performs systematic validation of data integrity, identifier accuracy, and statistical properties prior to downstream analysis.

### Core Validation Capabilities

The validator performs the following checks:

- **Gene identifier validation**: Cross-references gene symbols against NCBI Gene and Ensembl databases
- **Sample correlation analysis**: Identifies duplicate or highly similar samples (Pearson r > 0.99)
- **Data type integrity**: Verifies numeric data types and identifies non-numeric entries
- **Statistical outlier detection**: Flags genes or samples with anomalous value distributions
- **Missing data assessment**: Quantifies and reports patterns of missing values

### Supported Data Types

- RNA-seq expression matrices (TPM, FPKM, normalized counts)
- CRISPR-Cas9 genetic screen data (DepMap, Achilles)
- Proteomics abundance/intensity matrices
- Gene-by-sample matrices (CSV format)

---

## Installation

### Requirements

- Python 3.11 or higher
- Poetry package manager
- Internet connection (for gene identifier validation via NCBI/Ensembl APIs)

### Setup

```bash
# Clone repository
git clone https://github.com/your-org/bio-data-validation.git
cd bio-data-validation

# Install Poetry (if not already installed)
pip install poetry

# Install dependencies
poetry install
```

## Usage

### Basic Validation

```bash
# Validate a gene expression matrix
poetry run validate-bio validate expression_data.csv

# Validate with specific parameters
poetry run validate-bio validate data.csv --type expression --organism human
```

### Validation Report Format

The validator generates a structured report containing:

```
============================================================
             VALIDATION REPORT
============================================================

Dataset Information
------------------------------------------------------------
Genes: 20,000
Samples: 48
Missing: 0.23%
Value range: [-0.5, 15.2]

Status: PASSED
------------------------------------------------------------

Issues Found
------------------------------------------------------------
WARNING: Found 3 highly correlated samples (r > 0.99)
    • Sample_12 ↔ Sample_34 (r = 0.998)
    • Sample_15 ↔ Sample_42 (r = 0.996)
    • Sample_23 ↔ Sample_31 (r = 0.995)

    Recommendation: Verify sample identity or confirm technical replicates

INFO: 145 gene symbols not found in NCBI (0.7%)

Summary
------------------------------------------------------------
Data quality meets minimum thresholds for analysis
Review highly correlated samples before proceeding

Validation time: 2.3 seconds
```

**Status Levels:**
- **PASSED**: Dataset meets quality thresholds
- **WARNING**: Minor issues identified; manual review recommended
- **FAILED**: Critical issues detected; correction required before analysis

---

## Application Examples

### RNA-seq Expression Data

```bash
# Automatic detection
validate-bio validate rnaseq_counts.csv

# Explicit parameter specification
validate-bio validate rnaseq_counts.csv --type expression --organism human
```

**Expected format:**
```csv
gene,Sample1,Sample2,Sample3
BRCA1,10.5,12.3,11.8
TP53,8.2,9.1,8.7
EGFR,15.3,14.9,15.6
```
- Row identifiers: Gene symbols
- Column headers: Sample identifiers
- Values: Numeric expression measurements

### CRISPR-Cas9 Screen Data

```bash
# Enable negative values (fitness scores)
validate-bio validate crispr_screen.csv --type crispr --allow-negative
```

**Expected format:**
```csv
gene,CellLine1,CellLine2,CellLine3
BRCA1,-1.5,-2.3,-1.8
TP53,-0.2,-0.1,-0.3
EGFR,0.3,0.5,0.4
```
- Negative values indicate essential genes
- Positive values indicate non-essential genes

### Performance Optimization

```bash
# Skip gene validation for large datasets
validate-bio validate large_dataset.csv --quick
```

This mode bypasses external API calls, reducing validation time from ~30 seconds to ~0.1 seconds for large matrices.

### Output Formats

```bash
# Text report
validate-bio validate mydata.csv --output report.txt

# Structured JSON output
validate-bio validate mydata.csv --output report.json --format json
```

---

## Validation Issues and Interpretation

### Invalid Gene Symbols

**Description:** Gene identifiers not recognized by NCBI Gene or Ensembl databases.

**Common causes:**
- Typographical errors (e.g., `BRAC1` instead of `BRCA1`)
- Deprecated gene symbols requiring nomenclature updates
- Non-standard identifiers or placeholder text

**Resolution:** Verify gene symbols against current HGNC/MGI nomenclature standards.

### Highly Correlated Samples

**Description:** Sample pairs with Pearson correlation coefficient r > 0.99.

**Common causes:**
- Duplicate sample loading
- Sample mislabeling or tracking errors
- Technical replicates (expected behavior)

**Resolution:** Confirm sample metadata and verify intentional replication.

### Genes with Zero Variance

**Description:** Gene features with identical values across all samples.

**Common causes:**
- Genes with no detectable expression (biological)
- Improper normalization or scaling
- Data preprocessing artifacts

**Resolution:** Review normalization pipeline; filter invariant features if appropriate.

### Non-numeric Data

**Description:** Non-numeric entries detected in measurement columns.

**Common causes:**
- Missing value placeholders ("N/A", "null", "missing")
- Improper data formatting or delimiters
- Mixed data types within columns

**Resolution:** Replace missing values with NA or remove affected entries; verify CSV format.

---

## Configuration

### API Rate Limiting Optimization

To increase validation throughput, configure an NCBI API key:

```bash
validate-bio setup
```

Register for a free API key at: https://www.ncbi.nlm.nih.gov/account/

This increases NCBI E-utilities request rate from 3/second to 10/second.

### Batch Validation

Validate multiple datasets programmatically:

```bash
# Iterate over multiple files
for file in data/*.csv; do
    validate-bio validate "$file" --quick --output "reports/$(basename $file .csv)_report.txt"
done
```

### Pipeline Integration

Integrate validation as a quality control gate in analysis workflows:

```bash
#!/bin/bash
# Validation gate example

if validate-bio validate expression_data.csv; then
    Rscript differential_expression_analysis.R
else
    echo "Validation failed - analysis aborted"
    exit 1
fi
```

---

## Command Reference

### Primary Command

```bash
validate-bio validate <file> [OPTIONS]
```

**Parameters:**
- `--type <expression|crispr>` - Specify experiment type
- `--organism <human|mouse|rat>` - Specify organism for gene validation
- `--quick` - Bypass gene identifier validation
- `--output <path>` - Write report to file
- `--format <text|json>` - Output format
- `--allow-negative` - Accept negative values (e.g., CRISPR fitness scores)

### Utility Commands

```bash
validate-bio examples    # Display usage examples
validate-bio info        # Show system configuration
validate-bio setup       # Configure NCBI API key
validate-bio cache stats # Display cache statistics
```

### Exit Codes

- `0` - Validation passed
- `1` - Validation failed
- `2` - Invalid command syntax
- `3` - File not found

---

## Technical Notes

### Data Privacy

All validation is performed locally. Only gene identifiers (not expression values or metadata) are transmitted to NCBI/Ensembl APIs for nomenclature validation.

### Performance Considerations

- Gene validation via API calls: ~20-30 seconds for 20,000 genes
- Quick mode (no gene validation): ~0.1 seconds
- API key configuration improves throughput by 3x

### Input Format Requirements

- CSV format with comma delimiters
- First row: Column headers (required)
- First column: Gene/feature identifiers
- Remaining columns: Numeric sample measurements
- Excel files must be converted to CSV format

### Extensibility

Custom validation rules can be implemented via the Python API (see Programming Interface section).

---

## Programming Interface

### Python API

Direct integration in Python workflows:

```python
import asyncio
import pandas as pd
from src.validators.matrix_validator import MatrixValidator

async def validate_dataset():
    # Load data matrix
    df = pd.read_csv('expression_data.csv', index_col=0)

    # Initialize validator
    validator = MatrixValidator(
        organism="human",
        validate_genes=True,
        allow_negative=False,
        missing_threshold=0.10
    )

    # Execute validation
    result = await validator.validate(df, experiment_type="rna_seq")

    # Process results
    if result.passed:
        print("Validation passed")
    else:
        print("Validation failed:")
        for issue in result.issues:
            print(f"  {issue.severity}: {issue.message}")

    return result

# Execute
asyncio.run(validate_dataset())
```

### Workflow Integration

**Snakemake:**
```python
rule validate_data:
    input: "data/expression_matrix.csv"
    output: "qc/validation_report.txt"
    shell: "validate-bio validate {input} --output {output}"

rule differential_expression:
    input:
        data="data/expression_matrix.csv",
        validation="qc/validation_report.txt"
    output: "results/de_analysis.csv"
    shell: "Rscript scripts/run_deseq2.R {input.data} {output}"
```

**Nextflow:**
```groovy
process validateData {
    input:
    path expression_matrix

    output:
    path 'validation_report.txt'

    """
    validate-bio validate ${expression_matrix} --output validation_report.txt
    """
}
```

---

## Supported Data Modalities

### Feature × Sample Matrices

The validator supports standard omics data matrices including:

- **Transcriptomics**: RNA-seq (TPM, FPKM, normalized counts), microarray intensity values
- **Proteomics**: Protein abundance or intensity measurements
- **Functional genomics**: CRISPR-Cas9 fitness scores, drug response metrics (IC50, viability)
- **Metabolomics**: Metabolite abundance measurements

**Required structure:**
- Rows: Gene/protein/metabolite identifiers
- Columns: Sample/cell line/condition identifiers
- Values: Numeric measurements
- Format: CSV with row names in first column

### CRISPR Guide RNA Sequences

Validation includes:
- PAM sequence verification
- GC content analysis
- Off-target site prediction
- Target gene identifier validation

### Variant Call Format (VCF)

Supported checks:
- HGVS nomenclature compliance
- Allele frequency validation
- Functional consequence annotation
- ClinVar pathogenicity classification

### Sample Metadata

Quality control for:
- Ontology term compliance
- Batch structure analysis
- Missing data pattern detection

---

## System Requirements

**Minimum specifications:**
- Python 3.11+
- 2 GB RAM
- Internet connectivity (for gene validation)

**Recommended configuration:**
- Python 3.12
- 4 GB RAM
- NCBI API key (increases throughput 3x)

**Platform support:**
- macOS (Intel and Apple Silicon)
- Windows 10/11
- Linux (Ubuntu, CentOS, Debian)

---

## Troubleshooting

### Common Installation Issues

**Missing Python:**
```bash
# macOS
brew install python@3.11

# Ubuntu/Debian
sudo apt install python3.11

# CentOS/RHEL
sudo yum install python3.11
```

**Missing Poetry:**
```bash
pip install poetry
# or
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

**Module import errors:**
Ensure working directory is project root and use `poetry run`:
```bash
cd bio-data-validation
poetry run validate-bio validate data.csv
```

For additional support, submit an issue at the GitHub repository with:
- Operating system and version
- Python version (`python --version`)
- Complete error traceback

---

## Contributing

Contributions are welcome. To contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Implement changes with appropriate tests
4. Run test suite: `poetry run pytest`
5. Submit pull request with detailed description

**Development priorities:**
- Native Excel (.xlsx) file support
- HTML report generation
- Extended organism coverage
- Additional validation rule implementations
- Performance optimizations

---

## Citation

If this tool contributes to your research, please cite:

```bibtex
@software{validate_bio2025,
  title = {Validate-Bio: Automated Quality Assessment for Biological Datasets},
  author = {Your Team},
  year = {2025},
  url = {https://github.com/your-org/bio-data-validation},
  version = {1.0.0}
}
```

---

## License

This software is distributed under the MIT License, permitting use in both academic and commercial contexts.

See [LICENSE](LICENSE) for complete terms.

---

## Dependencies

This tool leverages the following resources:

- **NCBI E-utilities**: Gene identifier validation
- **Ensembl REST API**: Alternative gene nomenclature validation
- **Biopython**: Biological sequence analysis
- **Pandas**: Data structure manipulation
- **Click**: Command-line interface framework

---

## Support and Contact

- **Documentation**: Run `validate-bio examples` for usage demonstrations
- **Bug reports**: Submit via [GitHub Issues](https://github.com/your-org/bio-data-validation/issues)
- **Feature requests**: Open a GitHub Discussion
- **Email**: [your-email@example.com](mailto:your-email@example.com)

---

## Quick Reference

```bash
# Standard validation
validate-bio validate dataset.csv

# Accelerated mode
validate-bio validate dataset.csv --quick

# RNA-seq data
validate-bio validate rnaseq.csv --type expression --organism human

# CRISPR screen data
validate-bio validate crispr.csv --type crispr --allow-negative

# Export report
validate-bio validate dataset.csv --output report.txt

# Command help
validate-bio --help
validate-bio examples

# Configuration
validate-bio setup
validate-bio info
```
