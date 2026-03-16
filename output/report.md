# Data Quality Report

## Summary

| Metric                | Value | % of input | Description |
|-----------------------|-------|------------|-------------|
| Total input records   | 26 | 100% | Total rows read from the input file |
| Total output records  | 13 | 50.0% | Valid, unique episodes written to the output file |
| Discarded entries     | 4 | 15.4% | Rows removed due to missing required fields |
| Corrected entries     | 14 | 53.8% | Rows that had at least one field fixed or normalized |
| Duplicates detected   | 9 | 34.6% | Rows identified as duplicates of an already seen episode |

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

Once the 'garbage' rows are removed and the remaining data is corrected and normalized, we obtain a clean, parsed dataset ready for processing. 

## Deduplication strategy

The same episode could appear multiple times in the file, sometimes with slightly different data. To detect duplicates, I generate up to 3 different keys per episode:

1. `(SeriesName, SeasonNumber, EpisodeNumber)` - used when both season and episode number are known.
2. `(SeriesName, 0, EpisodeNumber, EpisodeTitle)` - used when the season is unknown but we have a number and a title.
3. `(SeriesName, SeasonNumber, 0, EpisodeTitle)` - used when the episode number is unknown but we have a season and a title.

Keys with fallback values (`0` or `"Untitled Episode"`) are skipped, since they don't carry real identifying information and could cause **False Positives**.

We can say that if two episodes share at least one key, they are considered the same episode. 
To keep track of this, I use a dictionary that maps each key to the best episode found so far for that group. When a new episode arrives, I check if any of its keys already exist in the dictionary. If they do, the two records are considered the same episode and I resolve the conflict by keeping only the best one, following this priority:

1. Prefer the record with a **known Air Date**.
2. Prefer the record with a **real Episode Title**.
3. Prefer the record with **both Season and Episode numbers** set.
4. If everything is equal, keep the **first one found** in the file.

# Transitive duplicate detection

An important edge case is when two records don't share a key directly, but are both duplicates of a third one.

For example:

- Record A and Record B share Key 1 → they are duplicates.
- Record B and Record C share Key 3 → they are also duplicates.
- Therefore, A, B and C are all the same episode, even though A and C share no key.

To handle this, every time a duplicate is found, **all keys from both records are registered in the catalog pointing to the same winning episode**. This way, if any future record shares a key with any of them, it will be correctly compared against the current winner.

