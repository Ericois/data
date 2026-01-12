#!/usr/bin/env python3
"""
CueBox Data Import Script

This script processes constituent data from input spreadsheets and produces
two output CSV files for import into CueBox.
"""

import pandas as pd
import requests
import re
from datetime import datetime
from typing import Optional


def fetch_tag_mapping() -> dict:
    """Fetch tag mapping from the CueBox API."""
    url = "https://6719768f7fc4c5ff8f4d84f1.mockapi.io/api/v1/tags"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        # Build mapping from original name to mapped name
        # Note: API has "Camp 2016 " with trailing space, so we strip names
        return {item["name"].strip(): item["mapped_name"] for item in data}
    except requests.RequestException as e:
        print(f"Warning: Could not fetch tag mapping from API: {e}")
        print("Using fallback tag mapping")
        # Fallback mapping based on known API response
        return {
            "Major Donor 2021": "Major Donor",
            "Top Donor": "Major Donor",
            "Summer School 2016": "Summer 2016",
            "Pitch Perfect Volunteer": "Pitch Perfect",
            "Pitch Perfect Staff": "Pitch Perfect",
            "Camp 2016": "Summer 2016",
            "Board Member": "Board Member",
        }


def is_valid_email(email: str) -> bool:
    """
    Check if email has valid format and domain.

    Validates:
    - Basic email format (contains @ with text before and after)
    - Domain has at least one dot
    - Common typos are NOT considered valid (e.g., gmaill.com, yaho.com)
    """
    if not email or pd.isna(email):
        return False

    email = str(email).strip().lower()

    # Basic format check
    if "@" not in email:
        return False

    parts = email.split("@")
    if len(parts) != 2:
        return False

    local, domain = parts
    if not local or not domain:
        return False

    # Domain must have at least one dot
    if "." not in domain:
        return False

    # Check for common typo domains (these are invalid)
    invalid_domains = {
        "gmaill.com",  # typo for gmail.com
        "yaho.com",    # typo for yahoo.com
        "hotmal.com",  # typo for hotmail.com
    }
    if domain in invalid_domains:
        return False

    # Basic regex for email format
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def standardize_email(email: str) -> str:
    """Standardize email format (lowercase, stripped)."""
    if not email or pd.isna(email):
        return ""
    return str(email).strip().lower()


def determine_constituent_type(row: pd.Series) -> str:
    """
    Determine if a constituent is a Person or Company.

    Decision logic:
    - If First Name OR Last Name is present → Person
    - If only Company is present (no name) AND Company is a legitimate business name → Company
    - Special cases like "Retired", "...", "Used to work here." are treated as Person
      (these appear to be notes about individuals, not company names)
    """
    has_first_name = pd.notna(row["First Name"]) and str(row["First Name"]).strip()
    has_last_name = pd.notna(row["Last Name"]) and str(row["Last Name"]).strip()
    has_company = pd.notna(row["Company"]) and str(row["Company"]).strip()

    # If they have any name, they're a person
    if has_first_name or has_last_name:
        return "Person"

    # If they only have a company and it's a legitimate business name
    if has_company:
        company = str(row["Company"]).strip()
        # These are not real companies - they're notes about individuals
        non_company_values = {"retired", "...", "used to work here."}
        if company.lower() in non_company_values:
            return "Person"  # These are actually persons with no name data
        return "Company"

    # Default to Person (shouldn't happen with valid data)
    return "Person"


def normalize_title(salutation: str) -> str:
    """
    Normalize salutation to one of: "Mr.", "Mrs.", "Ms.", "Dr.", or empty string.

    Decision logic:
    - "Dr" or "Dr." → "Dr."
    - "Mr" or "Mr." → "Mr."
    - "Mrs" or "Mrs." → "Mrs."
    - "Ms" or "Ms." → "Ms."
    - "Rev" → "" (not in allowed list)
    - "Mr. and Mrs." → "" (not a single title, cannot determine primary)
    - Any other value → ""
    """
    if not salutation or pd.isna(salutation):
        return ""

    salutation = str(salutation).strip().lower()

    mapping = {
        "dr": "Dr.",
        "dr.": "Dr.",
        "mr": "Mr.",
        "mr.": "Mr.",
        "mrs": "Mrs.",
        "mrs.": "Mrs.",
        "ms": "Ms.",
        "ms.": "Ms.",
    }

    return mapping.get(salutation, "")


def get_marital_status(gender_value: str) -> Optional[str]:
    """
    Extract marital status from the Gender column.

    The "Gender" column in the input data actually contains marital status values.
    - "Married" → Married
    - "Single" → Single
    - "Unknown" or NaN → None (no marital status available)
    """
    if not gender_value or pd.isna(gender_value):
        return None

    gender_value = str(gender_value).strip()
    if gender_value in ("Married", "Single"):
        return gender_value
    return None


def format_background_info(title: str, marital_status: Optional[str]) -> str:
    """
    Format background information string.

    Examples:
    - Job title and marital status: "Job Title: Professor; Marital Status: Married"
    - Only job title: "Job Title: Professor"
    - Only marital status: "Marital Status: Married"
    - Neither: ""
    """
    parts = []

    if title and pd.notna(title) and str(title).strip():
        parts.append(f"Job Title: {str(title).strip()}")

    if marital_status:
        parts.append(f"Marital Status: {marital_status}")

    return "; ".join(parts)


def format_currency(amount: float) -> str:
    """Format amount as currency string like '$10.00'."""
    if pd.isna(amount) or amount == 0:
        return ""
    return f"${amount:,.2f}"


def format_timestamp(date_value) -> str:
    """
    Format date value as ISO timestamp string.

    Handles various input formats from the spreadsheet.
    """
    if pd.isna(date_value):
        return ""

    # If already a datetime object
    if isinstance(date_value, (datetime, pd.Timestamp)):
        return date_value.strftime("%Y-%m-%d %H:%M:%S")

    # Try to parse string dates
    date_str = str(date_value).strip()

    # Try common formats
    formats = [
        "%b %d, %Y",      # "Jan 19, 2020"
        "%Y-%m-%d %H:%M:%S",  # "2022-04-19 00:00:00"
        "%Y-%m-%d",       # "2022-04-19"
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    # Return as-is if we can't parse
    return date_str


def map_tags(tags_str: str, tag_mapping: dict) -> str:
    """
    Map tags using the API mapping and return comma-separated list.

    - Tags are deduplicated after mapping (since multiple tags may map to same value)
    - Tags not in the mapping are kept as-is
    - Tags are sorted alphabetically for consistency
    """
    if not tags_str or pd.isna(tags_str):
        return ""

    original_tags = [t.strip() for t in str(tags_str).split(",")]
    mapped_tags = set()

    for tag in original_tags:
        if tag in tag_mapping:
            mapped_tags.add(tag_mapping[tag])
        else:
            # Keep unmapped tags as-is
            mapped_tags.add(tag)

    return ", ".join(sorted(mapped_tags))


def process_constituents(
    constituents_df: pd.DataFrame,
    emails_df: pd.DataFrame,
    donations_df: pd.DataFrame,
    tag_mapping: dict,
) -> pd.DataFrame:
    """Process all constituent data and return the output DataFrame."""

    # Pre-compute donation aggregates per patron
    donation_agg = donations_df.groupby("Patron ID").agg(
        lifetime_amount=("Donation Amount", "sum"),
        most_recent_date=("Donation Date", "max"),
    ).reset_index()

    # Get most recent donation amount (need separate query for this)
    donations_df["Donation Date"] = pd.to_datetime(donations_df["Donation Date"])
    idx = donations_df.groupby("Patron ID")["Donation Date"].idxmax()
    most_recent_donations = donations_df.loc[idx, ["Patron ID", "Donation Amount"]].rename(
        columns={"Donation Amount": "most_recent_amount"}
    )

    donation_agg = donation_agg.merge(most_recent_donations, on="Patron ID", how="left")

    # Group emails by patron
    emails_by_patron = emails_df.groupby("Patron ID")["Email"].apply(list).to_dict()

    output_rows = []

    for _, row in constituents_df.iterrows():
        patron_id = row["Patron ID"]

        # Determine constituent type
        const_type = determine_constituent_type(row)

        # Get names based on type
        first_name = ""
        last_name = ""
        company_name = ""

        if const_type == "Person":
            first_name = str(row["First Name"]).strip().title() if pd.notna(row["First Name"]) else ""
            last_name = str(row["Last Name"]).strip().title() if pd.notna(row["Last Name"]) else ""
        else:
            company_name = str(row["Company"]).strip() if pd.notna(row["Company"]) else ""

        # Get emails for this patron
        patron_emails = emails_by_patron.get(patron_id, [])
        # Filter to valid emails only and standardize
        valid_emails = []
        for email in patron_emails:
            std_email = standardize_email(email)
            if is_valid_email(std_email) and std_email not in valid_emails:
                valid_emails.append(std_email)

        email_1 = valid_emails[0] if len(valid_emails) > 0 else ""
        email_2 = valid_emails[1] if len(valid_emails) > 1 else ""

        # Get title
        cb_title = normalize_title(row["Salutation"])

        # Get tags
        cb_tags = map_tags(row["Tags"], tag_mapping)

        # Get background info (only for Person type)
        if const_type == "Person":
            marital_status = get_marital_status(row["Gender"])
            job_title = row["Title"] if pd.notna(row["Title"]) else ""
            background_info = format_background_info(job_title, marital_status)
        else:
            background_info = ""

        # Get donation info
        patron_donations = donation_agg[donation_agg["Patron ID"] == patron_id]
        if len(patron_donations) > 0:
            lifetime_amount = format_currency(patron_donations.iloc[0]["lifetime_amount"])
            most_recent_date = format_timestamp(patron_donations.iloc[0]["most_recent_date"])
            most_recent_amount = format_currency(patron_donations.iloc[0]["most_recent_amount"])
        else:
            lifetime_amount = ""
            most_recent_date = ""
            most_recent_amount = ""

        # Build output row
        output_rows.append({
            "CB Constituent ID": patron_id,
            "CB Constituent Type": const_type,
            "CB First Name": first_name,
            "CB Last Name": last_name,
            "CB Company Name": company_name,
            "CB Created At": format_timestamp(row["Date Entered"]),
            "CB Email 1 (Standardized)": email_1,
            "CB Email 2 (Standardized)": email_2,
            "CB Title": cb_title,
            "CB Tags": cb_tags,
            "CB Background Information": background_info,
            "CB Lifetime Donation Amount": lifetime_amount,
            "CB Most Recent Donation Date": most_recent_date,
            "CB Most Recent Donation Amount": most_recent_amount,
        })

    return pd.DataFrame(output_rows)


def process_tags(constituents_df: pd.DataFrame, tag_mapping: dict) -> pd.DataFrame:
    """
    Process tags and return DataFrame with tag name and count.

    Uses mapped tag names and counts unique constituents per tag.
    """
    tag_counts = {}

    for _, row in constituents_df.iterrows():
        if pd.isna(row["Tags"]):
            continue

        original_tags = [t.strip() for t in str(row["Tags"]).split(",")]
        mapped_tags = set()

        for tag in original_tags:
            if tag in tag_mapping:
                mapped_tags.add(tag_mapping[tag])
            else:
                mapped_tags.add(tag)

        for tag in mapped_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    output_rows = [
        {"CB Tag Name": tag, "CB Tag Count": count}
        for tag, count in sorted(tag_counts.items())
    ]

    return pd.DataFrame(output_rows)


def main():
    """Main entry point for the data import script."""
    input_file = "Copy of Data Import Assignment.xlsx"

    print("Loading input data...")
    xlsx = pd.ExcelFile(input_file)
    constituents_df = pd.read_excel(xlsx, sheet_name="Input Constituents")
    emails_df = pd.read_excel(xlsx, sheet_name="Input Emails")
    donations_df = pd.read_excel(xlsx, sheet_name="Input Donation History")

    print(f"Loaded {len(constituents_df)} constituents")
    print(f"Loaded {len(emails_df)} email records")
    print(f"Loaded {len(donations_df)} donation records")

    print("\nFetching tag mapping from API...")
    tag_mapping = fetch_tag_mapping()
    print(f"Loaded {len(tag_mapping)} tag mappings")

    print("\nProcessing constituents...")
    output_constituents = process_constituents(
        constituents_df, emails_df, donations_df, tag_mapping
    )

    print("Processing tags...")
    output_tags = process_tags(constituents_df, tag_mapping)

    # Save output files
    constituents_output_file = "output_cuebox_constituents.csv"
    tags_output_file = "output_cuebox_tags.csv"

    # Replace NaN with empty string for clean CSV output
    output_constituents = output_constituents.fillna("")
    output_tags = output_tags.fillna("")

    output_constituents.to_csv(constituents_output_file, index=False)
    output_tags.to_csv(tags_output_file, index=False)

    print(f"\nOutput saved to:")
    print(f"  - {constituents_output_file} ({len(output_constituents)} rows)")
    print(f"  - {tags_output_file} ({len(output_tags)} rows)")

    # Print summary statistics
    print("\n=== Summary Statistics ===")
    print(f"Total constituents: {len(output_constituents)}")
    print(f"  - Persons: {len(output_constituents[output_constituents['CB Constituent Type'] == 'Person'])}")
    print(f"  - Companies: {len(output_constituents[output_constituents['CB Constituent Type'] == 'Company'])}")
    print(f"Constituents with valid Email 1: {len(output_constituents[output_constituents['CB Email 1 (Standardized)'] != ''])}")
    print(f"Constituents with valid Email 2: {len(output_constituents[output_constituents['CB Email 2 (Standardized)'] != ''])}")
    print(f"Constituents with donations: {len(output_constituents[output_constituents['CB Lifetime Donation Amount'] != ''])}")
    print(f"Unique mapped tags: {len(output_tags)}")


if __name__ == "__main__":
    main()
