import gradio as gr
from ocr_processing import DocumentOCR
import os
import secrets
from dotenv import load_dotenv
import logging
import openai # Still needed for initialize_ocr_processor validation check? Maybe move validation fully into ui_interactions? Let's keep for now.
# Removed MistralClient, base64, json, zipfile, shutil, pathlib unless needed by initialize_ocr_processor
# Removed functools.partial as it's now used in interface.py

# Import the interface creator function
from interface.interface import create_interface
# Need DocumentOCR for type hinting or direct use if needed
from ocr_processing import DocumentOCR
# Import MAX_SIZE from variables
from variables import MAX_SIZE

# No longer need direct imports of callbacks here
# from interface.process_ocr import (...)
# from interface.ui_interactions import (...)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables for authentication only
load_dotenv()

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# --- Global State --- (Remains here)
api_keys = {"Mistral": "", "OpenAI": ""}
ocr_processor = None
available_engines = ["Tesseract"] # Initialize with Tesseract

# --- OCR Processor Initialization --- (Remains here)
def initialize_ocr_processor():
    """Initialize or reinitialize the OCR processor with current API keys."""
    global ocr_processor, available_engines, api_keys # Ensure access to globals

    # --- Environment Variable Handling (Context Manager Preferred) ---
    # Store original values, clearing them temporarily
    sensitive_vars = ["MISTRAL_API_KEY", "OPENAI_API_KEY"]
    original_env_values = {}
    for var in sensitive_vars:
        original_env_values[var] = os.environ.pop(var, None)
    logger.debug(f"Temporarily cleared env vars: {list(original_env_values.keys())}")

    try:
        # Temporarily set environment variables from api_keys if they exist
        if api_keys.get("Mistral"):
            os.environ["MISTRAL_API_KEY"] = api_keys["Mistral"]
            logger.debug("Temporarily set MISTRAL_API_KEY from api_keys dict.")
        if api_keys.get("OpenAI"):
            os.environ["OPENAI_API_KEY"] = api_keys["OpenAI"]
            logger.debug("Temporarily set OPENAI_API_KEY from api_keys dict.")

        # --- Initialize or Re-initialize the SINGLE ocr_processor instance --- #
        if ocr_processor is None:
            logger.info("Initializing OCR processor for the first time...")
            ocr_processor = DocumentOCR() # Create the instance
        else:
            logger.info("Re-initializing API engines on existing OCR processor...")
            # Call the method to re-initialize Mistral/OpenAI using current env vars
            ocr_processor.reinitialize_api_engines()

        # --- Update Available Engines List (Based on the single instance) --- #
        if ocr_processor: # Check if processor was successfully created/updated
            logger.info("Checking status of initialized engines within DocumentOCR...")
            mistral_ok = hasattr(ocr_processor, 'mistral') and ocr_processor.mistral
            openai_ok = hasattr(ocr_processor, 'openai') and ocr_processor.openai
            easyocr_ok = hasattr(ocr_processor, 'easyocr') and ocr_processor.easyocr
            tesseract_ok = hasattr(ocr_processor, 'tesseract') and ocr_processor.tesseract # Check Tesseract too
            logger.info(f"Engine Status - Tesseract: {tesseract_ok}, Mistral: {mistral_ok}, OpenAI: {openai_ok}, EasyOCR: {easyocr_ok}")

            current_available = []
            if tesseract_ok: current_available.append("Tesseract")
            if easyocr_ok: current_available.append("EasyOCR")
            if mistral_ok: current_available.append("Mistral")
            if openai_ok:
                current_available.append("OpenAI")
                if hasattr(ocr_processor, 'available_openai_models') and ocr_processor.available_openai_models:
                     logger.info(f"Available OpenAI Models: {ocr_processor.available_openai_models}")
                else:
                     logger.warning("OpenAI initialized but failed to get models list or list is empty.")

            # Update the list in-place so references remain valid
            available_engines.clear()
            available_engines.extend(current_available)
            logger.info(f"OCR Engines successfully initialized/updated: {available_engines}")
        else:
             logger.error("OCR processor object is None after initialization attempt!")
             available_engines.clear() # Reset if processor failed
             available_engines.append("Tesseract") # Basic default

    except Exception as e:
        logger.error(f"Fatal error during OCR initialization/re-initialization: {e}", exc_info=True)
        # Don't necessarily set ocr_processor to None here if it partially worked before?
        # For simplicity, let's reset, but a more robust approach might be needed.
        ocr_processor = None # Reset on major failure
        available_engines.clear()
        available_engines.append("Tesseract")
        logger.warning("OCR Processor initialization/re-initialization FAILED. Resetting state.")

    finally:
        # Restore original environment variables
        logger.debug("Restoring original environment variables...")
        for var, value in original_env_values.items():
            if value is not None:
                os.environ[var] = value
                logger.debug(f"Restored env var: {var}")
            else:
                 # If original value was None, ensure the variable is removed
                 # (It was already removed at the start of the block)
                 pass

# Initialize on startup
initialize_ocr_processor()


# --- Create Interface --- #
# Pass all necessary state and functions to the interface creator
# Note: We pass the lists/dicts themselves, allowing interface.py to modify them via partials
logger.info("Creating Gradio Interface...")
demo, ui_components = create_interface(
    initial_available_engines=available_engines[:], # Pass a copy of initial state
    ocr_processor=ocr_processor,
    api_keys=api_keys,
    available_engines=available_engines, # Pass the live list
    initialize_ocr_processor=initialize_ocr_processor
)

# --- Launch App --- (Remains here)
if __name__ == "__main__":
    auth_creds = (USERNAME, PASSWORD) if USERNAME and PASSWORD else None
    # Simplified launch logic
    print("Launching Gradio App...")
    # Use server_name="0.0.0.0" to make it accessible on the network if needed
    # demo.launch(auth=auth_creds, ssl_verify=False, share=True, max_file_size=MAX_SIZE) # ssl_verify=False often needed for local dev
    demo.launch(ssl_verify=False, max_file_size=MAX_SIZE)
    print("Gradio App stopped.")
