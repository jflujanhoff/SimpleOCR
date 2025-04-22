import gradio as gr
import logging
import openai
import os
from pathlib import Path # Needed for clear_ocr_fields

# Assuming Mistral client might be needed for validation if added later
# from mistralai.client import MistralClient
# Assuming clear_output_directory is passed in __init__
# from .process_ocr import clear_output_directory # Keep if not passed

logger = logging.getLogger(__name__)

class UIInteractions:
    """Handles UI interactions and state updates for the Gradio interface."""

    def __init__(self, api_keys, ocr_processor, ui_components, available_engines, initialize_ocr_processor):
        """
        Initializes the UIInteractions class with necessary dependencies.

        Args:
            api_keys (dict): Dictionary to store API keys.
            ocr_processor: Instance of the OCR processor class.
            ui_components (dict): Dictionary mapping names to Gradio components.
            available_engines (list): List of currently available OCR engine names.
            initialize_ocr_processor (callable): Function to re-initialize the OCR processor.
            # clear_output_directory (callable): Function to clear the output directory.
        """
        self.api_keys = api_keys
        self.ocr_processor = ocr_processor
        self.ui_components = ui_components
        self.available_engines = available_engines # Note: This might become stale if engines change after init
        self.initialize_ocr_processor = initialize_ocr_processor
        logger.info("UIInteractions initialized.")

    # --- Helper Functions --- #

    def _get_available_engines_markdown(self):
        """Generates markdown text listing available engines and their status."""
        # Base the markdown on the *currently available* engines list stored in self
        lines = []
        if "Tesseract" in self.available_engines:
            lines.append("- Tesseract (✅ always available)")
        else:
            lines.append("- Tesseract (❌ failed to initialize)") # Should not happen unless Tesseract is disabled

        easyocr_status = '✅ available' if 'EasyOCR' in self.available_engines else '❌ not available'
        lines.append(f"- EasyOCR ({easyocr_status})")

        mistral_status = '✅ available' if 'Mistral' in self.available_engines else '❌ not available'
        lines.append(f"- Mistral ({mistral_status})")

        openai_status = '✅ available' if 'OpenAI' in self.available_engines else '❌ not available'
        lines.append(f"- OpenAI ({openai_status})")
        return "\n".join(lines)

    # --- API Key Handlers --- #

    def save_api_key(self, api_key, engine):
        """Validate and save API key, reinitialize, and return status message."""
        if not api_key:
            return f"❓ No API key provided for {engine}. Please enter a valid key."

        logger.info(f"Attempting to save API key for {engine}")

        try:
            if engine == "OpenAI":
                try:
                    temp_client = openai.OpenAI(api_key=api_key)
                    temp_client.models.list()
                    logger.info(f"OpenAI API key validation successful for key ending in ...{api_key[-4:]}")
                except openai.AuthenticationError:
                    logger.warning(f"OpenAI API key validation failed (AuthenticationError) for key ending in ...{api_key[-4:]}")
                    return f"❌ Invalid OpenAI API Key. Authentication failed."
                except Exception as e:
                    logger.error(f"OpenAI API key validation failed for key ending in ...{api_key[-4:]}: {e}")
                    return f"❌ OpenAI key validation failed: {str(e)}"
            # Add Mistral validation if needed here

            logger.info(f"Saving API key for {engine}")
            self.api_keys[engine] = api_key # Modify instance dictionary

            self.initialize_ocr_processor() # Call instance method/passed function

            success = engine in self.available_engines # Check instance list (may need refresh?)
            if success:
                 status_message = f"✅ {engine} API key saved and engine initialized."
                 # Access processor via self
                 if engine == "OpenAI" and self.ocr_processor and self.ocr_processor.available_openai_models:
                      status_message += f" Model list loaded (e.g., {self.ocr_processor.available_openai_models[0]})."
                 elif engine == "OpenAI":
                      status_message += " Check logs for model loading details."
                 return status_message
            else:
                # If initialization failed despite valid key (potentially), log and inform user
                logger.error(f"{engine} key saved but engine failed to initialize. Check logs for details.")
                # Should we clear the key here? Maybe not, let re-init try again.
                # self.api_keys[engine] = "" # Clear the key? Reconsider this.
                # self.initialize_ocr_processor() # Re-init after clearing?
                return f"❌ Error: {engine} key saved, but engine failed post-initialization. Check logs."

        except Exception as e:
            logger.error(f"Error saving API key for {engine}: {str(e)}", exc_info=True)
            return f"❌ Unexpected error processing API key for {engine}: {str(e)}"

    def clear_api_key(self, engine):
        """Clear the API key for the specified engine."""
        if engine in self.api_keys:
            self.api_keys[engine] = ""
            self.initialize_ocr_processor() # Re-initialize after clearing
            logger.info(f"API key for {engine} has been cleared")
            return f"⚠️ {engine} API key has been cleared."
        else:
            # This case might indicate an engine that doesn't use keys or wasn't configured
            logger.warning(f"Attempted to clear API key for unknown or keyless engine: {engine}")
            return f"❓ Engine {engine} not found or doesn't use API keys."

    # --- OCR Tab UI Handlers --- #

    def clear_ocr_fields(self, current_results_state):
        """Clears the input and output fields in the OCR tab, including state.

        Returns:
            tuple: A tuple containing:
                - dict: Updates dictionary for Gradio components.
                - dict: The new (cleared) state for processed_results_state.
        """
        logger.info("Clearing OCR fields and results state.")
        # Determine default based on currently available engines
        default_engine = "Tesseract" if "Tesseract" in self.available_engines else (self.available_engines[0] if self.available_engines else None)
        cleared_state = {"text": {}, "images": {}} # Reset state
        updates = {
            self.ui_components["file_input"]: None,
            self.ui_components["ocr_engine"]: default_engine,
            self.ui_components["image_output"]: gr.update(value=None, visible=False),
            self.ui_components["md_output"]: "Extracted Text will appear here",
            self.ui_components["result_selector"]: gr.Dropdown(choices=[], value=None, visible=False, interactive=False),
            self.ui_components["download_format"]: gr.Radio(value="txt", visible=False, interactive=False),
            self.ui_components["download_selected_btn"]: gr.Button(visible=False),
            self.ui_components["download_all_btn"]: gr.Button(visible=False),
            self.ui_components["download_options_md"]: gr.update(visible=False),
            self.ui_components["single_download_trigger"]: gr.update(value=None, visible=False),
            self.ui_components["zip_download_trigger"]: gr.update(value=None, visible=False),
            self.ui_components["download_group"]: gr.update(visible=False), # Hide download group
            # NOTE: The state component itself is NOT included here.
            # It's returned separately.
        }
        return updates, cleared_state # Return components dict and new state dict

    def display_selected_result(self, selected_filename, current_results_state):
        """Updates the markdown and image preview based on dropdown selection."""
        if not selected_filename or not current_results_state or selected_filename not in current_results_state.get("text", {}):
            logger.warning(f"display_selected_result: Filename '{selected_filename}' not found in state.")
            # Check if state itself is the issue
            if not current_results_state:
                logger.warning("display_selected_result: current_results_state is empty or None.")
            elif "text" not in current_results_state:
                 logger.warning("display_selected_result: 'text' key missing in current_results_state.")
            elif selected_filename not in current_results_state["text"]:
                 logger.warning(f"display_selected_result: Filename '{selected_filename}' specifically not in state['text']. Keys: {list(current_results_state.get('text', {}).keys())}")

            return {
                self.ui_components["md_output"]: "Error: Could not load result for selected file.",
                self.ui_components["image_output"]: gr.update(value=None, visible=False)
            }

        text_result = current_results_state["text"][selected_filename]
        # Handle potential missing 'images' key or filename within 'images'
        image_paths = current_results_state.get("images", {}).get(selected_filename, [])
        valid_display_paths = [p for p in image_paths if p is not None and Path(p).exists()] # Use Pathlib

        logger.info(f"Displaying result for: {selected_filename}. Found {len(valid_display_paths)} valid images.")
        if not valid_display_paths and image_paths:
            logger.warning(f"Image paths found for {selected_filename} but none are valid: {image_paths}")


        return {
            self.ui_components["md_output"]: text_result,
            self.ui_components["image_output"]: gr.update(value=valid_display_paths, visible=bool(valid_display_paths))
        }

    # --- Clear Confirmation Handlers --- #

    def _show_confirmation(self):
        """Returns updates dictionary to show the confirmation UI elements."""
        return {
            self.ui_components["clear_confirm_msg"]: gr.Markdown(value="⚠️ Results exist. Are you sure you want to clear everything?", visible=True),
            self.ui_components["confirm_clear_btn"]: gr.Button(visible=True),
            self.ui_components["cancel_clear_btn"]: gr.Button(visible=True),
            self.ui_components["clear_confirmation_group"]: gr.update(visible=True) # Show group
        }

    def hide_confirmation(self):
        """Returns updates dictionary to hide the confirmation UI elements."""
        return {
            self.ui_components["clear_confirm_msg"]: gr.Markdown(value="", visible=False),
            self.ui_components["confirm_clear_btn"]: gr.Button(visible=False),
            self.ui_components["cancel_clear_btn"]: gr.Button(visible=False),
            self.ui_components["clear_confirmation_group"]: gr.update(visible=False) # Hide group
        }

    def handle_clear_click(self, current_results_state):
        """Handles the main Clear button click based on results state.

        Returns:
            tuple: A tuple containing exactly 18 update values, matching the
                   order expected by the listener in interface.py.
        """
        # Define the order of components expected by the listener (must match interface.py)
        # This list now includes the clear_confirmation_group and download_group.
        output_component_keys = [
            "file_input", "ocr_engine", "image_output", "md_output",
            "result_selector",
            "download_group", # Added download group key
            "download_format", "download_selected_btn", "download_all_btn",
            "download_options_md", # "download_trigger_md", <-- REMOVED
            "single_download_trigger", "zip_download_trigger",
            "clear_confirmation_group", # Added clear group key
            "clear_confirm_msg", "confirm_clear_btn", "cancel_clear_btn",
            "processed_results_state" # State must be last
        ]

        if current_results_state and current_results_state.get("text"):
            # --- Show Confirmation --- #
            logger.info("Clear clicked with existing results. Showing confirmation.")
            confirm_updates = self._show_confirmation() # This now includes the group update
            # We don't technically need hide_updates dict here anymore, as confirm_updates covers all confirm UI

            # Build the 18-element tuple
            output_values = []
            for key in output_component_keys[:-1]: # Exclude state for now
                component = self.ui_components[key]
                # Apply show/hide updates for confirm buttons/msg/group
                update_val = confirm_updates.get(component, gr.update()) # Default to no-change for non-confirm components
                output_values.append(update_val)

            # Add state update (no change)
            output_values.append(gr.update())

            logger.debug(f"Show confirmation returning tuple (length {len(output_values)}): {output_values}")
            return tuple(output_values)

        else:
            # --- Clear Directly --- #
            logger.info("Clear clicked with no results. Clearing directly.")
            component_updates, cleared_state = self.clear_ocr_fields(current_results_state)
            component_updates.update(self.hide_confirmation()) # Ensure confirmation UI (including group) is hidden

            # Build the 18-element tuple
            output_values = []
            for key in output_component_keys[:-1]: # Exclude state for now
                component = self.ui_components[key]
                # Get the update from the combined dictionary
                update_val = component_updates.get(component, gr.update()) # Default to no change if key missing
                output_values.append(update_val)

            # Add the new state value at the end
            output_values.append(cleared_state)

            logger.debug(f"Direct clear returning tuple (length {len(output_values)}): {output_values}")
            return tuple(output_values)


    def clear_and_hide_confirmation(self, current_results_state):
        """Clears the main fields, state, hides the confirmation UI.

        Returns:
            tuple: A tuple containing exactly 17 update values (after removal), matching the
                   order expected by the listener in interface.py.
        """
        logger.info("Confirm Clear clicked: Clearing fields and hiding confirmation.")

        # Define the order of components expected by the listener (must match interface.py)
        output_component_keys = [
            "file_input", "ocr_engine", "image_output", "md_output",
            "result_selector",
            "download_group", # Added download group key
            "download_format", "download_selected_btn", "download_all_btn",
            "download_options_md", # "download_trigger_md", <-- REMOVED
            "single_download_trigger", "zip_download_trigger",
            "clear_confirmation_group", # Added clear group key
            "clear_confirm_msg", "confirm_clear_btn", "cancel_clear_btn",
            "processed_results_state" # State must be last
        ]

        # Clear output directory first
        # TODO: Refactor clear_output_directory handling
        # The following assumes clear_output_directory is available via self.ocr_processor
        # This needs to be passed correctly during initialization.
        if hasattr(self, 'clear_output_directory') and callable(self.clear_output_directory):
             try:
                 if self.ocr_processor and self.ocr_processor.output_dir:
                     self.clear_output_directory(self.ocr_processor.output_dir)
                     logger.info(f"Cleared output directory: {self.ocr_processor.output_dir}")
                 else:
                      logger.warning("OCR processor or output directory not available, cannot clear.")
             except Exception as e:
                  # Catch potential errors if output_dir is None or clearing fails
                 logger.error(f"Error attempting to clear output directory: {e}", exc_info=True)
        elif self.ocr_processor and hasattr(self.ocr_processor, '_clear_output_directory') and callable(self.ocr_processor._clear_output_directory):
            # Fallback: Try calling the private method on the processor instance directly
            try:
                 self.ocr_processor._clear_output_directory()
                 logger.info(f"Cleared output directory using ocr_processor._clear_output_directory: {getattr(self.ocr_processor, 'output_dir', 'N/A')}")
            except Exception as e:
                 logger.error(f"Error attempting to clear output directory via processor: {e}", exc_info=True)
        else:
            logger.warning("clear_output_directory method not available on UIInteractions or ocr_processor. Skipping clear.")


        # Get component updates and new state from clear_ocr_fields
        component_updates, cleared_state = self.clear_ocr_fields(current_results_state)
        # Add updates to hide confirmation UI (including group)
        component_updates.update(self.hide_confirmation())

        # Build the 17-element tuple
        output_values = []
        for key in output_component_keys[:-1]: # Exclude state for now
            component = self.ui_components[key]
            # Get the update from the combined dictionary
            update_val = component_updates.get(component, gr.update()) # Default to no change if key missing
            output_values.append(update_val)

        # Add the new state value at the end
        output_values.append(cleared_state)

        logger.debug(f"Confirm clear returning tuple (length {len(output_values)}): {output_values}")
        return tuple(output_values)

    # --- UI Update Function --- #

    def update_all_ui_elements(self):
        """Updates engine list, radio choices, statuses, and OpenAI model dropdown based on current state."""
        # Important: Assumes self.available_engines and self.ocr_processor are up-to-date.
        # If engine availability changes dynamically, these need to be refreshed before calling this.
        logger.info(f"[update_all_ui_elements] Using available_engines: {self.available_engines}")
        markdown_text = self._get_available_engines_markdown() # Updated call

        default_engine_choice = "Tesseract" if "Tesseract" in self.available_engines else (self.available_engines[0] if self.available_engines else None)

        radio_update = gr.update(
            choices=self.available_engines,
            value=default_engine_choice,
            label="OCR Engine",
            interactive=bool(self.available_engines) # Disable if no engines
        )

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
             if self.ocr_processor and self.ocr_processor.available_openai_models:
                 openai_models = self.ocr_processor.available_openai_models
                 openai_dropdown_visible = True
                 # Try to keep current model if valid, else default
                 # current_model = self.ui_components["openai_model_select"].value # Need a way to get current value
                 # if current_model in openai_models:
                 #    openai_default_model = current_model
                 # else:
                 openai_default_model = openai_models[0] if openai_models else None
                 openai_status_text = f"✅ OpenAI Engine Available."
             else:
                 # Engine available but models failed to load
                 openai_status_text = "⚠️ OpenAI Initialized, but failed to load models (Check Logs)."
                 # Provide a default/fallback model if possible
                 openai_models = ["gpt-4o"] # Example fallback
                 openai_default_model = openai_models[0]
                 openai_dropdown_visible = True # Still show dropdown with fallback
        elif self.api_keys.get("OpenAI"): # Check if key exists even if engine failed
            openai_status_text = "❌ OpenAI Engine Failed to Initialize. Check API Key/Logs."
            openai_models = []
            openai_default_model = None
            openai_dropdown_visible = False
        else:
             openai_status_text = "ℹ️ Enter OpenAI API Key to enable."
             openai_models = []
             openai_default_model = None
             openai_dropdown_visible = False


        openai_model_dropdown_update = gr.update(
            choices=openai_models,
            value=openai_default_model,
            visible=openai_dropdown_visible,
            interactive=openai_dropdown_visible and bool(openai_models) # Interactive only if visible and has choices
        )

        # Return updates tuple matching Gradio outputs order in app.py
        # Example order (MUST match app.py):
        # [available_engines_text, ocr_engine_radio, mistral_status_md, openai_status_md, openai_model_select_dropdown]
        return_tuple = (
            markdown_text,
            radio_update,
            mistral_status_text,
            openai_status_text,
            openai_model_dropdown_update
        )
        logger.info(f"[update_all_ui_elements] Returning update tuple: {return_tuple}")
        return return_tuple
