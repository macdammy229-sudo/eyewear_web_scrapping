# Eye-Wear-Web-Scraping

This project introduces learners to real-world web scraping with Selenium, focusing on extracting unstructured product data from e-commerce sites, handling dynamic content, and creating structured datasets for analysis.

## Project Overview

The pipeline consists of three main components:

1. **Scrapers** (`frames.py`, `eyebuy.py`) - Extract raw eyewear product data from two retailers
2. **Unifier** (`unify.py`) - Validates, cleans, deduplicates, and attributes the scraped data
3. **Dashboard** (`app.py`) - Visualizes and analyzes the unified dataset with Streamlit

## The Problem

Two independent scrapers produce two separate CSV datasets. Without unification, you cannot answer business questions like:
- Which retailer sells this frame cheapest?
- How confident are we in that answer?
- Is this the same product at different prices, or a different product?

Data quality issues include:
- **Duplication within a source**: Re-running a scraper appends duplicate rows
- **Duplication across sources**: Same product (Ray-Ban RB7047) at different prices needs to be identified and labeled, not deleted
- **Inconsistent shape**: EyeBuyDirect folds brand into model name; FramesDirect separates them
- **Silent quality problems**: Null prices, whitespace in names, data that corrupts calculations
- **No provenance**: Once concatenated, rows lose track of which retailer provided the data

## Setup

### Prerequisites
- Python 3.10 or later
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/macdammy229-sudo/Eye-Wear-Web-Scraping.git
cd Eye-Wear-Web-Scraping
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Run Order

Follow these steps to generate the unified dataset:

### 1. Run the Scrapers

```bash
python frames.py
python eyebuy.py
```

This generates CSV and JSON files in `extracted_data/`:
- `framesdirect_data.csv`
- `eyebuydirect_data.csv`
- (JSON files are ignored by `.gitignore`)

### 2. Unify the Data

```bash
python unify.py
```

This processes all `*_data.csv` files and produces:
- `extracted_data/unified_eyewear.csv` - The final clean, deduplicated, attributed dataset

The unifier prints detailed progress at each stage:
```
======================================================================
STAGE 1: DISCOVER AND LOAD
======================================================================
✓ Loaded framesdirect_data.csv: 100 rows
✓ Loaded eyebuydirect_data.csv: 50 rows

======================================================================
STAGE 2: VALIDATE SCHEMA
======================================================================
✓ framesdirect_data.csv schema is valid
✓ eyebuydirect_data.csv schema is valid

[... continues through stages 3-6 ...]
```

### 3. Explore the Dashboard

```bash
streamlit run app.py
```

Opens an interactive dashboard at `http://localhost:8501` for filtering, analyzing, and comparing products.

## Data Schema

### Input Schema (from scrapers)

Both scrapers must emit exactly these 8 columns in this order:

| Column | Type | Notes |
|--------|------|-------|
| `source` | string | `framesdirect` or `eyebuydirect` |
| `brand` | string or null | Null for house frames or missing data |
| `name` | string | Model name; brand prefix removed |
| `former_price` | float or null | RRP; null when not discounted |
| `current_price` | float or null | Customer price (required) |
| `discount` | string or null | Example: `"30%"` |
| `product_link` | string | Absolute URL to product page |
| `page` | int | Catalogue page (for credibility) |

### Output Schema (unified dataset)

The unifier adds 5 columns to the input schema:

| Column | Type | Meaning |
|--------|------|---------|
| `discount_pct` | float or null | Discount as a number (e.g., `30.0`) |
| `savings` | float or null | `former_price - current_price` |
| `on_sale` | boolean | True where a genuine discount exists |
| `sold_by_n_sites` | int | Number of retailers listing this product |
| `scraped_at` | date string | Collection date in `YYYY-MM-DD` format |

**Null Handling**: Missing values are always Python `None`, never the string `"Unknown"`. String sentinels force object dtype and break downstream calculations.

## Design Decisions

### 1. Schema Validation (Stage 2)
- Each input file is validated against the required 8-column schema
- Invalid files are skipped with a clear error message (does not raise)
- Ensures data quality before any processing

### 2. Text Normalization (Stage 3)
- Whitespace is collapsed (multiple spaces → single space)
- Leading/trailing whitespace is stripped
- Applies to `brand`, `name`, `discount`, `product_link`
- Prevents mismatches from formatting differences

### 3. Price Coercion
- `pd.to_numeric(errors='coerce')` converts prices to float
- Non-numeric values become `NaN` (None in output)
- Allows safe arithmetic without silent failures

### 4. Discount Parsing (Stage 3)
- Regex extracts numeric value from discount strings (e.g., `"30%"` → `30.0`)
- Returns None for invalid or missing discounts
- Enables consistent discount calculations

### 5. Deduplication (Stage 4)
- **Within-source**: Exact duplicates (all columns identical) are removed, keeping first occurrence
- **Cross-source**: Products are identified as "the same" if:
  - `brand` (lowercased) matches
  - `name` (lowercased, whitespace-normalized) matches
  - These rows are **labeled** with `sold_by_n_sites > 1` but **not deleted**
  - Reasoning: A Ray-Ban RB7047 at FramesDirect ($176) and EyeBuyDirect ($105) is the most valuable insight—which retailer is cheapest?

### 6. Attribution & Derived Fields (Stage 5)
- `savings` = `former_price - current_price` (only when both are present)
- `on_sale` = True only where `discount_pct` is not null AND `savings > 0`
- `scraped_at` = today's date in `YYYY-MM-DD` format
- Ensures every row carries source, collection date, and price change context

### 7. Quality Warnings
The unifier prints warnings for:
- Rows with null `current_price` (cannot support analysis)
- Rows with null `name` (incomplete product)
- Null `brand` for non-house frames (data quality issue)
- `former_price < current_price` (logically inconsistent)
- String "None" or "Unknown" instead of proper None (breaks calculations)

Warnings do **not** cause rows to be dropped—they flag potential issues for review.

## Known Limitations

### Matching Strategy
- **Simple heuristic**: Brand + normalized name = same product
- **Limitations**:
  - Different color variants of the same model are treated as one product (they appear once per retailer)
  - Model numbers without brand context may incorrectly match unrelated products (e.g., two different brands' "Classic" model)
  - Spelling variations, abbreviations, or alternate names are not handled (e.g., "Ray Ban" vs "Ray-Ban")
  - No fuzzy matching—requires exact (case-insensitive) match

- **For production**: Consider fuzzy string matching (e.g., `fuzzywuzzy`) or a product database with canonical SKUs

### Data Scope
- **Scrapers are simplified examples**: Production scrapers would use Selenium to navigate pagination, handle dynamic content, and extract from JavaScript-rendered pages
- **No conflict resolution**: If a product appears with different metadata (e.g., different prices for the same URL), the first occurrence is kept
- **No time-series tracking**: Prices are snapshots; historical trends are not captured

### Attribution Gaps
- Retailer + product link provide attribution
- No timestamp tracking within a scrape run (only collection date)
- No tracking of which pagination page caused duplicates (only `page` column from scraper)

## File Structure

```
Eye-Wear-Web-Scraping/
├── extracted_data/
│   ├── framesdirect_data.csv        # FramesDirect scraper output
│   ├── eyebuydirect_data.csv        # EyeBuyDirect scraper output
│   └── unified_eyewear.csv          # Final unified dataset (generated)
│
├── frames.py                        # FramesDirect scraper (provided)
├── eyebuy.py                        # EyeBuyDirect scraper (provided)
├── unify.py                         # Data unifier (YOUR DELIVERABLE)
├── app.py                           # Streamlit dashboard (provided)
│
├── .gitignore                       # Excludes venv/ and JSON files
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
└── LICENSE                          # MIT License
```

## Quality Checks

The unifier performs these checks at each stage:

- **Stage 2 (Validate)**: Schema completeness, column presence
- **Stage 3 (Clean)**: Whitespace, price coercion, discount parsing
- **Stage 4 (Deduplicate)**: Exact duplicates within source, cross-source labeling
- **Stage 5 (Attribute)**: Savings calculation, on_sale flagging, date formatting, null handling

All checks produce console output for transparency. A silent script is a failed script.

## Testing the Output

Once `unify.py` runs, verify the output:

```bash
# Check the file exists and has rows
head -5 extracted_data/unified_eyewear.csv

# Load in Python to inspect
python -c "import pandas as pd; df = pd.read_csv('extracted_data/unified_eyewear.csv'); print(df.info())"

# Run the dashboard
streamlit run app.py
```

The dashboard should load without errors. If it fails, check the error message—it usually points to a missing or incorrectly formatted column.

## Development & Commit History

This project emphasizes **incremental commits**, not a final dump:

- Early commits: Scraper implementations, schema definition
- Mid commits: Unifier stages (validate, clean, deduplicate)
- Later commits: README, documentation, edge case handling

Review the commit log to see how the solution evolved.

## License

MIT License © 2026 Omotola Owoeye

See LICENSE file for details.

## Further Reading

- [pandas Documentation](https://pandas.pydata.org/)
- [Selenium Documentation](https://www.selenium.dev/documentation/)
- [Streamlit Documentation](https://docs.streamlit.io/)
