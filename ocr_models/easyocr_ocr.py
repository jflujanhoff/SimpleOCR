import easyocr
import numpy as np
from PIL import Image
import fitz  # PyMuPDF
import tempfile
import os
import re
from typing import Tuple, List
from .base import BaseOCR
import logging

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

    def _format_as_markdown(self, results: List[Tuple[List[List[int]], str, float]]) -> str:
        """Format EasyOCR results as markdown.

        Args:
            results: List of tuples from EasyOCR: (bounding_box, text, confidence)

        Returns:
            Formatted markdown text
        """
        if not results:
            return ""

        # Extract text from results
        text_lines = [item[1] for item in results]
        
        # Basic joining, similar structure to Tesseract formatting could be applied
        # For simplicity, just join lines for now.
        full_text = "\n".join(text_lines).strip()
        
        # Clean the text
        full_text = full_text.strip()
        
        # Split text into lines for potential further formatting
        lines = full_text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            # Skip empty lines
            if not line.strip():
                formatted_lines.append("")
                continue
                
            # Example: Make potential headings bold (simple heuristic)
            if len(line.strip()) < 60 and line.strip().isupper():
                 formatted_lines.append(f"**{line.strip()}**")
                 continue

            # Regular text
            formatted_lines.append(line)
        
        # Join lines back together
        return "\n".join(formatted_lines)


    def process_image(self, image: Image.Image) -> Tuple[List[str], str]:
        """Process a single image using EasyOCR.

        Returns:
            Tuple containing:
            - List with path to the processed image for display
            - Extracted text from the image as markdown
        """
        # Convert image to RGB if it's not already
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # EasyOCR works with NumPy arrays
        image_np = np.array(image)

        try:
            # Perform OCR
            results = self.reader.readtext(image_np)
            
            # Format results as markdown
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
                all_text.append(f"## Page {i}\n\n{text}")
            except Exception as e:
                all_text.append(f"## Page {i}\n\nError processing page {i}: {e}")


        # Filter out None paths if any saving failed
        valid_image_paths = [p for p in image_paths if p is not None]
        
        return valid_image_paths, "\n\n".join(all_text) 