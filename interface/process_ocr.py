import gradio as gr
import os
import secrets
import zipfile
import shutil
from pathlib import Path
import logging
from docx import Document # Assuming python-docx is installed or added to requirements
from docx.shared import Inches # Might be useful for image insertion later

# Import MAX_FILES
from variables import MAX_FILES

logger = logging.getLogger(__name__)

class ProcessOCR:
    def __init__(self, ocr_processor=None, available_engines=None, ui_components=None):
        """Initialize the ProcessOCR interface handler."""
        # Store references if needed, or perform other setup
        self.ocr_processor = ocr_processor
        self.available_engines = available_engines
        self.ui_components = ui_components
        # TODO: Consider if output_dir should be passed here or fetched from ocr_processor
        self.output_dir = getattr(ocr_processor, 'output_dir', None)
        if not self.output_dir:
            logger.warning("ProcessOCR initialized without a valid output directory from ocr_processor.")
        logger.info("ProcessOCR class initialized.")


    # --- Helper function to clear output directory ---
    def _clear_output_directory(self, output_dir_path_str=None):
        """Removes all files and subdirectories within the specified directory."""
        # Use instance output_dir if available and no specific path is given
        if output_dir_path_str is None:
            output_dir_path_str = self.output_dir

        if not output_dir_path_str:
            logger.warning("Output directory path is not set. Skipping cleanup.")
            return

        output_dir_path = Path(output_dir_path_str)
        logger.info(f"Attempting to clear output directory: {output_dir_path}")

        if output_dir_path.exists() and output_dir_path.is_dir():
            for item in output_dir_path.iterdir():
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                        logger.debug(f"Deleted file: {item}")
                    elif item.is_dir():
                        shutil.rmtree(item)
                        logger.debug(f"Deleted directory: {item}")
                except Exception as e:
                    logger.error(f"Error deleting item {item}: {e}", exc_info=True)
            logger.info(f"Successfully cleared output directory: {output_dir_path}")
        elif not output_dir_path.exists():
            logger.info(f"Output directory {output_dir_path} does not exist. No cleanup needed.")
        else:
            logger.warning(f"Path {output_dir_path} exists but is not a directory. Skipping cleanup.")

    # --- Helper function to create docx (text only for now) ---
    def _create_docx_file(self, text_content, output_path):
        """Creates a .docx file with the given text content."""
        try:
            document = Document()
            document.add_paragraph(text_content)
            # Future Enhancement: Could add logic here to insert images
            # image_paths = ... # Get image paths corresponding to text_content
            # for img_path in image_paths:
            #     if Path(img_path).exists():
            #         try:
            #             document.add_picture(img_path, width=Inches(6.0)) # Example width
            #         except Exception as img_e:
            #             logger.warning(f"Could not add image {img_path} to docx: {img_e}")
            document.save(output_path)
            logger.info(f"Successfully created DOCX file: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating DOCX file at {output_path}: {e}", exc_info=True)
            return False

    # --- Main OCR Processing Function --- #
    # TODO: Refactor to use self.ocr_processor, self.available_engines, self.ui_components if initialized
    def process_document(self, files, ocr_engine, selected_openai_model, current_results_state, ocr_processor=None, available_engines=None, ui_components=None):
        """Process a list of documents, update state, and UI components."""
        # Use instance attributes if arguments are not provided (prefer arguments if passed)
        ocr_processor = ocr_processor or self.ocr_processor
        available_engines = available_engines or self.available_engines
        ui_components = ui_components or self.ui_components

        # Basic check if essential components are available
        if not ocr_processor or not available_engines or not ui_components:
             logger.error("ProcessOCR.process_document called without necessary components (ocr_processor, available_engines, ui_components).")
             # Return error state for all UI components
             num_outputs = 11 # Count based on the return signature
             error_md = "Error: Interface components not initialized. Check server logs."
             # Need to construct the return tuple matching the expected output structure
             # This assumes ui_components has the expected keys, otherwise this will fail
             error_updates = {
                 ui_components["result_selector"]: gr.Dropdown(choices=[], value=None, visible=False),
                 ui_components["md_output"]: error_md,
                 ui_components["image_output"]: gr.update(value=None, visible=False),
                 ui_components["download_format"]: gr.Radio(visible=False),
                 ui_components["download_selected_btn"]: gr.Button(visible=False),
                 ui_components["download_all_btn"]: gr.Button(visible=False),
                 ui_components["download_options_md"]: gr.update(visible=False),
                 ui_components["single_download_trigger"]: gr.update(value=None, visible=False),
                 ui_components["zip_download_trigger"]: gr.update(value=None, visible=False)
             }
             # Check if current_results_state is passed correctly
             if isinstance(current_results_state, dict):
                 return (*error_updates.values(), current_results_state)
             else:
                 # Fallback if state is not as expected
                 logger.error("current_results_state is not a dict in process_document error path.")
                 return (*error_updates.values(), {"text": {}, "images": {}})


        logger.info(f"Received {len(files) if files else 0} file(s) for processing with engine {ocr_engine}")

        # --- Initialize UI update dictionary --- #
        initial_updates = {
            ui_components["result_selector"]: gr.Dropdown(choices=[], value=None, visible=False),
            ui_components["md_output"]: "Initializing...", # Changed initial message
            ui_components["image_output"]: gr.update(value=None, visible=False),
            ui_components["download_format"]: gr.Radio(visible=False),
            ui_components["download_selected_btn"]: gr.Button(visible=False),
            ui_components["download_all_btn"]: gr.Button(visible=False),
            ui_components["download_options_md"]: gr.update(visible=False),
            ui_components["single_download_trigger"]: gr.update(value=None, visible=False),
            ui_components["zip_download_trigger"]: gr.update(value=None, visible=False)
        }

        # --- Input Validation --- #
        if not files:
            initial_updates[ui_components["md_output"]] = "Error: No files uploaded."
            # Return the current state if no files
            return (*initial_updates.values(), current_results_state)

        # --- Check File Count Limit --- #
        if len(files) > MAX_FILES:
            error_msg = f"Error: Too many files uploaded. Maximum allowed is {MAX_FILES}. You uploaded {len(files)}."
            logger.warning(error_msg)
            gr.Warning(error_msg) # Display warning popup to user
            initial_updates[ui_components["md_output"]] = error_msg # Update markdown as well
            # Return the current state if too many files
            return (*initial_updates.values(), current_results_state)

        # --- Clear Output Directory Before Processing --- #
        # Use the instance's output_dir if available
        output_dir_to_clear = getattr(ocr_processor, 'output_dir', self.output_dir)
        if output_dir_to_clear:
             self._clear_output_directory(output_dir_to_clear)
        else:
            logger.warning("Output directory not available, cannot clear output directory.")


        processed_results = {"text": {}, "images": {}}
        errors_occurred = False
        error_messages = []

        # --- Pre-processing Checks --- #
        # Note: ocr_processor should be initialized before calling this method
        if ocr_processor is None:
            initial_updates[ui_components["md_output"]] = "Error: OCR processor is not initialized. Check server logs."
            logger.error("process_document called with uninitialized OCR processor.")
            return (*initial_updates.values(), current_results_state)

        if ocr_engine not in available_engines:
            initial_updates[ui_components["md_output"]] = f"Error: {ocr_engine} OCR is not available. Check API keys or server logs."
            return (*initial_updates.values(), current_results_state)

        if ocr_engine == "OpenAI" and not selected_openai_model:
            if not (ocr_processor and ocr_processor.available_openai_models):
                 initial_updates[ui_components["md_output"]] = "Error: OpenAI engine selected, but no models could be loaded."
            else:
                initial_updates[ui_components["md_output"]] = "Error: OpenAI engine selected, but no specific model chosen."
            return (*initial_updates.values(), current_results_state)

        # --- Process Each File --- #
        for file_obj in files:
            # Gradio File objects might have absolute paths, ensure we only use the filename part
            original_filename = Path(getattr(file_obj, 'name', f"unknown_file_{secrets.token_hex(4)}")).name
            logger.info(f"Processing file: {original_filename}")
            try:
                logger.info(f"[process_document callback] Before calling process_document for {original_filename}:")
                logger.info(f"  ocr_processor object: {ocr_processor}")
                mistral_engine_state = getattr(ocr_processor, 'mistral', 'Attribute not found')
                logger.info(f"  ocr_processor.mistral state: {mistral_engine_state}")

                _ , image_paths, result_text = ocr_processor.process_document(
                    file_obj, # Pass the file object (e.g., temp file path)
                    ocr_engine,
                    openai_model=selected_openai_model if ocr_engine == "OpenAI" else None
                )

                if result_text is not None and result_text.startswith("Error:"):
                    logger.error(f"Error processing {original_filename}: {result_text}")
                    errors_occurred = True
                    error_messages.append(f"- {original_filename}: {result_text}")
                    processed_results["text"][original_filename] = result_text
                    processed_results["images"][original_filename] = image_paths or []
                elif result_text is None:
                    logger.warning(f"No text extracted from {original_filename}.")
                    errors_occurred = True
                    error_msg = f"- {original_filename}: Could not extract text."
                    error_messages.append(error_msg)
                    processed_results["text"][original_filename] = "Error: Could not extract text."
                    processed_results["images"][original_filename] = image_paths or []
                else:
                    logger.info(f"Successfully processed {original_filename}. Text length: {len(result_text)}")
                    processed_results["text"][original_filename] = result_text
                    processed_results["images"][original_filename] = image_paths or []

            except Exception as e:
                error_msg = f"Error processing file {original_filename}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors_occurred = True
                error_messages.append(f"- {original_filename}: Processing failed unexpectedly. Check logs.")
                processed_results["text"][original_filename] = f"Error: Processing failed unexpectedly."
                processed_results["images"][original_filename] = []

        # --- Update UI Based on Results --- #
        final_md_output = ""
        final_image_output_update = gr.update(value=None, visible=False)
        final_dropdown_update = gr.Dropdown(choices=[], value=None, visible=False)
        final_download_format_update = gr.Radio(visible=True, interactive=True)
        final_dl_selected_btn_update = gr.Button(visible=True)
        final_dl_all_btn_update = gr.Button(visible=True)
        final_dl_options_md_update = gr.update(visible=False)
        final_download_group_update = gr.update(visible=False) # Initialize as hidden
        final_result_group_update = gr.update(visible=False) # Initialize result group as hidden

        processed_filenames = list(processed_results["text"].keys())

        if not processed_filenames:
            final_md_output = "Error: No files were processed successfully."
            if error_messages:
                 final_md_output += "\n\nErrors:\n" + "\n".join(error_messages)
            final_dl_options_md_update = gr.update(visible=False)
            # Ensure download buttons are hidden if nothing processed
            final_download_format_update = gr.Radio(visible=False)
            final_dl_selected_btn_update = gr.Button(visible=False)
            final_dl_all_btn_update = gr.Button(visible=False)
            # Keep final_download_group_update and final_result_group_update as hidden (already are)
        else:
            # Make result group visible since we have results
            final_result_group_update = gr.update(visible=True)
            # Also make the download group visible (buttons inside might still be hidden)
            final_download_group_update = gr.update(visible=True)

            first_filename = processed_filenames[0]
            # Use original filename as both label and value for simplicity
            dropdown_choices = processed_filenames
            # Ensure we don't try to display error messages as primary output
            first_file_result = processed_results["text"][first_filename]
            if first_file_result.startswith("Error:"):
                final_md_output = first_file_result # Display the error for the first file
            else:
                final_md_output = first_file_result

            first_file_images = processed_results["images"].get(first_filename, [])
            valid_display_paths = [p for p in first_file_images if p is not None and os.path.exists(p)]
            final_image_output_update = gr.update(value=valid_display_paths, visible=bool(valid_display_paths))

            final_dropdown_update = gr.Dropdown(
                choices=dropdown_choices,
                value=first_filename,
                label="Select Processed File to View/Download",
                interactive=True,
                visible=True
            )
            final_dl_options_md_update = gr.update(visible=True)

            # Only show download buttons if there's at least one non-error result
            has_successful_result = any(not res.startswith("Error:") for res in processed_results["text"].values())
            if not has_successful_result:
                # If no success, keep format selector and options text visible,
                # but hide the actual download buttons and the trigger explanation.
                final_dl_selected_btn_update = gr.Button(visible=False)
                final_dl_all_btn_update = gr.Button(visible=False)

        # Return the tuple matching outputs_process in interface.py
        # Ensure the order matches the outputs_process list in interface.py
        return (
            final_result_group_update,     # result_group (NEW)
            final_dropdown_update,           # result_selector
            final_md_output,               # md_output
            final_image_output_update,     # image_output
            final_download_group_update,   # download_group
            final_download_format_update,  # download_format
            final_dl_selected_btn_update,  # download_selected_btn
            final_dl_all_btn_update,       # download_all_btn
            final_dl_options_md_update,    # download_options_md
            gr.update(value=None, visible=False), # Reset single_download_trigger
            gr.update(value=None, visible=False), # Reset zip_download_trigger
            processed_results              # processed_results_state
        )


    # --- Download Handlers --- #
    def download_selected_file(self, selected_filename, format_type, current_results_state, ocr_processor=None):
        """Prepares a single file for download based on selected format."""
        ocr_processor = ocr_processor or self.ocr_processor
        output_dir = getattr(ocr_processor, 'output_dir', self.output_dir)
        # Default return value for failure/skip cases
        fail_return = (gr.update(value=None, visible=False), gr.update(visible=False))

        if not output_dir:
            logger.error("Output directory not configured for download.")
            gr.Error("Server configuration error: Output directory not set.")
            return fail_return # Return tuple

        if not selected_filename or not current_results_state or selected_filename not in current_results_state.get("text", {}):
            logger.warning(f"Download failed: Selected filename '{selected_filename}' not found in results state.")
            gr.Warning(f"Could not find result for '{selected_filename}'. Please process files first.")
            return fail_return # Return tuple

        text_content = current_results_state["text"][selected_filename]
        # Skip download if the result was an error message
        if text_content.startswith("Error:"):
             logger.warning(f"Download skipped: Result for '{selected_filename}' is an error.")
             gr.Info(f"Cannot download '{selected_filename}' as it contains an error message.")
             return fail_return # Return tuple

        # Base filename without extension
        base_filename = Path(selected_filename).stem
        # Define output path within the configured output directory
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True) # Ensure directory exists

        try:
            output_path = None
            if format_type == "txt":
                output_filename = f"{base_filename}.txt"
                output_path = output_dir_path / output_filename
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(text_content)
                logger.info(f"Prepared TXT file for download: {output_path}")

            elif format_type == "md":
                output_filename = f"{base_filename}.md"
                output_path = output_dir_path / output_filename
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(text_content) # For now, same as txt
                logger.info(f"Prepared MD file for download: {output_path}")

            elif format_type == "doc":
                output_filename = f"{base_filename}.docx"
                output_path = output_dir_path / output_filename
                if not self._create_docx_file(text_content, output_path):
                    gr.Error(f"Failed to create DOCX file for {selected_filename}.")
                    return fail_return # Return tuple on docx creation failure
                # If successful, output_path is set

            else:
                logger.error(f"Unsupported download format selected: {format_type}")
                gr.Error(f"Unsupported format '{format_type}'. Cannot download.")
                return fail_return # Return tuple

            # If we reach here and output_path is set, it means success
            if output_path and output_path.exists():
                return (
                    gr.update(value=str(output_path), visible=True),
                    gr.update(visible=True) # Make trigger group visible
                )
            else:
                 # Should not happen if logic is correct, but as a fallback
                 logger.error(f"File creation failed unexpectedly for {selected_filename} with format {format_type}")
                 gr.Error(f"Failed to prepare download for {selected_filename}.")
                 return fail_return

        except Exception as e:
            logger.error(f"Error preparing file '{selected_filename}' for download as {format_type}: {e}", exc_info=True)
            gr.Error(f"Failed to prepare download for {selected_filename}.")
            return fail_return # Return tuple

    def download_all_files(self, format_type, current_results_state, ocr_processor=None):
        """Prepares a ZIP archive containing all processed files in the selected format."""
        ocr_processor = ocr_processor or self.ocr_processor
        output_dir = getattr(ocr_processor, 'output_dir', self.output_dir)
        # Default return value for failure/skip cases
        fail_return = (gr.update(value=None, visible=False), gr.update(visible=False))

        if not output_dir:
            logger.error("Output directory not configured for ZIP download.")
            gr.Error("Server configuration error: Output directory not set.")
            return fail_return # Return tuple

        if not current_results_state or not current_results_state.get("text"):
            logger.warning("Download All failed: No results found in state.")
            gr.Info("No processed files available to download.")
            return fail_return # Return tuple

        output_dir_path = Path(output_dir)
        # Create a unique sub-directory for temporary files to avoid conflicts
        temp_zip_dir = output_dir_path / f"temp_zip_{secrets.token_hex(8)}"
        zip_filepath = None # Define zip_filepath outside try block
        try:
            temp_zip_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created temporary directory for zipping: {temp_zip_dir}")

            zip_filename = f"ocr_results_{format_type}_{secrets.token_hex(4)}.zip"
            zip_filepath = output_dir_path / zip_filename
            files_added_count = 0

            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for original_filename, text_content in current_results_state["text"].items():
                    # Skip files that resulted in errors
                    if text_content.startswith("Error:"):
                        logger.debug(f"Skipping error result for {original_filename} in zip.")
                        continue

                    base_filename = Path(original_filename).stem
                    temp_file_path = None # Path for the intermediate file
                    temp_filename = None # Define temp_filename here

                    try:
                        if format_type == "txt":
                            file_ext = "txt"
                            temp_filename = f"{base_filename}.{file_ext}"
                            temp_file_path = temp_zip_dir / temp_filename
                            with open(temp_file_path, "w", encoding="utf-8") as f:
                                f.write(text_content)

                        elif format_type == "md":
                            file_ext = "md"
                            temp_filename = f"{base_filename}.{file_ext}"
                            temp_file_path = temp_zip_dir / temp_filename
                            with open(temp_file_path, "w", encoding="utf-8") as f:
                                f.write(text_content) # Same as txt for now

                        elif format_type == "doc":
                            file_ext = "docx"
                            temp_filename = f"{base_filename}.{file_ext}"
                            temp_file_path = temp_zip_dir / temp_filename
                            if not self._create_docx_file(text_content, temp_file_path):
                                 logger.warning(f"Failed to create DOCX for {original_filename}. Skipping in zip.")
                                 continue # Skip adding this file to the zip

                        else:
                            logger.warning(f"Unsupported format '{format_type}' for file {original_filename}. Skipping in zip.")
                            continue # Skip unsupported formats

                        # Add the created file to the zip
                        if temp_file_path and temp_file_path.exists() and temp_filename:
                            zipf.write(temp_file_path, arcname=temp_filename)
                            logger.debug(f"Added {temp_filename} to zip.")
                            files_added_count += 1
                        else:
                            logger.warning(f"Temporary file {temp_file_path} not found or not created for {original_filename}. Not added to zip.")

                    except Exception as file_e:
                        logger.error(f"Error processing file {original_filename} for zip archive: {file_e}", exc_info=True)
                        # Optionally continue to try other files

            if files_added_count > 0:
                logger.info(f"Created ZIP archive with {files_added_count} file(s): {zip_filepath}")
                return (
                    gr.update(value=str(zip_filepath), visible=True),
                    gr.update(visible=True) # Make trigger group visible
                )
            else:
                logger.warning("No valid files were added to the ZIP archive.")
                gr.Info("No valid results available to include in the download.")
                # Clean up empty zip file if created
                if zip_filepath and zip_filepath.exists():
                    try:
                        zip_filepath.unlink()
                    except OSError as del_e:
                        logger.error(f"Error deleting empty zip file {zip_filepath}: {del_e}")
                return fail_return # Return tuple

        except Exception as e:
            logger.error(f"Error creating ZIP archive: {e}", exc_info=True)
            gr.Error("Failed to create ZIP archive.")
            return fail_return # Return tuple
        finally:
            # Clean up the temporary directory
            if temp_zip_dir.exists():
                try:
                    shutil.rmtree(temp_zip_dir)
                    logger.info(f"Cleaned up temporary zip directory: {temp_zip_dir}")
                except Exception as cleanup_e:
                    logger.error(f"Error cleaning up temporary zip directory {temp_zip_dir}: {cleanup_e}", exc_info=True)


# --- Standalone UI Update Functions (Consider moving to UIInteractions or keeping separate) ---
# These were likely intended to be called directly if ProcessOCR wasn't handling UI updates,
# but currently, process_document returns all necessary UI updates.
# Keeping them commented out or removing them might be cleaner unless used elsewhere.

# def update_output_display(selected_filename, current_results_state):
#     """Updates the markdown and image preview based on dropdown selection."""
#     # This logic is now handled within UIInteractions.display_selected_result
#     pass

# def get_ui_components_dict(*args):
#     """Helper to create a dictionary from UI component references."""
#     # This seems redundant if ui_components is managed correctly in interface.py
#     pass

# Example of how clear_output_directory might be used if passed separately
# def clear_output_directory(output_dir):
#     path = Path(output_dir)
#     if path.exists() and path.is_dir():
#         logger.info(f"Clearing output directory: {output_dir}")
#         # ... (implementation as in _clear_output_directory)
#     else:
#         logger.warning(f"Cannot clear non-existent or non-directory path: {output_dir}")
