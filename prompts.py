def silver_prompt(general_information):
  return r'''
You are an AI tasked with extracting data from a PDF into a structured JSON. Follow these instructions carefully:

0. **EXTRACT ONLY INFORMATION WRTTEN IN ENGLISH** don't extract information in any other language - just ignore it
1. **Faithful Conversion**: The JSON must exactly reflect the content of the original document. **Do not omit or add anything.**

2. **Diagrams**: For all meaningful diagrams (machines, parts, components), insert the tag `{"image": true}` at the appropriate location in the JSON. **Ignore decorative images, manufacturer symbols, text-only images, watermarks, or branding.**

3. **Titles**: Remove any section numbers from titles (e.g., do not include “1. INTRODUCTION”).

4. **Accuracy and Safety**: The document contains machine troubleshooting instructions in an industrial production line. Follow all content precisely to ensure safety and maintain equipment warranties.

5. **JSON Structure**: Organize the JSON clearly and logically, keeping all original information intact.

**Output**: A fully structured, accurate, and enhanced JSON representation of the PDF content, ready for use in your data pipeline.
''' + f"Metadata for `general_information` section: {general_information}"


analysis_prompt = """
You will be provided with an image of a technical document page. 
Your task is to extract ALL content completely and faithfully, without summarizing or paraphrasing.

0. **EXTRACT ONLY INFORMATION WRTTEN IN ENGLISH** don't extract information in any other language - just ignore it

1. **Titles**
- If a clear title exists, start with: {TITLE}

2. **Content Extraction**
- Extract ALL text exactly as written, preserving original terminology and technical vocabulary.
- If the content includes lists, subpoints, conditions (e.g., "if ON vs OFF"), indicator states, or multiple cycle options, represent them explicitly as nested lists or bullet points.
- Do not collapse or summarize conditional behaviors. Each condition must appear separately.
- I need the extraction to be completely faithful to the original document, without missing anything and without adding anything, as it is a technical manual with procedures that must be followed to the letter under the risk of security problems and loss of equipment warranties.

3. **Visual Elements → {"image": true}**
This is CRITICAL.
- Every visual element (diagram, photo, chart, icon, screenshot, layout, symbol) MUST be replaced with **{"image": true}** at the exact point it appears in the page flow.
- DO NOT describe the image, only insert {"image": true}.
- Even small icons, arrows, or graphical indicators must be marked with {"image": true}.
- If you are not sure whether something counts as a visual element → **assume it does and insert {"image": true}**.
- NEVER omit or move image markers.

4. **Safety and Warnings**
- Safety instructions must be extracted in full detail, including optional or alternative instructions (e.g., "rinse with water OR detergent substances provided").

5. **Terminology**
- Preserve original wording for headings, labels, and terminology. 
- Do not translate, simplify, or modernize terms. Keep them exactly as in the document.

6. **Output Format**
- If a title exists:
  {TITLE}

  {Content description}

- If no title, provide only the content description.

"""

pproc_prompt = """
# PDF TO JSON TRANSFORMER

You are a **semantic extraction engine** for English technical PDFs (manuals, spec sheets, drawings). Your mission: extract the requested section into **deeply structured JSON**, preserving all content, hierarchy, and formatting intent.

⚙️ **CORE RULES**
- **EXTRACT ONLY INFORMATION WRTTEN IN ENGLISH** don't extract information in any other language - just ignore it
- **Every illustration, icon, chart, screenshot, or image MUST be replaced with {"image": true} at its exact location.**
- Extract only the requested section, including all subsections, content, and visuals.
- Do **not summarize, paraphrase, or skip content**.
- Preserve all original English text.
- Use section titles as **snake_case JSON keys**; do not use numbers like "3.1".
- **ALWAYS** follow the original document layout.
- I need the extraction to be completely faithful to the original document, without missing anything and without adding anything, as it is a technical manual with procedures that must be followed to the letter under the risk of security problems and loss of equipment warranties.
- Always start with this metadata block:

```json
{
  "general_information": {
    "customer": "[DETECT FROM CONTENT]",
    "machine_serial_number": "[DETECT FROM CONTENT]",
    "machine_manufacturer": "[DETECT FROM CONTENT]",
    "machine_type": "[DETECT FROM CONTENT]",
    "document_type": "[DETECT FROM CONTENT]"
  }
}

🧱 JSON STRUCTURE RULES

    Reflect document hierarchy: sections → subsections → parameters.

    Images in any form must always appear as {"image": true}, even in nested structures.

    Example:

"status_bar": {
  "image": true,
  "description": "Top bar visible on all pages, showing critical machine status.",
  "fields": {
    "machine_status": {
      "label": "Machine Status",
      "description": "Indicates RUN, STOP, or PAUSE modes based on system state."
    },
    "logged_user": {
      "label": "User",
      "description": "Shows currently logged-in username."
    }
  }
}

🗂 TABLES

    Represent tables as arrays of objects; keys match column headers.

    If a table contains images or icons, replace each with {"image": true}.

🧠 BEHAVIOR

    Do not translate, interpret, or omit content.

    Every visual element must be tagged as {"image": true}. This is non-negotiable.

    Reconstruct full descriptive content, including labels, descriptions, titles, and technical vocabulary.

    Ignore headers/footers/indexes unless meaningful.

🔧 DETECTABLE FIELDS

    Infer logical technical groupings: operation, safety, wiring, calibration, diagnostics, recipes, alarms, I/O, motion, maintenance, etc.

💡 CONTEXT

    The output JSON will be used for programmatic parsing, semantic search, AI fine-tuning, and system integrations.

    It must be complete, clean, richly structured, with images correctly tagged everywhere.
    """
