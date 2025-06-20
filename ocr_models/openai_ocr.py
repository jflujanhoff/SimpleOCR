import os
import base64
from typing import Tuple, List
from PIL import Image
import io
import openai
from .base import BaseOCR
import logging
import re
from .utils import format_page_marker

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
            
        # Validate API key format
        if not api_key.startswith('sk-'):
            logger.warning("API key doesn't start with 'sk-' - this might be invalid")
            
        logger.info(f"Initializing OpenAI client with API key length: {len(api_key)}")
            
        # Only initialize client if we have a key
        try:
            # Store client for potential use later (e.g., fetching models in app.py)
            self.client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
            # Test connection briefly - list models is a light way
            # self.client.models.list() # Optional: test connectivity here
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise ValueError(f"Failed to initialize OpenAI client: {str(e)}")
    
    def _ensure_client_ready(self) -> bool:
        """Ensure the OpenAI client is properly initialized and ready.
        
        Returns:
            bool: True if client is ready, False otherwise
        """
        try:
            # Check if client exists
            if not hasattr(self, 'client') or self.client is None:
                logger.error("OpenAI client is not initialized")
                return False
                
            # Check if API key is still available
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY is not set in environment")
                return False
                
            # Re-create client if needed to ensure fresh connection
            if not hasattr(self, '_last_api_key') or self._last_api_key != api_key:
                logger.info("Re-initializing OpenAI client with current API key")
                self.client = openai.OpenAI(api_key=api_key)
                self._last_api_key = api_key
                
                # Test the client with a simple call
                try:
                    logger.info("Testing OpenAI client connection...")
                    models = self.client.models.list()
                    logger.info(f"Client test successful. Available models: {len(models.data)}")
                except Exception as test_e:
                    logger.error(f"Client test failed: {str(test_e)}")
                    return False
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure OpenAI client readiness: {str(e)}")
            return False
    
    def _validate_message_structure(self, messages: list) -> bool:
        """Validate the message structure before sending to OpenAI API.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            bool: True if structure is valid, False otherwise
        """
        try:
            import json
            
            # Try to serialize the messages to JSON to validate structure
            json_str = json.dumps(messages)
            
            # Basic validation checks
            if not isinstance(messages, list) or len(messages) == 0:
                logger.error("Messages must be a non-empty list")
                return False
                
            for msg in messages:
                if not isinstance(msg, dict):
                    logger.error("Each message must be a dictionary")
                    return False
                    
                if 'role' not in msg or 'content' not in msg:
                    logger.error("Each message must have 'role' and 'content' fields")
                    return False
                    
                # Validate content structure for vision messages
                if isinstance(msg['content'], list):
                    for content_item in msg['content']:
                        if not isinstance(content_item, dict):
                            logger.error("Content items must be dictionaries")
                            return False
                        if 'type' not in content_item:
                            logger.error("Content items must have a 'type' field")
                            return False
                            
            logger.debug(f"Message structure validation passed. JSON length: {len(json_str)}")
            return True
            
        except Exception as e:
            logger.error(f"Message structure validation failed: {str(e)}")
            return False
    
    def validate_connection(self) -> bool:
        """Validate the OpenAI connection by making a simple API call.
        
        Returns:
            bool: True if connection is valid, False otherwise
        """
        try:
            # Make a simple request to validate the connection
            models = self.client.models.list()
            logger.info(f"Successfully connected to OpenAI API. Available models: {len(models.data)}")
            return True
        except Exception as e:
            logger.error(f"Failed to validate OpenAI connection: {str(e)}")
            return False
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string.
        
        Args:
            image: PIL Image object
            
        Returns:
            Base64 encoded string of the image
        """
        try:
            buffered = io.BytesIO()
            # Convert to RGB to ensure compatibility
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save as JPEG for better compression and OpenAI compatibility
            image.save(buffered, format="JPEG", quality=85)
            img_bytes = buffered.getvalue()
            
            # Encode to base64 and ensure it's clean
            base64_str = base64.b64encode(img_bytes).decode('utf-8')
            
            # Validate that the base64 string is valid
            if not base64_str or len(base64_str) == 0:
                raise ValueError("Generated base64 string is empty")
                
            return base64_str
            
        except Exception as e:
            logger.error(f"Failed to convert image to base64: {str(e)}")
            raise ValueError(f"Image to base64 conversion failed: {str(e)}")
    
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
            # Ensure OpenAI client is ready before processing
            if not self._ensure_client_ready():
                raise ValueError("OpenAI client is not ready for processing")
            
            # Test vision API first with a minimal request
            if not hasattr(self, '_vision_tested'):
                logger.info("Running vision API test before processing...")
                if not self.test_vision_api():
                    raise ValueError("Vision API test failed - cannot proceed with OCR")
                self._vision_tested = True
                logger.info("Vision API test passed, proceeding with OCR...")
            
            # Save a copy of the image for display
            image_path = os.path.join(self.temp_dir, f"openai_image_{os.urandom(8).hex()}.png")
            # Ensure image is saved in a compatible format (like PNG)
            save_image = image.convert("RGB") if image.mode != 'RGB' else image
            save_image.save(image_path, format="PNG")
            
            # Convert image to base64 with error handling
            try:
                base64_image = self._image_to_base64(save_image)
                logger.info(f"Successfully converted image to base64, length: {len(base64_image)}")
            except Exception as e:
                logger.error(f"Failed to encode image as base64: {str(e)}")
                raise ValueError(f"Image encoding failed: {str(e)}")
            
            # Use the model_name parameter here
            logger.info(f"Using OpenAI model: {model_name} for image OCR")
            
            # Construct the messages payload with proper validation
            messages = [
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
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            # Validate message structure before sending
            if not self._validate_message_structure(messages):
                raise ValueError("Invalid message structure for OpenAI API")
            
            # Log the request structure for debugging (without the actual base64 data)
            logger.debug(f"Sending request to OpenAI with model: {model_name}")
            
            # Add extensive debugging
            try:
                import json
                # Create a sanitized version for logging (without base64 data)
                debug_messages = []
                for msg in messages:
                    debug_msg = {"role": msg["role"]}
                    if isinstance(msg["content"], list):
                        debug_content = []
                        for item in msg["content"]:
                            if item["type"] == "text":
                                debug_content.append(item)
                            elif item["type"] == "image_url":
                                debug_content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,[BASE64_DATA_{len(base64_image)}_CHARS]"
                                    }
                                })
                        debug_msg["content"] = debug_content
                    else:
                        debug_msg["content"] = msg["content"]
                    debug_messages.append(debug_msg)
                
                logger.info(f"Request structure: model={model_name}, max_tokens=4096")
                logger.info(f"Messages structure: {json.dumps(debug_messages, indent=2)}")
                logger.info(f"Base64 image length: {len(base64_image)} characters")
                
                # Validate the actual request parameters
                request_params = {
                    "model": model_name,
                    "messages": messages,
                    "max_tokens": 4096
                }
                
                # Try to serialize the actual request to catch JSON issues
                json.dumps(request_params, default=str)
                logger.info("Request serialization validation passed")
                
            except Exception as debug_e:
                logger.error(f"Debug serialization failed: {str(debug_e)}")
                raise ValueError(f"Request structure is not JSON serializable: {str(debug_e)}")
            
            response = self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=4096
            )
            
            # Get the response content and ensure it's properly formatted
            result = response.choices[0].message.content
            if result:
                # Clean up the result to ensure proper markdown formatting
                # Remove backtick code blocks that might be around markdown
                result = result.replace("```markdown", "").replace("```", "")
                
                # Ensure headings have space after #
                result = re.sub(r'(^|\n)#([^#\s])', r'\1# \2', result)
                
            return [image_path], result if result else "[No text extracted]"
            
        except Exception as e:
            logger.error(f"OpenAI OCR processing failed: {str(e)}")
            # Reraise the exception to be handled upstream
            raise e
    
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
            # Ensure OpenAI client is ready before processing
            if not self._ensure_client_ready():
                raise ValueError("OpenAI client is not ready for processing")
                
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            image_paths = []
            all_text = []
            
            page_count = len(doc) # Get page count
            
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
                    # Use H4 format for page indicator
                    if page_text:
                        # Remove the H4 header from the page_text itself (it comes from process_image now reverted)
                        # No longer needed as process_image doesn't add page count
                        page_text_lines = page_text.split('\n') # Use single backslash
                    #    if len(page_text_lines) > 2 and page_text_lines[0].startswith("#### Page Count:"):
                    #        page_text = '\n'.join(page_text_lines[2:]) # Use single backslash
                            
                        # Use the standardized marker function
                        page_marker = format_page_marker(page_num=page_num + 1, total_pages=page_count)
                        all_text.append(f"{page_marker}{page_text}")
                    else:
                        # Use the standardized marker function even for empty pages
                        page_marker = format_page_marker(page_num=page_num + 1, total_pages=page_count)
                        all_text.append(f"{page_marker}[No text extracted]")
            
            doc.close() # Close the document
            
            # Combine text without the overall page count header
            final_text = "\n\n".join(all_text) # Use single backslash
            # page_count_header = f"#### Page Count: {page_count}\n\n"
            # final_output = page_count_header + final_text
            
            return image_paths, final_text # Return combined text
            
        except Exception as e:
            logger.error(f"OpenAI PDF processing failed: {str(e)}")
            # Reraise the exception
            raise e # Re-raise the original exception 

    def test_vision_api(self) -> bool:
        """Test the vision API with a minimal request.
        
        Returns:
            bool: True if vision API works, False otherwise
        """
        try:
            # Ensure client is ready
            if not self._ensure_client_ready():
                return False
                
            # Create a minimal test image (1x1 white pixel)
            from PIL import Image
            test_image = Image.new('RGB', (1, 1), color='white')
            test_base64 = self._image_to_base64(test_image)
            
            # Minimal test request
            test_messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What do you see?"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{test_base64}"
                            }
                        }
                    ]
                }
            ]
            
            logger.info("Testing vision API with minimal request...")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=test_messages,
                max_tokens=10
            )
            
            logger.info(f"Vision API test successful: {response.choices[0].message.content}")
            return True
            
        except Exception as e:
            logger.error(f"Vision API test failed: {str(e)}")
            return False 