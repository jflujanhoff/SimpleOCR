import os
import tempfile
import base64
from typing import Literal, Optional, Tuple, List
from PIL import Image
import io
from ocr_models import TesseractOCR, MistralOCR
import logging
import pillow_heif

# Register HEIF opener
pillow_heif.register_heif_opener()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentOCR:
    """A class for performing OCR on documents using different OCR engines."""
    
    def __init__(self):
        """Initialize the DocumentOCR class with necessary configurations."""
        # Create a temporary directory for storing images
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize OCR models
        self.tesseract = TesseractOCR(self.temp_dir)
        try:
            self.mistral = MistralOCR(self.temp_dir)
        except ValueError as e:
            logger.warning(f"Warning: {str(e)}")
            logger.warning("Mistral OCR will not be available. Only Tesseract OCR will work.")
            self.mistral = None
    
    def __del__(self):
        """Cleanup temporary directory when the object is destroyed."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
    
    def _process_pdf_document(self, file_content: bytes, file_name: str, ocr_engine: Literal["Tesseract", "Mistral"]) -> Tuple[str, List[str], str]:
        """Process a PDF document using the specified OCR engine."""
        # Create temporary PDF file
        tmp_path = os.path.join(self.temp_dir, f"temp_{os.urandom(8).hex()}.pdf")
        with open(tmp_path, 'wb') as f:
            f.write(file_content)
        
        try:
            # Process PDF based on selected engine
            if ocr_engine == "Tesseract":
                image_paths, result_text = self.tesseract.process_pdf(tmp_path)
            else:  # Mistral
                if self.mistral is None:
                    raise ValueError("Mistral OCR is not available")
                image_paths, result_text = self.mistral.process_pdf(tmp_path)
            
            return file_name, image_paths, result_text
            
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _process_image_document(self, file_content: bytes, file_name: str, ocr_engine: Literal["Tesseract", "Mistral"]) -> Tuple[str, List[str], str]:
        """Process an image document using the specified OCR engine."""
        try:
            # Validate file content
            if not file_content:
                raise ValueError("Empty file content")
            
            # Try to identify the image format
            try:
                image = Image.open(io.BytesIO(file_content))
                logger.info(f"Successfully opened image: {file_name}")
            except Exception as e:
                logger.error(f"Failed to open image {file_name}: {str(e)}")
                raise ValueError(f"Invalid image format: {str(e)}")
            
            # Save image to temporary file for display
            image_path = os.path.join(self.temp_dir, f"image_{os.urandom(8).hex()}.png")
            try:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image.save(image_path, format='PNG')
                logger.info(f"Successfully saved image to: {image_path}")
            except Exception as e:
                logger.error(f"Failed to save image {file_name}: {str(e)}")
                raise ValueError(f"Failed to process image: {str(e)}")
            
            try:
                # Process image based on selected engine
                if ocr_engine == "Tesseract":
                    result_text = self.tesseract.process_image(image)
                else:  # Mistral
                    if self.mistral is None:
                        raise ValueError("Mistral OCR is not available")
                    result_text = self.mistral.process_image(image)
                
                if not result_text:
                    logger.warning(f"No text could be extracted from image: {file_name}")
                
                return file_name, [image_path], result_text
                
            except Exception as e:
                logger.error(f"OCR processing failed for {file_name}: {str(e)}")
                raise ValueError(f"OCR processing failed: {str(e)}")
            
        except Exception as e:
            try:
                if 'image_path' in locals():
                    os.unlink(image_path)
            except:
                pass
            raise e
    
    def process_document(self, file, ocr_engine: Literal["Tesseract", "Mistral"]) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Process a document using the specified OCR engine."""
        try:
            # For Gradio file objects, we need to access the file path directly
            file_path = file.name
            file_name = os.path.basename(file_path)
            logger.info(f"Processing document: {file_name}")
            
            # Read the file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Determine file type and process accordingly
            if file_name.lower().endswith('.pdf'):
                return self._process_pdf_document(file_content, file_name, ocr_engine)
            else:
                return self._process_image_document(file_content, file_name, ocr_engine)
                
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return None, None, None
    
    def download_ocr_result(self, ocr_result: str, file_format: str) -> Tuple[str, List[Tuple[str, str]]]:
        """Generate a downloadable file from the OCR result."""
        # Extract and replace images with placeholders
        import re
        image_counter = 0
        extracted_images = []
        
        # Function to replace image with placeholder
        def replace_image(match):
            nonlocal image_counter
            image_counter += 1
            placeholder = f"img-{image_counter}.jpeg"
            extracted_images.append((placeholder, match.group(0)))
            return placeholder
        
        # Replace markdown image syntax ![alt](url)
        text_with_placeholders = re.sub(r'!\[.*?\]\((data:image/[^;]+;base64,[^\s]+)\)', replace_image, ocr_result)
        # Clean up any extra newlines that might have been left
        text_with_placeholders = re.sub(r'\n\s*\n', '\n\n', text_with_placeholders).strip()
        
        # Create a temporary file with the appropriate extension
        temp_path = os.path.join(self.temp_dir, f"ocr_result_{os.urandom(8).hex()}.{file_format}")
        
        # Write the result to the file
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(text_with_placeholders)
            
        return temp_path, extracted_images 