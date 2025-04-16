import os
from typing import Tuple, List
from PIL import Image
from mistralai import Mistral
from mistralai.models import OCRResponse
from .base import BaseOCR
from dotenv import load_dotenv

load_dotenv()

class MistralOCR(BaseOCR):
    """Mistral OCR implementation."""
    
    def __init__(self, temp_dir: str):
        """Initialize Mistral OCR.
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = temp_dir
        self.mistral_api_key = os.getenv('MISTRAL_API_KEY')
        if not self.mistral_api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is not set")
        
        self.mistral_client = Mistral(api_key=self.mistral_api_key)
    
    def _mistral_ocr(self, file_path: str, is_image: bool = False) -> OCRResponse:
        """Perform OCR using Mistral API."""
        try:
            # Upload the file to Mistral
            with open(file_path, "rb") as f:
                uploaded_file = self.mistral_client.files.upload(
                    file={
                        "file_name": os.path.basename(file_path),
                        "content": f.read(),
                    },
                    purpose="ocr"
                )
            
            # Get signed URL for the uploaded file
            signed_url = self.mistral_client.files.get_signed_url(file_id=uploaded_file.id)
            
            # Process the document using OCR
            response = self.mistral_client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "image_url" if is_image else "document_url",
                    "image_url" if is_image else "document_url": signed_url.url,
                },
                include_image_base64=True
            )
            
            return response
            
        except Exception as e:
            print(f"Error in Mistral OCR processing: {str(e)}")
            raise
    
    def process_image(self, image: Image.Image) -> str:
        """Process a single image using Mistral OCR."""
        # Save the image temporarily
        temp_path = os.path.join(self.temp_dir, f"temp_{os.urandom(8).hex()}.png")
        image.save(temp_path, format='PNG')
        
        try:
            result = self._mistral_ocr(temp_path, is_image=True)
            if not result.pages:
                return "No text could be extracted from the image."
            
            # Combine text from all pages
            return "\n\n".join(page.markdown for page in result.pages)
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def process_pdf(self, pdf_path: str) -> Tuple[List[str], str]:
        """Process a PDF document using Mistral OCR."""
        try:
            result = self._mistral_ocr(pdf_path)
            if not result.pages:
                return [], "No text could be extracted from the document."
            
            # Extract images and save them
            image_paths = []
            for i, page in enumerate(result.pages, 1):
                for img in page.images:
                    if img.image_base64:
                        # Save the image
                        img_path = os.path.join(self.temp_dir, f"page_{i}_{os.urandom(8).hex()}.png")
                        with open(img_path, 'wb') as f:
                            f.write(img.image_base64)
                        image_paths.append(img_path)
            
            # Combine text from all pages
            text = "\n\n".join(page.markdown for page in result.pages)
            return image_paths, text
            
        except Exception as e:
            print(f"Error processing PDF with Mistral OCR: {str(e)}")
            return [], f"Error processing PDF: {str(e)}" 