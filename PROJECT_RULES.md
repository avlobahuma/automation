# Project Rules

This repository contains automation scripts used for marketing, ecommerce and data workflows.

The goal is to generate simple, fast and practical automation scripts that are ready to run with minimal manual adjustment.

---

# General Philosophy

Scripts in this repository are utility tools.

They should be:

- simple
- fast
- readable
- easy to run locally
- easy to modify
- focused on saving time

Prefer direct and practical solutions over complex architecture.

Do not introduce unnecessary abstraction, frameworks or over-engineering.

Speed is more important than elegance.

---

# Code Generation Rules

When generating code:

- Always provide the complete script
- Never provide partial snippets unless explicitly requested
- Never respond with "change only this part"
- Output must always be copy-paste ready
- Do not assume manual edits are required after generation

The default output should be a complete, working script.

---

# Comments

Do not include comments in code by default.

Code should remain clean and minimal.

Exception:
Comments are allowed only when they provide essential setup instructions, such as dependency installation commands.

Example:

```python
# pip install pillow pandas
```

---

# Logging

Scripts must produce clear and extensive console output so the user can follow progress.

Logging should include, where relevant:

- script start
- discovered files or items
- current processing step
- progress counts
- completion summary
- total execution time

Examples of useful output:

- Starting script...
- Found 120 images
- Processing image 1 of 120
- Finished processing 120 images
- Total execution time: 2.34 seconds

Console output should be in English.

---

# Error Handling

Scripts should fail clearly and explicitly.

If required input is missing or invalid:

- stop execution
- show a clear error message
- do not fail silently

Prefer explicit failure over unclear behaviour.

---

# Folder Creation

If a script depends on folders that do not yet exist, it must create them automatically when appropriate.

Examples:

- input folder
- output folder
- temp folder
- export folder

The user should not have to create basic folders manually.

---

# File Handling

By default, generated output files may overwrite existing files.

Do not generate duplicate filenames unless explicitly requested.

Practical output is preferred over protective behaviour.

---

# File Naming

Use snake_case for all file names, function names and variables.

Examples:

- resize_images.py
- import_feed.py
- build_rsa.py
- input_folder
- output_file

Avoid camelCase.

---

# Script Configuration

Configuration should appear at the top of the script.

Examples:

- INPUT_FOLDER
- OUTPUT_FOLDER
- ALLOWED_EXTENSIONS
- MAX_WIDTH

Do not rely on command line arguments unless explicitly requested.

Default assumption:
All key settings should be directly editable in the config section at the top of the script.

---

# Python Rules

Python is used for local automation scripts.

## Python Version

Use modern Python 3 syntax compatible with current mainstream Python 3 versions.

Do not use outdated patterns unless necessary.

## Style

- Prefer simple procedural scripts
- Prefer functions over classes
- Avoid classes unless clearly beneficial
- Avoid unnecessary OOP
- Avoid unnecessary design patterns
- Prefer direct execution and practical logic

## Script Structure

Use the fastest and most practical structure.

A typical script should contain:

1. imports
2. configuration section
3. helper functions
4. main processing logic
5. execution entry point when useful

Use an entry point such as:

```python
if __name__ == "__main__":
    main()
```

when that improves reliability or structure.

Do not force structure for its own sake.

## Dependencies

External libraries may be used if they make the script simpler, faster or more reliable.

Acceptable examples include:

- pillow
- pandas
- requests

Avoid heavy or unnecessary frameworks.

If dependencies are required, include a short installation comment at the top of the script.

Example:

```python
# pip install pillow
```

## Paths

Prefer modern and robust path handling.

Use `pathlib` by default unless another approach is clearly better.

Scripts should be safe and practical across environments where possible.

## Performance

Performance matters.

Prefer fast implementations over overly elegant ones.

If beneficial, parallel processing may be used.

Acceptable examples include:

- concurrent.futures
- multiprocessing

Use parallelism when it provides real speed gains without unnecessary complexity.

---

# Google Apps Script Rules

Google Apps Script is used for Google Sheets and Google Ads related automation.

## Style

- Prefer small practical functions
- Avoid deeply nested logic
- Avoid unnecessary abstraction
- Prioritize speed and clarity

## Structure

Use the fastest and simplest structure that fits the task.

Do not split code into many parts unless there is a clear benefit.

## Naming

Use clear function names such as:

- build_rsa()
- import_feed()
- update_prices()

## Spreadsheet Interaction

Always reference spreadsheets, sheets and ranges clearly.

Example:

```javascript
const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("data");
```

If a required sheet is missing, fail clearly with an explicit error.

Do not silently continue when expected spreadsheet structure is missing.

---

# Output Expectations

Generated scripts should:

- run with minimal setup
- be easy to copy and use immediately
- provide clear progress visibility
- save time in real work
- avoid unnecessary explanation inside the code

The user values practical working code over theory.

---

# Default Priorities

When in doubt, prioritize in this order:

1. speed
2. practical usability
3. clean code
4. readability
5. architectural purity

---

# Summary

All generated scripts should be:

- complete
- fast
- practical
- copy-paste ready
- clearly logged
- easy to run
- easy to edit from the config section
- free from unnecessary comments and abstraction
