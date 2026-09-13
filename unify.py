"""
Data Unifier for Eyewear Scraper Outputs
Reads CSV files from extracted_data/, validates, cleans, deduplicates,
and attributes all data, producing a unified dataset for analysis.

Usage:
    python unify.py

Output:
    extracted_data/unified_eyewear.csv - Clean, deduplicated, attributed dataset
    Console output - Progress and quality metrics at each stage
"""

import pandas as pd
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Optional
import numpy as np


# Expected schema from scrapers
REQUIRED_COLUMNS = [
    "source",
    "brand",
    "name",
    "former_price",
    "current_price",
    "discount",
    "product_link",
    "page"
]

OUTPUT_COLUMNS = REQUIRED_COLUMNS + [
    "discount_pct",
    "savings",
    "on_sale",
    "sold_by_n_sites",
    "scraped_at"
]


def discover_and_load_csvs(extracted_data_dir: str) -> Tuple[dict, List[str]]:
    """
    Discover all *_data.csv files in extracted_data directory.
    Exclude unified_eyewear.csv to prevent self-reference on re-runs.

    Args:
        extracted_data_dir: Path to extracted_data directory

    Returns:
        Tuple of (dict of DataFrames keyed by source, list of file paths loaded)
    """
    print("=" * 70)
    print("STAGE 1: DISCOVER AND LOAD")
    print("=" * 70)

    os.makedirs(extracted_data_dir, exist_ok=True)

    dataframes = {}
    loaded_files = []

    # Find all *_data.csv files
    pattern = os.path.join(extracted_data_dir, "*_data.csv")
    csv_files = sorted([f for f in Path(extracted_data_dir).glob("*_data.csv")
                       if os.path.basename(f) != "unified_eyewear.csv"])

    if not csv_files:
        print(f"⚠ No CSV files found in {extracted_data_dir}")
        return dataframes, loaded_files

    for filepath in csv_files:
        filename = os.path.basename(filepath)
        try:
            df = pd.read_csv(filepath)
            dataframes[filename] = df
            loaded_files.append(str(filepath))
            print(f"✓ Loaded {filename}: {len(df)} rows")
        except Exception as e:
            print(f"✗ Failed to load {filename}: {str(e)}")

    print(f"\nTotal files loaded: {len(dataframes)}\n")
    return dataframes, loaded_files


def validate_schema(df: pd.DataFrame, filename: str) -> bool:
    """
    Validate that a DataFrame has all required columns.

    Args:
        df: DataFrame to validate
        filename: Filename for error reporting

    Returns:
        True if valid, False otherwise
    """
    missing = set(REQUIRED_COLUMNS) - set(df.columns)

    if missing:
        print(f"✗ {filename} missing columns: {', '.join(sorted(missing))}")
        return False

    extra = set(df.columns) - set(REQUIRED_COLUMNS)
    if extra:
        print(
            f"⚠ {filename} has extra columns (will be ignored): {', '.join(sorted(extra))}")

    return True


def validate_all(dataframes: dict) -> dict:
    """
    Validate all loaded DataFrames against required schema.
    Skip invalid files.

    Args:
        dataframes: Dict of DataFrames to validate

    Returns:
        Dict of valid DataFrames only
    """
    print("=" * 70)
    print("STAGE 2: VALIDATE SCHEMA")
    print("=" * 70)

    valid_dfs = {}

    for filename, df in dataframes.items():
        if validate_schema(df, filename):
            valid_dfs[filename] = df
            print(f"✓ {filename} schema is valid")
        else:
            print(f"⊘ {filename} skipped (schema invalid)")

    print(f"\nValid files: {len(valid_dfs)}/{len(dataframes)}\n")

    if not valid_dfs:
        raise ValueError("No valid input files found")

    return valid_dfs


def normalize_text(value: any) -> Optional[str]:
    """
    Normalize text: collapse whitespace, strip, handle None.

    Args:
        value: Text value to normalize

    Returns:
        Normalized string or None
    """
    if pd.isna(value):
        return None

    text = str(value).strip()
    # Collapse multiple whitespace
    text = re.sub(r'\s+', ' ', text)

    return text if text else None


def parse_discount(discount_str: Optional[str]) -> Optional[float]:
    """
    Parse discount string (e.g., "30%") to float (30.0).

    Args:
        discount_str: String like "30%" or None

    Returns:
        Float percentage or None
    """
    if pd.isna(discount_str):
        return None

    discount_str = str(discount_str).strip()

    if not discount_str:
        return None

    # Extract percentage number
    match = re.search(r'(\d+(?:\.\d+)?)', discount_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None

    return None


def clean_dataframe(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """
    Clean a single DataFrame:
    - Normalize text fields
    - Coerce prices to numeric
    - Parse discount strings
    - Add source and collection date

    Args:
        df: DataFrame to clean
        source_name: Source name from filename (e.g., "framesdirect_data.csv")

    Returns:
        Cleaned DataFrame
    """
    df = df[REQUIRED_COLUMNS].copy()

    # Normalize text fields
    df['brand'] = df['brand'].apply(normalize_text)
    df['name'] = df['name'].apply(normalize_text)
    df['discount'] = df['discount'].apply(normalize_text)
    df['product_link'] = df['product_link'].apply(normalize_text)

    # Coerce prices to numeric (NaN for non-coercible)
    df['former_price'] = pd.to_numeric(df['former_price'], errors='coerce')
    df['current_price'] = pd.to_numeric(df['current_price'], errors='coerce')

    # Parse discount to percentage
    df['discount_pct'] = df['discount'].apply(parse_discount)

    return df


def clean_all(valid_dfs: dict) -> pd.DataFrame:
    """
    Clean all valid DataFrames and combine them.

    Args:
        valid_dfs: Dict of valid DataFrames

    Returns:
        Combined cleaned DataFrame
    """
    print("=" * 70)
    print("STAGE 3: CLEAN")
    print("=" * 70)

    cleaned_dfs = []

    for filename, df in valid_dfs.items():
        print(f"\nCleaning {filename} ({len(df)} rows)...")

        # Count issues before cleaning
        original_len = len(df)

        # Clean
        cleaned = clean_dataframe(df, filename)

        # Report findings
        null_former = cleaned['former_price'].isna().sum()
        null_current = cleaned['current_price'].isna().sum()
        null_name = cleaned['name'].isna().sum()
        null_brand = cleaned['brand'].isna().sum()

        if null_current > 0:
            print(f"  ⚠ {null_current} rows with null current_price")
        if null_former > 0:
            print(
                f"  ⚠ {null_former} rows with null former_price (expected for non-discounted)")
        if null_name > 0:
            print(f"  ⚠ {null_name} rows with null name (potential data issue)")
        if null_brand > 0:
            print(
                f"  ⚠ {null_brand} rows with null brand (house frames or incomplete data)")

        # Check for negative savings (former < current, which is illogical)
        has_discount = cleaned['former_price'].notna(
        ) & cleaned['current_price'].notna()
        negative_savings = ((cleaned.loc[has_discount, 'former_price'] <
                             cleaned.loc[has_discount, 'current_price']).sum())
        if negative_savings > 0:
            print(
                f"  ⚠ {negative_savings} rows where former_price < current_price (data quality issue)")

        cleaned_dfs.append(cleaned)
        print(f"  ✓ Cleaned")

    # Combine all cleaned data
    combined = pd.concat(cleaned_dfs, ignore_index=True)
    print(f"\nTotal rows after cleaning: {len(combined)}\n")

    return combined


def detect_duplicates_within_source(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    Detect and remove exact duplicates within a single source.
    Duplicates are identical rows (all columns).

    Args:
        df: DataFrame to deduplicate

    Returns:
        Tuple of (deduplicated DataFrame, count of duplicates removed)
    """
    before = len(df)

    # Identify exact duplicates across all columns
    df = df.drop_duplicates(subset=REQUIRED_COLUMNS, keep='first')

    removed = before - len(df)
    return df, removed


def detect_duplicates_across_sources(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect and label the same product across sources.
    Uses a simple heuristic: same brand + normalized name = same product.

    Args:
        df: Combined DataFrame from multiple sources

    Returns:
        DataFrame with added 'sold_by_n_sites' column
    """
    # Normalize name for matching (remove extra whitespace, case-insensitive)
    df['_match_key'] = (df['brand'].fillna('').str.lower().str.strip() + '|' +
                        df['name'].fillna('').str.lower().str.strip())

    # Count how many sites sell each product
    site_counts = df.groupby('_match_key')['source'].nunique().reset_index()
    site_counts.columns = ['_match_key', 'sold_by_n_sites']

    df = df.merge(site_counts, on='_match_key', how='left')
    df = df.drop('_match_key', axis=1)

    return df


def deduplicate_all(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicate: remove exact duplicates within sources,
    and label cross-source duplicates.

    Args:
        cleaned_df: Combined cleaned DataFrame

    Returns:
        Deduplicated DataFrame
    """
    print("=" * 70)
    print("STAGE 4: DEDUPLICATE")
    print("=" * 70)

    before = len(cleaned_df)

    # Remove exact duplicates within each source
    total_removed = 0
    for source in cleaned_df['source'].unique():
        source_df = cleaned_df[cleaned_df['source'] == source]
        _, removed = detect_duplicates_within_source(source_df)
        if removed > 0:
            print(f"✓ Removed {removed} exact duplicates from {source}")
            total_removed += removed

    # Re-deduplicate on the full set
    cleaned_df = cleaned_df.drop_duplicates(
        subset=REQUIRED_COLUMNS, keep='first'
    )

    if total_removed > 0:
        print(f"\nTotal duplicates removed: {total_removed}")

    # Label cross-source duplicates
    cleaned_df = detect_duplicates_across_sources(cleaned_df)

    cross_source_dupes = (cleaned_df['sold_by_n_sites'] > 1).sum()
    print(
        f"✓ Identified {cross_source_dupes} products sold by multiple sites (labeled, not removed)")

    after = len(cleaned_df)
    print(f"\nRows after deduplication: {after} (removed {before - after})\n")

    return cleaned_df


def attribute_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add attribution and derived fields.

    Args:
        df: Deduplicated DataFrame

    Returns:
        DataFrame with attribution columns
    """
    print("=" * 70)
    print("STAGE 5: ATTRIBUTE")
    print("=" * 70)

    # Calculate savings
    df['savings'] = None
    has_both_prices = df['former_price'].notna() & df['current_price'].notna()
    df.loc[has_both_prices, 'savings'] = (
        df.loc[has_both_prices, 'former_price'] -
        df.loc[has_both_prices, 'current_price']
    )

    # Mark items on sale (has discount_pct and savings > 0)
    df['on_sale'] = ((df['discount_pct'].notna()) &
                     (df['savings'].notna()) &
                     (df['savings'] > 0))

    # Add collection date (today)
    df['scraped_at'] = datetime.now().strftime('%Y-%m-%d')

    # Ensure all output columns exist and are in correct order
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[OUTPUT_COLUMNS]

    on_sale_count = df['on_sale'].sum()
    print(f"✓ Items marked on_sale: {on_sale_count}")
    print(f"✓ Collection date: {df['scraped_at'].iloc[0]}")
    print(
        f"✓ sold_by_n_sites range: {df['sold_by_n_sites'].min()} to {df['sold_by_n_sites'].max()}")

    # Quality checks
    print("\nQuality Report:")
    print(f"  Rows with savings calculated: {df['savings'].notna().sum()}")
    print(f"  Rows with discount_pct: {df['discount_pct'].notna().sum()}")
    print(f"  Rows with null name: {df['name'].isna().sum()}")
    print(
        f"  Rows with null current_price: {df['current_price'].isna().sum()}")

    # Null sanity check: ensure no string "None" or "Unknown"
    for col in df.select_dtypes(include=['object']).columns:
        string_nones = (df[col].astype(
            str).str.lower().isin(['none', 'unknown'])).sum()
        if string_nones > 0:
            print(
                f"  ⚠ {col} has {string_nones} string 'None'/'Unknown' values (should be None)")

    print()

    return df


def write_output(df: pd.DataFrame, output_path: str) -> None:
    """
    Write final DataFrame to CSV.

    Args:
        df: Final DataFrame to write
        output_path: Path to write CSV
    """
    print("=" * 70)
    print("STAGE 6: WRITE OUTPUT")
    print("=" * 70)

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(
        output_path) else '.', exist_ok=True)

    df.to_csv(output_path, index=False)

    print(f"✓ Wrote {len(df)} rows to {output_path}")
    print(f"✓ Output schema: {len(df.columns)} columns")
    print(f"✓ File size: {os.path.getsize(output_path) / 1024:.1f} KB\n")


def summary_report(df: pd.DataFrame) -> None:
    """
    Print a summary report of the unified dataset.

    Args:
        df: Final unified DataFrame
    """
    print("=" * 70)
    print("SUMMARY REPORT")
    print("=" * 70)
    print(f"Total products: {len(df)}")
    print(f"Total unique sources: {df['source'].nunique()}")
    print(f"Sources: {', '.join(sorted(df['source'].unique()))}")
    print(f"\nProducts by site count:")
    print(df['sold_by_n_sites'].value_counts().sort_index())
    print(f"\nPrice statistics:")
    print(f"  Current price - mean: ${df['current_price'].mean():.2f}, "
          f"min: ${df['current_price'].min():.2f}, max: ${df['current_price'].max():.2f}")
    if df['savings'].notna().sum() > 0:
        print(f"  Savings - mean: ${df['savings'].mean():.2f}, "
              f"max: ${df['savings'].max():.2f}")
    print(
        f"\nOn sale: {df['on_sale'].sum()} items ({df['on_sale'].sum() / len(df) * 100:.1f}%)")
    print(f"\nCross-site duplicates (same brand/model, different prices):")
    multi_site = df[df['sold_by_n_sites'] > 1].copy()
    if len(multi_site) > 0:
        print(
            f"  {len(multi_site)} rows for {multi_site.groupby(['brand', 'name']).ngroups} products")
    print("=" * 70 + "\n")


def main():
    """Main pipeline."""
    try:
        extracted_data_dir = "extracted_data"
        output_path = os.path.join(extracted_data_dir, "unified_eyewear.csv")

        # Stage 1: Discover and load
        dataframes, loaded_files = discover_and_load_csvs(extracted_data_dir)

        if not dataframes:
            print("No files to process. Run frames.py and eyebuy.py first.\n")
            return

        # Stage 2: Validate
        valid_dfs = validate_all(dataframes)

        # Stage 3: Clean
        cleaned = clean_all(valid_dfs)

        # Stage 4: Deduplicate
        deduplicated = deduplicate_all(cleaned)

        # Stage 5: Attribute
        attributed = attribute_data(deduplicated)

        # Stage 6: Write
        write_output(attributed, output_path)

        # Summary
        summary_report(attributed)

        print("✓ Unification complete!\n")

    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}\n")
        raise


if __name__ == "__main__":
    main()
