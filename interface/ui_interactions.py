import gradio as gr
import logging
# import openai # No longer needed for validation here
import os
from pathlib import Path # Needed for clear_ocr_fields
# from openai import OpenAI # No longer needed for validation here

# Assuming Mistral client might be needed for validation if added later
# from mistralai.client import MistralClient
# Assuming clear_output_directory is passed in __init__
# from .process_ocr import clear_output_directory # Keep if not passed

logger = logging.getLogger(__name__)

# Explanation prompt template
# Use a standard string and explicitly add newlines
EXPLANATION_PROMPT_TEMPLATE = ( # Wrap in parentheses for readability
    "Act as an expert communicator skilled at simplifying complex information. "
    "I will provide you with content from a file below. Your task is to:\n\n"
    "1.  **Identify the Core Subject:** What is this file fundamentally about?\n"
    "2.  **Extract Key Information:** What are the most crucial pieces of information, findings, or instructions?\n"
    "3.  **Simplify the Language:** Rewrite these points using everyday words. Imagine you are explaining it to someone completely unfamiliar with this topic or field.\n"
    "4.  **Explain Necessary Jargon:** If technical terms are unavoidable for accuracy, define them briefly in simple terms.\n"
    "5.  **Summarize Concisely:** Provide a brief summary that captures the essence of the file's content.\n\n"
    "Focus on clarity and accuracy, ensuring the main message is not lost.\n\n"
    "**File Content:**\n"
    "---\n"
    "{file_content}\n"
    "---"
)

class UIInteractions:
    """Handles UI interactions and state updates for the Gradio interface."""

    def __init__(self, api_keys, ocr_processor, ui_components, available_engines, initialize_ocr_processor):
        """
        Initializes the UIInteractions class with necessary dependencies.

        Args:
            api_keys (dict): Dictionary to store API keys (reference passed, but not used directly here anymore).
            ocr_processor: Instance of the OCR processor class (potentially used by other methods).
            ui_components (dict): Dictionary mapping names to Gradio components.
            available_engines (list): List of currently available OCR engine names (used to update OCR engine dropdown).
            initialize_ocr_processor (callable): Function to re-initialize the OCR processor (reference passed, but not used directly here anymore).
            # clear_output_directory (callable): Function to clear the output directory.
        """
        self.api_keys = api_keys # Keep reference for potential future use, but direct use removed
        self.ocr_processor = ocr_processor
        self.ui_components = ui_components
        self.available_engines = available_engines # Still needed
        self.initialize_ocr_processor = initialize_ocr_processor # Keep reference
        logger.info("UIInteractions initialized (API key methods removed).")

    # --- Helper Functions --- #

    # --- API Key Handlers REMOVED --- #
    # def save_api_key(...): ...
    # def clear_api_key(...): ...

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

    # --- Explanation Generator --- #

    def generate_explanation(self, current_results_state):
        """Generates a summary/explanation of the processed text using an LLM."""
        logger.info("Attempting to generate explanation...")

        if not current_results_state or not current_results_state.get("text"):
            logger.warning("No processed text found in state to explain.")
            return (
                "Processed Files: 0 | Total Pages: 0",
                "No processed text available to explain. Please process documents first."
            )

        # 1. Calculate counts and combine text
        file_count = len(current_results_state["text"])
        total_page_count = 0
        all_text_content = []
        for filename, pages in current_results_state["text"].items():
            if isinstance(pages, list): # Expecting list of strings per page
                 total_page_count += len(pages)
                 all_text_content.extend(pages) # Add all pages from this file
            else:
                 logger.warning(f"Unexpected data format for file '{filename}' text: {type(pages)}. Skipping for explanation.")
                 # Fallback: maybe it's a single string? Try adding it.
                 if isinstance(pages, str):
                     all_text_content.append(pages)
                     total_page_count += 1 # Assume 1 page if it's just a string

        combined_text = "\\n\\n".join(all_text_content).strip() # Join pages with double newline
        count_string = f"Processed Files: {file_count} | Total Pages: {total_page_count}"

        if not combined_text:
            logger.warning("Combined text is empty after processing state.")
            return (
                count_string,
                "No text content found in the processed files to explain."
            )

        # 2. Check for OpenAI API key
        openai_api_key = self.api_keys.get("OpenAI")
        if not openai_api_key:
            logger.warning("OpenAI API key not found.")
            return (
                count_string,
                "Explanation requires an OpenAI API key. Please configure it in the 'API Keys' tab."
            )

        # 3. Call OpenAI API
        try:
            logger.info(f"Calling OpenAI API to explain text ({len(combined_text)} characters)...")
            client = OpenAI(api_key=openai_api_key) # Use explicit import
            prompt = EXPLANATION_PROMPT_TEMPLATE.format(file_content=combined_text)

            # Consider chunking if combined_text is very large
            # For now, assume it fits within typical context limits

            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="gpt-4o-mini", # Or another suitable model like gpt-3.5-turbo
            )

            explanation = chat_completion.choices[0].message.content
            logger.info("Successfully generated explanation from OpenAI.")
            return (
                count_string,
                explanation.strip() # Return the count and the explanation
            )

        except openai.AuthenticationError:
            logger.error("OpenAI API authentication failed. Please check your key.")
            return (
                count_string,
                "Error: OpenAI API key is invalid. Please check it in the 'API Keys' tab."
            )
        except Exception as e:
            logger.error(f"Error calling OpenAI API for explanation: {str(e)}", exc_info=True)
            return (
                count_string,
                f"Error generating explanation: {str(e)}"
            )

    # --- General UI Update --- #

    def update_main_page_ui(self):
        """Updates UI elements on the main OCR page based on the current engine availability.

        Primarily updates the choices and value of the OCR engine selector.
        """
        # Refresh the available_engines list? No, rely on the list passed during init,
        # which should be the live list from app.py updated by initialize_ocr_processor.
        logger.debug(f"Updating main page UI. Current available engines: {self.available_engines}")

        # Determine default and choices for OCR engine dropdown
        choices = sorted(list(set(self.available_engines))) # Ensure unique and sorted
        if not choices:
            choices = ["Tesseract"] # Fallback if something went wrong
            logger.warning("No available engines found! Defaulting OCR engine list to Tesseract.")

        # Try to keep the current value if possible and still available, else default to first
        current_selection = self.ui_components["ocr_engine"].value # Get current UI value
        if current_selection in choices:
            value = current_selection
        else:
            value = choices[0]
            logger.info(f"Previous OCR engine '{current_selection}' not available. Defaulting to '{value}'.")

        ocr_engine_update = gr.update(choices=choices, value=value, interactive=bool(choices))

        # Return updates only for components on the main page
        # The output signature MUST match the `outputs` list in the `.load()` call in interface.py
        return ocr_engine_update # Only return the update for the ocr_engine component
