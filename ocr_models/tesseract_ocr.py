import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import tempfile
import os
from typing import Tuple, List
from .base import BaseOCR

class TesseractOCR(BaseOCR):
    """Tesseract OCR implementation."""
    
    def __init__(self, temp_dir: str):
        """Initialize Tesseract OCR.
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = temp_dir
    
    def process_image(self, image: Image.Image) -> str:
        """Process a single image using Tesseract OCR."""
        # Convert image to RGB if it's not already
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Save the image temporarily in a format Tesseract can handle
        temp_path = os.path.join(self.temp_dir, f"temp_{os.urandom(8).hex()}.png")
        image.save(temp_path, format='PNG')
        
        try:
            # Process the saved PNG file
            text = pytesseract.image_to_string(temp_path)
            return text
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
        
        for i, img in enumerate(images, 1):
            # Save image for display
            img_path = os.path.join(self.temp_dir, f"page_{i}_{os.urandom(8).hex()}.png")
            img.save(img_path, format='PNG')
            image_paths.append(img_path)
            
            # Process image with OCR
            text = self.process_image(img)
            all_text.append(f"Page {i}:\n{text}")
        
        return image_paths, "\n\n".join(all_text) 