# Species Name Converter

A small utility for replacing species names (or other string identifiers) across one or more tabular files using a reference mapping.

The script reads:

* an **"old"** column containing names to find
* a **"new"** column containing names to replace them with
* one or more **target files** to update

Each occurrence of an entry in the `old` column is replaced with the corresponding entry at the same row index in the `new` column.

## What it does

If your reference file contains:

| old | new    |
| --- | ------ |
| ERK | MAPK1  |
| AKT | AKT1   |
| MEK | MAP2K1 |

and your update file contains:

```text
ERK + AKT -> MEK
```

the output becomes:

```text
MAPK1 + AKT1 -> MAP2K1
```

## Important assumptions

This script assumes:

1. **The `old` and `new` columns are row-aligned**

   * The first value in `old` maps to the first value in `new`
   * The second value in `old` maps to the second value in `new`
   * and so on

2. **Input files are structured tabular files**

   * Typically `.tsv` or `.csv`

3. **Scientific notation is protected**

   * Values like `1.2E-3` are intentionally **not modified**
   * This prevents accidental corruption of numeric expressions

4. **Only string-like cells are modified**

   * Non-string cells are left unchanged

---

## Repository structure

A typical layout might look like this:

```text
project/
├── species_name_converter.py
├── config/
│   └── swap_config.yaml
├── data/
│   ├── swap-reference.tsv
│   └── SPARCED - Ratelaws.tsv
├── file_loader.py
└── utils.py
```

---

## Requirements

* Python 3.8+
* `pandas`
* `pyyaml` (if using YAML config files)

Install common dependencies if needed:

```bash
pip install pandas pyyaml
```

---

## Usage

Run the script from the command line and provide a config file path.

```bash
python species_name_converter.py --path path/to/config.yaml
```

### Short form

```bash
python species_name_converter.py -p path/to/config.yaml
```

### Verbose logging

```bash
python species_name_converter.py -p path/to/config.yaml --verbose
```

or

```bash
python species_name_converter.py -p path/to/config.yaml -v
```

### Passing extra file-loading arguments

The script supports optional catch-all keyword arguments that are passed through to your file 
loader and writer.

Example:

```bash
python species_name_converter.py -p path/to/config.yaml -c sep='\t' index=False
```

These are parsed as:

```python
{
    "sep": "\t",
    "index": False
}
```

---

## Configuration file

The script accepts either **YAML** or **JSON** configuration files.

### YAML example

```yaml
swap_files:
  old:
    filename: "swap-reference.tsv"
    column: "old"
    datatype: "string"

  new:
    filename: "swap-reference.tsv"
    column: "new"
    datatype: "string"

  update:
    - file1:
      filename: "SPARCED - Ratelaws.tsv"
      output: "SPARCED-Ratelaws-updated.tsv"
```

### JSON example

```json
{
  "swap_files": {
    "old": {
      "filename": "swap-reference.tsv",
      "column": "old",
      "datatype": "string"
    },
    "new": {
      "filename": "swap-reference.tsv",
      "column": "new",
      "datatype": "string"
    },
    "update": [
      {
        "file1": null,
        "filename": "SPARCED - Ratelaws.tsv",
        "output": "SPARCED-Ratelaws-updated.tsv"
      }
    ]
  }
}
```

---

## Config fields

### `swap_files.old`

Defines the file and column containing the **original names** to search for.

```yaml
old:
  filename: "swap-reference.tsv"
  column: "old"
```

### `swap_files.new`

Defines the file and column containing the **replacement names**.

```yaml
new:
  filename: "swap-reference.tsv"
  column: "new"
```

### `swap_files.update`

Defines one or more files to scan and rewrite.

```yaml
update:
  - file1:
    filename: "SPARCED - Ratelaws.tsv"
    output: "SPARCED-Ratelaws-updated.tsv"
```

#### Meaning

* `filename` = input file to modify
* `output` = output file to write after replacements

---

## Input reference file example

Example `swap-reference.tsv`:

```tsv
old	new
ERK	MAPK1
AKT	AKT1
MEK	MAP2K1
```

---

## Example run

### Files

#### `swap-reference.tsv`

```tsv
old	new
ERK	MAPK1
AKT	AKT1
MEK	MAP2K1
```

#### `SPARCED - Ratelaws.tsv`

```tsv
rule
ERK + AKT -> MEK
MEK = ERK * 2
```

### Command

```bash
python species_name_converter.py -p config/swap_config.yaml -c sep='\t' index=False
```

### Output

#### `SPARCED-Ratelaws-updated.tsv`

```tsv
rule
MAPK1 + AKT1 -> MAP2K1
MAP2K1 = MAPK1 * 2
```

---

## Notes on replacement behavior

The script uses regex-based replacement with some boundary protection.

### Good behavior

It is designed to avoid replacing names inside larger tokens when possible.

For example, replacing `AKT` should not unintentionally replace part of an unrelated longer identifier like:

```text
AKT_complex
```

depending on the exact boundary context.

### Scientific notation is preserved

This expression:

```text
k = 1.5E-3 * ERK
```

becomes:

```text
k = 1.5E-3 * MAPK1
```

and **not**:

```text
k = 1.5MAPK1-3 * MAPK1
```

---

## Logging

The script logs progress as it runs.

Default logging includes:

* config loading
* mapping creation
* file processing
* output writing

Use `--verbose` for debug-level logging:

```bash
python species_name_converter.py -p config/swap_config.yaml --verbose
```

---

## Known limitations

* The script assumes the mapping file is correct and aligned.
* There is currently **no built-in validation** that:

  * `old` and `new` columns are the same length
  * all referenced files exist
  * all configured columns exist
* Replacement order may matter if one identifier is a substring of another.
* The current `update` config structure is slightly awkward and could be simplified later.

---

## Script entry point

Main script:

```bash
species_name_converter.py
```

CLI options:

```text
--path, -p       Path to YAML/JSON config file
--catchall, -c   Optional key=value arguments passed through to loader/writer
--verbose, -v    Enable debug logging
```

---
