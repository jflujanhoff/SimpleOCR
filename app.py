import gradio as gr
from ocr_processing import DocumentOCR
import os
import secrets
from dotenv import load_dotenv
import base64
import logging
import json
import openai
from mistralai.client import MistralClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables for authentication only
load_dotenv()

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# Global variables to store user-provided API keys - use an in-memory dict with no defaults
api_keys = {
    "Mistral": "",
    "OpenAI": ""
}

# Initialize OCR processor
ocr_processor = None
available_engines = ["Tesseract"]  # Tesseract is always available

# Load custom theme
from custom_theme import delite_theme

def initialize_ocr_processor():
    """Initialize or reinitialize the OCR processor with current API keys."""
    global ocr_processor, available_engines

    try:
        # Clear existing environment variables specific to API keys
        # Note: DocumentOCR now primarily uses keys during its own __init__.
        # This block might be less critical unless other parts rely on these env vars.
        env_vars_to_clear = [f"{engine.upper()}_API_KEY" for engine in api_keys.keys()]
        original_env = {var: os.environ.get(var) for var in env_vars_to_clear}

        for var in env_vars_to_clear:
            if var in os.environ:
                 os.environ.pop(var)

        # Temporarily set environment variables for the keys provided by the user
        for engine, key in api_keys.items():
            if key:
                env_var = f"{engine.upper()}_API_KEY"
                os.environ[env_var] = key
                logger.info(f"Temporarily setting {env_var} for initialization")

        # Initialize processor (which now also attempts to init models and fetch OpenAI models)
        logger.info("Initializing OCR processor with potentially updated API keys")
        ocr_processor = DocumentOCR()
        available_engines = ["Tesseract"] # Start with Tesseract

        # Check which engines initialized successfully based on the processor's state
        if ocr_processor.easyocr is not None:
            available_engines.append("EasyOCR")
            logger.info("EasyOCR engine is available")
        else:
            logger.info("EasyOCR engine is not available (initialization failed)")

        if ocr_processor.mistral is not None:
            available_engines.append("Mistral")
            logger.info("Mistral OCR engine is available")
        else:
            logger.info("Mistral OCR engine is not available")

        if ocr_processor.openai is not None:
            available_engines.append("OpenAI")
            logger.info("OpenAI OCR engine is available")
            # Log the fetched models (already logged in DocumentOCR init)
            # logger.info(f"Fetched OpenAI Models: {ocr_processor.available_openai_models}")
        else:
            logger.info("OpenAI OCR engine is not available")

        # Restore original environment variables that were temporarily set
        # This might be important if other processes outside this app rely on them.
        for var, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = original_value
            logger.info(f"Restored original value for {var}")

    except Exception as e: # Catch potential errors during DocumentOCR() init
        logger.error(f"Error during OCR initialization: {str(e)}", exc_info=True)
        # Reset processor and engines on failure
        ocr_processor = None
        available_engines = ["Tesseract"] # Fallback
        logger.warning("OCR Processor initialization failed. Only Tesseract might be available if base init succeeds.")
        # Restore environment variables even on failure
        try:
            if 'original_env' in locals():
                for var, original_value in original_env.items():
                    if original_value is None:
                        os.environ.pop(var, None)
                    else:
                        os.environ[var] = original_value
        except Exception as restore_e:
            logger.error(f"Failed to restore environment variables after init error: {restore_e}")

# Initialize on startup
initialize_ocr_processor()

# Helper function to generate the markdown text for available engines
def get_available_engines_markdown():
    # Base the markdown on the *currently available* engines list
    lines = []
    if "Tesseract" in available_engines:
        lines.append("- Tesseract (✅ always available)") # Assuming Tesseract init is robust
    else:
        lines.append("- Tesseract (❌ failed to initialize)")

    easyocr_status = '✅ available' if 'EasyOCR' in available_engines else '❌ not available'
    lines.append(f"- EasyOCR ({easyocr_status})")

    mistral_status = '✅ available' if 'Mistral' in available_engines else '❌ not available'
    lines.append(f"- Mistral ({mistral_status})")

    openai_status = '✅ available' if 'OpenAI' in available_engines else '❌ not available'
    lines.append(f"- OpenAI ({openai_status})")
    return "\n".join(lines)

def save_api_key(api_key, engine):
    """Validate and save API key, reinitialize, and return status message."""
    if not api_key:
        return f"❓ No API key provided for {engine}. Please enter a valid key."

    logger.info(f"Attempting to save API key for {engine}")

    # --- Key Validation Step --- #
    try:
        if engine == "OpenAI":
            try:
                temp_client = openai.OpenAI(api_key=api_key)
                temp_client.models.list() # Lightweight check
                logger.info(f"OpenAI API key validation successful for key ending in ...{api_key[-4:]}")
            except openai.AuthenticationError:
                logger.warning(f"OpenAI API key validation failed (AuthenticationError) for key ending in ...{api_key[-4:]}")
                return f"❌ Invalid OpenAI API Key. Authentication failed."
            except Exception as e:
                logger.error(f"OpenAI API key validation failed for key ending in ...{api_key[-4:]}: {e}")
                return f"❌ OpenAI key validation failed: {str(e)}"

        # For Mistral, we'll just save the key without validation
        # The initialization process will handle validation errors

        # --- Save Key and Re-initialize --- #
        logger.info(f"Saving API key for {engine}")
        global api_keys
        api_keys[engine] = api_key

        # Reinitialize with the new key
        initialize_ocr_processor() # This will re-check all engines based on current api_keys

        # Check if the specific engine we tried to enable is now available *after* init
        success = engine in available_engines
        if success:
             status_message = f"✅ {engine} API key saved and engine initialized."
             if engine == "OpenAI" and ocr_processor and ocr_processor.available_openai_models:
                  # Don't list all models, just confirm they loaded or mention the first one
                  status_message += f" Model list loaded (e.g., {ocr_processor.available_openai_models[0]})."
             elif engine == "OpenAI":
                  status_message += " Check logs for model loading details."
             return status_message
        else:
            # This case occurs when initialization fails
            logger.error(f"{engine} key saved but engine failed to initialize. Check logs for details.")
            if engine == "Mistral":
                # Don't clear the key for Mistral - just report the initialization failure
                return f"⚠️ Mistral API key saved, but engine initialization failed. Check server logs for details."
            else:
                # For other engines, clear the key
                api_keys[engine] = ""
                initialize_ocr_processor() # Re-initialize again to ensure state is clean
                return f"❌ Error: {engine} key failed post-initialization. Check logs."

    except Exception as e:
        # Catch any unexpected errors during the whole process
        logger.error(f"Error saving API key for {engine}: {str(e)}", exc_info=True)
        return f"❌ Unexpected error processing API key for {engine}: {str(e)}"

def clear_api_key(engine):
    """Clear the API key for the specified engine."""
    global api_keys
    if engine in api_keys:
        api_keys[engine] = ""
        initialize_ocr_processor() # Re-initialize to update engine list
        logger.info(f"API key for {engine} has been cleared")
        return f"⚠️ {engine} API key has been cleared."
    else:
        return f"❓ Engine {engine} not found or doesn't use API keys."

# Modify process_document function signature
def process_document(file, ocr_engine, selected_openai_model):
    """Process a document using the specified OCR engine and selected OpenAI model."""
    # Default error/empty state with hidden outputs
    error_updates = {
        image_output: gr.update(value=None, visible=False),
        md_output: "Error: Processing failed. Check inputs or logs.",
        download_output: gr.update(value=[], visible=False)
    }

    if file is None:
        error_updates[md_output] = "Error: No file uploaded."
        return error_updates

    if ocr_processor is None:
        initialize_ocr_processor() # Attempt recovery
        if ocr_processor is None:
             error_updates[md_output] = "Error: OCR processor failed to initialize. Check server logs."
             return error_updates
        logger.warning("OCR processor was None, attempted re-initialization.")

    # Check availability before processing
    if ocr_engine not in available_engines:
         error_updates[md_output] = f"Error: {ocr_engine} OCR is not available. Check API keys or server logs."
         return error_updates

    # Added check for OpenAI model selection validity if OpenAI is the engine
    if ocr_engine == "OpenAI" and not selected_openai_model:
        # Check if models are available at all on the processor
        if not (ocr_processor and ocr_processor.available_openai_models):
             error_updates[md_output] = "Error: OpenAI engine selected, but no models could be loaded. Check API key and logs."
        else:
            error_updates[md_output] = "Error: OpenAI engine selected, but no specific model chosen. Please select a model in the API Keys tab."
        return error_updates

    try:
        # Environment variable handling assumed done within DocumentOCR init/methods now

        # Process the document, passing the selected OpenAI model
        logger.info(f"Calling process_document with engine: {ocr_engine}, openai_model: {selected_openai_model if ocr_engine == 'OpenAI' else 'N/A'}")
        file_name, image_paths, result_text = ocr_processor.process_document(
            file,
            ocr_engine,
            openai_model=selected_openai_model if ocr_engine == "OpenAI" else None # Pass model only if OpenAI is selected
        )

        # Check for errors returned by process_document
        if result_text is not None and result_text.startswith("Error:"):
            error_updates[md_output] = result_text # Pass error message directly to UI
            # Keep any potentially generated image previews for context
            valid_display_paths = [p for p in image_paths if p is not None and os.path.exists(p)] if image_paths else []
            error_updates[image_output] = gr.update(value=valid_display_paths, visible=bool(valid_display_paths))
            return error_updates

        if result_text is None:
            error_updates[md_output] = "Error: Could not extract text from the document. Please try again with a different file or OCR engine."
             # Keep any potentially generated image previews for context
            valid_display_paths = [p for p in image_paths if p is not None and os.path.exists(p)] if image_paths else []
            error_updates[image_output] = gr.update(value=valid_display_paths, visible=bool(valid_display_paths))
            return error_updates

        # Generate downloadable files
        txt_path, _ = ocr_processor.download_ocr_result(result_text, "txt")
        md_path, _ = ocr_processor.download_ocr_result(result_text, "md")
        doc_path, _ = ocr_processor.download_ocr_result(result_text, "doc")

        download_files = [txt_path, md_path, doc_path]
        existing_download_files = [f for f in download_files if f is not None and f != "" and os.path.exists(f)]

        valid_display_paths = [p for p in image_paths if p is not None and os.path.exists(p)] if image_paths else []

        success_updates = {
            image_output: gr.update(value=valid_display_paths, visible=bool(valid_display_paths)),
            md_output: result_text,
            download_output: gr.update(value=existing_download_files, visible=bool(existing_download_files))
        }
        return success_updates

    except Exception as e:
        error_msg = f"Error processing document: {str(e)}"
        logger.error(error_msg, exc_info=True)
        error_updates[md_output] = error_msg
        return error_updates

# Function to clear OCR tab fields - now returns a dictionary
def clear_ocr_fields():
    """Clears the input and output fields in the OCR tab, returning updates dictionary."""
    # Find the default engine, preferring Tesseract if available
    default_engine = "Tesseract" if "Tesseract" in available_engines else (available_engines[0] if available_engines else None)
    return {
        file_input: None,
        ocr_engine: default_engine,
        image_output: gr.update(value=None, visible=False), # Clear and hide
        md_output: "Extracted Text will appear here",
        download_output: gr.update(value=[], visible=False) # Clear and hide
    }

# --- New Functions for Modal Confirmation --- (Keep as is)
# ... show_confirmation ...
# ... hide_confirmation ...
# ... handle_clear_click ...
# ... clear_and_hide_confirmation ...
# --- Functions for Modal Confirmation --- #

def show_confirmation():
    """Returns updates dictionary to show the confirmation UI elements."""
    return {
        clear_confirm_msg: gr.Markdown(value="⚠️ Results exist. Are you sure you want to clear everything?", visible=True),
        confirm_clear_btn: gr.Button(visible=True),
        cancel_clear_btn: gr.Button(visible=True)
    }

def hide_confirmation():
    """Returns updates dictionary to hide the confirmation UI elements."""
    return {
        clear_confirm_msg: gr.Markdown(value="", visible=False),
        confirm_clear_btn: gr.Button(visible=False),
        cancel_clear_btn: gr.Button(visible=False)
    }

def handle_clear_click(current_download: list | None):
    """Handles the main Clear button click. Shows confirmation or clears directly."""
    if current_download: # Check if there are files in download_output (proxy for results)
        # Results exist, show confirmation
        updates = show_confirmation()
        # Add gr.update() for main fields to indicate no change yet
        updates[file_input] = gr.update()
        updates[ocr_engine] = gr.update()
        updates[image_output] = gr.update()
        updates[md_output] = gr.update()
        updates[download_output] = gr.update()
        return updates
    else:
        # No results, clear directly and ensure confirmation is hidden
        # Merge updates from clear_ocr_fields and hide_confirmation
        updates = clear_ocr_fields() # Gets updates for main fields (including visibility)
        updates.update(hide_confirmation()) # Adds updates for confirmation UI
        return updates

def clear_and_hide_confirmation():
    """Clears the main fields and hides the confirmation UI."""
    # Merge updates from clear_ocr_fields and hide_confirmation
    updates = clear_ocr_fields() # Gets updates for main fields (including visibility)
    updates.update(hide_confirmation()) # Adds updates for confirmation UI
    return updates


# Create Gradio interface
with gr.Blocks(theme=delite_theme) as demo:
    gr.Markdown("# Document OCR")
    gr.Markdown("Upload a document (PDF or image) to extract text using OCR.")

    with gr.Tabs():
        # OCR Tab
        with gr.Tab("OCR"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("Upload Document to OCR")
                    file_input = gr.File(label="Upload Document")
                    # Initialize Radio button with currently available engines
                    ocr_engine = gr.Radio(
                        choices=available_engines,
                        value=available_engines[0] if available_engines else None,
                        label="OCR Engine",
                        interactive=True
                    )
                    # Main action buttons
                    with gr.Row():
                        process_btn = gr.Button("Process Document", variant="primary", scale=1)
                        clear_btn = gr.Button("Clear", variant="secondary", scale=1)

                    # Confirmation UI (initially hidden)
                    clear_confirm_msg = gr.Markdown(value="", visible=False)
                    confirm_clear_btn = gr.Button("Confirm Clear", variant="stop", visible=False)
                    cancel_clear_btn = gr.Button("Cancel", variant="secondary", visible=False)
                    with gr.Row(): # Contains the confirmation message
                        clear_confirm_msg
                    with gr.Row(): # Contains the confirmation buttons
                        confirm_clear_btn
                        cancel_clear_btn

                    image_output = gr.Gallery(label="Document Pages", visible=False) # Initially hidden

                with gr.Column():
                    # Revert to original markdown component with label and container
                    gr.Markdown("Extracted Text")
                    md_output = gr.Markdown(label="Extracted Text", container=True, show_copy_button=True, value="Extracted Text will appear here")
                    # Configure download_output for multiple files
                    download_output = gr.File(label="Download Results", file_count="multiple", visible=False) # Initially hidden
                    # Update the download description
                    gr.Markdown("Download the extracted text as .txt, .md, or .doc files.")

        # API Keys Tab
        with gr.Tab("API Keys"):
            gr.Markdown("### Configure OCR API Keys")
            gr.Markdown("Enter your API keys for Mistral and OpenAI to enable their OCR engines. Keys are stored in memory only for the current session.")
            gr.Markdown("⚠️ **Security Note**: API keys are stored in memory and are not persisted when the server restarts.")

            with gr.Accordion("Mistral OCR", open=False):
                mistral_status = gr.Markdown(label="Status", value="")
                with gr.Column():
                    mistral_key = gr.Textbox(
                        label="Mistral API Key",
                        placeholder="Enter your Mistral API key...",
                        type="password",
                        value=""
                    )
                    with gr.Row():
                        mistral_save_btn = gr.Button("Save Mistral API Key", variant="primary")
                        mistral_clear_btn = gr.Button("Clear Key", variant="stop")

            with gr.Accordion("OpenAI OCR", open=False):
                openai_status = gr.Markdown(label="Status", value="")
                with gr.Column():
                    openai_key = gr.Textbox(
                        label="OpenAI API Key",
                        placeholder="Enter your OpenAI API key...",
                        type="password",
                        value=""  # Don't display key values
                    )
                    # Add the model selection dropdown here
                    openai_model_select = gr.Dropdown(
                        label="Select OpenAI Model",
                        choices=[], # Will be populated dynamically
                        value=None,
                        visible=False, # Initially hidden
                        interactive=True
                    )
                    with gr.Row():
                        openai_save_btn = gr.Button("Save OpenAI API Key", variant="primary")
                        openai_clear_btn = gr.Button("Clear Key", variant="stop")

            gr.Markdown("### Available OCR Engines")
            gr.Markdown("The following OCR engines are currently available:")
            # Update Markdown text using the helper function
            available_engines_text = gr.Markdown(value=get_available_engines_markdown())

    # --- Event Handlers --- #

    # Process button click - Add openai_model_select to inputs
    process_btn.click(
        fn=process_document,
        # Add openai_model_select to inputs
        inputs=[file_input, ocr_engine, openai_model_select],
        outputs=[image_output, md_output, download_output]
    )

    # Define the comprehensive UI update function
    def update_all_ui_elements():
        """Updates engine list, radio choices, statuses, and OpenAI model dropdown based on current state."""
        # Update available engines markdown
        markdown_text = get_available_engines_markdown()

        # Update OCR engine radio button choices and value
        # Prefer Tesseract if available, otherwise the first in the list
        default_engine_choice = "Tesseract" if "Tesseract" in available_engines else (available_engines[0] if available_engines else None)
        radio_update = gr.Radio(
            choices=available_engines,
            value=default_engine_choice,
            label="OCR Engine",
            interactive=True
        )

        # Determine Mistral Status
        mistral_status_text = ""
        if "Mistral" in available_engines:
            mistral_status_text = "✅ Mistral Engine Available."
        elif "Mistral" in api_keys and api_keys["Mistral"]:
             mistral_status_text = "❌ Mistral Engine Failed to Initialize. Check API Key/Logs."
        else:
             mistral_status_text = "ℹ️ Enter Mistral API Key to enable."


        # Determine OpenAI Status & Model Dropdown State
        openai_models = []
        openai_dropdown_visible = False
        openai_default_model = None
        openai_status_text = ""

        if "OpenAI" in available_engines:
             # Engine is available, check for models from the processor instance
             if ocr_processor and ocr_processor.available_openai_models:
                 openai_models = ocr_processor.available_openai_models
                 openai_dropdown_visible = True
                 openai_default_model = openai_models[0] # Default to the first available model
                 openai_status_text = f"✅ OpenAI Engine Available."
                 # Optionally list models in status: Models: {', '.join(openai_models)}
             else:
                 # Init succeeded but model fetch likely failed or returned empty
                 openai_status_text = "⚠️ OpenAI Engine Initialized, but failed to load models (Check Logs). Using default model."
                 openai_models = ["gpt-4o"] # Fallback list
                 openai_default_model = openai_models[0]
                 openai_dropdown_visible = True # Show dropdown even with default
        elif "OpenAI" in api_keys and api_keys["OpenAI"]:
            # Key provided, but engine not in available_engines (init failed)
            openai_status_text = "❌ OpenAI Engine Failed to Initialize. Check API Key/Logs."
        else:
             # No key provided or cleared
             openai_status_text = "ℹ️ Enter OpenAI API Key to enable."


        openai_model_dropdown_update = gr.Dropdown(
            choices=openai_models,
            value=openai_default_model,
            visible=openai_dropdown_visible,
            interactive=openai_dropdown_visible
        )

        # Return updates for all affected components in a dictionary
        return {
            available_engines_text: markdown_text,
            ocr_engine: radio_update,
            mistral_status: mistral_status_text,
            openai_status: openai_status_text,
            openai_model_select: openai_model_dropdown_update
        }

    # --- API key save/clear button logic --- #

    mistral_save_btn.click(
        fn=save_api_key,
        inputs=[mistral_key, gr.Text(value="Mistral", visible=False)],
        outputs=[mistral_status] # Let save_api_key return the immediate status
    ).then(
        fn=update_all_ui_elements, # Update all UI based on the new state
        outputs=[available_engines_text, ocr_engine, mistral_status, openai_status, openai_model_select]
    ).then(
        fn=lambda: "", # Clear input
        outputs=[mistral_key]
    )

    mistral_clear_btn.click(
        fn=clear_api_key,
        inputs=[gr.Text(value="Mistral", visible=False)],
        outputs=[mistral_status]
    ).then(
        fn=update_all_ui_elements,
        outputs=[available_engines_text, ocr_engine, mistral_status, openai_status, openai_model_select]
    ).then(
        fn=lambda: "",
        outputs=[mistral_key]
    )

    openai_save_btn.click(
        fn=save_api_key,
        inputs=[openai_key, gr.Text(value="OpenAI", visible=False)],
        outputs=[openai_status] # Let save_api_key return the immediate status
    ).then(
        fn=update_all_ui_elements,
        outputs=[available_engines_text, ocr_engine, mistral_status, openai_status, openai_model_select]
    ).then(
        fn=lambda: "",  # Clear input
        outputs=[openai_key]
    )

    openai_clear_btn.click(
        fn=clear_api_key,
        inputs=[gr.Text(value="OpenAI", visible=False)],
        outputs=[openai_status]
    ).then(
        fn=update_all_ui_elements,
        outputs=[available_engines_text, ocr_engine, mistral_status, openai_status, openai_model_select]
    ).then(
        fn=lambda: "",
        outputs=[openai_key]
    )

    # --- Clear Confirmation Handlers (remain the same) --- #
    clear_btn.click(
        fn=handle_clear_click,
        inputs=[download_output],
        outputs=[
            file_input, ocr_engine, image_output, md_output, download_output,
            clear_confirm_msg, confirm_clear_btn, cancel_clear_btn
        ]
    )
    confirm_clear_btn.click(
        fn=clear_and_hide_confirmation,
        inputs=[],
        outputs=[
            file_input, ocr_engine, image_output, md_output, download_output,
            clear_confirm_msg, confirm_clear_btn, cancel_clear_btn
        ]
    )
    cancel_clear_btn.click(
        fn=hide_confirmation,
        inputs=[],
        outputs=[
            clear_confirm_msg, confirm_clear_btn, cancel_clear_btn
        ]
    )

    # Add a startup event to initialize the UI correctly based on initial state
    demo.load(
        fn=update_all_ui_elements,
        outputs=[available_engines_text, ocr_engine, mistral_status, openai_status, openai_model_select]
    )

if __name__ == "__main__":
    auth_creds = (USERNAME, PASSWORD) if USERNAME and PASSWORD else None
    # Simplified launch logic
    demo.launch(auth=auth_creds, ssl_verify=True, share=False) # Set share=True if needed
    # demo.launch(ssl_verify=True) # Set share=True if needed 