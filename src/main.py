import csv
import re
import os
from datetime import datetime

# --- Constants ------------------
INPUT_FILE = 'data/episodes.csv'
OUTPUT_FILE = 'output/episodes_clean.csv'
REPORT_FILE = 'output/report.md'

# Valid data formats considered for air date (for validation)
DATE_FORMATS_TO_TRY = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%Y/%m/%d", "%d-%m-%Y", "%B %d, %Y",
        "%b %d, %Y", "%d %B %Y",
    ]

# Normalized date format for output (YYYY-MM-DD)
NORMALIZE_DATE_FORMAT = "%Y-%m-%d"

#  Define Default / fallback values for missing or invalid fields
#  These are used to determine if a field is "missing" and to apply the deduplication rules.
FALLBACK_SEASON_NUMBER = 0
FALLBACK_EPISODE_NUMBER = 0
FALLBACK_TITLE = 'Untitled Episode'
FALLBACK_AIR_DATE = 'Unknown'


# --- Helper functions ------------------
def normalize_text(text):
    """
        Trimmed, collapsed spaces (preserves original casing)
    """
    text = re.sub(r'\s+', ' ', str(text)).strip()
    return text


def normalize_text_for_comparison(text):
    """
        Lowercase, trimmed, collapsed spaces.
    """
    text = normalize_text(text).lower()
    return text


def parse_number (value):
    """
        Try to parse a number from the value, allowing for some common formatting.
        Returns None if missing, empty, negative, not a number, or not a whole number.
    """
    if not value:
        return None

    try:
        num_float = float(str(value).strip())
        
        if not num_float.is_integer():
            return None
        
        num = int(num_float)

        if num < 0:
            return None
        return num
    
    except (ValueError, TypeError):
        return None


def parse_date(date_value):
    """
        Try to parse using known date formats (defined in DATE_FORMATS), if successful, reformat to NORMALIZE_DATE_FORMAT (YYYY-MM-DD) for output.
        
        Returns None if missing, empty, or cannot be parsed with any of the known formats.
    """

    if date_value is None or str(date_value).strip() == "":
        return None
    
    for fmt in DATE_FORMATS_TO_TRY:
        try:
            parsed_date = datetime.strptime(str(date_value).strip(), fmt)
            # If parsing is successful, return the date in normalized format
            return parsed_date.strftime(NORMALIZE_DATE_FORMAT)
        except (ValueError, TypeError):
            # If parsing fails, try the next format
            continue
    
    return None


def was_row_corrected(raw_row, parsed_row):
    """
        Compares the raw CSV row with the parsed dictionary.
        If any value was reformatted, stripped of spaces, or replaced by a fallback,
        it means the row was 'corrected'.
    """
    # 1. Check strings (Title and Series Name)
    # If the original didn't exist, or had extra spaces that got removed:
    if raw_row.get('Series Name') != parsed_row['SeriesName']:
        return True
        
    if raw_row.get('Episode Title') != parsed_row['EpisodeTitle']:
        return True

    # 2. Check dates (Format changes or missing dates replaced by 'Unknown')
    if raw_row.get('Air Date') != parsed_row['AirDate']:
        return True

    # 3. Check numbers (e.g., raw was " 1.0 " or missing, and now is 1)
    raw_season = raw_row.get('Season Number')
    if raw_season is None or str(raw_season).strip() != str(parsed_row['SeasonNumber']):
        return True

    raw_episode = raw_row.get('Episode Number')
    if raw_episode is None or str(raw_episode).strip() != str(parsed_row['EpisodeNumber']):
        return True

    # If it passed all checks, the raw data was already completely perfect
    return False

    
def clean_record(row):
    """
        Receives a raw CSV row and returns a cleaned episode dict (with normalized values and fallback defaults for missing/invalid fields).
        Returns None if the row should be discarded.

        Discard rules:
        - Series Name is empty or missing → discard
        - EpisodeNumber + EpisodeTitle + AirDate are all "missing" → discard
    """

    # 1. Validate Series Name (required field)
    series_name = normalize_text(row.get('Series Name'))
    if not series_name:
        return None
    
    # 2. Season Number
    season_number = parse_number(row.get("Season Number"))
    if season_number is None:
        season_number = FALLBACK_SEASON_NUMBER

    # 3. Episode Number
    episode_number = parse_number(row.get("Episode Number"))
    if episode_number is None:
        episode_number = FALLBACK_EPISODE_NUMBER

    # 4. Episode Title
    episode_title = normalize_text(row.get("Episode Title"))
    if not episode_title:
        episode_title = FALLBACK_TITLE
    
    # 5. Air Date
    air_date = parse_date(row.get("Air Date"))
    if air_date is None:
        air_date = FALLBACK_AIR_DATE
    
    # 6. Check if all of EpisodeNumber, EpisodeTitle, AirDate are "missing" (fallback values)
    if (episode_number == FALLBACK_EPISODE_NUMBER and 
        episode_title == FALLBACK_TITLE and 
        air_date == FALLBACK_AIR_DATE):
        return None
    
    # We return a cleaned episode dict with the normalized values
    return {
        "SeriesName": series_name,
        "SeasonNumber": season_number,
        "EpisodeNumber": episode_number,
        "EpisodeTitle": episode_title,
        "AirDate": air_date
    }


def generate_deduplication_keys(episode):
    """
        Generate the possible deduplication keys for an episode.
        A key is a tuple of values that is used to identify a episode.
        We generate multiple keys for each episode to allow for different types of duplicates to be detected.
        If two episodes share at least one of these keys, they are considered duplicates and only one of them should be kept.
    """
    keys = []

    series_name = normalize_text_for_comparison(episode["SeriesName"])
    season_number = episode["SeasonNumber"]
    episode_number = episode["EpisodeNumber"]
    episode_title = normalize_text_for_comparison(episode["EpisodeTitle"])
    fallback_title_norm = normalize_text_for_comparison(FALLBACK_TITLE)

    # Key 1: (SeriesName_normalized, SeasonNumber, EpisodeNumber)
    # It just have sense if both SeasonNumber and EpisodeNumber are valid (not fallback):s
    if season_number != FALLBACK_SEASON_NUMBER and episode_number != FALLBACK_EPISODE_NUMBER:
        keys.append((series_name, season_number, episode_number))

    # Key 2: (SeriesName_normalized, 0, EpisodeNumber, EpisodeTitle_normalized) 
    # It just have sense if EpisodeNumber is valid (not fallback) and EpisodeTitle is valid (not fallback):
    if episode_number != FALLBACK_EPISODE_NUMBER and episode_title != fallback_title_norm:
        keys.append((series_name, 0, episode_number, episode_title))

    # Key 3: SeriesName_normalized, SeasonNumber, 0, EpisodeTitle_normalized)
    # It just have sense if SeasonNumber is valid (not fallback) and EpisodeTitle is valid (not fallback):
    if season_number != FALLBACK_SEASON_NUMBER and episode_title != fallback_title_norm:
        keys.append((series_name, season_number, 0, episode_title))

    return keys


def get_best_episode(existing, new):
    """
        Given two episodes (existing and new) that are considered duplicates, decide which one to keep following this priority:
            1. Episodes with a valid Air Date over "Unknown" 
            2. Episodes with a known Episode Title over "Untitled Episode" 
            3. Episodes with a valid Season Number and Episode Number 
            4. If still tied → keep the first entry encountered in the file
    """

    # Priority 1: Air Date
    existing_has_date = existing['AirDate'] != FALLBACK_AIR_DATE
    new_has_date = new['AirDate'] != FALLBACK_AIR_DATE

    if existing_has_date and not new_has_date:
        return existing
    if new_has_date and not existing_has_date:
        return new
    
    # Priority 2: Episode Title
    existing_has_title = existing['EpisodeTitle'] != FALLBACK_TITLE
    new_has_title = new['EpisodeTitle'] != FALLBACK_TITLE

    if existing_has_title and not new_has_title:
        return existing
    if new_has_title and not existing_has_title:
        return new
    
    # Priority 3: Season and Episode Number
    existing_has_nums = (existing['SeasonNumber'] != FALLBACK_SEASON_NUMBER and 
                         existing['EpisodeNumber'] != FALLBACK_EPISODE_NUMBER)
    new_has_nums = (new['SeasonNumber'] != FALLBACK_SEASON_NUMBER and 
                    new['EpisodeNumber'] != FALLBACK_EPISODE_NUMBER)
    
    if existing_has_nums and not new_has_nums:
        return existing
    if new_has_nums and not existing_has_nums:
        return new
    
    # If still tied, keep the existing one (first encountered in the file)
    return existing


def sort_episodes(episodes):
    """
        Sort episodes by Series Name (A-Z), then by Season Number (ascending), then by Episode Number (ascending).
    """
    return sorted(episodes, key=lambda ep: (
        normalize_text_for_comparison(ep['SeriesName']),
        ep['SeasonNumber'],
        ep['EpisodeNumber']
    ))


def generate_quality_report(input_records, output_records, discarded, corrected, duplicates):
    """
        Generates a markdown report assessing data quality and the deduplication strategy.
    """
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("# Data Quality Report\n\n")

        f.write("## Summary\n\n")
        
        discard_pct    = (discarded / input_records * 100) if input_records else 0
        corrected_pct  = (corrected / input_records * 100) if input_records else 0
        duplicates_pct = (duplicates / input_records * 100) if input_records else 0
        kept_pct       = (output_records / input_records * 100) if input_records else 0

        f.write(f"| Metric                | Value | % of input | Description |\n")
        f.write(f"|-----------------------|-------|------------|-------------|\n")
        f.write(f"| Total input records   | {input_records} | 100% | Total rows read from the input file |\n")
        f.write(f"| Total output records  | {output_records} | {kept_pct:.1f}% | Valid, unique episodes written to the output file |\n")
        f.write(f"| Discarded entries     | {discarded} | {discard_pct:.1f}% | Rows removed due to missing required fields |\n")
        f.write(f"| Corrected entries     | {corrected} | {corrected_pct:.1f}% | Rows that had at least one field fixed or normalized |\n")
        f.write(f"| Duplicates detected   | {duplicates} | {duplicates_pct:.1f}% | Rows identified as duplicates of an already seen episode |\n")
        f.write("\n")

        f.write("## What was discarded and why\n\n")
        f.write("Some records were removed completely because they didn't have enough information to be useful:\n\n")
        f.write("- **Missing Series Name**: without a series name we have no way to know which show the episode belongs to, so the record is useless.\n")
        f.write("- **No identifiable content**: if Episode Number, Episode Title, and Air Date were all missing or invalid at the same time, there was nothing left to identify the episode.\n\n")

        f.write("## What was corrected\n\n")
        f.write("Records that were kept but had some invalid or missing fields were corrected with safe default values:\n\n")
        f.write("- **Season or Episode Number** that were missing, negative, or not a number → replaced with `0`.\n")
        f.write("- **Episode Title** that was empty → replaced with `\"Untitled Episode\"`.\n")
        f.write("- **Air Date** that was missing or in an unrecognized format → replaced with `\"Unknown\"`.\n")
        f.write("- **Dates in valid formats** were normalized to `YYYY-MM-DD` for consistency.\n")
        f.write("- **Extra whitespace** in text fields was trimmed and collapsed.\n\n")

        f.write("Once the invalid rows are removed and the remaining data is corrected and normalized, ")
        f.write("we obtain a clean, parsed dataset of episodes ready for processing. \n\n")

        f.write("## Deduplication strategy\n\n")
        
        f.write("The same episode could appear multiple times in the file, sometimes with slightly different data. To detect duplicates, up to 3 different keys are generated per episode:\n\n")
        
        f.write("1. `(SeriesName, SeasonNumber, EpisodeNumber)`\n")
        f.write("2. `(SeriesName, 0, EpisodeNumber, EpisodeTitle)`\n")
        f.write("3. `(SeriesName, SeasonNumber, 0, EpisodeTitle)`\n\n")
                
        f.write("Keys with fallback values for any of those fields (like `0` or `\"Untitled Episode\"`) are skipped, since they don't carry real identifying information and could cause **false positives**.\n\n")
        
        f.write("To keep track of unique records and efficiently resolve duplicates, a memory catalog is implemented using a Python dictionary. This catalog maps each unique key to the best version of an episode found so far.\n\n")
        
        f.write("The process works by iterating through the array of parsed episodes. For each episode, its corresponding keys are generated and checked to see if any of them already exist in the catalog:\n\n")
        
        f.write("* **If no keys exist in the catalog:** The episode is considered new. Its keys are added to the dictionary, pointing to this current episode.\n")
        f.write("* **If at least one key already exists:** A duplicate is detected (in other words, if two episodes share at least one key, we can say that they represent the same episode).\n\n")
        
        f.write("When a duplication is detected, the current episode is compared against the existing episode in the catalog to determine which one is the \"best\" version to keep, discarding the other. To resolve this conflict, the following priority cascade is applied:\n\n")
        
        f.write("1. Prefer the record with a **known Air Date**.\n")
        f.write("2. Prefer the record with a **real Episode Title**.\n")
        f.write("3. Prefer the record with **both Season and Episode numbers** set.\n")
        f.write("4. If everything is equal, keep the **first one found** in the file.\n\n")
        
        f.write("Finally, after the winner is decided, the catalog is updated. All valid keys from both the current and the previous episode are linked to the winning record, keeping the catalog unified and up-to-date.\n\n")
        f.write("This last strategy of linking keys from both records enables a transitive property: if a future row shares keys only with the discarded record, it will still be correctly identified as a duplicate of the winner, even without a direct key match.\n\n")
        

# --- Main processing function ------------------
def main():
    """
        Main data processing pipeline.

        Steps:
        1. Validate input file and output directory
        2. Read and clean input CSV records
        3. Deduplicate episodes using multiple matching keys
        4. Sort the resulting episodes
        5. Write cleaned data to output CSV
        6. Generate a quality report with processing statistics
    """

    # Ensure input file exists
    if not os.path.isfile(INPUT_FILE):
        print(f"Error: Input file '{INPUT_FILE}' not found.")
        return
    
    # Ensure output directory exists
    output_dir = os.path.dirname(OUTPUT_FILE)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)


    # ---- Variables for reporting ----
    input_records = 0
    output_records = 0
    discarded_entries_count = 0
    corrected_entries_count = 0
    duplicates_detected_count = 0
    # ----------------------------------

    parsed_episodes = []
    episodes_seen_by_key = {} # catalog for deduplication: key -> episode
    unique_episodes = []

    # 1. Read and clean the input CSV
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)

            # Validate empty file
            if not reader.fieldnames:
                print("Error: Input CSV appears to be empty.")
                return

            # Validate required columns
            required_fields = {
                "Series Name",
                "Season Number",
                "Episode Number",
                "Episode Title",
                "Air Date"
            }
            if not required_fields.issubset(reader.fieldnames):
                print("Error: Input CSV missing required columns.")
                print(f"Required columns: {required_fields}")
                print(f"Found columns: {reader.fieldnames}")
                return
            
            # Process each row in the CSV
            for row in reader:
                # Count total input records
                input_records += 1
                parsed_row = clean_record(row)

                # Count discarded entries (those that returned None from clean_record)
                if not parsed_row:
                    discarded_entries_count += 1
                    continue

                # Count corrected entries (based on comparison between raw row and parsed row)
                if was_row_corrected(row, parsed_row):
                    corrected_entries_count += 1

                parsed_episodes.append(parsed_row)

    except Exception as e:
        print(f"Error while reading input file: {e}")
        return
    
    
    # 2. Deduplicate parsed episodes
    for episode in parsed_episodes:
        keys = generate_deduplication_keys(episode)

        # Some episodes may not generate any keys if they are missing too much information,
        # but we still want to keep them as they passed the discard rules.
        # (in this exercise, the only possible case is an episode with only a series name and a valid air date)
        if not keys:
            unique_episodes.append(episode)
            continue

        # Check if any of the keys exist in episodes_seen_by_key, if so, we have a duplicate
        existing_episode = None
        for key in keys:
            if key in episodes_seen_by_key:
                existing_episode = episodes_seen_by_key[key]
                break

        if existing_episode:
            # We have a duplicate. We need to decide which one to keep.
            duplicates_detected_count += 1
            best_episode = get_best_episode(existing_episode, episode)
            
            # If the winner is the new episode, 
            #  we need to update the catalog to point all keys that were pointing to the existing episode
            #  to now point to the best episode.
            if best_episode is not existing_episode:       
                for k in list(episodes_seen_by_key.keys()):
                    if episodes_seen_by_key[k] is existing_episode:
                        episodes_seen_by_key[k] = best_episode
            
            # Map the current episode's keys to the winner in the catalog.
            for key in keys:
                episodes_seen_by_key[key] = best_episode

        else:
            # No duplicate, store this episode for all its keys
            for key in keys:
                episodes_seen_by_key[key] = episode

    
    # 3. Collect unique episodes from the deduplication map (dict --> array)
    seen = set()
    for ep in episodes_seen_by_key.values():
        if id(ep) not in seen:
            unique_episodes.append(ep)
            seen.add(id(ep))


    # 4. Sort episodes by Series Name, Season Number, Episode Number
    unique_episodes = sort_episodes(unique_episodes)
    output_records = len(unique_episodes)
    

    # 5. Write cleaned data to output CSV
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as outfile:
            fieldnames = [
                "SeriesName",
                "SeasonNumber",
                "EpisodeNumber",
                "EpisodeTitle",
                "AirDate"
            ]

            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()

            for episode in unique_episodes:
                writer.writerow(episode)

    except Exception as e:
        print(f"Error while writing output file: {e}")
        return


    # 6. Generate quality report
    generate_quality_report(
        input_records,
        output_records,
        discarded_entries_count,
        corrected_entries_count,
        duplicates_detected_count
    )


    print(f"Done! {output_records} episodes written to {OUTPUT_FILE}")
    print(f"Report saved to {REPORT_FILE}")


# Entry point
if __name__ == "__main__":
    main()

    
    
