# variables.py

# Maximum number of files allowed for upload
MAX_FILES = 10

# Maximum size per file allowed for upload (in bytes)
# 5 MB = 5 * 1024 * 1024 bytes
MAX_SIZE = 5 * 1024 * 1024 

# Template for formatting page markers in OCR output
PAGE_MARKER_TEMPLATE = """

> **Page {page_num} of {total_pages}**

---
"""