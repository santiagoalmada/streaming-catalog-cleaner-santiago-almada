# Streaming Catalog Cleaner

A Python solution for processing, cleaning, and deduplicating streaming episode data.

**Author:** Santiago Almada

## Overview

This tool validates corrupted streaming catalogs by fixing missing/invalid fields, detecting duplicates through multi-key matching, and generating quality reports.

## Input

CSV file (`data/episodes.csv`) with: Series Name, Season Number, Episode Number, Episode Title, Air Date

## Output

1. **episodes_clean.csv** – Deduplicated, normalized catalog
2. **report.md** – Quality metrics and deduplication details

## How to run
1. Clone the repository.
2. Ensure the input file is at `data/episodes.csv`.
3. Run the script:
    ```bash
    python src/main.py
    ```

