import gradio as gr
from ocr_processing import DocumentOCR
import os
import secrets
from dotenv import load_dotenv
import base64
import logging

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

def initialize_ocr_processor():
    """Initialize or reinitialize the OCR processor with current API keys."""
    global ocr_processor, available_engines
    
    try:
        # Clear existing environment variables to ensure we're only using user-provided keys
        for engine in api_keys.keys():
            env_var = f"{engine.upper()}_API_KEY"
            if env_var in os.environ:
                os.environ.pop(env_var)
        
        # Only set environment variables temporarily during initialization
        # for the keys actually provided by the user
        original_env = {}
        for engine, key in api_keys.items():
            if key:  # Only set if the user has provided a key
                env_var = f"{engine.upper()}_API_KEY"
                original_env[env_var] = os.environ.get(env_var)
                os.environ[env_var] = key
                logger.info(f"Setting {env_var} for initialization")
        
        # Initialize processor and check available engines
        logger.info("Initializing OCR processor with user-provided API keys")
        ocr_processor = DocumentOCR()
        available_engines = ["Tesseract"]
        
        if ocr_processor.mistral is not None:
            available_engines.append("Mistral")
            logger.info("Mistral OCR engine is available")
        else:
            logger.info("Mistral OCR engine is not available")
            
        if ocr_processor.openai is not None:
            available_engines.append("OpenAI")
            logger.info("OpenAI OCR engine is available")
        else:
            logger.info("OpenAI OCR engine is not available")
        
        # Restore original environment variables
        for env_var, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(env_var, None)
            else:
                os.environ[env_var] = original_value
                
    except ValueError as e:
        logger.warning(f"Warning during OCR initialization: {str(e)}")
        logger.warning("Some OCR engines may not be available. Please check your API keys and try again.")

# Initialize on startup
initialize_ocr_processor()

def save_api_key(api_key, engine):
    """Save API key for the specified engine and reinitialize OCR processor."""
    if not api_key:
        return f"❓ No API key provided for {engine}. Please enter a valid key."
    
    try:
        # Sanitize input - no logging of the actual key
        logger.info(f"Attempting to save and validate API key for {engine}")
        
        # Save the key securely (only in memory)
        global api_keys
        api_keys[engine] = api_key
        
        # Reinitialize with the new key
        initialize_ocr_processor()
        
        # Generate a message for the user
        success = engine in available_engines
        if success:
            return f"✅ {engine} API key is valid and has been saved. Engine is now available."
        else:
            # Clear invalid key from memory
            api_keys[engine] = ""
            return f"❌ Failed to initialize {engine}. Please check your API key and try again."
            
    except Exception as e:
        # Clear key in case of errors
        api_keys[engine] = ""
        logger.error(f"Error saving API key for {engine}: {str(e)}")
        return f"❌ Error processing API key for {engine}: {str(e)}"

def clear_api_key(engine):
    """Clear the API key for the specified engine."""
    global api_keys
    api_keys[engine] = ""
    initialize_ocr_processor()
    logger.info(f"API key for {engine} has been cleared")
    return f"⚠️ {engine} API key has been cleared."

def process_document(file, ocr_engine):
    """Process a document using the specified OCR engine."""
    if file is None:
        return None, None, None
    
    if ocr_processor is None:
        return None, "Error: OCR processor is not available. Please check your API keys and try again.", None
    
    if ocr_engine in ["Mistral", "OpenAI"] and getattr(ocr_processor, ocr_engine.lower()) is None:
        return None, f"Error: {ocr_engine} OCR is not available. Please check your API key and try again.", None
    
    try:
        # Clear environment variables first
        for engine in api_keys.keys():
            env_var = f"{engine.upper()}_API_KEY"
            if env_var in os.environ:
                os.environ.pop(env_var)
                
        # Temporarily set environment variables for the operation
        original_env = {}
        for engine, key in api_keys.items():
            if key:  # Only set if the user has provided a key
                env_var = f"{engine.upper()}_API_KEY"
                original_env[env_var] = os.environ.get(env_var)
                os.environ[env_var] = key
                
        # Process the document
        file_name, image_paths, result_text = ocr_processor.process_document(file, ocr_engine)
        
        # Restore original environment variables
        for env_var, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(env_var, None)
            else:
                os.environ[env_var] = original_value
        
        if result_text is None:
            return None, "Error: Could not extract text from the document. Please try again with a different file or OCR engine.", None
        
        # Generate downloadable files
        txt_path, txt_images = ocr_processor.download_ocr_result(result_text, "txt")
        md_path, md_images = ocr_processor.download_ocr_result(result_text, "md")
        
        # Create a list of files to download
        download_files = [txt_path, md_path]
        
        # Only add image paths for Tesseract OCR
        if ocr_engine == "Tesseract" and image_paths:
            download_files.extend(image_paths)
        
        # If there are any embedded images in the markdown
        for img_name, base64_data in txt_images + md_images:
            if base64_data.startswith('data:image'):
                # Extract base64 data
                img_data = base64.b64decode(base64_data.split(',')[1])
                # Create temporary file
                img_path = os.path.join(ocr_processor.temp_dir, img_name)
                with open(img_path, 'wb') as f:
                    f.write(img_data)
                if img_path not in download_files:
                    download_files.append(img_path)
        
        return image_paths, result_text, download_files
    except Exception as e:
        error_msg = f"Error processing document: {str(e)}"
        logger.error(error_msg)
        return None, error_msg, None

# Create Gradio interface
with gr.Blocks(theme='allenai/gradio-theme') as demo:
    gr.Markdown("# Document OCR")
    gr.Markdown("Upload a document (PDF or image) to extract text using OCR.")
    
    with gr.Tabs():
        # OCR Tab
        with gr.TabItem("OCR"):
            with gr.Row():
                with gr.Column():
                    file_input = gr.File(label="Upload Document")
                    ocr_engine = gr.Radio(
                        choices=available_engines,
                        value=available_engines[0],
                        label="OCR Engine",
                        interactive=True
                    )
                    process_btn = gr.Button("Process Document")
                    image_output = gr.Gallery(label="Document Pages")
                
                with gr.Column():
                    # Revert to original markdown component with label and container
                    md_output = gr.Markdown(label="Extracted Text", show_label=True, container=True)
                    download_output = gr.File(label="Download Results")
                    gr.Markdown("Download the extracted text and images. Images are numbered as img-1.jpeg, img-2.jpeg, etc.")
        
        # API Keys Tab
        with gr.TabItem("API Keys"):
            gr.Markdown("### Configure OCR API Keys")
            gr.Markdown("Enter your API keys for Mistral and OpenAI to enable their OCR engines. Keys are securely stored in memory only for the current session.")
            gr.Markdown("⚠️ **Security Note**: API keys are stored in memory and are not persisted when the server restarts.")
            
            with gr.Column():
                mistral_key = gr.Textbox(
                    label="Mistral API Key",
                    placeholder="Enter your Mistral API key...",
                    type="password",
                    value=""  # Don't display key values
                )
                with gr.Row():
                    mistral_status = gr.Textbox(label="Status", interactive=False)
                    with gr.Column():  
                        mistral_save_btn = gr.Button("Save Mistral API Key", variant="primary")
                        mistral_clear_btn = gr.Button("Clear Key", variant="stop")
                
            with gr.Column():
                openai_key = gr.Textbox(
                    label="OpenAI API Key",
                    placeholder="Enter your OpenAI API key...",
                    type="password",
                    value=""  # Don't display key values
                )
                with gr.Row():
                    openai_status = gr.Textbox(label="Status", interactive=False)
                    with gr.Column():  
                        openai_save_btn = gr.Button("Save OpenAI API Key", variant="primary")
                        openai_clear_btn = gr.Button("Clear Key", variant="stop")
            
            gr.Markdown("### Available OCR Engines")
            gr.Markdown("The following OCR engines are currently available:")
            available_engines_text = gr.Markdown(f"- Tesseract (always available)\n" + 
                                                 f"- Mistral {'(available)' if 'Mistral' in available_engines else '(not available)'}\n" +
                                                 f"- OpenAI {'(available)' if 'OpenAI' in available_engines else '(not available)'}")
    
    # Set up event handlers
    process_btn.click(
        fn=process_document,
        inputs=[file_input, ocr_engine],
        outputs=[image_output, md_output, download_output]
    )
    
    # API key save buttons
    mistral_save_btn.click(
        fn=save_api_key,
        inputs=[mistral_key, gr.Text(value="Mistral", visible=False)],
        outputs=[mistral_status]
    ).then(
        fn=lambda: f"- Tesseract (always available)\n- Mistral {'(available)' if 'Mistral' in available_engines else '(not available)'}\n- OpenAI {'(available)' if 'OpenAI' in available_engines else '(not available)'}",
        outputs=[available_engines_text]
    ).then(
        fn=lambda: gr.Radio(choices=available_engines, value=available_engines[0], label="OCR Engine", interactive=True),
        outputs=[ocr_engine]
    ).then(
        fn=lambda: "",  # Clear the input field after saving
        outputs=[mistral_key]
    )
    
    mistral_clear_btn.click(
        fn=clear_api_key,
        inputs=[gr.Text(value="Mistral", visible=False)],
        outputs=[mistral_status]
    ).then(
        fn=lambda: f"- Tesseract (always available)\n- Mistral {'(available)' if 'Mistral' in available_engines else '(not available)'}\n- OpenAI {'(available)' if 'OpenAI' in available_engines else '(not available)'}",
        outputs=[available_engines_text]
    ).then(
        fn=lambda: gr.Radio(choices=available_engines, value=available_engines[0], label="OCR Engine", interactive=True),
        outputs=[ocr_engine]
    ).then(
        fn=lambda: "",
        outputs=[mistral_key]
    )
    
    openai_save_btn.click(
        fn=save_api_key,
        inputs=[openai_key, gr.Text(value="OpenAI", visible=False)],
        outputs=[openai_status]
    ).then(
        fn=lambda: f"- Tesseract (always available)\n- Mistral {'(available)' if 'Mistral' in available_engines else '(not available)'}\n- OpenAI {'(available)' if 'OpenAI' in available_engines else '(not available)'}",
        outputs=[available_engines_text]
    ).then(
        fn=lambda: gr.Radio(choices=available_engines, value=available_engines[0], label="OCR Engine", interactive=True),
        outputs=[ocr_engine]
    ).then(
        fn=lambda: "",  # Clear the input field after saving
        outputs=[openai_key]
    )
    
    openai_clear_btn.click(
        fn=clear_api_key,
        inputs=[gr.Text(value="OpenAI", visible=False)],
        outputs=[openai_status]
    ).then(
        fn=lambda: f"- Tesseract (always available)\n- Mistral {'(available)' if 'Mistral' in available_engines else '(not available)'}\n- OpenAI {'(available)' if 'OpenAI' in available_engines else '(not available)'}",
        outputs=[available_engines_text]
    ).then(
        fn=lambda: gr.Radio(choices=available_engines, value=available_engines[0], label="OCR Engine", interactive=True),
        outputs=[ocr_engine]
    ).then(
        fn=lambda: "",
        outputs=[openai_key]
    )

if __name__ == "__main__":
    # Enable secure server with authentication if credentials are provided
    if USERNAME and PASSWORD:
        demo.launch(auth=(USERNAME, PASSWORD), share=True, ssl_verify=True)
    else:
        # Default launch without authentication 
        demo.launch(ssl_verify=True) 