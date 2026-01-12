# Data Import

This project processes constituent data from input spreadsheets and produces two output CSV files for import into CueBox.

## How to Run

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Setup

1. Create a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate  # On Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Ensure the input file `Copy of Data Import Assignment.xlsx` is in the project directory.

### Running the Script

```bash
python3 data_import.py
```

This will generate two output files:
- `output_cuebox_constituents.csv` - Constituent data formatted for CueBox import
- `output_cuebox_tags.csv` - Tag counts for CueBox import

---

## Assumptions and Decisions

### 1. Constituent Type Determination (Person vs Company)

**Decision:** A constituent is classified as:
- **Person**: If they have a First Name OR Last Name populated
- **Company**: If they have ONLY a Company name populated (no First/Last Name)

**Special cases:**
- Values like "Retired", "...", "Used to work here." in the Company field are NOT treated as company names. These appear to be notes about individuals, so constituents with only these values and no name are still classified as "Person".
- If a constituent has both a name and company (e.g., "Courtney Haney" at "Lawrence LLC"), they are classified as "Person" (the company is their employer, not their constituent type).

**Rationale:** Real company names follow business naming conventions (LLC, Ltd, PLC, Group, etc.), while the special cases listed above are clearly informal notes.

### 2. Email Validation and Standardization

**Decision:** Emails are validated for:
- Basic format (contains @, has local and domain parts)
- Domain has at least one dot
- Domain is not a known typo (e.g., "gmaill.com", "yaho.com", "hotmal.com")

**Handling:**
- Invalid emails are excluded from the output
- Valid emails are standardized to lowercase and trimmed
- Email 1 and Email 2 are guaranteed to be different

**Rationale:** The input data contains obvious typos like "gmaill.com" and "yaho.com" which would cause delivery failures. These are excluded rather than auto-corrected to avoid making assumptions about the intended domain.

### 3. Tag Mapping

**Decision:**
- Tags are mapped using the API at `https://6719768f7fc4c5ff8f4d84f1.mockapi.io/api/v1/tags`
- A fallback mapping is used if the API is unavailable
- Tags not in the mapping are kept as-is
- Duplicate mapped tags are deduplicated (e.g., if a constituent has both "Top Donor" and "Major Donor 2021", which both map to "Major Donor", they only get "Major Donor" once)
- Tags are sorted alphabetically for consistency

**Tags not in API mapping (kept as-is):**
- "Major Donor 2022"
- "Student Scholar"
- "Tag Test"
- "VIP"

**Rationale:** The API mapping represents the client's intentional cleanup. Tags not in the mapping may be newer tags or intentionally distinct categories that the client wants to preserve.

### 4. Title/Salutation Normalization

**Decision:** Salutations are normalized as follows:
- "Dr" or "Dr." → "Dr."
- "Mr" or "Mr." → "Mr."
- "Mrs" or "Mrs." → "Mrs."
- "Ms" or "Ms." → "Ms."
- "Rev" → "" (not in allowed output list)
- "Mr. and Mrs." → "" (cannot determine single applicable title)

**Rationale:** The output format only allows "Mr.", "Mrs.", "Ms.", "Dr.", or empty string. Values outside this list are converted to empty string.

### 5. Gender Column Interpretation

**Decision:** The "Gender" column in the input data actually contains marital status values:
- "Married" → Used as marital status
- "Single" → Used as marital status
- "Unknown" or empty → No marital status recorded

**Rationale:** The actual values in the column are "Married", "Single", "Unknown", and empty - these are clearly marital status values, not gender values. This appears to be a mislabeled column.

### 6. Background Information Formatting

**Decision:** Background information is only populated for Person constituents, not Companies. Format follows the examples provided:
- Both job title and marital status: "Job Title: Professor; Marital Status: Married"
- Only job title: "Job Title: Professor"
- Only marital status: "Marital Status: Married"

**Rationale:** Companies don't have personal attributes like marital status or individual job titles.

### 7. Date Formatting

**Decision:** All dates are converted to "YYYY-MM-DD HH:MM:SS" format for consistency.

**Rationale:** ISO 8601-based format is unambiguous and universally parseable.

### 8. Currency Formatting

**Decision:** Currency amounts are formatted as "$X,XXX.XX" with comma separators for thousands and two decimal places.

**Rationale:** Standard US currency formatting for readability.

---

## Clarifying Questions for Client Success Manager

1. **Persons without names:** There are constituents classified as "Person" who have no First Name or Last Name (e.g., Patron ID 5287 with "Retired" in Company field). The output format states First Name and Last Name are required for Person type. Should these:
   - Be excluded from the import?
   - Be imported with placeholder names?
   - Remain as-is and be reviewed post-import?

2. **Company constituents with marital status:** Some Company-type constituents have marital status data in the source. We currently exclude marital status from Background Information for companies. Should this data be preserved elsewhere or is discarding it correct?

3. **Unmapped tags:** Tags like "Major Donor 2022", "Student Scholar", "Tag Test", and "VIP" are not in the API mapping. Should these:
   - Be kept as-is (current behavior)?
   - Be excluded from the import?
   - Have specific mappings applied?

4. **Email typo corrections:** Should obviously typo'd email domains (e.g., "gmaill.com" → "gmail.com") be auto-corrected, or is exclusion the correct approach? Auto-correction risks changing valid but unusual domains.

5. **Constituents with Primary Email in Constituents sheet but not in Emails sheet:** The instructions say "If a constituent has a Primary Email in the Constituent sheet, then that email is guaranteed to be in the Emails input sheet as well." Should we validate this assumption or trust the data?

6. **Tag deduplication:** When the same original tag appears multiple times for a constituent (e.g., "Student Scholar, Student Scholar"), we deduplicate after mapping. Is this correct?

---

## QA Process

### Validation Steps Performed

1. **Row count verification:**
   - Input: 100 constituents
   - Output: 100 constituents (no data loss)

2. **Constituent type distribution:**
   - Persons: 88 (verified by checking First/Last Name presence)
   - Companies: 12 (verified by checking Company-only records)

3. **Email validation:**
   - 84 constituents have at least one valid email
   - 59 constituents have two valid emails
   - Verified invalid emails (gmaill.com, yaho.com, hotmal.com) are excluded

4. **Donation data accuracy:**
   - 89 constituents have donation history (verified against Input Donation History)
   - 11 constituents have no donations (verified as non-donors)
   - Spot-checked lifetime amounts by manually summing donations for sample patrons

5. **Tag mapping verification:**
   - Verified all 7 API mappings are applied correctly
   - Confirmed tag deduplication works (e.g., "Top Donor" + "Major Donor 2021" → single "Major Donor")
   - Tag counts sum correctly across all constituents

6. **Date format consistency:**
   - All dates in output use consistent "YYYY-MM-DD HH:MM:SS" format
   - Verified parsing of multiple input formats ("Jan 19, 2020" and "2022-04-19 00:00:00")

7. **Field format validation:**
   - All CB Title values are in {"Mr.", "Mrs.", "Ms.", "Dr.", ""}
   - All CB Constituent Type values are in {"Person", "Company"}
   - Currency amounts properly formatted with $ and commas

8. **Edge case testing:**
   - Constituents with no emails: Verified Email 1/2 are empty
   - Constituents with no donations: Verified donation fields are empty
   - Constituents with special Company values: "Retired", "..." correctly handled as Person

### Sample Data Verification

Manually verified 5 random constituents by tracing through all input files:
- Patron 5966: Verified name, emails (excluding invalid gmaill.com), donations ($13,100 lifetime), tags
- Patron 3660: Verified as Company, correct emails, no donations
- Patron 8101: Verified name, title (Ms.), donations ($4,500 lifetime)
- Patron 5287: Verified as Person (Retired handling), emails, donations ($9,000 lifetime)
- Patron 5034: Verified no valid emails (none in Emails sheet), donations ($1,500 lifetime)

---

## AI Tool Usage Statement

This project was developed with assistance from Claude. Here is a breakdown of the contributions:

### What I did:
- Provided the initial requirements and context
- Made key decisions about data interpretation (Person vs Company logic, email validation rules)
- Reviewed and validated the output
- Determined edge case handling approaches
- Formulated clarifying questions for the client

### What AI assisted with:
- Initial code scaffolding and structure
- Implementing the data processing logic based on my decisions
- Writing documentation drafts
- Suggesting validation approaches

### Review and Verification:
All code was reviewed, and all output was manually verified against the input data to ensure correctness. The AI served as a tool to accelerate development while I maintained responsibility for the final decisions and quality.
