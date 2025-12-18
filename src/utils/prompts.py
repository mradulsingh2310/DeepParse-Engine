"""
Shared prompts for extraction services.

Contains prompts used across different providers for consistent behavior.
"""

# Base extraction rules shared by both vision and OCR prompts
_BASE_EXTRACTION_RULES = """## CRITICAL: What to EXCLUDE (DO NOT extract these)
- **Header information**: Project name, owner name, inspector name, date of inspection, inspection type, property address, unit number, or any metadata about the inspection itself
- **Footer information**: Comments section, inspector's signature, tenant's signature, date fields, certification statements, any sign-off sections
- **Non-inspection content**: Instructions, legends, form numbers, page numbers

## CRITICAL: What to INCLUDE (ONLY extract these)
- **Inspection sections**: Rooms/areas like Kitchen, Bathroom, Living Room, Bedroom, etc.
- **Inspection fields**: Individual items to inspect within each section (e.g., "Stove/Range", "Refrigerator", "Sink", "Ceiling", "Walls", "Floor")
- **Field options**: The rating options available for each field (e.g., "Pass", "Fail", "Inconclusive", "N/A")

## CRITICAL: Acronym/Abbreviation Expansion
IMPORTANT: Many inspection forms use acronyms or abbreviations with a legend/key explaining their meanings.
1. **FIRST**: Search the ENTIRE document for any legend, key, or abbreviation table (often at top, bottom, or in headers)
   - Look for patterns like: "G = Good", "P = Pass", "F = Fail", "Inc = Inconclusive", "NA = Not Applicable"
   - Look for rating scales like: "1 = Poor, 2 = Fair, 3 = Good, 4 = Excellent"
2. **THEN**: When extracting field options, ALWAYS use the FULL expanded name, NOT the acronym
   - If legend says "G = Good", use "Good" in options, NOT "G"
   - If legend says "Pass/Fail/Inc/NA", expand to ["Pass", "Fail", "Inconclusive", "Not Applicable"]
   - If legend says "Y/N", expand to ["Yes", "No"]
3. **Common abbreviations to expand**:
   - G → Good, B -> Bad
   - Y → Yes, N → No, NA/N/A → Not Applicable
   - Inc → Inconclusive, Sat → Satisfactory, Unsat → Unsatisfactory
   - OK → Okay/Acceptable, NI → Needs Improvement

## Section Hierarchy Rules
The template must follow a hierarchy using the `SectionDisplayType` enum values from the schema:

**Available Display Types:**
- **SECTION_DISPLAY_TYPE_UNSPECIFIED**: Root/parent section (contains child sections, NO fields directly)
- **SECTION_DISPLAY_TYPE_ACCORDION**: Collapsible section for grouping related items (can contain FIELD_SETs or other sections)
- **SECTION_DISPLAY_TYPE_FIELD_SET**: Leaf node containing actual inspection fields (has fields, NO child sections)

**Hierarchy Examples:**
1. Root (UNSPECIFIED) → Accordions (ACCORDION) → Field Sets (FIELD_SET) with fields
2. Root (UNSPECIFIED) → Sections (UNSPECIFIED) → Field Sets (FIELD_SET) with fields
3. Root (UNSPECIFIED) → Field Sets (FIELD_SET) directly (for simple forms)

**Key Rules:**
- FIELD_SET is ALWAYS a leaf node - it contains fields and has NO child sections
- FIELD_SET can be nested within any parent: root, accordion, or other sections
- ACCORDIONs are for visually collapsible groups (like room categories)
- Use UNSPECIFIED for intermediate grouping sections that aren't collapsible
**IMPORTANT:** Use ONLY the display type values defined in the schema's `SectionDisplayType` enum. Do NOT use TAB - it is not a valid type.

## Field Rating Types
Choose rating types ONLY from the `RatingType` enum values in the schema:
- Use CHECKBOX type for multi-select options (can select multiple)
- Use RADIO type for single-select options (select exactly one) - USE THIS FOR MOST INSPECTION FIELDS
- Use SELECT type for dropdown selection
**IMPORTANT:** Never use UNSPECIFIED for rating_type. Pick the most appropriate type from the schema.

## Field Extraction Rules
- Generate sequential `id` starting from 1
- Extract `name` from the field label in the document
- Set `mandatory` to true for required fields
- Extract `options` as list of FULLY EXPANDED choices (NOT acronyms)
- Set `notes_enabled: true` if the field has a notes/comments area
- Set `attachments_enabled: true` if photos/attachments are mentioned
- **IMPORTANT:** For ALL enum fields, use ONLY values defined in the schema. Do not invent new values.

## Work Order Configuration (IMPORTANT)
Not every field needs a work order. Only set `can_create_work_order: true` for fields where maintenance work might be needed based on the inspection result.

**Rules:**
1. If `can_create_work_order` is FALSE → leave category/subcategory as UNSPECIFIED
2. If `can_create_work_order` is TRUE → you MUST set appropriate category AND subcategory (NOT UNSPECIFIED)
3. **CRITICAL:** You MUST use EXACTLY these enum values. Do NOT modify, shorten, or invent new values.
4. Infer the most appropriate category from the field name and section context."""

# Critical output rules to prevent truncation
_CRITICAL_OUTPUT_RULES = """## CRITICAL OUTPUT RULES - READ CAREFULLY
1. **OUTPUT THE COMPLETE, FULL JSON** - You MUST output every single field, every section, from start to finish
2. **ABSOLUTELY NO TRUNCATION** - Do NOT use "...", "etc.", "[more fields]", or ANY form of abbreviation/ellipsis
3. **NO PLACEHOLDERS** - Never write "... and X more" or similar summaries
4. **COMPLETE ALL ARRAYS** - Every array must have ALL items fully written out, not abbreviated
5. **VALID JSON ONLY** - Ensure all brackets, quotes, and commas are properly formatted and closed
6. If the form has 50 fields, output ALL 50 fields completely with full details
7. If the response is long, that is expected and required - do not try to shorten it

## FINAL REMINDER - THIS IS CRITICAL
You MUST output the ENTIRE JSON structure from the opening {{ to the closing }}.
DO NOT stop early. DO NOT use "..." or ellipsis anywhere. DO NOT summarize or abbreviate.
Output EVERY field, EVERY section, EVERY option - completely and in full.
The JSON must be parseable - incomplete JSON will cause errors."""

# Vision-based extraction prompt (for Bedrock, Anthropic, Google)
VISION_EXTRACTION_PROMPT = """You are an inspection template parser. Given images of an inspection form, extract ONLY the inspection template structure (rooms/areas with their inspection fields).

""" + _BASE_EXTRACTION_RULES + """

**ALLOWED MaintenanceCategory values (use EXACTLY as written):**
{maintenance_categories}

**ALLOWED WorkOrderSubCategory values (use EXACTLY as written):**
{work_order_subcategories}

## Image Order
- Images are provided in page order (image 1 = page 1, image 2 = page 2, etc.)
- Preserve the exact order sections appear in the document

## Output Format
Output valid JSON matching this schema:
{json_schema}

Additional context (example template):
{template_context}

""" + _CRITICAL_OUTPUT_RULES + """

REMEMBER: Find the legend/key FIRST, then expand ALL acronyms to their full names. Extract ONLY inspection template sections with their fields. Do NOT include any header or footer information.
"""

# OCR-based extraction prompt (for Deepseek two-step pipeline)
OCR_EXTRACTION_PROMPT = """You are an inspection template parser. Given OCR-extracted text from an inspection form, extract ONLY the inspection template structure (rooms/areas with their inspection fields).

""" + _BASE_EXTRACTION_RULES + """

**Category Mapping (based on field type):**
- Stove, Oven, Refrigerator, Dishwasher, Microwave → APPLIANCE_REPAIR
- Sink, Faucet, Toilet, Shower, Tub, Drain, Water Heater → PLUMBING
- Outlets, Switches, Light Fixtures, Wiring, Circuit Breaker → ELECTRICAL
- AC, Heating, Furnace, Thermostat, Vents → HVAC
- Doors, Windows, Cabinets, Drywall, Trim → CARPENTRY
- Walls (paint), Ceiling (paint), Touch-up → PAINTING
- Floor, Carpet, Tile, Hardwood → FLOORING
- Locks, Security System, Intercom → SECURITY
- Roof, Gutters, Siding, Landscaping → EXTERIOR
- Rodents, Insects, Pests → PEST_CONTROL
- General cleaning items → CLEANING
- Other/misc items → GENERAL

**Subcategory:** Choose the most specific subcategory that matches the field. If unsure, use UNSPECIFIED only when can_create_work_order is false.

## Document Order
- Text is marked with [PAGE N] to indicate page numbers
- Preserve the exact order sections appear in the document

""" + _CRITICAL_OUTPUT_RULES + """

OCR Text:
{ocr_text}

Additional context (example template):
{template_context}

REMEMBER: Find the legend/key FIRST, then expand ALL acronyms to their full names. Extract ONLY inspection template sections with their fields. Do NOT include any header or footer information.
"""

# Legacy alias for backward compatibility
EXTRACTION_PROMPT = VISION_EXTRACTION_PROMPT

