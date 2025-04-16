import os
import re
from typing import Tuple, List, Dict, Union
from PIL import Image
from mistralai import Mistral
from mistralai.models import OCRResponse
from .base import BaseOCR
from dotenv import load_dotenv
import fitz  # PyMuPDF
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class MistralOCR(BaseOCR):
    """Mistral OCR implementation that provides markdown output."""
    
    def __init__(self, temp_dir: str, debug_mode: bool = False):
        """Initialize Mistral OCR.
        
        Args:
            temp_dir: Directory for temporary files
            debug_mode: Whether to enable debug mode for verbose logging
        """
        self.temp_dir = temp_dir
        self.debug_mode = debug_mode
        
        # Get API key and validate
        self.mistral_api_key = os.getenv('MISTRAL_API_KEY')
        if not self.mistral_api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is not set")
        
        # Only initialize client if we have a key
        try:
            self.mistral_client = Mistral(api_key=self.mistral_api_key)
            self._debug_log("Mistral client initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize Mistral client: {str(e)}"
            logger.error(error_msg)
            self._debug_log(error_msg)
            raise ValueError(error_msg)
    
    def _debug_log(self, message: str):
        """Log a debug message if debug mode is enabled."""
        if self.debug_mode:
            print(f"[DEBUG] {message}")
            
    def _clean_markdown(self, markdown_text: str) -> str:
        """Clean and format markdown text to ensure proper rendering.
        
        Args:
            markdown_text: Raw markdown text to clean
            
        Returns:
            Cleaned markdown text
        """
        if not markdown_text:
            return markdown_text
            
        # Remove any markdown code blocks that might surround the content
        markdown_text = re.sub(r'```markdown\s*', '', markdown_text)
        markdown_text = re.sub(r'```\s*$', '', markdown_text)
        
        # Ensure headings have space after #
        markdown_text = re.sub(r'(^|\n)#([^#\s])', r'\1# \2', markdown_text)
        
        # Ensure lists have space after bullet
        markdown_text = re.sub(r'(^|\n)-([^\s])', r'\1- \2', markdown_text)
        
        # Remove consecutive newlines (more than 2)
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
        
        return markdown_text.strip()

    def _mistral_ocr(self, file_path: str, is_image: bool = False) -> OCRResponse:
        """Perform OCR using Mistral API."""
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File {file_path} does not exist")
                
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise ValueError(f"File {file_path} is empty")
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                raise ValueError(f"File is too large ({file_size / (1024 * 1024):.2f} MB). Maximum size is 50MB")
            
            self._debug_log(f"Processing file: {file_path} (size: {file_size / 1024:.2f} KB)")
            
            # Upload the file to Mistral
            with open(file_path, "rb") as f:
                file_content = f.read()
                if isinstance(file_content, str):
                    file_content = file_content.encode('utf-8')
                
                try:
                    self._debug_log("Uploading file to Mistral API...")
                    uploaded_file = self.mistral_client.files.upload(
                        file={
                            "file_name": os.path.basename(file_path),
                            "content": file_content,
                        },
                        purpose="ocr"
                    )
                    self._debug_log(f"File uploaded successfully. File ID: {uploaded_file.id}")
                except Exception as e:
                    self._debug_log(f"File upload failed: {str(e)}")
                    raise ValueError(f"Failed to upload file to Mistral API: {str(e)}")
            
            # Get signed URL for the uploaded file
            try:
                self._debug_log("Getting signed URL...")
                signed_url = self.mistral_client.files.get_signed_url(file_id=uploaded_file.id)
                self._debug_log("Signed URL obtained successfully")
            except Exception as e:
                self._debug_log(f"Failed to get signed URL: {str(e)}")
                raise ValueError(f"Failed to get signed URL for uploaded file: {str(e)}")
            
            # Process the document using OCR
            try:
                self._debug_log("Sending OCR processing request...")
                document_type = "image_url" if is_image else "document_url"
                self._debug_log(f"Document type: {document_type}")
                
                response = self.mistral_client.ocr.process(
                    model="mistral-ocr-latest",
                    document={
                        "type": document_type,
                        document_type: signed_url.url,
                    },
                    include_image_base64=False  # No need for image data
                )
                
                self._debug_log("OCR processing completed")
                
                # Validate the response
                if not response:
                    self._debug_log("Response is None or empty")
                    raise ValueError("OCR processing returned empty results")
                
                if not hasattr(response, 'pages'):
                    self._debug_log(f"Response has no 'pages' attribute: {response}")
                    raise ValueError("OCR processing returned invalid results with no pages attribute")
                    
                if not response.pages:
                    self._debug_log("Response has empty pages list")
                    raise ValueError("OCR processing returned empty pages list")
                    
                return response
            except Exception as e:
                self._debug_log(f"OCR processing failed: {str(e)}")
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    self._debug_log(f"Error response: {e.response.text}")
                raise ValueError(f"OCR processing failed: {str(e)}")
            
        except Exception as e:
            print(f"Error in Mistral OCR processing: {str(e)}")
            raise
    
    def process_image(self, image: Image.Image) -> Tuple[List[str], str]:
        """Process a single image using Mistral OCR.
        
        Returns:
            Tuple containing:
            - List of image paths (empty for Mistral OCR)
            - Extracted text in markdown format
        """
        # Save the image temporarily
        temp_path = os.path.join(self.temp_dir, f"temp_{os.urandom(8).hex()}.png")
        image.save(temp_path, format='PNG')
        
        try:
            try:
                result = self._mistral_ocr(temp_path, is_image=True)
            except ValueError as e:
                return [], f"OCR processing error: {str(e)}"
            except Exception as e:
                return [], f"Unexpected error during OCR processing: {str(e)}"
                
            if not result.pages:
                return [], "No text could be extracted from the image. The OCR engine didn't recognize any content."
            
            markdown_parts = []
            
            # Process each page
            for page in result.pages:
                # Clean the markdown before adding it
                cleaned_markdown = self._clean_markdown(page.markdown)
                markdown_parts.append(cleaned_markdown)
            
            final_markdown = "\n\n".join(markdown_parts)
            if not final_markdown.strip():
                return [], "The document was processed, but no readable text content was found."
                
            return [], final_markdown
            
        finally:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                print(f"Warning: Failed to delete temporary file {temp_path}: {str(e)}")
    
    def process_pdf(self, pdf_path: str) -> Tuple[List[str], str]:
        """Process a PDF document using Mistral OCR.
        
        Returns:
            Tuple containing:
            - List of image paths (empty for Mistral OCR)
            - Extracted text in markdown format
        """
        try:
            self._debug_log(f"Starting PDF processing: {pdf_path}")
            
            # Validate PDF file
            if not os.path.exists(pdf_path):
                self._debug_log(f"PDF file does not exist: {pdf_path}")
                return [], f"Error: PDF file '{pdf_path}' does not exist"
                
            # Check if file is a valid PDF
            try:
                self._debug_log("Validating PDF file...")
                doc = fitz.open(pdf_path)
                if not doc:
                    self._debug_log("Invalid PDF file - could not be opened")
                    return [], "Error: Invalid or corrupted PDF file"
                    
                page_count = len(doc)
                self._debug_log(f"PDF has {page_count} pages")
                
                if page_count == 0:
                    self._debug_log("PDF has no pages")
                    return [], "Error: PDF file contains no pages"
                if page_count > 1000:
                    self._debug_log(f"PDF has too many pages: {page_count}")
                    return [], f"Error: PDF file contains {page_count} pages, which exceeds the 1000 page limit"
                doc.close()
                self._debug_log("PDF validation successful")
            except Exception as e:
                self._debug_log(f"PDF validation failed: {str(e)}")
                return [], f"Error validating PDF file: {str(e)}"
            
            # Process with Mistral OCR
            try:
                self._debug_log("Sending PDF to Mistral OCR...")
                result = self._mistral_ocr(pdf_path)
                self._debug_log("Mistral OCR processing completed")
            except ValueError as e:
                self._debug_log(f"OCR processing error: {str(e)}")
                return [], f"OCR processing error: {str(e)}"
            except Exception as e:
                self._debug_log(f"Unexpected OCR processing error: {str(e)}")
                return [], f"Unexpected error during OCR processing: {str(e)}"
                
            if not result.pages:
                self._debug_log("No pages in OCR result")
                return [], "No text could be extracted from the document. The OCR engine didn't recognize any content."
            
            markdown_parts = []
            
            # Format each page's markdown content
            for i, page in enumerate(result.pages, 1):
                # Clean the markdown before adding it
                cleaned_markdown = self._clean_markdown(page.markdown)
                markdown_parts.append(f"## Page {i}\n\n{cleaned_markdown}")
            
            # Combine all pages with proper markdown formatting
            final_markdown = "\n\n".join(markdown_parts)
            if not final_markdown.strip():
                return [], "The document was processed, but no readable text content was found."
                
            return [], final_markdown
            
        except Exception as e:
            error_message = str(e)
            print(f"Error processing PDF with Mistral OCR: {error_message}")
            return [], f"Error processing PDF: {error_message}" 