# Species Name Converter

A utility for replacing string identifiers (typically species names) across one or more tabular files using an index-aligned swap reference table.

Each row in the swap table defines one replacement: the value in the `old` column is replaced with the value at the same row index in the `new` column.

## What it does

If your swap reference contains:

| old | new    |
| --- | ------ |
| ERK | MAPK1  |
| AKT | AKT1   |
| MEK | MAP2K1 |

and your target file contains:

```text
ERK + AKT -> MEK
```

the output becomes:

```text
MAPK1 + AKT1 -> MAP2K1
```

The tool also protects:

- scientific notation (for example `1.5E-3`)
- compound identifiers where one name is a prefix of another (for example `cyt_prot__EGF_1_` inside `cyt_prot__EGF_1__EGFR_1_`)

---

## Repository structure

```text
SpeciesNameConverter/
├── src/
│   ├── species_name_converter.py   # CLI entry point
│   ├── file_loader.py              # JSON/YAML/TSV/CSV/TXT loading
│   ├── name_replacer.py            # Safe regex replacement engine
│   ├── swap_report.py              # Optional verification + summary report
│   └── utils.py
├── Demo/
│   ├── config.yaml                 # Example YAML configuration
│   ├── config.json                 # Example JSON configuration
│   ├── swap-reference.tsv          # Read-only swap table (old -> new)
│   ├── SPARCEDv1-files/            # Read-only SPARCED v1 source files
│   │   ├── Ratelaws.txt
│   │   ├── Species.txt
│   │   └── GeneReg.txt
│   └── output/                     # Converted files written here
└── README.md
```

---

## Requirements

- Python 3.10+
- `pandas`
- `pyyaml` (required only for YAML config files)

```bash
pip install pandas pyyaml
```

---

## Usage

Run the entry script with a configuration file path. All input and output paths are defined in the config.

```bash
python src/species_name_converter.py --path Demo/config.yaml
```

Short form:

```bash
python src/species_name_converter.py -p Demo/config.yaml
```

Verbose logging:

```bash
python src/species_name_converter.py -p Demo/config.yaml --verbose
```

Optional loader arguments:

```bash
python src/species_name_converter.py -p Demo/config.yaml -c sep='\t' header=None
```

When the run completes, a summary report is printed to the terminal (see `src/report_template.txt` for the layout).

---

## Configuration file

Configuration files may be **YAML** (`.yaml`, `.yml`) or **JSON** (`.json`).

### Recommended YAML layout

```yaml
# Directory for relative paths (defaults to the config file directory)
base_dir: "."

# Index-aligned swap table
swap_reference:
  file: "swap-reference.tsv"
  old_column: "old"
  new_column: "new"

# Files to transform
outputs:
  - input: "sample-ratelaws.tsv"
    output: "sample-ratelaws-updated.tsv"

# Optional verification (disabled by default)
verify:
  enabled: false
  standard_file: "standard-species.tsv"
  standard_column: "speciesId"
  detail_output: "discrepancies.tsv"

# Optional pandas overrides
load_kwargs:
  sep: "\t"
  dtype: str
  keep_default_na: false

save_kwargs:
  sep: "\t"
  index: false
```

### JSON equivalent

See `Demo/config.json` for a full example.

---

## Config fields

| Field | Required | Description |
| --- | --- | --- |
| `base_dir` | No | Base directory for relative paths. Defaults to the config file directory. |
| `swap_reference.file` | Yes | TSV/CSV file containing old and new columns. |
| `swap_reference.old_column` | Yes | Column with strings to find. |
| `swap_reference.new_column` | Yes | Column with replacement strings (row-aligned with `old_column`). |
| `outputs` | Yes | List of `{input, output}` file pairs to transform. |
| `outputs[].header` | No | Optional pandas `header` value for headerless files (`header: null`). |
| `outputs[].format` | No | `table` (default) or `text`. Use `text` for variable-width files or matrix headers. |
| `protected_paths` | No | Files or directories that outputs must not overwrite (see below). |
| `verify.enabled` | No | When `true`, compare output identifiers against a reference list. Default: `false`. |
| `verify.standard_file` | When verifying | Reference TSV/CSV with expected identifiers. |
| `verify.standard_column` | When verifying | Column to read from the reference file. |
| `verify.detail_output` | No | Optional TSV path for standard-only / target-only discrepancies. |
| `load_kwargs` | No | Extra keyword arguments passed to `pandas.read_csv` when loading inputs. |
| `save_kwargs` | No | Extra keyword arguments passed when writing outputs. |

### Protected source files

The converter always refuses to overwrite:

- the swap reference file
- any configured input file

You can list additional read-only paths in `protected_paths`. The Demo config protects both `swap-reference.tsv` and the entire `SPARCEDv1-files/` directory, and writes converted results to `Demo/output/` instead.

```yaml
protected_paths:
  - "swap-reference.tsv"
  - "SPARCEDv1-files"

outputs:
  - input: "SPARCEDv1-files/Ratelaws.txt"
    output: "output/Ratelaws-updated.txt"
```

### Legacy config format

The previous `swap_files.old` / `swap_files.new` / `swap_files.update` layout is still supported for backward compatibility.

---

## Swap reference file

Example `swap-reference.tsv`:

```tsv
old	new
cyt_imp__Ribosome_	cyt_abs__ribosome_
nuc_prot_i__TP53_	nuc_prot_i__P53_
```

---

## Replacement behavior

Replacements use a compiled regex engine with token boundaries designed for underscore-heavy identifiers:

- Longer identifiers are matched before shorter ones.
- Identifiers ending in `_` are not replaced when followed by another `_` (compound names).
- Scientific notation is temporarily masked before replacement.

Example: replacing `cyt_prot__EGF_1_` does **not** modify `cyt_prot__EGF_1__EGFR_1_`, but does replace standalone occurrences such as `exc_prot__EGF_1_ + cyt_prot__EGFR_1_`.

---

## Summary report

After processing, the tool prints a report like:

```text
+--------------------------------------------------+
| String Harmonization Summary                     |
+--------------------------------------------------+
| Mapping entries loaded       : 601               |
| Target entries processed     : 16                |
| Entries renamed              : 3 (18.8%)         |
| Entries unchanged            : 13                |
| Failed / unmapped renames    : 0                 |
| Naming collisions detected   : 8                 |
| Detail files                 : none              |
+--------------------------------------------------+
```

When `verify.enabled` is `true`, additional overlap statistics and an optional discrepancies file are included.

---

## CLI reference

| Option | Description |
| --- | --- |
| `--path`, `-p` | Path to YAML or JSON config file (required) |
| `--catchall`, `-c` | Optional `key=value` pairs forwarded to tabular loading |
| `--verbose`, `-v` | Enable debug logging |

---

## Example run

```bash
cd SpeciesNameConverter
python src/species_name_converter.py -p Demo/config.yaml
```

This reads the SPARCED v1 source files and swap table from `Demo/`, leaves those source files unchanged, and writes updated copies to `Demo/output/`.
