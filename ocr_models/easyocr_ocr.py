import easyocr
import numpy as np
from PIL import Image
import fitz  # PyMuPDF
import tempfile
import os
# import re # Removed unused import
from typing import Tuple, List
from .base import BaseOCR
import logging
from .utils import format_page_marker # Import the new function

# Set up logging
logger = logging.getLogger(__name__)

class EasyOCROCR(BaseOCR):
    """EasyOCR implementation."""

    def __init__(self, temp_dir: str, languages: List[str] = ['en']):
        """Initialize EasyOCR.

        Args:
            temp_dir: Directory for temporary files.
            languages: List of language codes for EasyOCR (e.g., ['en', 'es']).
                       Defaults to English.
        """
        self.temp_dir = temp_dir
        try:
            # Initialize the EasyOCR reader
            # You might need to specify gpu=True/False depending on your setup
            self.reader = easyocr.Reader(languages, gpu=True)
            logger.info(f"EasyOCR initialized with languages: {languages}")
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            # Optionally, re-raise or handle the error appropriately
            raise RuntimeError(f"EasyOCR initialization failed: {e}")

    # Re-introduce parts of the formatting logic for line reconstruction and paragraph breaks
    def _format_as_markdown(self, results: List[Tuple[List[List[int]], str, float]]) -> str:
        """Formats EasyOCR results by reconstructing lines and adding paragraph breaks based on vertical spacing.

        Args:
            results: List of tuples from EasyOCR: (bounding_box, text, confidence)

        Returns:
            Formatted text string with single newlines within paragraphs and double newlines between paragraphs.
        """
        if not results:
            return ""

        # --- Helper functions (re-introduced) ---
        def get_vertical_center(bbox):
            # Use min/max for robustness if box isn't perfectly rectangular
            min_y = min(p[1] for p in bbox)
            max_y = max(p[1] for p in bbox)
            return (min_y + max_y) / 2.0

        def get_height(bbox):
            min_y = min(p[1] for p in bbox)
            max_y = max(p[1] for p in bbox)
            return max_y - min_y
        # --- End Helper functions ---

        # Sort results primarily by top y-coordinate, secondarily by left x-coordinate
        results.sort(key=lambda item: (item[0][0][1], item[0][0][0]))

        # --- Line Reconstruction ---
        lines_data = []  # Stores lists of blocks for each detected line
        if not results: return "" # Should be caught above, but safety first

        current_line_blocks = [results[0]]

        for i in range(1, len(results)):
            prev_block = current_line_blocks[-1]
            curr_block = results[i]

            prev_center_y = get_vertical_center(prev_block[0])
            curr_center_y = get_vertical_center(curr_block[0])
            prev_height = get_height(prev_block[0])

            # Threshold for starting a new line (if vertical distance > ~60% of prev block height)
            # Add a small absolute minimum (e.g., 5 pixels)
            vertical_threshold = max(5, prev_height * 0.6)

            # Condition: Current block starts a new line if its center is significantly below the previous block's center
            if curr_center_y > (prev_center_y + vertical_threshold):
                lines_data.append(current_line_blocks) # Finalize previous line
                current_line_blocks = [curr_block]      # Start new line
            else:
                current_line_blocks.append(curr_block) # Add to current line

        # Add the last line
        if current_line_blocks:
            lines_data.append(current_line_blocks)
        # --- End Line Reconstruction ---

        # --- Calculate Line Geometry and Format Output ---
        lines_geometry = []
        for line_blocks in lines_data:
            if not line_blocks: continue
            # Sort blocks within the line horizontally before joining text
            line_blocks.sort(key=lambda block: block[0][0][0])
            line_text = " ".join([block[1] for block in line_blocks])

            # Calculate overall line bounding box properties
            min_y = min(block[0][0][1] for block in line_blocks) # Top-left Y of highest block
            max_y = max(block[0][2][1] for block in line_blocks) # Bottom-right Y of lowest block
            height = max_y - min_y

            lines_geometry.append({
                'text': line_text,
                'top': min_y,
                'bottom': max_y,
                'height': height
            })

        output_lines = []
        # Paragraph break threshold factor (e.g., gap > 0.7 * previous line height)
        paragraph_threshold_factor = 0.7

        for i, current_line_geom in enumerate(lines_geometry):
            line_text = current_line_geom['text']
            line_break = "\n" # Default break is a single newline

            # Check for paragraph break *before* this line (if not the first line)
            if i > 0:
                prev_line_geom = lines_geometry[i-1]
                vertical_gap = current_line_geom['top'] - prev_line_geom['bottom']
                # Use previous line height as reference, add minimum threshold (e.g., 5px)
                para_thresh = max(5, prev_line_geom['height'] * paragraph_threshold_factor)

                if vertical_gap > para_thresh:
                    line_break = "\n\n" # Use double newline for paragraph break

            # Append the break character (if not the first line) and the line text
            if i > 0:
                output_lines.append(line_break)
            output_lines.append(line_text)

        return "".join(output_lines).strip() # Join lines with calculated breaks

    def process_image(self, image: Image.Image) -> Tuple[List[str], str]:
        """Process a single image using EasyOCR.

        Returns:
            Tuple containing:
            - List with path to the processed image for display
            - Extracted text from the image (simplified format)
        """
        # Convert image to RGB if it's not already
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # EasyOCR works with NumPy arrays
        image_np = np.array(image)

        try:
            # Perform OCR
            results = self.reader.readtext(image_np)

            # Format results using the *simplified* function
            markdown_text = self._format_as_markdown(results)

            # Save the original image for display in the UI
            display_path = os.path.join(self.temp_dir, f"easyocr_image_{os.urandom(8).hex()}.png")
            image.save(display_path, format='PNG')

            return [display_path], markdown_text
        except Exception as e:
            logger.error(f"Error during EasyOCR processing: {e}")
            # Save image even on error for potential debugging or display
            display_path = os.path.join(self.temp_dir, f"easyocr_error_image_{os.urandom(8).hex()}.png")
            image.save(display_path, format='PNG')
            return [display_path], f"Error processing image with EasyOCR: {e}"


    def _pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """Convert PDF pages to PIL Images."""
        images = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap()
                # Convert PyMuPDF pixmap to PIL Image
                if pix.alpha:
                    img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                else:
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
            doc.close()
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            raise # Re-raise the exception to be caught in process_pdf
        return images

    def process_pdf(self, pdf_path: str) -> Tuple[List[str], str]:
        """Process a PDF document using EasyOCR."""
        try:
            images = self._pdf_to_images(pdf_path)
        except Exception as e:
            return [], f"Error converting PDF to images: {e}"

        image_paths = []
        all_text = []
        page_count = len(images) # Get page count

        for i, img in enumerate(images, 1):
            # Save each page image for potential display
            img_path = os.path.join(self.temp_dir, f"easyocr_page_{i}_{os.urandom(8).hex()}.png")
            try:
                # Ensure image is in RGB format before saving as PNG
                if img.mode != 'RGB':
                    img_display = img.convert('RGB')
                else:
                    img_display = img
                img_display.save(img_path, format='PNG')
                image_paths.append(img_path)
            except Exception as e:
                 logger.warning(f"Could not save image for page {i}: {e}")
                 # Add a placeholder or skip if saving fails
                 image_paths.append(None) # Or some indicator

            # Process image with OCR
            try:
                _, text = self.process_image(img) # Reuses the image processing method

                # Use the standardized marker function
                page_marker = format_page_marker(page_num=i, total_pages=page_count)
                # Append the extracted text for this page after the marker
                all_text.append(f"{page_marker}\n{text}") # Added newline after marker
            except Exception as e:
                # Use H4 format for error message page indicator
                page_marker = format_page_marker(page_num=i, total_pages=page_count)
                all_text.append(f"{page_marker}\nError processing page {i}: {e}") # Added newline after marker


        # Filter out None paths if any saving failed
        valid_image_paths = [p for p in image_paths if p is not None]

        # Combine text from all pages
        final_text = "\n\n".join(all_text) # Use double newline between pages

        return valid_image_paths, final_text # Return combined text 