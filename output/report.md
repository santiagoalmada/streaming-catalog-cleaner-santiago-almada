# Data Quality Report

## Summary

| Metric                | Value | % of input | Description |
|-----------------------|-------|------------|-------------|
| Total input records   | 39 | 100% | Total rows read from the input file |
| Total output records  | 28 | 71.8% | Valid, unique episodes written to the output file |
| Discarded entries     | 3 | 7.7% | Rows removed due to missing required fields |
| Corrected entries     | 15 | 38.5% | Rows that had at least one field fixed or normalized |
| Duplicates detected   | 8 | 20.5% | Rows identified as duplicates of an already seen episode |

## What was discarded and why

Some records were removed completely because they didn't have enough information to be useful:

- **Missing Series Name**: without a series name we have no way to know which show the episode belongs to, so the record is useless.
- **No identifiable content**: if Episode Number, Episode Title, and Air Date were all missing or invalid at the same time, there was nothing left to identify the episode.

## What was corrected

Records that were kept but had some invalid or missing fields were corrected with safe default values:

- **Season or Episode Number** that were missing, negative, or not a number → replaced with `0`.
- **Episode Title** that was empty → replaced with `"Untitled Episode"`.
- **Air Date** that was missing or in an unrecognized format → replaced with `"Unknown"`.
- **Dates in valid formats** were normalized to `YYYY-MM-DD` for consistency.
- **Extra whitespace** in text fields was trimmed and collapsed.

Once the invalid rows are removed and the remaining data is corrected and normalized, we obtain a clean, parsed dataset of episodes ready for processing. 

## Deduplication strategy

The same episode could appear multiple times in the file, sometimes with slightly different data. To detect duplicates, up to 3 different keys are generated per episode:

1. `(SeriesName, SeasonNumber, EpisodeNumber)`
2. `(SeriesName, 0, EpisodeNumber, EpisodeTitle)`
3. `(SeriesName, SeasonNumber, 0, EpisodeTitle)`

Keys with fallback values for any of those fields (like `0` or `"Untitled Episode"`) are skipped, since they don't carry real identifying information and could cause **false positives**.

To keep track of unique records and efficiently resolve duplicates, a memory catalog is implemented using a Python dictionary. This catalog maps each unique key to the best version of an episode found so far.

The process works by iterating through the array of parsed episodes. For each episode, its corresponding keys are generated and checked to see if any of them already exist in the catalog:

* **If no keys exist in the catalog:** The episode is considered new. Its keys are added to the dictionary, pointing to this current episode.
* **If at least one key already exists:** A duplicate is detected (in other words, if two episodes share at least one key, we can say that they represent the same episode).

When a duplication is detected, the current episode is compared against the existing episode in the catalog to determine which one is the "best" version to keep, discarding the other. To resolve this conflict, the following priority cascade is applied:

1. Prefer the record with a **known Air Date**.
2. Prefer the record with a **real Episode Title**.
3. Prefer the record with **both Season and Episode numbers** set.
4. If everything is equal, keep the **first one found** in the file.

Finally, after the winner is decided, the catalog is updated. All valid keys from both the current and the previous episode are linked to the winning record, keeping the catalog unified and up-to-date.

This last strategy of linking keys from both records enables a transitive property: if a future row shares keys only with the discarded record, it will still be correctly identified as a duplicate of the winner, even without a direct key match.

