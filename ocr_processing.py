import os
import tempfile
import base64
from typing import Literal, Optional, Tuple, List
from PIL import Image
import io
from ocr_models import TesseractOCR, MistralOCR, OpenAICR, EasyOCROCR
import logging
import pillow_heif
import openai # Need openai to handle potential exceptions during model listing
from pathlib import Path
import secrets
try:
    from docx import Document
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False
    # logger.warning("python-docx not installed. .doc/.docx file creation will be disabled.")
    # Note: Logger might not be initialized here yet.

# Register HEIF opener
pillow_heif.register_heif_opener()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Update Literal type hint to include EasyOCR
OCR_ENGINE_TYPE = Literal["Tesseract", "Mistral", "OpenAI", "EasyOCR"]

class DocumentOCR:
    """A class for performing OCR on documents using different OCR engines."""
    
    def __init__(self):
        """Initialize the DocumentOCR class with base configurations and non-API engines."""
        # Create a temporary directory for storing images
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {self.temp_dir}")

        # Initialize attributes
        self.tesseract = None
        self.mistral = None
        self.openai = None
        self.available_openai_models: List[str] = []
        self.easyocr = None
        self.output_dir = "output_files"
        os.makedirs(self.output_dir, exist_ok=True)

        # Add logger initialization confirmation for python-docx
        if not PYTHON_DOCX_AVAILABLE:
             logger.warning("python-docx not installed. .doc file creation will be disabled.")

        # Always initialize Tesseract (assuming it doesn't fail catastrophically)
        try:
            self.tesseract = TesseractOCR(self.temp_dir)
            logger.info("Tesseract initialized successfully.")
        except Exception as e:
             logger.error(f"CRITICAL: Failed to initialize Tesseract: {e}", exc_info=True)
             # Optionally raise an error or handle the fact that Tesseract is core

        # Initialize EasyOCR (doesn't require API keys)
        self._initialize_easyocr()

        # Initialize API-dependent engines (will check env vars set during this init)
        self.reinitialize_api_engines()

    def _initialize_easyocr(self):
        """Initializes the EasyOCR engine."""
        try:
            # You might configure languages here if needed, e.g., languages=['en', 'es']
            self.easyocr = EasyOCROCR(self.temp_dir)
            logger.info("EasyOCR initialized successfully")
        except ImportError:
            logger.warning("EasyOCR library not found. Please install it (`pip install easyocr`). EasyOCR will not be available.")
            self.easyocr = None
        except Exception as e: # Catching other potential exceptions
            logger.warning(f"Warning: Failed to initialize EasyOCR: {str(e)}", exc_info=True)
            logger.warning("EasyOCR will not be available.")
            self.easyocr = None

    def _initialize_mistral(self):
        """Initializes the Mistral OCR engine if the API key is available."""
        mistral_api_key = os.getenv('MISTRAL_API_KEY')
        if mistral_api_key:
            try:
                # Pass key explicitly or ensure MistralOCR reads it from env
                self.mistral = MistralOCR(self.temp_dir) # Assumes MistralOCR uses os.getenv internally if no key passed
                logger.info("Mistral OCR initialized successfully")
            except ImportError:
                 logger.warning("MistralAI library not found. Please install it (`pip install mistralai`). Mistral OCR will not be available.")
                 self.mistral = None
            except ValueError as e: # Catch specific client init errors (like bad key format?)
                logger.warning(f"Mistral OCR Initialization Warning: {str(e)}. Engine will not be available.")
                self.mistral = None
            except Exception as e: # Catch other potential errors (network, etc.)
                logger.error(f"Unexpected error initializing Mistral OCR: {str(e)}", exc_info=True)
                self.mistral = None
        else:
            logger.info("Mistral OCR not initialized - no API key provided in environment")
            self.mistral = None # Ensure it's None if no key

    def _initialize_openai(self):
        """Initializes the OpenAI OCR engine if the API key is available and fetches models."""
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            try:
                self.openai = OpenAICR(self.temp_dir) # Assumes OpenAICR uses os.getenv internally if no key passed
                logger.info("OpenAI OCR initialized successfully")
                # Fetch available vision models using the initialized client
                try:
                    models = self.openai.client.models.list()
                    # Filter for vision-capable models (simple check)
                    self.available_openai_models = sorted([
                        m.id for m in models.data
                        if 'gpt-4' in m.id or 'vision' in m.id or 'o' in m.id # Added 'o' for gpt-4o
                    ])
                    # Ensure a default is present if filtering is too aggressive or list is empty
                    if not self.available_openai_models:
                         self.available_openai_models = ['gpt-4o'] # Fallback default
                    logger.info(f"Available OpenAI vision models: {self.available_openai_models}")
                except openai.AuthenticationError:
                     logger.error("OpenAI Authentication Error: Invalid API key. OpenAI OCR will not be available.")
                     self.openai = None # Disable OpenAI if key is invalid
                     self.available_openai_models = []
                except Exception as model_e:
                     logger.warning(f"Could not fetch OpenAI models: {str(model_e)}. Using default: ['gpt-4o']")
                     self.available_openai_models = ['gpt-4o'] # Use default if model listing fails

            except ImportError:
                logger.warning("OpenAI library not found. Please install it (`pip install openai`). OpenAI OCR will not be available.")
                self.openai = None
                self.available_openai_models = []
            except ValueError as e: # Catch specific client init errors (like bad key format?)
                logger.warning(f"OpenAI OCR Initialization Warning: {str(e)}. Engine will not be available.")
                self.openai = None
                self.available_openai_models = []
            except Exception as e: # Catch other potential errors
                logger.error(f"Unexpected error initializing OpenAI OCR: {str(e)}", exc_info=True)
                self.openai = None
                self.available_openai_models = []
        else:
            logger.info("OpenAI OCR not initialized - no API key provided in environment")
            self.openai = None # Ensure it's None if no key
            self.available_openai_models = []

    def reinitialize_api_engines(self):
        """Re-initializes engines that depend on API keys (Mistral, OpenAI)."""
        logger.info("Re-initializing API-dependent OCR engines...")
        self._initialize_mistral()
        self._initialize_openai()
        logger.info("Finished re-initializing API engines.")

    def __del__(self):
        """Cleanup temporary directory when the object is destroyed."""
        try:
            if hasattr(self, 'temp_dir') and Path(self.temp_dir).exists():
                logger.info(f"Cleaning up temporary directory: {self.temp_dir}")
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            # Log error during cleanup but don't prevent program exit
            logger.error(f"Error during DocumentOCR cleanup: {e}", exc_info=True)
            pass # Keep pass as __del__ should not raise exceptions
    
    def _process_pdf_document(self, file_content: bytes, file_name: str, ocr_engine: OCR_ENGINE_TYPE, openai_model: str | None = None) -> Tuple[str, List[str], str]:
        """Process a PDF document using the specified OCR engine."""
        # Create temporary PDF file
        tmp_path = os.path.join(self.temp_dir, f"temp_{os.urandom(8).hex()}.pdf")
        with open(tmp_path, 'wb') as f:
            f.write(file_content)
        
        result_text = "Error: No OCR engine processed the document."
        image_paths = []

        try:
            # Process PDF based on selected engine
            if ocr_engine == "Tesseract":
                if self.tesseract:
                    image_paths, result_text = self.tesseract.process_pdf(tmp_path)
                else:
                     raise ValueError("Tesseract OCR is not available")
            elif ocr_engine == "Mistral":
                if self.mistral:
                    image_paths, result_text = self.mistral.process_pdf(tmp_path)
                    # Add preview generation logic if needed (as before)
                    if not image_paths and result_text and not result_text.startswith("Error:"):
                        import fitz
                        try:
                            doc = fitz.open(tmp_path)
                            previews = []
                            for i, page in enumerate(doc, 1):
                                try:
                                    pix = page.get_pixmap()
                                    preview_path = os.path.join(self.temp_dir, f"page_{i}.png")
                                    pix.save(preview_path)
                                    previews.append(preview_path)
                                except Exception as e:
                                    logger.warning(f"Failed to render preview for page {i}: {str(e)}")
                            doc.close()
                            image_paths = previews # Use previews if successful
                        except Exception as e:
                            logger.warning(f"Failed to generate PDF previews for Mistral: {str(e)}")
                else:
                    raise ValueError("Mistral OCR is not available")
            elif ocr_engine == "EasyOCR":
                if self.easyocr:
                    image_paths, result_text = self.easyocr.process_pdf(tmp_path)
                else:
                    raise ValueError("EasyOCR is not available")
            elif ocr_engine == "OpenAI": # Use elif for clarity
                if self.openai:
                    # Use selected model or default from OpenAICR if None
                    selected_model = openai_model if openai_model else self.available_openai_models[0] if self.available_openai_models else "gpt-4o"
                    image_paths, result_text = self.openai.process_pdf(tmp_path, model_name=selected_model)
                else:
                    raise ValueError("OpenAI OCR is not available")
            else:
                 raise ValueError(f"Unknown or unavailable OCR engine: {ocr_engine}")

            return file_name, image_paths, result_text
            
        finally:
            try:
                os.unlink(tmp_path)
            except OSError as e:
                 logger.warning(f"Could not delete temporary PDF {tmp_path}: {e}")

    def _process_image_document(self, file_content: bytes, file_name: str, ocr_engine: OCR_ENGINE_TYPE, openai_model: str | None = None) -> Tuple[str, List[str], str]:
        """Process an image document using the specified OCR engine."""
        image_paths = [] # Default to empty list
        result_text = "Error: No OCR engine processed the image."
        try:
            # Validate file content
            if not file_content:
                raise ValueError("Empty file content")
            
            # Try to identify the image format
            try:
                image = Image.open(io.BytesIO(file_content))
                # Keep original format info if possible, useful for debugging
                logger.info(f"Successfully opened image: {file_name} (Format: {image.format}, Mode: {image.mode})")
            except Exception as e:
                logger.error(f"Failed to open image {file_name}: {str(e)}")
                # Return a specific error message if possible
                return file_name, [], f"Error: Invalid or unsupported image format: {str(e)}"
            
            # Save image to temporary file for display or use by engines
            # Ensure consistent format like PNG for processing and display
            # Determine a safe filename
            base, ext = os.path.splitext(file_name)
            safe_ext = ext.lower() if ext.lower() in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.heic'] else '.png'
            if safe_ext == '.heic': safe_ext = '.png' # Convert HEIC to PNG for consistency
            temp_image_filename = f"image_{os.urandom(8).hex()}{safe_ext}"
            image_path = os.path.join(self.temp_dir, temp_image_filename)

            try:
                # Convert to RGB before saving non-RGB formats to PNG/JPG if needed
                save_image = image
                target_format = 'PNG' # Default save format
                if safe_ext in ['.jpg', '.jpeg']:
                    target_format = 'JPEG'
                elif safe_ext == '.gif':
                     target_format = 'GIF' # Or convert to PNG? Let's stick to PNG.
                     target_format = 'PNG'
                     safe_ext = '.png' # Update extension if changing format
                     image_path = os.path.join(self.temp_dir, f"image_{os.urandom(8).hex()}.png") # Update path

                if save_image.mode not in ('RGB', 'L') and target_format != 'GIF': # Allow L mode (grayscale)
                    logger.info(f"Converting image from mode {save_image.mode} to RGB for saving.")
                    save_image = image.convert('RGB')

                save_image.save(image_path, format=target_format)
                logger.info(f"Successfully saved image copy to: {image_path}")
                image_paths = [image_path] # Use the saved path for display/return

            except Exception as e:
                logger.error(f"Failed to save image {file_name}: {str(e)}")
                # Return empty paths and error text
                return file_name, [], f"Error: Failed to process/save input image: {str(e)}"

            # Process image based on selected engine
            try:
                 if ocr_engine == "Tesseract":
                    if self.tesseract:
                        # Tesseract likely processes the PIL Image directly
                        _, result_text = self.tesseract.process_image(image) # Assuming returns text only now
                        # Keep image_paths as the saved copy
                    else:
                         raise ValueError("Tesseract OCR is not available")
                 elif ocr_engine == "Mistral":
                    logger.info(f"Checking Mistral engine availability inside _process_image_document. self.mistral = {self.mistral}")
                    if self.mistral:
                        # Mistral uses PIL Image
                        _, result_text = self.mistral.process_image(image)
                        # Keep image_paths as the saved copy
                    else:
                        raise ValueError("Mistral OCR is not available")
                 elif ocr_engine == "EasyOCR":
                    if self.easyocr:
                         # EasyOCR might work with path or PIL image - check its implementation
                         # Assuming it works with PIL Image for consistency:
                         _, result_text = self.easyocr.process_image(image)
                         # Keep image_paths as the saved copy
                    else:
                        raise ValueError("EasyOCR is not available")
                 elif ocr_engine == "OpenAI":
                    if self.openai:
                         selected_model = openai_model if openai_model else self.available_openai_models[0] if self.available_openai_models else "gpt-4o"
                         # OpenAI processes PIL Image, returns path list and text
                         _, result_text = self.openai.process_image(image, model_name=selected_model)
                         # Keep image_paths as the saved copy
                    else:
                         raise ValueError("OpenAI OCR is not available")
                 else:
                    raise ValueError(f"Unknown or unavailable OCR engine: {ocr_engine}")

                 # Return the saved image path and the extracted text
                 return file_name, image_paths, result_text

            except Exception as ocr_e:
                 logger.error(f"OCR processing failed for {file_name} with {ocr_engine}: {str(ocr_e)}")
                 # Return the saved image path for context, but with an error message
                 return file_name, image_paths, f"Error during {ocr_engine} processing: {str(ocr_e)}"

        except Exception as e:
             logger.error(f"Error in _process_image_document for {file_name}: {str(e)}", exc_info=True)
             # Return generic error, potentially with no image path if saving failed
             return file_name, image_paths, f"Error processing image: {str(e)}"
    
    def process_document(self, file, ocr_engine: OCR_ENGINE_TYPE, openai_model: str | None = None) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Process a document using the specified OCR engine."""
        try:
            # For Gradio file objects, we need to access the file path directly
            if not hasattr(file, 'name'):
                 return None, None, "Error: Invalid file object received."

            file_path = file.name
            file_name = os.path.basename(file_path)
            logger.info(f"Processing document: {file_name} with engine: {ocr_engine}")
            if ocr_engine == "OpenAI" and openai_model:
                logger.info(f"Using OpenAI model: {openai_model}")

            # Check engine availability early (redundant with checks inside _process methods, but good practice)
            if ocr_engine == "Mistral" and self.mistral is None:
                return None, None, "Error: Mistral OCR is not available. Check API key or server logs."
            if ocr_engine == "OpenAI" and self.openai is None:
                return None, None, "Error: OpenAI OCR is not available. Check API key or server logs."
            if ocr_engine == "EasyOCR" and self.easyocr is None:
                return None, None, "Error: EasyOCR is not available. Check server logs for initialization errors."
            if ocr_engine == "Tesseract" and self.tesseract is None: # Should always be available unless init failed badly
                 return None, None, "Error: Tesseract OCR is not available. Check server logs."

            # Read the file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Determine file type and process accordingly
            # Pass openai_model to the processing methods
            if file_name.lower().endswith('.pdf'):
                _, image_paths, result_text = self._process_pdf_document(file_content, file_name, ocr_engine, openai_model=openai_model)
            elif file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.heic')):
                _, image_paths, result_text = self._process_image_document(file_content, file_name, ocr_engine, openai_model=openai_model)
            else:
                return None, None, f"Error: Unsupported file type: {os.path.splitext(file_name)[1]}. Please upload a PDF or image file."
            
            # Check for errors returned as result_text
            if result_text is not None and result_text.startswith("Error:"):
                # Return image paths even if text extraction failed, for context
                return file_name, image_paths, result_text # Propagate error message

            if result_text is None:
                # Provide image paths if available
                return file_name, image_paths, "Error: Could not extract text from the document. Please try again with a different file or OCR engine."

            # Ensure image_paths is a list
            if image_paths is None: image_paths = []

            return file_name, image_paths, result_text
                
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}", exc_info=True)
            # Provide a more generic error message to the user
            return None, None, f"An unexpected error occurred: {str(e)}"
    
    def download_ocr_result(self, ocr_result: str, file_format: str, original_filename: str) -> str | None:
        """Generate a downloadable text file from the OCR result in the specified format, named after the original file."""
        if not original_filename:
            logger.error("Download failed: Original filename not provided.")
            return None

        try:
            # Create the output filename using pathlib
            base_name = Path(original_filename).stem
            output_filename = f"{base_name}_{secrets.token_hex(4)}.{file_format}" # Add token to avoid collisions
            output_path = Path(self.output_dir) / output_filename

            logger.info(f"Attempting to save OCR result for '{original_filename}' to: {output_path}")

            # Write the result to the file based on format
            if file_format == 'txt':
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(ocr_result)
            elif file_format == 'md':
                # Assuming ocr_result is plain text, just save it as .md
                # If specific markdown conversion is needed, add it here.
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(ocr_result)
            elif file_format == 'doc':
                if not PYTHON_DOCX_AVAILABLE:
                    logger.error("Cannot create .doc file: python-docx package is missing.")
                    # Consider raising an error or returning None
                    return None
                try:
                    document = Document()
                    # Add paragraph with the text
                    document.add_paragraph(ocr_result)
                    document.save(output_path)
                    logger.info(f"Successfully created .doc file: {output_path}")
                except Exception as docx_e:
                    logger.error(f"Failed to create .doc file {output_path}: {docx_e}", exc_info=True)
                    return None # Indicate failure
            else:
                logger.error(f"Unsupported file format requested: {file_format}")
                return None

            # Verify file creation
            if output_path.exists():
                logger.info(f"Successfully saved OCR result to: {output_path}")
                return str(output_path) # Return the string path
            else:
                logger.error(f"File was not created after write attempt: {output_path}")
                return None

        except Exception as e:
            logger.error(f"Error writing OCR result to file for {original_filename}: {e}", exc_info=True)
            return None # Indicate failure 