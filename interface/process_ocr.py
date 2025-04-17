import gradio as gr
import os
import secrets
import zipfile
import shutil
from pathlib import Path
import logging
from docx import Document # Assuming python-docx is installed or added to requirements

# Import MAX_FILES
from variables import MAX_FILES

logger = logging.getLogger(__name__)

# --- Helper function to clear output directory --- # TODO: Pass ocr_processor.output_dir
def clear_output_directory(output_dir_path_str):
    """Removes all files and subdirectories within the specified directory."""
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


# --- Main OCR Processing Function --- #
# TODO: Pass ocr_processor, available_engines, ui_components as args
def process_document(files, ocr_engine, selected_openai_model, current_results_state, ocr_processor, available_engines, ui_components):
    """Process a list of documents, update state, and UI components."""
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
        ui_components["download_trigger_md"]: gr.update(visible=False),
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
    if ocr_processor and ocr_processor.output_dir:
        clear_output_directory(ocr_processor.output_dir)
    else:
        logger.warning("OCR processor or output directory not available, cannot clear output directory.")

    processed_results = {"text": {}, "images": {}}
    errors_occurred = False
    error_messages = []

    # --- Pre-processing Checks --- #
    # Note: ocr_processor initialization should happen in app.py
    if ocr_processor is None:
        # Attempt recovery - This might be better handled before calling this function
        # initialize_ocr_processor() # Can't call directly, should be passed or handled in app.py
        # if ocr_processor is None:
        initial_updates[ui_components["md_output"]] = "Error: OCR processor is not initialized. Check server logs."
        logger.error("process_document called with uninitialized OCR processor.")
        return (*initial_updates.values(), current_results_state)
        # logger.warning("OCR processor was None, attempted re-initialization.")

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
        original_filename = Path(file_obj.name).name # Use pathlib for robust name extraction
        logger.info(f"Processing file: {original_filename}")
        try:
            logger.info(f"[process_document callback] Before calling process_document for {original_filename}:")
            logger.info(f"  ocr_processor object: {ocr_processor}")
            mistral_engine_state = getattr(ocr_processor, 'mistral', 'Attribute not found')
            logger.info(f"  ocr_processor.mistral state: {mistral_engine_state}")

            _ , image_paths, result_text = ocr_processor.process_document(
                file_obj,
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
    final_dl_trigger_md_update = gr.update(visible=False)

    processed_filenames = list(processed_results["text"].keys())

    if not processed_filenames:
        final_md_output = "Error: No files were processed successfully."
        if error_messages:
             final_md_output += "\n\nErrors:\n" + "\n".join(error_messages)
        final_dl_options_md_update = gr.update(visible=False)
        final_dl_trigger_md_update = gr.update(visible=False)
    else:
        first_filename = processed_filenames[0]
        dropdown_choices = [(f"{Path(fn).stem}.md", fn) for fn in processed_filenames]
        final_md_output = processed_results["text"][first_filename]

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
        final_dl_trigger_md_update = gr.update(visible=True)

        if errors_occurred:
            error_summary = f"**Warning:** Processing completed with errors for some files:\n" + "\n".join(error_messages) + "\n\n---\n\n"
            final_md_output = error_summary + final_md_output

    final_single_dl_trigger_update = gr.update(visible=False)
    final_zip_dl_trigger_update = gr.update(visible=False)

    return (
        final_dropdown_update,              # result_selector
        final_md_output,                  # md_output
        final_image_output_update,        # image_output
        final_download_format_update,     # download_format
        final_dl_selected_btn_update,     # download_selected_btn
        final_dl_all_btn_update,          # download_all_btn
        final_dl_options_md_update,       # download_options_md
        final_dl_trigger_md_update,       # download_trigger_md
        final_single_dl_trigger_update,   # single_download_trigger
        final_zip_dl_trigger_update,      # zip_download_trigger
        processed_results                 # processed_results_state (new state)
    )

# --- Download Functions --- #

# TODO: Pass ocr_processor as arg
def download_selected_file(selected_filename, format_type, current_results_state, ocr_processor):
    """Generates a file for the selected document and returns its path for download."""
    logger.info(f"Request to download '{selected_filename}' as '{format_type}'")
    if not ocr_processor or not ocr_processor.output_dir:
        logger.error("Download failed: OCR processor or output directory not configured.")
        gr.Error("Download failed: Output directory not configured.")
        return gr.update(visible=False)

    if not selected_filename or selected_filename not in current_results_state["text"]:
        logger.error(f"Download failed: Filename '{selected_filename}' not found in results.")
        gr.Warning(f"Cannot download: Result for '{selected_filename}' not found.")
        return gr.update(visible=False)

    result_text = current_results_state["text"][selected_filename]
    if result_text.startswith("Error:"):
        logger.warning(f"Attempting to download a file with processing errors: {selected_filename}")
        gr.Warning(f"Cannot download: '{selected_filename}' had processing errors.")
        return gr.update(visible=False)

    try:
        # Assume download_ocr_result exists in ocr_processor
        # If not, we need to reimplement the logic here
        if hasattr(ocr_processor, 'download_ocr_result'):
            download_path = ocr_processor.download_ocr_result(result_text, format_type, original_filename=selected_filename)
        else:
             # Basic implementation if method doesn't exist on processor
             output_dir = Path(ocr_processor.output_dir)
             output_dir.mkdir(parents=True, exist_ok=True)
             base_name = Path(selected_filename).stem
             safe_base_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in base_name)
             download_filename = f"{safe_base_name}.{format_type}"
             download_path = output_dir / download_filename

             if format_type == 'txt' or format_type == 'md':
                 with open(download_path, 'w', encoding='utf-8') as f:
                     f.write(result_text)
             elif format_type == 'doc':
                 try:
                    document = Document()
                    document.add_paragraph(result_text)
                    document.save(download_path)
                 except ImportError:
                    logger.error("python-docx not installed. Cannot create .doc file.")
                    gr.Error("Cannot create .doc file: python-docx package is missing.")
                    return gr.update(visible=False)
                 except Exception as docx_e:
                    logger.error(f"Failed to create .doc for {selected_filename}: {docx_e}", exc_info=True)
                    gr.Error(f"Failed to create .doc file for {selected_filename}.")
                    return gr.update(visible=False)
             else:
                 logger.error(f"Unsupported download format: {format_type}")
                 gr.Error(f"Unsupported download format: {format_type}")
                 return gr.update(visible=False)

        if download_path and os.path.exists(download_path):
            logger.info(f"Prepared file for download: {download_path}")
            return gr.update(value=download_path, visible=True)
        else:
            logger.error(f"Failed to create download file for {selected_filename}. Path: {download_path}")
            gr.Error(f"Failed to create download file for {selected_filename}.")
            return gr.update(visible=False)
    except Exception as e:
        logger.error(f"Error during download preparation for {selected_filename}: {e}", exc_info=True)
        gr.Error(f"Error creating download for {selected_filename}: {e}")
        return gr.update(visible=False)

# TODO: Pass ocr_processor as arg
def download_all_files(format_type, current_results_state, ocr_processor):
    """Generates files for all results, zips them, and returns the zip path."""
    logger.info(f"Request to download all results as '{format_type}' in a ZIP archive.")

    if not ocr_processor or not ocr_processor.output_dir:
        logger.error("Download all failed: OCR processor or output directory not configured.")
        gr.Error("Download failed: Output directory not configured.")
        return gr.update(visible=False)

    filenames = list(current_results_state["text"].keys())
    if not filenames:
        logger.warning("Download all aborted: No results found.")
        gr.Warning("No processed files available to download.")
        return gr.update(visible=False)

    output_dir = Path(ocr_processor.output_dir)
    temp_dir = output_dir / f"temp_zip_{secrets.token_hex(4)}"
    zip_path = output_dir / f"ocr_results_{secrets.token_hex(8)}.zip"
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        files_to_zip = []
        files_with_errors = []

        for filename in filenames:
            result_text = current_results_state["text"][filename]
            if result_text.startswith("Error:"):
                logger.warning(f"Skipping file with error in zip: {filename}")
                files_with_errors.append(filename)
                continue

            try:
                base_name = Path(filename).stem
                safe_base_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in base_name)
                output_filename = f"{safe_base_name}.{format_type}"
                output_path = temp_dir / output_filename

                if format_type == 'txt' or format_type == 'md':
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(result_text)
                elif format_type == 'doc':
                    try:
                        document = Document()
                        document.add_paragraph(result_text)
                        document.save(output_path)
                    except ImportError:
                        logger.error("python-docx not installed. Cannot create .doc file.")
                        gr.Error("Cannot create .doc file: python-docx package is missing.")
                        # Handle error for this specific file, maybe add to files_with_errors
                        files_with_errors.append(f"{filename} (.doc creation failed: missing package)")
                        continue # Skip this file for .doc format
                    except Exception as docx_e:
                        logger.error(f"Failed to create .doc for {filename}: {docx_e}", exc_info=True)
                        gr.Warning(f"Failed to create .doc file for {filename}.")
                        files_with_errors.append(f"{filename} (.doc creation failed: {docx_e})")
                        continue # Skip this file
                else:
                    logger.warning(f"Unsupported format '{format_type}' for file {filename}")
                    files_with_errors.append(f"{filename} (unsupported format: {format_type})")
                    continue

                if output_path.exists():
                    files_to_zip.append(output_path)
                else:
                    logger.warning(f"File not created for zip: {output_path}")
                    files_with_errors.append(f"{filename} (file not created)")

            except Exception as file_e:
                logger.error(f"Error generating file {filename} for zip: {file_e}", exc_info=True)
                files_with_errors.append(f"{filename} (generation error: {file_e})")

        if not files_to_zip:
            logger.warning("No valid files were generated to include in the zip.")
            if files_with_errors:
                 error_str = "; ".join(files_with_errors)
                 gr.Warning(f"Could not create zip: All file(s) had errors or could not be generated. Errors: {error_str}")
            else:
                 gr.Warning("Could not create zip: No files to include.")
            return gr.update(visible=False)

        # Create the zip file
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for file_path in files_to_zip:
                zf.write(file_path, arcname=file_path.name)

        logger.info(f"Created zip archive: {zip_path} with {len(files_to_zip)} file(s).")
        if files_with_errors:
             error_str = "; ".join(files_with_errors)
             gr.Info(f"Zip created, but some file(s) were skipped due to errors: {error_str}")

        return gr.update(value=str(zip_path), visible=True)

    except Exception as e:
        logger.error(f"Error creating zip file: {e}", exc_info=True)
        gr.Error(f"Failed to create zip archive: {e}")
        return gr.update(visible=False)
    finally:
        # Clean up the temporary directory
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as cleanup_e:
                logger.error(f"Error cleaning up temp directory {temp_dir}: {cleanup_e}")
