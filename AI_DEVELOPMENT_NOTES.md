# AI Development Notes
*RSG Graduate Engineer Trainee Selection Assignment*

This document provides a transparent, detailed retrospective of the AI-assisted development workflow used to build the **Mini AI Business Intelligence Assistant**.

---

## 1. AI Tools Used

- **ChatGPT:** Used for development guidance, troubleshooting, code review, documentation improvements, and understanding test results.
- **Google Gemini API:** Integrated for natural-language question interpretation. When Gemini requests fail because of API quota limits or service availability issues, the application uses a deterministic fallback engine to handle supported business questions.
- **Python, FastAPI, SQLite, Streamlit, and Pytest:** Used to implement the application, manage and query sales data, display results, and test functionality.
---

## 2. How AI Assisted During Development

### A. Dataset Quality Inspection & Imputation Discovery
- **Action:** AI inspected all 51 rows of the raw sales CSV before writing application code.
- **Finding:** It detected that `TXN0051` had a missing unit price for "Laptop Stand", `TXN0033` had a `Status = 'Returned'`, `TXN0034` had a `Quantity = 0`, and four records contained discounts.
- **Contribution:** Rather than silently discarding `TXN0051`, AI discovered that "Laptop Stand" had an established catalog price of ₹1,200.00 across all 6 other completed sales. This led to a defensible, auditable imputation strategy (`is_imputed = 1`) that preserves data integrity while documenting alternative baselines.

### B. Test-Driven Architecture Design
- **Action:** Formulated clean separation of concerns:
  - `data_loader.py` for deterministic ETL.
  - `database.py` for connection lifecycle and URI read-only isolation.
  - `query_service.py` for deterministic SQL templates and safety validation.
  - `llm_service.py` for two-tier intent routing and documented fallback.
  - `main.py` for FastAPI REST API endpoints.
  - `dashboard.py` for Streamlit visualization.

### C. Automated Test Generation
- **Action:** Generated an extensive 19-test Pytest suite covering data cleaning, SQLite ingestion, SQL safety guards, FastAPI endpoint contracts, edge-case month comparisons, and malicious input handling.

---

## 3. Real Problems Encountered & Debugging Steps

### Problem 1: Windows Console `UnicodeEncodeError` with Rupee Symbol (`₹`)
- **Symptom:** When running CLI verification scripts on Windows PowerShell, Python threw:
  ```
  UnicodeEncodeError: 'charmap' codec can't encode character '\u20b9' in position 63: character maps to <undefined>
  ```
- **Root Cause:** Default Windows PowerShell stdout encoding was `cp1252`, which cannot encode the Indian Rupee symbol (`\u20b9`).
- **Debugging & Resolution:** Configured `sys.stdout.reconfigure(encoding='utf-8')` in Python runtime and ensured all web interfaces (FastAPI and Streamlit) transmit JSON and render HTML in UTF-8.

### Problem 2: Initial Discrepancy in Automated Unit Count Assertions
- **Symptom:** During the first `pytest` run, `test_query_total_revenue` failed with `assert 638 == 546`, and `test_query_highest_sales_region` failed with `assert 182 == 152`.
- **Root Cause:** A preliminary theoretical calculation had undercounted multi-item orders. The database query sum:
  `SELECT SUM(quantity) FROM sales WHERE status = 'Completed' AND quantity > 0;`
  yielded exactly 638 units (and 182 units for the South region).
- **Debugging & Resolution:** Ran raw verification queries directly against the SQLite database to confirm the true mathematical baseline. Updated the unit test assertions to reflect actual data rather than fabricated approximations, adhering strictly to the constraint: *"Do not invent dataset values or claim that tests passed without running them."*

### Problem 3: Starlette Test Client Deprecation Warning

- **Symptom:** The test suite passed but reported a deprecation warning concerning the use of `httpx` with `starlette.testclient`.
- **Root Cause:** The installed testing dependencies reported that the current test-client integration is deprecated.
- **Status:** All 19 tests passed despite the warning. Updating the testing dependencies and verifying compatibility would be a future maintenance task.

### Problem 4: Host Disk Space Exhaustion During Package Installation
- **Symptom:** Writing `README.md` failed with OS error: `There is not enough space on the disk.`
- **Root Cause:** `Get-PSDrive C` revealed `0.00 GB` free space on Drive C due to accumulated pip HTTP wheel cache (`c:\users\dell\appdata\local\pip\cache\http-v2` holding 768.4 MB).
- **Debugging & Resolution:** Executed `pip cache purge`, immediately reclaiming 720 MB of free storage, allowing file creation to proceed smoothly.

### Problem 5: Gemini API Availability

- **Symptom:** Requests to the configured Gemini model returned a service-unavailable error, and some requests timed out.
- **Investigation:** Direct API requests also encountered availability issues, so the problem could not be resolved by changing the application's question-handling logic alone.
- **Resolution:** The application uses its deterministic fallback engine when the LLM request fails. The five sample business questions were tested successfully through this fallback.
- **Limitation:** The fallback supports predefined business-question patterns. Successful operation of the Gemini-powered interpretation path remains unverified and should be tested again when the configured model is available.

---

## 4. What Would Be Improved with Another Day of Work

If given an additional 24 hours of development time, the following enhancements would be added:

1. **RAG-Powered Schema & Vectorless SQL Routing (Text-to-SQL):**
   - Implement dynamic schema retrieval (Vectorless RAG) where user queries are matched against table schemas, column descriptions, and business glossary terms before generating ad-hoc read-only SQL for questions outside the pre-approved templates.

2. **Expanded Multi-Hop Analytical Intents:**
   - Support comparative queries across channels (Online vs. Retail) and cross-dimensional analyses (e.g., *"What is the most profitable sales channel in the South region for Furniture?"*).

3. **Database Migration to DuckDB or PostgreSQL:**
   - While SQLite is lightweight and zero-dependency, migrating to DuckDB would provide vectorized analytics and native Parquet/CSV querying without requiring an ingestion step.

4. **Multi-Turn Conversation Memory:**
   - Add conversation session state so users can ask follow-up questions (e.g., *"Which product generated the highest revenue?"* followed by *"What about its sales in the North region?"*).

5. **Containerization & CI/CD Pipeline:**
   - Package the backend and frontend into Docker containers with a `docker-compose.yml` file and GitHub Actions workflow running `pytest` and linting on every push.
