import gradio as gr
import logging
import openai
import os
from pathlib import Path # Needed for clear_ocr_fields

# Assuming Mistral client might be needed for validation if added later
# from mistralai.client import MistralClient

logger = logging.getLogger(__name__)

# --- Helper Functions --- #

# TODO: Pass available_engines as arg
def get_available_engines_markdown(available_engines):
    # Base the markdown on the *currently available* engines list
    lines = []
    if "Tesseract" in available_engines:
        lines.append("- Tesseract (✅ always available)")
    else:
        lines.append("- Tesseract (❌ failed to initialize)")

    easyocr_status = '✅ available' if 'EasyOCR' in available_engines else '❌ not available'
    lines.append(f"- EasyOCR ({easyocr_status})")

    mistral_status = '✅ available' if 'Mistral' in available_engines else '❌ not available'
    lines.append(f"- Mistral ({mistral_status})")

    openai_status = '✅ available' if 'OpenAI' in available_engines else '❌ not available'
    lines.append(f"- OpenAI ({openai_status})")
    return "\n".join(lines)

# --- API Key Handlers --- #

# TODO: Pass api_keys, initialize_ocr_processor, ocr_processor, available_engines as args
def save_api_key(api_key, engine, api_keys, initialize_ocr_processor, ocr_processor, available_engines):
    """Validate and save API key, reinitialize, and return status message."""
    if not api_key:
        return f"❓ No API key provided for {engine}. Please enter a valid key."

    logger.info(f"Attempting to save API key for {engine}")

    try:
        if engine == "OpenAI":
            try:
                temp_client = openai.OpenAI(api_key=api_key)
                temp_client.models.list()
                logger.info(f"OpenAI API key validation successful for key ending in ...")
            except openai.AuthenticationError:
                logger.warning(f"OpenAI API key validation failed (AuthenticationError) for key ending in ...")
                return f"❌ Invalid OpenAI API Key. Authentication failed."
            except Exception as e:
                logger.error(f"OpenAI API key validation failed for key ending in ...: {e}")
                return f"❌ OpenAI key validation failed: {str(e)}"

        logger.info(f"Saving API key for {engine}")
        api_keys[engine] = api_key # Modify the passed dictionary

        initialize_ocr_processor() # Call the passed function

        success = engine in available_engines # Check the passed list
        if success:
             status_message = f"✅ {engine} API key saved and engine initialized."
             # Access processor via argument
             if engine == "OpenAI" and ocr_processor and ocr_processor.available_openai_models:
                  status_message += f" Model list loaded (e.g., {ocr_processor.available_openai_models[0]})."
             elif engine == "OpenAI":
                  status_message += " Check logs for model loading details."
             return status_message
        else:
            logger.error(f"{engine} key saved but engine failed to initialize. Check logs for details.")
            if engine == "Mistral":
                return f"⚠️ Mistral API key saved, but engine initialization failed. Check server logs for details."
            else:
                api_keys[engine] = "" # Clear the key in the passed dict
                initialize_ocr_processor()
                return f"❌ Error: {engine} key failed post-initialization. Check logs."

    except Exception as e:
        logger.error(f"Error saving API key for {engine}: {str(e)}", exc_info=True)
        return f"❌ Unexpected error processing API key for {engine}: {str(e)}"

# TODO: Pass api_keys, initialize_ocr_processor as args
def clear_api_key(engine, api_keys, initialize_ocr_processor):
    """Clear the API key for the specified engine."""
    if engine in api_keys:
        api_keys[engine] = ""
        initialize_ocr_processor()
        logger.info(f"API key for {engine} has been cleared")
        return f"⚠️ {engine} API key has been cleared."
    else:
        return f"❓ Engine {engine} not found or doesn't use API keys."

# --- OCR Tab UI Handlers --- #

# TODO: Pass available_engines, ui_components as args
def clear_ocr_fields(current_results_state, available_engines, ui_components):
    """Clears the input and output fields in the OCR tab, including state."""
    logger.info("Clearing OCR fields and results state.")
    default_engine = "Tesseract" if "Tesseract" in available_engines else (available_engines[0] if available_engines else None)
    cleared_state = {"text": {}, "images": {}} # Reset state
    return {
        ui_components["file_input"]: None,
        ui_components["ocr_engine"]: default_engine,
        ui_components["image_output"]: gr.update(value=None, visible=False),
        ui_components["md_output"]: "Extracted Text will appear here",
        ui_components["result_selector"]: gr.Dropdown(choices=[], value=None, visible=False, interactive=False),
        ui_components["download_format"]: gr.Radio(value="txt", visible=False, interactive=False),
        ui_components["download_selected_btn"]: gr.Button(visible=False),
        ui_components["download_all_btn"]: gr.Button(visible=False),
        ui_components["download_options_md"]: gr.update(visible=False),
        ui_components["download_trigger_md"]: gr.update(visible=False),
        ui_components["single_download_trigger"]: gr.update(value=None, visible=False),
        ui_components["zip_download_trigger"]: gr.update(value=None, visible=False),
        # This key needs special handling in app.py as it updates gr.State
        ui_components["processed_results_state"]: cleared_state
    }

# TODO: Pass ui_components as args
def display_selected_result(selected_filename, current_results_state, ui_components):
    """Updates the markdown and image preview based on dropdown selection."""
    if not selected_filename or not current_results_state or selected_filename not in current_results_state["text"]:
        logger.warning(f"display_selected_result: Filename '{selected_filename}' not found in state.")
        return {
            ui_components["md_output"]: "Error: Could not load result for selected file.",
            ui_components["image_output"]: gr.update(value=None, visible=False)
        }

    text_result = current_results_state["text"][selected_filename]
    image_paths = current_results_state["images"].get(selected_filename, [])
    valid_display_paths = [p for p in image_paths if p is not None and os.path.exists(p)]

    logger.info(f"Displaying result for: {selected_filename}")
    return {
        ui_components["md_output"]: text_result,
        ui_components["image_output"]: gr.update(value=valid_display_paths, visible=bool(valid_display_paths))
    }

# --- Clear Confirmation Handlers --- #

# TODO: Pass ui_components as args
def show_confirmation(ui_components):
    """Returns updates dictionary to show the confirmation UI elements."""
    return {
        ui_components["clear_confirm_msg"]: gr.Markdown(value="⚠️ Results exist. Are you sure you want to clear everything?", visible=True),
        ui_components["confirm_clear_btn"]: gr.Button(visible=True),
        ui_components["cancel_clear_btn"]: gr.Button(visible=True)
    }

# TODO: Pass ui_components as args
def hide_confirmation(ui_components):
    """Returns updates dictionary to hide the confirmation UI elements."""
    return {
        ui_components["clear_confirm_msg"]: gr.Markdown(value="", visible=False),
        ui_components["confirm_clear_btn"]: gr.Button(visible=False),
        ui_components["cancel_clear_btn"]: gr.Button(visible=False)
    }

# TODO: Pass available_engines, ui_components, ocr_processor (for clear_output_directory) as args
# Need `clear_output_directory` imported or passed as well.
# For now, assume `clear_output_directory` is available globally or imported.
from .process_ocr import clear_output_directory # Updated relative import

def handle_clear_click(current_results_state, available_engines, ui_components, ocr_processor):
    """Handles the main Clear button click based on results state."""
    if current_results_state and current_results_state.get("text"):
        updates = show_confirmation(ui_components)
        # Add passthrough updates for all output components of clear_ocr_fields
        updates[ui_components["file_input"]] = gr.update()
        updates[ui_components["ocr_engine"]] = gr.update()
        updates[ui_components["image_output"]] = gr.update()
        updates[ui_components["md_output"]] = gr.update()
        updates[ui_components["result_selector"]] = gr.update()
        updates[ui_components["download_format"]] = gr.update()
        updates[ui_components["download_selected_btn"]] = gr.update()
        updates[ui_components["download_all_btn"]] = gr.update()
        updates[ui_components["download_options_md"]] = gr.update()
        updates[ui_components["download_trigger_md"]] = gr.update()
        updates[ui_components["single_download_trigger"]] = gr.update()
        updates[ui_components["zip_download_trigger"]] = gr.update()
        updates[ui_components["processed_results_state"]] = gr.update() # State passed through
        return updates # Return dictionary
    else:
        # Clear directly
        updates = clear_ocr_fields(current_results_state, available_engines, ui_components)
        updates.update(hide_confirmation(ui_components))
        # The state update is handled differently in Gradio, return it separately
        cleared_state = updates.pop(ui_components["processed_results_state"])
        # We need to return a tuple in the format expected by the Gradio outputs list
        # This requires knowing the exact order defined in app.py
        # For now, let's just return the dict and handle the state update separately
        return updates # Return dictionary - app.py needs to handle state

# TODO: Pass available_engines, ui_components, ocr_processor (for clear_output_directory) as args
def clear_and_hide_confirmation(current_results_state, available_engines, ui_components, ocr_processor):
    """Clears the main fields, state, hides the confirmation UI, and returns an updates dictionary."""
    logger.info("Confirm Clear clicked: Clearing fields and hiding confirmation.")

    if ocr_processor and ocr_processor.output_dir:
        clear_output_directory(ocr_processor.output_dir) # Use imported/passed function
    else:
        logger.warning("OCR processor or output directory not available during clear confirmation.")

    updates = clear_ocr_fields(current_results_state, available_engines, ui_components)
    updates.update(hide_confirmation(ui_components))
    # Return dictionary - app.py needs to handle state update separately
    return updates

# --- UI Update Function --- #

# TODO: Pass available_engines, ocr_processor as args
def update_all_ui_elements(available_engines, ocr_processor):
    """Updates engine list, radio choices, statuses, and OpenAI model dropdown based on current state."""
    logger.info(f"[update_all_ui_elements] Received available_engines: {available_engines}") # Added Log
    markdown_text = get_available_engines_markdown(available_engines)

    default_engine_choice = "Tesseract" if "Tesseract" in available_engines else (available_engines[0] if available_engines else None)
    # Use gr.update() for modifying existing components
    radio_update = gr.update( # Changed from gr.Radio.update(...)
        choices=available_engines,
        value=default_engine_choice,
        label="OCR Engine",
        interactive=True
    )

    mistral_status_text = ""
    # This check relies on api_keys, which isn't passed here yet. Needs adjustment.
    # Assuming api_keys might be accessed globally or passed additionally later.
    if "Mistral" in available_engines:
        mistral_status_text = "✅ Mistral Engine Available."
    # elif "Mistral" in api_keys and api_keys["Mistral"]:
    #      mistral_status_text = "❌ Mistral Engine Failed to Initialize. Check API Key/Logs."
    else:
         mistral_status_text = "ℹ️ Enter Mistral API Key to enable."

    openai_models = []
    openai_dropdown_visible = False
    openai_default_model = None
    openai_status_text = ""

    if "OpenAI" in available_engines:
         if ocr_processor and ocr_processor.available_openai_models:
             openai_models = ocr_processor.available_openai_models
             openai_dropdown_visible = True
             openai_default_model = openai_models[0]
             openai_status_text = f"✅ OpenAI Engine Available."
         else:
             openai_status_text = "⚠️ OpenAI Engine Initialized, but failed to load models (Check Logs). Using default model."
             openai_models = ["gpt-4o"] # Fallback list
             openai_default_model = openai_models[0]
             openai_dropdown_visible = True
    # elif "OpenAI" in api_keys and api_keys["OpenAI"]:
    #     openai_status_text = "❌ OpenAI Engine Failed to Initialize. Check API Key/Logs."
    else:
         openai_status_text = "ℹ️ Enter OpenAI API Key to enable."

    # Use gr.update() for modifying existing components
    openai_model_dropdown_update = gr.update( # Changed from gr.Dropdown.update(...)
        choices=openai_models,
        value=openai_default_model,
        visible=openai_dropdown_visible,
        interactive=openai_dropdown_visible
    )

    # Return updates for all affected components as a tuple in the correct order
    # for the Gradio outputs list:
    # [available_engines_text, ocr_engine, mistral_status, openai_status, openai_model_select]
    return_tuple = (
        markdown_text,
        radio_update,
        mistral_status_text,
        openai_status_text,
        openai_model_dropdown_update
    )
    logger.info(f"[update_all_ui_elements] Returning update tuple: {return_tuple}") # Added Log
    return return_tuple
