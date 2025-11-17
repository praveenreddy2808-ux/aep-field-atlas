# AEP Field Atlas  
A Streamlit app for discovering nested field paths across Adobe Experience Platform (AEP) datasets.

This utility connects directly to AEP Query Service (Postgres interface), identifies datasets containing a chosen root field (for example `_luma`, `_luma.contactIds`, `identityMap`, `commerce`, etc.), and extracts nested paths up to four levels deep. It provides an interactive search interface so you can quickly locate where any nested JSON/struct attribute exists.

> Note: This is a first working draft. It solves the core use case but is not production-hardened.

---

## Features

### ✓ Dynamic dataset scanning  
Automatically detects all datasets that contain the specified root field.

### ✓ Nested path extraction  
Parses JSON/struct fields up to 4 levels deep using SQL functions supported by AEP Query Service.

### ✓ Interactive search  
Search nested field paths using:
- Exact match  
- Contains (case-insensitive)  
- Regex  

### ✓ No file uploads required  
All scanning happens dynamically via direct SQL queries.

### ✓ Exportable results  
Download matches as CSV for documentation or further analysis.

---

## Example Use Cases

- Locate where `luma.contactIds.primary.id` appears across your datasets  
- Identify all datasets that use identity-related substructures under a namespace  
- Validate ingestion pipelines for complex JSON payloads  
- Troubleshoot missing or inconsistent fields across datasets  

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/aep-field-atlas.git
cd aep-field-atlas
