import os
import base64
from typing import Tuple, List
from PIL import Image
import io
import openai
from .base import BaseOCR
import logging

logger = logging.getLogger(__name__)

class OpenAICR(BaseOCR):
    """OCR implementation using OpenAI's Vision API."""
    
    def __init__(self, temp_dir: str):
        """Initialize the OpenAI OCR model.
        
        Args:
            temp_dir: Directory for temporary file storage
        """
        self.temp_dir = temp_dir
        self.client = openai.OpenAI()
        
        # Verify API key is set
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string.
        
        Args:
            image: PIL Image object
            
        Returns:
            Base64 encoded string of the image
        """
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    def process_image(self, image: Image.Image) -> Tuple[List[str], str]:
        """Process a single image using OpenAI's Vision API.
        
        Args:
            image: PIL Image object to process
            
        Returns:
            Tuple containing:
            - List with path to the processed image
            - Extracted text from the image
        """
        try:
            # Save a copy of the image for display
            image_path = os.path.join(self.temp_dir, f"openai_image_{os.urandom(8).hex()}.png")
            image.save(image_path, format="PNG")
            
            # Convert image to base64
            base64_image = self._image_to_base64(image)
            
            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                # model="gpt-4o-mini",
                model="gpt-4.1",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract all text content from this image. Format your response as clean, properly formatted markdown. Preserve the layout structure, including proper headings, lists, tables, and code blocks if present. Do not include any explanatory text - just output the extracted content."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096
            )
            
            # Get the response content and ensure it's properly formatted
            result = response.choices[0].message.content
            if result:
                # Clean up the result to ensure proper markdown formatting
                # Remove backtick code blocks that might be around markdown
                result = result.replace("```markdown", "").replace("```", "")
                
                # Ensure headings have space after #
                import re
                result = re.sub(r'(^|\n)#([^#\s])', r'\1# \2', result)
                
            return [image_path], result
            
        except Exception as e:
            logger.error(f"OpenAI OCR processing failed: {str(e)}")
            raise
    
    def process_pdf(self, pdf_path: str) -> Tuple[List[str], str]:
        """Process a PDF document using OpenAI's Vision API.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Tuple containing:
            - List of image paths
            - Extracted text from the PDF
        """
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            image_paths = []
            all_text = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap()
                
                # Save page as image
                image_path = os.path.join(self.temp_dir, f"page_{page_num}.png")
                pix.save(image_path)
                image_paths.append(image_path)
                
                # Process image with OpenAI
                with Image.open(image_path) as img:
                    _, page_text = self.process_image(img)
                    all_text.append(f"## Page {page_num+1}\n\n{page_text}")
            
            return image_paths, "\n\n".join(all_text)
            
        except Exception as e:
            logger.error(f"OpenAI PDF processing failed: {str(e)}")
            raise 