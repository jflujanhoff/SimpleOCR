import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import tempfile
import os
import re
from typing import Tuple, List
from .base import BaseOCR
from .utils import format_page_marker

class TesseractOCR(BaseOCR):
    """Tesseract OCR implementation."""
    
    def __init__(self, temp_dir: str):
        """Initialize Tesseract OCR.
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = temp_dir
    
    def _format_as_markdown(self, text: str) -> str:
        """Format plain text as markdown.
        
        Args:
            text: Plain text from Tesseract OCR
            
        Returns:
            Formatted markdown text
        """
        if not text:
            return ""
            
        # Clean the text
        text = text.strip()
        
        # Split text into lines
        lines = text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            # Skip empty lines
            if not line.strip():
                formatted_lines.append("")
                continue
                
            # Check if line might be a heading (short line, less than 60 chars)
            if len(line.strip()) < 60 and i > 0 and not lines[i-1].strip():
                # Check if line is all caps or starts with a number
                if line.strip().isupper() or re.match(r'^\d+\.', line.strip()):
                    formatted_lines.append(f"### {line.strip()}")
                    continue
            
            # Regular text
            formatted_lines.append(line)
        
        # Join lines back together
        return "\n".join(formatted_lines)
    
    def process_image(self, image: Image.Image) -> Tuple[List[str], str]:
        """Process a single image using Tesseract OCR.
        
        Returns:
            Tuple containing:
            - List with path to the processed image
            - Extracted text from the image as markdown
        """
        # Convert image to RGB if it's not already
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Save the image temporarily in a format Tesseract can handle
        temp_path = os.path.join(self.temp_dir, f"temp_{os.urandom(8).hex()}.png")
        image.save(temp_path, format='PNG')
        
        try:
            # Process the saved PNG file
            text = pytesseract.image_to_string(temp_path)
            
            # Format as markdown
            markdown_text = self._format_as_markdown(text)
            
            # Create a display image path
            display_path = os.path.join(self.temp_dir, f"image_{os.urandom(8).hex()}.png")
            image.save(display_path, format='PNG')
            
            return [display_path], markdown_text
        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def _pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """Convert PDF pages to images."""
        doc = fitz.open(pdf_path)
        images = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        return images
    
    def process_pdf(self, pdf_path: str) -> Tuple[List[str], str]:
        """Process a PDF document using Tesseract OCR."""
        images = self._pdf_to_images(pdf_path)
        image_paths = []
        all_text = []
        page_count = len(images) # Get page count
        
        for i, img in enumerate(images, 1):
            # Save image for display
            img_path = os.path.join(self.temp_dir, f"page_{i}_{os.urandom(8).hex()}.png")
            img.save(img_path, format='PNG')
            image_paths.append(img_path)
            
            # Process image with OCR
            _, text = self.process_image(img)
            # Use H4 format for page indicator
            # No longer needed as process_image doesn't add page count
            text_lines = text.split('\n')
            # if len(text_lines) > 2 and text_lines[0].startswith("#### Page Count:"):
            #     text = '\n'.join(text_lines[2:])
            # Use the standardized marker function
            page_marker = format_page_marker(page_num=i, total_pages=page_count)
            all_text.append(f"{page_marker}{text}")
        
        # Combine text without the overall page count header
        final_text = "\n\n".join(all_text)
        # page_count_header = f"#### Page Count: {page_count}\n\n"
        # final_output = page_count_header + final_text
        
        return image_paths, final_text # Return combined text 