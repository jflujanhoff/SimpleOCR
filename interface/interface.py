import gradio as gr
from custom_theme import delite_theme
from functools import partial
import logging # Add logging if wrappers use it

# Import callback functions needed for wiring
from .process_ocr import ProcessOCR # Removed individual function imports
# Import the class, not individual functions
from .ui_interactions import UIInteractions

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
                with gr.Column():
                    with gr.Column():
                        # --- Upload Document(s) ---
                        gr.Markdown("Upload Document(s) to OCR")
                        with gr.Group():
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
                            clear_btn = gr.Button("Clear", variant="secondary", scale=1)
                            process_btn = gr.Button("Process Documents", variant="primary", scale=1) # Renamed slightly
                            
                        # Confirmation UI (initially hidden) - unchanged for now
                        with gr.Group(visible=False) as clear_confirmation_group: # Assign variable and set initial visibility
                            with gr.Row():
                                clear_confirm_msg = gr.Markdown(value="", visible=False, container=True)
                            
                            with gr.Row():
                                confirm_clear_btn = gr.Button("Confirm Clear", variant="stop", visible=False)
                                cancel_clear_btn = gr.Button("Cancel", variant="secondary", visible=False)


                    with gr.Column():
                        # --- New Result Selection and Download UI ---
                        gr.Markdown("Extracted Text & Download")
                        with gr.Group(visible=True) as result_group:
                            with gr.Group():
                                result_selector = gr.Dropdown(
                                    label="Select Processed File to View/Download",
                                    choices=[],
                                    value=None,
                                    interactive=True,
                                    visible=False # Initially hidden
                                )
                                with gr.Row():
                                    image_output = gr.Gallery(label="Document Pages Preview", visible=False) # Renamed, initially hidden
                                    md_output = gr.Markdown(label="Extracted Text", container=True, show_copy_button=True, value="Extracted Text will appear here", height=451)

                with gr.Column():
                    # Assign variable and set initial visibility
                    download_options_md = gr.Markdown("Download Options", visible=False)
                    with gr.Group(visible=False) as download_group:

                        with gr.Row():
                            download_format = gr.Radio(
                                choices=["txt", "md", "doc"],
                                value="txt",
                                label="Format",
                                interactive=True,
                                scale=1,
                                visible=False # Initially hidden
                            )
                        
                        # --- Change: Make File components visible but non-interactive ---
                        # Assign variable and set initial visibility
                        # Rename inner group to avoid conflict
                        with gr.Group(visible=False) as download_trigger_components_group:
                            with gr.Row():
                                single_download_trigger = gr.File(
                                    label="Selected File Download",
                                    visible=False, # Set back to False
                                    interactive=False
                                )
                                zip_download_trigger = gr.File(
                                    label="ZIP Archive Download",
                                    visible=False, # Set back to False
                                    interactive=False
                                )

                    with gr.Row():
                        download_selected_btn = gr.Button("Download Selected", variant="secondary", scale=1, visible=False) # Initially hidden
                        download_all_btn = gr.Button("Download All (ZIP)", variant="secondary", scale=1, visible=False) # Initially hidden


                                
            # API Keys Tab
            with gr.Tab("API Keys"):
                gr.Markdown("### Configure OCR API Keys")
                gr.Markdown("Enter your API keys for Mistral and OpenAI to enable their OCR engines. Keys are stored in memory only for the current session.")
                gr.Markdown("⚠️ **Security Note**: API keys are stored in memory and are not persisted when the server restarts.")

                with gr.Accordion("Mistral OCR", open=False):
                    mistral_status = gr.Markdown(label="Status", value="")
                    with gr.Column():
                        with gr.Group():
                            mistral_key = gr.Textbox(
                                label="Mistral API Key",
                                placeholder="Enter your Mistral API key...",
                                type="password",
                                value=""
                            )
                            with gr.Row():
                                mistral_clear_btn = gr.Button("Clear Key", variant="stop")
                                mistral_save_btn = gr.Button("Save Mistral API Key", variant="primary")

                with gr.Accordion("OpenAI OCR", open=False):
                    openai_status = gr.Markdown(label="Status", value="")
                    with gr.Column():
                        with gr.Group():
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
                                openai_clear_btn = gr.Button("Clear Key", variant="stop")
                                openai_save_btn = gr.Button("Save OpenAI API Key", variant="primary")

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
            "available_engines_text": available_engines_text,
            "clear_confirmation_group": clear_confirmation_group,
            "download_group": download_group, # Add download group
            "result_group": result_group, # Add result group
            "download_trigger_components_group": download_trigger_components_group # Add trigger group
        }

        # --- Instantiate UIInteractions (New) ---
        ui_interactions = UIInteractions(
            api_keys=api_keys,
            ocr_processor=ocr_processor,
            ui_components=ui_components,
            available_engines=available_engines, # Pass the live list reference
            initialize_ocr_processor=initialize_ocr_processor,
            # clear_output_directory=clear_output_directory # Pass the function
        )

        # --- Instantiate ProcessOCR (New) ---
        process_ocr_handler = ProcessOCR(
            ocr_processor=ocr_processor,
            available_engines=available_engines,
            ui_components=ui_components
        )

        # --- Wire Up Event Handlers (Moved from app.py) ---

        # Process button click
        outputs_process = [
            ui_components["result_group"], # Add result group here
            ui_components["result_selector"],
            ui_components["md_output"],
            ui_components["image_output"],
            ui_components["download_group"], # Add download group here
            ui_components["download_format"],
            ui_components["download_selected_btn"],
            ui_components["download_all_btn"],
            ui_components["download_options_md"],
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
            fn=process_ocr_handler.process_document, # Call the instance method directly
            inputs=inputs_process,
            outputs=outputs_process
        )

        # Update display when dropdown selection changes
        result_selector.change(
            fn=ui_interactions.display_selected_result, # Use instance method
            inputs=[result_selector, processed_results_state],
            outputs=[md_output, image_output]
        )

        # Trigger single file download button click
        download_selected_btn.click(
            fn=process_ocr_handler.download_selected_file, # Call the instance method directly
            inputs=[result_selector, download_format, processed_results_state],
            outputs=[
                single_download_trigger,
                ui_components["download_trigger_components_group"] # Also update parent group visibility
            ]
        )

        # Trigger zip file download button click
        download_all_btn.click(
            fn=process_ocr_handler.download_all_files, # Call the instance method directly
            inputs=[download_format, processed_results_state],
            outputs=[
                zip_download_trigger,
                ui_components["download_trigger_components_group"] # Also update parent group visibility
            ]
        )

        # API key save/clear buttons
        # Define the common outputs for UI updates after key changes
        update_ui_outputs = [
            ui_components["available_engines_text"],
            ui_components["ocr_engine"],
            ui_components["mistral_status"],
            ui_components["openai_status"],
            ui_components["openai_model_select"]
        ]

        # Wrapper to call the instance method for UI updates
        def run_update_all_ui_elements_wrapper():
            logger.debug("Wrapper called: Running ui_interactions.update_all_ui_elements()")
            # The ui_interactions instance holds references to api_keys, ocr_processor,
            # available_engines which should be updated by initialize_ocr_processor
            return ui_interactions.update_all_ui_elements()

        # Mistral Save
        mistral_save_btn.click(
            fn=ui_interactions.save_api_key, # Use instance method
            inputs=[mistral_key, gr.Textbox(value="Mistral", visible=False)], # Pass engine name
            outputs=[mistral_status]
        ).then(
            fn=run_update_all_ui_elements_wrapper,
            inputs=None,
            outputs=update_ui_outputs
        )

        # Mistral Clear
        mistral_clear_btn.click(
            fn=ui_interactions.clear_api_key, # Use instance method
            inputs=[gr.Textbox(value="Mistral", visible=False)], # Pass engine name
            outputs=[mistral_status]
        ).then(
            fn=run_update_all_ui_elements_wrapper,
            inputs=None,
            outputs=update_ui_outputs
        )

        # OpenAI Save
        openai_save_btn.click(
            fn=ui_interactions.save_api_key, # Use instance method
            inputs=[openai_key, gr.Textbox(value="OpenAI", visible=False)], # Pass engine name
            outputs=[openai_status]
        ).then(
            fn=run_update_all_ui_elements_wrapper,
            inputs=None,
            outputs=update_ui_outputs
        )

        # OpenAI Clear
        openai_clear_btn.click(
            fn=ui_interactions.clear_api_key, # Use instance method
            inputs=[gr.Textbox(value="OpenAI", visible=False)], # Pass engine name
            outputs=[openai_status]
        ).then(
            fn=run_update_all_ui_elements_wrapper,
            inputs=None,
            outputs=update_ui_outputs
        )

        # --- Clear Button Logic ---
        # Define the full list of outputs affected by clearing or showing confirmation
        clear_outputs_list = [
            # Components potentially cleared
            ui_components["file_input"],
            ui_components["ocr_engine"],
            ui_components["image_output"],
            ui_components["md_output"],
            ui_components["result_selector"],
            ui_components["download_group"], # Added download group here
            ui_components["download_format"],
            ui_components["download_selected_btn"],
            ui_components["download_all_btn"],
            ui_components["download_options_md"],
            ui_components["single_download_trigger"],
            ui_components["zip_download_trigger"],
            # Confirmation UI components
            ui_components["clear_confirmation_group"],
            ui_components["clear_confirm_msg"],
            ui_components["confirm_clear_btn"],
            ui_components["cancel_clear_btn"],
            # State component (must be last if method returns tuple(dict, state))
            ui_components["processed_results_state"]
        ]

        # Initial Clear button click
        clear_btn.click(
            fn=ui_interactions.handle_clear_click, # Use instance method directly
            inputs=[processed_results_state],
            outputs=clear_outputs_list # Use the comprehensive list
            # Note: Gradio maps the dict keys in the first element of the tuple
            # to the corresponding components in the outputs list, and the second
            # element of the tuple to the last component (the state).
        )

        # Confirm Clear button click
        confirm_clear_btn.click(
            fn=ui_interactions.clear_and_hide_confirmation, # Use instance method directly
            inputs=[processed_results_state],
            outputs=clear_outputs_list # Use the same comprehensive list
        )

        # Cancel Clear button click
        cancel_clear_btn.click(
            fn=ui_interactions.hide_confirmation, # Updated call back
            inputs=None,
            outputs=[
                ui_components["clear_confirmation_group"], # Added group
                ui_components["clear_confirm_msg"],
                ui_components["confirm_clear_btn"],
                ui_components["cancel_clear_btn"]
            ]
        )

        # --- Initial UI State Update ---
        # Update UI elements based on initial state on load
        # Needs to run after the UI is fully defined
        demo.load(
             fn=run_update_all_ui_elements_wrapper, # Use the wrapper to call instance method
             inputs=None,
             outputs=update_ui_outputs
        )

    # Return the demo object and the components dictionary
    return demo, ui_components
