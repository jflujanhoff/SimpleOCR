import gradio as gr
from custom_theme import delite_theme
from functools import partial
import logging # Add logging if wrappers use it

# Import variables
from variables import MAX_FILES

# Import callback functions needed for wiring
from .process_ocr import (
    process_document,
    download_selected_file,
    download_all_files,
    clear_output_directory # May be needed by clear wrappers
)
from .ui_interactions import (
    save_api_key,
    clear_api_key,
    display_selected_result,
    show_confirmation,
    hide_confirmation,
    handle_clear_click,
    clear_and_hide_confirmation,
    update_all_ui_elements
)

logger = logging.getLogger(__name__) # Add logger if needed

def create_interface(
    # Dependencies passed from app.py
    initial_available_engines,
    ocr_processor, # The processor instance (can be None initially)
    api_keys, # The global api_keys dictionary
    available_engines, # The global available_engines list
    initialize_ocr_processor # The function to re-initialize
):
    """Creates the Gradio interface Blocks, wires events, and returns the demo object and UI components."""

    with gr.Blocks(theme=delite_theme) as demo:
        gr.Markdown("# Document OCR")
        gr.Markdown("Upload a document (PDF or image) to extract text using OCR.")

        # State is defined here
        processed_results_state = gr.State({"text": {}, "images": {}})

        with gr.Tabs():
            # OCR Tab
            with gr.Tab("OCR"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("Upload Document(s) to OCR")
                        # --- Allow multiple files ---
                        file_input = gr.File(label="Upload Document(s)", file_count="multiple")
                        # Initialize Radio button with currently available engines
                        ocr_engine = gr.Radio(
                            choices=initial_available_engines,
                            value=initial_available_engines[0] if initial_available_engines else None,
                            label="OCR Engine",
                            interactive=True
                        )
                        # Main action buttons
                        with gr.Row():
                            process_btn = gr.Button("Process Documents", variant="primary", scale=1) # Renamed slightly
                            clear_btn = gr.Button("Clear", variant="secondary", scale=1)

                        # Confirmation UI (initially hidden) - unchanged for now
                        clear_confirm_msg = gr.Markdown(value="", visible=False)
                        confirm_clear_btn = gr.Button("Confirm Clear", variant="stop", visible=False)
                        cancel_clear_btn = gr.Button("Cancel", variant="secondary", visible=False)
                        with gr.Row(): # Contains the confirmation message
                            clear_confirm_msg
                        with gr.Row(): # Contains the confirmation buttons
                            confirm_clear_btn
                            cancel_clear_btn

                        image_output = gr.Gallery(label="Document Pages Preview", visible=False) # Renamed, initially hidden

                    with gr.Column():
                        # --- New Result Selection and Download UI ---
                        gr.Markdown("Extracted Text & Download")
                        result_selector = gr.Dropdown(
                            label="Select Processed File to View/Download",
                            choices=[],
                            value=None,
                            interactive=True,
                            visible=False # Initially hidden
                        )
                        md_output = gr.Markdown(label="Extracted Text", container=True, show_copy_button=True, value="Extracted Text will appear here")

                        # Assign variable and set initial visibility
                        download_options_md = gr.Markdown("Download Options", visible=False)
                        with gr.Row():
                            download_format = gr.Radio(
                                choices=["txt", "md", "doc"],
                                value="txt",
                                label="Download Format",
                                interactive=True,
                                scale=1,
                                visible=False # Initially hidden
                            )
                        with gr.Row():
                            download_selected_btn = gr.Button("Download Selected", variant="secondary", scale=1, visible=False) # Initially hidden
                            download_all_btn = gr.Button("Download All (ZIP)", variant="secondary", scale=1, visible=False) # Initially hidden

                        # --- Change: Make File components visible but non-interactive ---
                        # Assign variable and set initial visibility
                        download_trigger_md = gr.Markdown("Download Trigger Area (ignore)", visible=False) # Add explanation for user
                        single_download_trigger = gr.File(
                            label="Selected File Download",
                            visible=False, # Initially hidden
                            interactive=False
                        )
                        zip_download_trigger = gr.File(
                            label="ZIP Archive Download",
                            visible=False, # Initially hidden
                            interactive=False
                        )

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
                # Update Markdown text using the helper function - will be populated by update_all_ui_elements
                available_engines_text = gr.Markdown(value="Loading available engines...") # Initial placeholder

        # --- Store components in a dictionary for easy access ---
        ui_components = {
            "processed_results_state": processed_results_state,
            "file_input": file_input,
            "ocr_engine": ocr_engine,
            "process_btn": process_btn,
            "clear_btn": clear_btn,
            "clear_confirm_msg": clear_confirm_msg,
            "confirm_clear_btn": confirm_clear_btn,
            "cancel_clear_btn": cancel_clear_btn,
            "image_output": image_output,
            "result_selector": result_selector,
            "md_output": md_output,
            "download_options_md": download_options_md,
            "download_format": download_format,
            "download_selected_btn": download_selected_btn,
            "download_all_btn": download_all_btn,
            "download_trigger_md": download_trigger_md,
            "single_download_trigger": single_download_trigger,
            "zip_download_trigger": zip_download_trigger,
            "mistral_status": mistral_status,
            "mistral_key": mistral_key,
            "mistral_save_btn": mistral_save_btn,
            "mistral_clear_btn": mistral_clear_btn,
            "openai_status": openai_status,
            "openai_key": openai_key,
            "openai_model_select": openai_model_select,
            "openai_save_btn": openai_save_btn,
            "openai_clear_btn": openai_clear_btn,
            "available_engines_text": available_engines_text
        }

        # --- Wire Up Event Handlers (Moved from app.py) ---

        # Process button click
        outputs_process = [
            ui_components["result_selector"],
            ui_components["md_output"],
            ui_components["image_output"],
            ui_components["download_format"],
            ui_components["download_selected_btn"],
            ui_components["download_all_btn"],
            ui_components["download_options_md"],
            ui_components["download_trigger_md"],
            ui_components["single_download_trigger"],
            ui_components["zip_download_trigger"],
            ui_components["processed_results_state"]
        ]
        inputs_process = [
            ui_components["file_input"],
            ui_components["ocr_engine"],
            ui_components["openai_model_select"],
            ui_components["processed_results_state"]
        ]
        # Use dependencies passed to create_interface
        process_btn.click(
            fn=partial(process_document, ocr_processor=ocr_processor, available_engines=available_engines, ui_components=ui_components),
            inputs=inputs_process,
            outputs=outputs_process
        )

        # Update display when dropdown selection changes
        result_selector.change(
            fn=partial(display_selected_result, ui_components=ui_components),
            inputs=[result_selector, processed_results_state],
            outputs=[md_output, image_output]
        )

        # Trigger single file download button click
        download_selected_btn.click(
            fn=partial(download_selected_file, ocr_processor=ocr_processor),
            inputs=[result_selector, download_format, processed_results_state],
            outputs=[single_download_trigger]
        )

        # Trigger zip file download button click
        download_all_btn.click(
            fn=partial(download_all_files, ocr_processor=ocr_processor),
            inputs=[download_format, processed_results_state],
            outputs=[zip_download_trigger]
        )

        # API key save/clear buttons
        update_ui_outputs = [
            ui_components["available_engines_text"],
            ui_components["ocr_engine"],
            ui_components["mistral_status"],
            ui_components["openai_status"],
            ui_components["openai_model_select"]
        ]

        # Create partials using passed-in dependencies
        partial_save_key = partial(save_api_key,
                                   api_keys=api_keys,
                                   initialize_ocr_processor=initialize_ocr_processor,
                                   ocr_processor=ocr_processor,
                                   available_engines=available_engines)

        partial_clear_key = partial(clear_api_key,
                                    api_keys=api_keys,
                                    initialize_ocr_processor=initialize_ocr_processor)

        # Wrapper needed for .then() to get current state
        def run_update_all_ui_elements_wrapper():
             # This wrapper ensures the function uses the *current* state
             # of passed dependencies (like available_engines which is mutable list)
             # or refreshed ocr_processor instance when called by .then()
             # It assumes update_all_ui_elements can handle ocr_processor being None
             logger.info(f"[Wrapper] Running update_all_ui_elements. Current available_engines: {available_engines}") # Added Log
             update_tuple = update_all_ui_elements(
                 available_engines=available_engines,
                 ocr_processor=ocr_processor,
                 # Pass api_keys if needed by update_all_ui_elements
                 # api_keys=api_keys
             )
             logger.info(f"[Wrapper] update_all_ui_elements returned: {update_tuple}") # Added Log
             return update_tuple

        mistral_save_btn.click(
            fn=partial_save_key,
            inputs=[mistral_key, gr.Text(value="Mistral", visible=False)],
            outputs=[mistral_status]
        ).then(
            fn=run_update_all_ui_elements_wrapper, # Use wrapper
            outputs=update_ui_outputs
        ).then(
            fn=lambda: "", outputs=[mistral_key]
        )

        mistral_clear_btn.click(
            fn=partial_clear_key,
            inputs=[gr.Text(value="Mistral", visible=False)],
            outputs=[mistral_status]
        ).then(
            fn=run_update_all_ui_elements_wrapper,
            outputs=update_ui_outputs
        ).then(
            fn=lambda: "", outputs=[mistral_key]
        )

        openai_save_btn.click(
            fn=partial_save_key,
            inputs=[openai_key, gr.Text(value="OpenAI", visible=False)],
            outputs=[openai_status]
        ).then(
            fn=run_update_all_ui_elements_wrapper,
            outputs=update_ui_outputs
        ).then(
            fn=lambda: "", outputs=[openai_key]
        )

        openai_clear_btn.click(
            fn=partial_clear_key,
            inputs=[gr.Text(value="OpenAI", visible=False)],
            outputs=[openai_status]
        ).then(
            fn=run_update_all_ui_elements_wrapper,
            outputs=update_ui_outputs
        ).then(
            fn=lambda: "", outputs=[openai_key]
        )

        # --- Clear Confirmation Handlers --- (Keep wrappers for now)
        clear_outputs_ordered = [
            ui_components["file_input"], ui_components["ocr_engine"], ui_components["image_output"],
            ui_components["md_output"], ui_components["result_selector"], ui_components["download_format"],
            ui_components["download_selected_btn"], ui_components["download_all_btn"],
            ui_components["download_options_md"], ui_components["download_trigger_md"],
            ui_components["single_download_trigger"], ui_components["zip_download_trigger"],
            ui_components["clear_confirm_msg"], ui_components["confirm_clear_btn"],
            ui_components["cancel_clear_btn"],
            processed_results_state # State MUST BE LAST
        ]

        # Wrapper functions moved inside create_interface scope
        def handle_clear_click_wrapper(current_results_state_val):
            updates = handle_clear_click(
                current_results_state=current_results_state_val,
                available_engines=available_engines,
                ui_components=ui_components,
                ocr_processor=ocr_processor,
                # Pass clear_output_directory if needed by the handler
                # clear_output_directory_func=clear_output_directory
            )
            output_values = []
            for comp in clear_outputs_ordered:
                if comp == processed_results_state:
                     output_values.append(updates.get(comp, gr.update()))
                else:
                    output_values.append(updates.get(comp, gr.update()))
            return tuple(output_values)

        def clear_and_hide_confirmation_wrapper(current_results_state_val):
            updates = clear_and_hide_confirmation(
                current_results_state=current_results_state_val,
                available_engines=available_engines,
                ui_components=ui_components,
                ocr_processor=ocr_processor,
                # Pass clear_output_directory if needed
                # clear_output_directory_func=clear_output_directory
            )
            output_values = []
            for comp in clear_outputs_ordered:
                if comp == processed_results_state:
                     output_values.append(updates.get(comp, {"text": {}, "images": {}}))
                else:
                    output_values.append(updates.get(comp, gr.update()))
            return tuple(output_values)

        clear_btn.click(
            fn=handle_clear_click_wrapper,
            inputs=[processed_results_state],
            outputs=clear_outputs_ordered
        )

        confirm_clear_btn.click(
            fn=clear_and_hide_confirmation_wrapper,
            inputs=[processed_results_state],
            outputs=clear_outputs_ordered
        )

        cancel_clear_btn.click(
            fn=partial(hide_confirmation, ui_components=ui_components),
            inputs=[],
            outputs=[
                ui_components["clear_confirm_msg"],
                ui_components["confirm_clear_btn"],
                ui_components["cancel_clear_btn"]
            ]
        )

        # Startup event
        demo.load(
            fn=run_update_all_ui_elements_wrapper, # Use wrapper
            outputs=update_ui_outputs
        )

    # Return the demo object and the UI components dictionary
    return demo, ui_components
