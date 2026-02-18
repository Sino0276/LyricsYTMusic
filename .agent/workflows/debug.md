---
description: Run the application and view logs to identify and fix runtime errors.
---

1.  **Run Application**:
    *   Execute the application using `run_command` (e.g., `python main.py`).
    *   Wait for a few seconds to capture startup logs.
    *   // turbo
    *   Use `command_status` to view the logs, specifically looking for `Traceback`, `Error`, or `Exception`.

2.  **Analyze Logs**:
    *   Identify the file, line number, and error message from the traceback.
    *   Use `view_file` to inspect the code around the error.

3.  **Fix Bug**:
    *   Determine the cause of the error.
    *   Apply a fix using `replace_file_content` or `multi_replace_file_content`.
    *   Add a comment explaining the fix.

4.  **Verify**:
    *   Re-run the application to ensure the error is resolved.
    *   If new errors appear, repeat Step 2.
    *   If successful, notify the user.
