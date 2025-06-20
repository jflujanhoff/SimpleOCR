import gradio as gr
import logging
import openai # Needed for validation

# Import necessary interaction handlers or define them locally
# from .ui_interactions import UIInteractions # Or relevant functions

logger = logging.getLogger(__name__)

class APIKeysInteractions:
    """Handles UI interactions specifically for the API Keys page."""
    def __init__(self, api_keys, ocr_processor, available_engines, initialize_ocr_processor, ui_components):
        self.api_keys = api_keys
        self.ocr_processor = ocr_processor
        self.available_engines = available_engines
        self.initialize_ocr_processor = initialize_ocr_processor
        self.ui_components = ui_components # UI components *local* to this page
        logger.info("APIKeysInteractions initialized.")

    def save_api_key(self, api_key, engine):
        """Validate and save API key, reinitialize, and return UI updates for the API key page."""
        if not api_key:
            status_update = f"❓ No API key provided for {engine}. Please enter a valid key."
            # Return updates for all relevant components on this page
            return self._get_full_ui_update(mistral_status=status_update if engine == "Mistral" else gr.update(),
                                            openai_status=status_update if engine == "OpenAI" else gr.update()) 

        logger.info(f"Attempting to save API key for {engine}")
        validation_passed = False
        validation_message = ""
        try:
            if engine == "OpenAI":
                try:
                    # Use a temporary client for validation
                    temp_client = openai.OpenAI(api_key=api_key)
                    temp_client.models.list() # Simple check
                    logger.info(f"OpenAI API key validation successful for key ending in ...{api_key[-4:]}")
                    validation_passed = True
                except openai.AuthenticationError:
                    logger.warning(f"OpenAI API key validation failed (AuthenticationError) for key ending in ...{api_key[-4:]}")
                    validation_message = f"❌ Invalid OpenAI API Key. Authentication failed."
                    validation_passed = False
                except Exception as e:
                    logger.error(f"OpenAI API key validation failed for key ending in ...{api_key[-4:]}: {e}")
                    validation_message = f"❌ OpenAI key validation failed: {str(e)}"
                    validation_passed = False
            elif engine == "Mistral":
                # Add Mistral validation logic here if available/needed
                # For now, assume valid if provided
                logger.info("Mistral key provided, skipping validation for now.")
                validation_passed = True 
            else:
                validation_message = f"❓ Unknown engine '{engine}'"
                validation_passed = False

            if validation_passed:
                logger.info(f"Saving API key for {engine}")
                self.api_keys[engine] = api_key
                self.initialize_ocr_processor() # Trigger re-initialization
                # Update UI based on the *new* state after re-initialization
                return self.update_api_page_ui() # Return the full set of updates
            else:
                # Validation failed, update only the status for the specific engine
                 return self._get_full_ui_update(mistral_status=validation_message if engine == "Mistral" else gr.update(),
                                                openai_status=validation_message if engine == "OpenAI" else gr.update())

        except Exception as e:
            logger.error(f"Error saving API key for {engine}: {str(e)}", exc_info=True)
            error_message = f"❌ Unexpected error saving key for {engine}: {str(e)}"
            # Update status for the specific engine
            return self._get_full_ui_update(mistral_status=error_message if engine == "Mistral" else gr.update(),
                                            openai_status=error_message if engine == "OpenAI" else gr.update())

    def clear_api_key(self, engine):
        """Clear API key, reinitialize, and return UI updates for the API key page."""
        logger.info(f"Clearing API key for {engine}")
        if engine in self.api_keys:
            self.api_keys[engine] = ""
            self.initialize_ocr_processor() # Trigger re-initialization
            # Update UI based on the *new* state after re-initialization
            return self.update_api_page_ui() # Return the full set of updates
        else:
            logger.warning(f"Attempted to clear key for unknown engine: {engine}")
            # No change needed, but return current state update
            return self.update_api_page_ui()

    def _get_available_engines_markdown(self):
        """Generates markdown text listing available engines and their status based on the live list."""
        lines = []
        # Always check the live self.available_engines list
        if "Tesseract" in self.available_engines:
            lines.append("- Tesseract (✅ always available)")
        # Assuming Tesseract is always attempted

        easyocr_status = '✅ available' if 'EasyOCR' in self.available_engines else '❌ not available (or disabled)'
        lines.append(f"- EasyOCR ({easyocr_status})")

        mistral_status = '✅ available' if 'Mistral' in self.available_engines else (
            'ℹ️ key needed' if not self.api_keys.get("Mistral") else '❌ key set, but failed init (check logs)'
        )
        lines.append(f"- Mistral ({mistral_status})")

        openai_status = '✅ available' if 'OpenAI' in self.available_engines else (
            'ℹ️ key needed' if not self.api_keys.get("OpenAI") else '❌ key set, but failed init (check logs)'
        )
        lines.append(f"- OpenAI ({openai_status})")
        return "\n".join(lines)

    def update_api_page_ui(self):
        """Returns a dictionary of Gradio updates for all relevant components on the API key page."""
        logger.debug(f"Updating API keys page UI. Current available: {self.available_engines}")
        # Mistral Status
        if "Mistral" in self.available_engines:
            mistral_status_text = "✅ Mistral Engine Available."
        elif self.api_keys.get("Mistral"): # Check if key exists even if engine failed
            mistral_status_text = "❌ Mistral Engine Failed to Initialize. Check API Key/Logs."
        else:
            mistral_status_text = "ℹ️ Enter Mistral API Key to enable."

        # OpenAI Status and Models
        openai_models = []
        openai_dropdown_visible = False
        openai_default_model = None
        openai_status_text = ""

        if "OpenAI" in self.available_engines:
            if self.ocr_processor and hasattr(self.ocr_processor, 'available_openai_models') and self.ocr_processor.available_openai_models:
                openai_models = self.ocr_processor.available_openai_models
                openai_dropdown_visible = True
                openai_default_model = openai_models[0] # Default to first available
                # TODO: Consider saving/loading selected model preference?
                openai_status_text = f"✅ OpenAI Engine Available. Models loaded."
            else:
                openai_status_text = "⚠️ OpenAI Initialized, but failed to load models (Check Logs)."
                openai_models = []
                openai_dropdown_visible = False # Hide if models failed
        elif self.api_keys.get("OpenAI"): # Check if key exists even if engine failed
            openai_status_text = "❌ OpenAI Engine Failed to Initialize. Check API Key/Logs."
            openai_dropdown_visible = False
        else:
            openai_status_text = "ℹ️ Enter OpenAI API Key to enable."
            openai_dropdown_visible = False

        openai_model_dropdown_update = gr.update(
            choices=openai_models,
            value=openai_default_model,
            visible=openai_dropdown_visible,
            interactive=openai_dropdown_visible and bool(openai_models)
        )

        # Available Engines Text
        engines_markdown = self._get_available_engines_markdown()

        # Return dictionary mapping components to updates
        return {
            self.ui_components["mistral_status"]: mistral_status_text,
            self.ui_components["openai_status"]: openai_status_text,
            self.ui_components["openai_model_select"]: openai_model_dropdown_update,
            self.ui_components["available_engines_text"]: engines_markdown,
            # Update textboxes to be empty after save/clear for security
            self.ui_components["mistral_key"]: "",
            self.ui_components["openai_key"]: "",
        }
    
    def _get_full_ui_update(self, mistral_status=gr.update(), openai_status=gr.update(), openai_model_select=gr.update(), available_engines_text=gr.update(), mistral_key=gr.update(), openai_key=gr.update()):
        """Helper to return a dictionary for all components, applying specific updates."""
        return {
            self.ui_components["mistral_status"]: mistral_status,
            self.ui_components["openai_status"]: openai_status,
            self.ui_components["openai_model_select"]: openai_model_select,
            self.ui_components["available_engines_text"]: available_engines_text,
            self.ui_components["mistral_key"]: mistral_key,
            self.ui_components["openai_key"]: openai_key,
        }

def create_api_keys_page(
    api_keys, # Shared state dictionary
    ocr_processor, # Shared OCR processor instance
    available_engines, # Shared list of available engines
    initialize_ocr_processor # Shared function to re-initialize
):
    """Creates the Gradio Blocks UI for the API Keys page."""
    with gr.Blocks() as api_keys_demo:
        gr.Markdown("# API Key Management")
        gr.Markdown("Configure API keys for different OCR engines.")
        gr.Markdown("Changes saved here will affect the available engines in the main OCR tab.")
        gr.Markdown("⚠️ **Security Note**: API keys are stored in memory and are not persisted when the server restarts.")

        # Define UI components for this page
        ui_components = {}

        with gr.Accordion("Mistral OCR", open=False):
            ui_components["mistral_status"] = gr.Markdown(label="Status", value="Checking...")
            with gr.Column():
                with gr.Group():
                    ui_components["mistral_key"] = gr.Textbox(
                        label="Mistral API Key",
                        placeholder="Enter your Mistral API key...",
                        type="password",
                        value="" # Never display saved keys
                    )
                    with gr.Row():
                        ui_components["mistral_clear_btn"] = gr.Button("Clear Key", variant="stop")
                        ui_components["mistral_save_btn"] = gr.Button("Save Mistral API Key", variant="primary")

        with gr.Accordion("OpenAI OCR", open=False):
            ui_components["openai_status"] = gr.Markdown(label="Status", value="Checking...")
            with gr.Column():
                with gr.Group():
                    ui_components["openai_key"] = gr.Textbox(
                        label="OpenAI API Key",
                        placeholder="Enter your OpenAI API key...",
                        type="password",
                        value=""  # Never display saved keys
                    )
                    # Add the model selection dropdown here
                    ui_components["openai_model_select"] = gr.Dropdown(
                        label="Select OpenAI Model",
                        choices=[], # Will be populated dynamically by interaction logic
                        value=None,
                        visible=False, # Initially hidden, shown if key is valid
                        interactive=True
                    )
                    with gr.Row():
                        ui_components["openai_clear_btn"] = gr.Button("Clear Key", variant="stop")
                        ui_components["openai_save_btn"] = gr.Button("Save OpenAI API Key", variant="primary")

        gr.Markdown("### Current Engine Status")
        # Display simple status here based on initialization
        ui_components["available_engines_text"] = gr.Markdown(value="Loading status...")

        # --- Instantiate interaction handler for this page ---
        api_key_interactions = APIKeysInteractions(
            api_keys=api_keys,
            ocr_processor=ocr_processor,
            available_engines=available_engines,
            initialize_ocr_processor=initialize_ocr_processor,
            ui_components=ui_components # Pass the dict of components defined above
        )

        # --- Wire up Event Handlers --- #
        
        # Define outputs for UI updates on this page
        api_page_outputs = [
            ui_components["mistral_status"],
            ui_components["openai_status"],
            ui_components["openai_model_select"],
            ui_components["available_engines_text"],
            ui_components["mistral_key"], # To clear the textbox
            ui_components["openai_key"], # To clear the textbox
        ]

        # Mistral Save
        ui_components["mistral_save_btn"].click(
            fn=api_key_interactions.save_api_key,
            inputs=[ui_components["mistral_key"], gr.Textbox(value="Mistral", visible=False)],
            outputs=api_page_outputs
        )
        # Mistral Clear
        ui_components["mistral_clear_btn"].click(
            fn=api_key_interactions.clear_api_key,
            inputs=[gr.Textbox(value="Mistral", visible=False)],
            outputs=api_page_outputs
        )
        # OpenAI Save
        ui_components["openai_save_btn"].click(
            fn=api_key_interactions.save_api_key,
            inputs=[ui_components["openai_key"], gr.Textbox(value="OpenAI", visible=False)],
            outputs=api_page_outputs
        )
        # OpenAI Clear
        ui_components["openai_clear_btn"].click(
            fn=api_key_interactions.clear_api_key,
            inputs=[gr.Textbox(value="OpenAI", visible=False)],
            outputs=api_page_outputs
        )

        # --- Initial UI Update on Page Load ---
        api_keys_demo.load(
            fn=api_key_interactions.update_api_page_ui,
            inputs=None,
            outputs=api_page_outputs
        )

    return api_keys_demo

# Add for standalone testing if desired
# if __name__ == "__main__":
#     # Need to mock or provide dummy shared state for standalone run
#     mock_api_keys = {"Mistral": "", "OpenAI": ""}
#     mock_available_engines = ["Tesseract"]
#     def mock_init(): print("Mock init called")
#     api_keys_page = create_api_keys_page(mock_api_keys, None, mock_available_engines, mock_init)
#     api_keys_page.launch() 