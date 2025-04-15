import pytesseract
from PIL import Image
import pillow_heif
import io
import fitz  # PyMuPDF
import tempfile
import os
import base64
from typing import Literal, Dict, Any, Optional, Tuple, List
from mistralai import Mistral
from mistralai.models import OCRResponse
from dotenv import load_dotenv

# Register HEIF opener
pillow_heif.register_heif_opener()

class DocumentOCR:
    """A class for performing OCR on documents using either Tesseract or Mistral."""
    
    def __init__(self):
        """Initialize the DocumentOCR class with necessary clients and configurations."""
        self.ocr_result = ""
        # Load environment variables
        load_dotenv()
        
        # Get API key from environment variable
        self.mistral_api_key = os.getenv('MISTRAL_API_KEY')
        if not self.mistral_api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is not set. Please set it before running the application.")
        
        # Initialize Mistral client
        try:
            self.mistral_client = Mistral(api_key=self.mistral_api_key)
        except Exception as e:
            raise ValueError(f"Failed to initialize Mistral client: {str(e)}")
        
        # Create a temporary directory for storing images
        self.temp_dir = tempfile.mkdtemp()
    
    def __del__(self):
        """Cleanup temporary directory when the object is destroyed."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
    
    def _mistral_ocr(self, file_path: str, is_image: bool = False) -> OCRResponse:
        """Perform OCR using Mistral API"""
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
    
    def _pdf_to_images(self, pdf_path: str) -> list[Image.Image]:
        """Convert PDF pages to images"""
        doc = fitz.open(pdf_path)
        images = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        return images
    
    def _process_pdf_with_tesseract(self, pdf_path: str, image_paths: List[str]) -> str:
        """Process PDF using Tesseract OCR"""
        images = self._pdf_to_images(pdf_path)
        all_text = []
        for i, img in enumerate(images, 1):
            text = pytesseract.image_to_string(img)
            all_text.append(f"Page {i}:\n{text}")
        return "\n\n".join(all_text)
    
    def _process_image_with_tesseract(self, image: Image.Image, image_path: str) -> str:
        """Process image using Tesseract OCR"""
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
    
    def _replace_images_in_markdown_with_mistral(self, markdown_str: str, images_dict: dict) -> str:
        """
        Replace image placeholders in markdown with base64-encoded images.

        Args:
            markdown_str: Markdown text containing image placeholders
            images_dict: Dictionary mapping image IDs to base64 strings

        Returns:
            Markdown text with images replaced by base64 data
        """
        print(markdown_str)
        for img_name, base64_str in images_dict.items():
            markdown_str = markdown_str.replace(
                f"![{img_name}]({img_name})", f"![{img_name}]({base64_str})"
            )
        return markdown_str
    
    def _get_combined_markdown(self, ocr_response: OCRResponse) -> str:
        """
        Combine OCR text and images into a single markdown document.

        Args:
            ocr_response: Response from OCR processing containing text and images

        Returns:
            Combined markdown string with embedded images
        """
        markdowns: list[str] = []
        # Extract images from page
        for page in ocr_response.pages:
            image_data = {}
            for img in page.images:
                image_data[img.id] = img.image_base64
            # Replace image placeholders with actual images
            markdowns.append(self._replace_images_in_markdown_with_mistral(page.markdown, image_data))

        return "\n\n".join(markdowns)
    
    def _process_with_mistral(self, file_path: str, is_image: bool = False) -> str:
        """Process file using Mistral OCR"""
        try:
            result = self._mistral_ocr(file_path, is_image)
            if not result.pages:
                return "No text could be extracted from the document."
            
            return self._get_combined_markdown(result)
        except Exception as e:
            return f"Error processing with Mistral OCR: {str(e)}"
    
    def _create_temp_file(self, content: bytes, suffix: str) -> str:
        """Create a temporary file and return its path"""
        # Create file in our managed temp directory
        temp_path = os.path.join(self.temp_dir, f"temp_{os.urandom(8).hex()}{suffix}")
        with open(temp_path, 'wb') as f:
            f.write(content)
        return temp_path
    
    def _process_pdf_document(self, file_content: bytes, file_name: str, ocr_engine: Literal["Tesseract", "Mistral"]) -> Tuple[str, List[str], str]:
        """Process a PDF document using the specified OCR engine.
        
        Args:
            file_content: The binary content of the PDF file
            file_name: The original name of the file
            ocr_engine: The OCR engine to use ("Tesseract" or "Mistral")
            
        Returns:
            Tuple containing (original file name, list of image paths, OCR result text)
        """
        # Create temporary PDF file
        tmp_path = self._create_temp_file(file_content, '.pdf')
        image_paths = []
        
        try:
            # Convert PDF to images for display
            images = self._pdf_to_images(tmp_path)
            
            # Save images to temporary files for display
            for i, img in enumerate(images):
                # Create a temporary file with .png extension in our temp directory
                img_path = os.path.join(self.temp_dir, f"page_{i}_{os.urandom(8).hex()}.png")
                # Save the image properly using PIL
                img.save(img_path, format='PNG')
                image_paths.append(img_path)
            
            # Perform OCR based on selected engine
            if ocr_engine == "Tesseract":
                result_text = self._process_pdf_with_tesseract(tmp_path, image_paths)
            else:  # Mistral
                result_text = self._process_with_mistral(tmp_path)
            
            return file_name, image_paths, result_text
            
        except Exception as e:
            # Clean up on error
            for img_path in image_paths:
                try:
                    os.unlink(img_path)
                except:
                    pass
            raise e

    def _process_image_document(self, file_content: bytes, file_name: str, ocr_engine: Literal["Tesseract", "Mistral"]) -> Tuple[str, List[str], str]:
        """Process an image document using the specified OCR engine.
        
        Args:
            file_content: The binary content of the image file
            file_name: The original name of the file
            ocr_engine: The OCR engine to use ("Tesseract" or "Mistral")
            
        Returns:
            Tuple containing (original file name, list of image paths, OCR result text)
        """
        image = Image.open(io.BytesIO(file_content))
        # Create temporary image file with original extension
        original_ext = os.path.splitext(file_name)[1].lower()
        tmp_path = self._create_temp_file(file_content, original_ext)
        
        try:
            # Save image to temporary file for display in our temp directory
            image_path = os.path.join(self.temp_dir, f"image_{os.urandom(8).hex()}.png")
            # Convert to RGB if needed and save as PNG
            if image.mode != 'RGB':
                image = image.convert('RGB')
            image.save(image_path, format='PNG')
            
            # Perform OCR based on selected engine
            if ocr_engine == "Tesseract":
                result_text = self._process_image_with_tesseract(image, image_path)
            else:  # Mistral
                result_text = self._process_with_mistral(tmp_path, is_image=True)
            
            return file_name, [image_path], result_text
            
        except Exception as e:
            # Clean up on error
            try:
                os.unlink(image_path)
            except:
                pass
            raise e
    
    def process_document(self, file, ocr_engine: Literal["Tesseract", "Mistral"]) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Process a document using the specified OCR engine.
        
        Args:
            file: The file to process (Gradio file object)
            ocr_engine: The OCR engine to use ("Tesseract" or "Mistral")
            
        Returns:
            Tuple containing (original file name, list of image paths, OCR result text)
        """
        try:
            # For Gradio file objects, we need to access the file path directly
            file_path = file.name
            file_name = os.path.basename(file_path)
            
            # Read the file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Determine file type and process accordingly
            if file_name.lower().endswith('.pdf'):
                return self._process_pdf_document(file_content, file_name, ocr_engine)
            else:
                return self._process_image_document(file_content, file_name, ocr_engine)
                
        except Exception as e:
            print(f"Error processing document: {str(e)}")
            return None, None, None
    
    def download_ocr_result(self, ocr_result: str, file_format: str) -> str:
        """Generate a downloadable file from the OCR result.
        
        Args:
            ocr_result: The OCR result text
            file_format: The desired output format ("txt" or "md")
            
        Returns:
            Path to the generated file
        """
        # Create a temporary file with the appropriate extension
        temp_path = os.path.join(self.temp_dir, f"ocr_result_{os.urandom(8).hex()}.{file_format}")
        
        # Write the result to the file
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(ocr_result)
            
        return temp_path 