import gradio as gr
from ocr_processing import DocumentOCR
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# Initialize OCR processor
try:
    ocr_processor = DocumentOCR()
except ValueError as e:
    print(f"Warning: {str(e)}")
    print("Mistral OCR will not be available. Only Tesseract OCR will work.")
    ocr_processor = None

def process_document(file, ocr_engine):
    """Process a document using the specified OCR engine."""
    if file is None:
        return None, None, None
    
    if ocr_engine == "Mistral" and ocr_processor is None:
        return None, "Error: Mistral OCR is not available. Please check your API key and try again.", None
    
    try:
        # Process the document
        file_name, image_paths, result_text = ocr_processor.process_document(file, ocr_engine)
        
        if result_text is None:
            return None, "Error: Could not extract text from the document. Please try again with a different file or OCR engine.", None
        
        # Generate downloadable files
        txt_path = ocr_processor.download_ocr_result(result_text, "txt")
        md_path = ocr_processor.download_ocr_result(result_text, "md")
        
        return image_paths, result_text, [txt_path, md_path]
    except Exception as e:
        error_msg = f"Error processing document: {str(e)}"
        print(error_msg)
        return None, error_msg, None

# Create Gradio interface
with gr.Blocks(theme='allenai/gradio-theme') as demo:
    gr.Markdown("# Document OCR")
    gr.Markdown("Upload a document (PDF or image) to extract text using OCR.")
    
    with gr.Row():
        with gr.Column():
            file_input = gr.File(label="Upload Document")
            ocr_engine = gr.Radio(
                choices=["Tesseract", "Mistral"],
                value="Tesseract",
                label="OCR Engine"
            )
            process_btn = gr.Button("Process Document")
            image_output = gr.Gallery(label="Document Pages")
        
        with gr.Column():
            md_output = gr.Markdown(label="Extracted Text", show_label=True, container=True)
            download_output = gr.File(label="Download Results")
    
    process_btn.click(
        fn=process_document,
        inputs=[file_input, ocr_engine],
        outputs=[image_output, md_output, download_output]
    )

if __name__ == "__main__":
    demo.launch(auth=(USERNAME, PASSWORD)) 