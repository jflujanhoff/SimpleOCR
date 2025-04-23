# ocr_models/utils.py
import sys
import os
from typing import TYPE_CHECKING

# Add the parent directory (workspace root) to the Python path
# This allows importing 'variables' directly
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if TYPE_CHECKING:
    # This avoids circular imports if variables.py ever needs to import from utils
    # Though unlikely in this simple case, it's good practice.
    pass

# Attempt to import the template from the root directory (variables.py)
try:
    from variables import PAGE_MARKER_TEMPLATE
except ImportError:
    # Fallback if running from a different context or structure changes
    # This might indicate a project structure issue if it happens often
    print("Warning: Could not import PAGE_MARKER_TEMPLATE from variables.py. Using default.")
    PAGE_MARKER_TEMPLATE = "#### Page {page_num} of {total_pages}\n\n" # Default fallback


def format_page_marker(page_num: int, total_pages: int) -> str:
    """Formats the page number marker using a template from variables.py.

    Args:
        page_num: The current page number (1-indexed).
        total_pages: The total number of pages in the document.

    Returns:
        A formatted markdown string for the page marker.
    """
    # Basic validation
    if not isinstance(page_num, int) or page_num < 1:
        # Return a marker indicating an issue instead of raising an error
        # This makes the OCR process more resilient if page numbering is off
        print(f"Warning: Invalid page_num received: {page_num}")
        return f"#### [Invalid Page Num: {page_num}] of {total_pages}\n\n"
    if not isinstance(total_pages, int) or total_pages < 1:
         print(f"Warning: Invalid total_pages received: {total_pages}")
         return f"#### Page {page_num} of [Invalid Total Pages: {total_pages}]\n\n"
    if page_num > total_pages:
        # Log a warning but still format the output
        print(f"Warning: page_num ({page_num}) is greater than total_pages ({total_pages}).")

    # Use the imported template string
    return PAGE_MARKER_TEMPLATE.format(page_num=page_num, total_pages=total_pages)

# Clean up sys.path modification if it was added
# This is good practice to avoid polluting the path for other modules
# However, depending on execution context, this might remove necessary paths
# Let's comment it out for now to ensure broader compatibility in simple scripts
# if parent_dir in sys.path and sys.path[0] == parent_dir:
#     sys.path.pop(0) 