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
                            # OpenAI Model Selection (visible only when OpenAI is selected)
                            openai_model_select = gr.Dropdown(
                                choices=["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"],
                                value="gpt-4o",
                                label="OpenAI Model",
                                visible=False,
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

            # Placeholder Tabs
            with gr.Tab("Download"):
                gr.Markdown("### Download Options")
                gr.Markdown("Download functionality will be implemented here.")
                # We can move the existing download buttons/options here later if desired.

            with gr.Tab("Make a Resume"):
                gr.Markdown("### Document Summary & Explanation")
                with gr.Row():
                    # Placeholder for file/page counts
                    file_page_count_md = gr.Markdown("Processed Files: 0 | Total Pages: 0")
                with gr.Row():
                    # Button to trigger explanation
                    explain_btn = gr.Button("Explain Text", variant="primary")
                with gr.Row():
                    # Area to display the explanation
                    explanation_output_md = gr.Markdown("Click 'Explain Text' to generate a summary based on the processed content.", visible=True)

            with gr.Tab("Translate"):
                gr.Markdown("### Translation")
                gr.Markdown("Translation functionality will be implemented here.")

        # --- Store components in a dictionary for easy access ---
        ui_components = {
            "processed_results_state": processed_results_state,
            "file_input": file_input,
            "ocr_engine": ocr_engine,
            "openai_model_select": openai_model_select,
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
            "clear_confirmation_group": clear_confirmation_group,
            "download_group": download_group, # Add download group
            "result_group": result_group, # Add result group
            "download_trigger_components_group": download_trigger_components_group, # Add trigger group
            # --- Add new components for explanation ---
            "file_page_count_md": file_page_count_md,
            "explain_btn": explain_btn,
            "explanation_output_md": explanation_output_md
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
            ui_components["processed_results_state"],
            # --- Add update for file/page count ---
            ui_components["file_page_count_md"]
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

        # Show/hide OpenAI model selector based on OCR engine selection
        def toggle_openai_model_select(engine):
            if engine == "OpenAI":
                return gr.update(visible=True)
            else:
                return gr.update(visible=False)
        
        ocr_engine.change(
            fn=toggle_openai_model_select,
            inputs=[ocr_engine],
            outputs=[openai_model_select]
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

        # --- Clear Button Logic ---
        # Define the full list of outputs affected by clearing or showing confirmation
        clear_outputs_list = [
            # Components potentially cleared
            ui_components["file_input"],
            ui_components["ocr_engine"],
            ui_components["openai_model_select"],
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

        # --- Wire up Explain Text button ---
        explain_btn.click(
            fn=ui_interactions.generate_explanation, # New method in UIInteractions
            inputs=[processed_results_state],
            outputs=[
                ui_components["file_page_count_md"],
                ui_components["explanation_output_md"]
            ]
        )

        # --- Initial UI State Update ---
        # Update UI elements based on initial state on load
        # Needs to run after the UI is fully defined
        demo.load(
             fn=ui_interactions.update_main_page_ui, # Call the simplified method directly
             inputs=None,
             outputs=[ui_components["ocr_engine"]] # Target only the ocr_engine component
        )

    # Return the demo object and the components dictionary
    return demo, ui_components
