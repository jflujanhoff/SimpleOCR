from abc import ABC, abstractmethod
from typing import Tuple, List, Optional
from PIL import Image

class BaseOCR(ABC):
    """Base class for OCR models that defines the common interface."""
    
    @abstractmethod
    def process_image(self, image: Image.Image) -> str:
        """Process a single image and return the extracted text.
        
        Args:
            image: PIL Image object to process
            
        Returns:
            Extracted text from the image
        """
        pass
    
    @abstractmethod
    def process_pdf(self, pdf_path: str) -> Tuple[List[str], str]:
        """Process a PDF document and return the extracted text and image paths.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Tuple containing:
            - List of image paths
            - Extracted text from the PDF
        """
        pass 