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
        
        # Verify API key is set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
            
        # Only initialize client if we have a key
        try:
            # Store client for potential use later (e.g., fetching models in app.py)
            self.client = openai.OpenAI(api_key=api_key)
            # Test connection briefly - list models is a light way
            # self.client.models.list() # Optional: test connectivity here
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise ValueError(f"Failed to initialize OpenAI client: {str(e)}")
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string.
        
        Args:
            image: PIL Image object
            
        Returns:
            Base64 encoded string of the image
        """
        buffered = io.BytesIO()
        # Ensure image is PNG for consistency with base64 data URL
        save_format = "PNG"
        if image.format == "JPEG": # Keep JPEG if original was JPEG? Let's stick to PNG for OpenAI
            save_format = "PNG"

        # Handle potential transparency issues by converting to RGB before saving as PNG
        save_image = image
        if image.mode in ("RGBA", "P"):
             save_image = image.convert("RGB")

        save_image.save(buffered, format=save_format)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    def process_image(self, image: Image.Image, model_name: str = "gpt-4o") -> Tuple[List[str], str]:
        """Process a single image using OpenAI's Vision API.
        
        Args:
            image: PIL Image object to process
            model_name: The specific OpenAI model to use (e.g., "gpt-4o", "gpt-4-vision-preview")
            
        Returns:
            Tuple containing:
            - List with path to the processed image
            - Extracted text from the image
        """
        try:
            # Save a copy of the image for display
            image_path = os.path.join(self.temp_dir, f"openai_image_{os.urandom(8).hex()}.png")
            # Ensure image is saved in a compatible format (like PNG)
            save_image = image.convert("RGB") if image.mode != 'RGB' else image
            save_image.save(image_path, format="PNG")
            
            base64_image = self._image_to_base64(save_image)
            
            # Use the model_name parameter here
            logger.info(f"Using OpenAI model: {model_name} for image OCR")
            response = self.client.chat.completions.create(
                model=model_name, # Use the parameter
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
                max_tokens=4096 # Consider making this configurable if needed
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
            # Reraise the exception to be handled upstream
            raise e # Re-raise the original exception
    
    def process_pdf(self, pdf_path: str, model_name: str = "gpt-4o") -> Tuple[List[str], str]:
        """Process a PDF document using OpenAI's Vision API.
        
        Args:
            pdf_path: Path to the PDF file
            model_name: The specific OpenAI model to use
            
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
                # Increase resolution for better OCR quality if needed
                # pix = page.get_pixmap(dpi=300)
                pix = page.get_pixmap()
                
                # Save page as image
                image_path = os.path.join(self.temp_dir, f"page_{page_num}.png")
                pix.save(image_path)
                image_paths.append(image_path)
                
                # Process image with OpenAI using the provided model_name
                with Image.open(image_path) as img:
                     # Pass the model_name down
                    _, page_text = self.process_image(img, model_name=model_name)
                    # Handle potential None or empty page_text
                    if page_text:
                        all_text.append(f"## Page {page_num+1}\n\n{page_text}")
                    else:
                         all_text.append(f"## Page {page_num+1}\n\n[No text extracted]")
            
            doc.close() # Close the document
            return image_paths, "\n\n".join(all_text)
            
        except Exception as e:
            logger.error(f"OpenAI PDF processing failed: {str(e)}")
            # Reraise the exception
            raise e # Re-raise the original exception 