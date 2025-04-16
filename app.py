import gradio as gr
from ocr_processing import DocumentOCR
import os
from dotenv import load_dotenv
import base64

# Load environment variables
load_dotenv()

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# Initialize OCR processor
try:
    ocr_processor = DocumentOCR()
except ValueError as e:
    print(f"Warning: {str(e)}")
    print("Some OCR engines may not be available. Please check your API keys and try again.")
    ocr_processor = None

def process_document(file, ocr_engine):
    """Process a document using the specified OCR engine."""
    if file is None:
        return None, None, None
    
    if ocr_processor is None:
        return None, "Error: OCR processor is not available. Please check your API keys and try again.", None
    
    if ocr_engine in ["Mistral", "OpenAI"] and getattr(ocr_processor, ocr_engine.lower()) is None:
        return None, f"Error: {ocr_engine} OCR is not available. Please check your API key and try again.", None
    
    try:
        # Process the document
        file_name, image_paths, result_text = ocr_processor.process_document(file, ocr_engine)
        
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
                choices=["Tesseract", "Mistral", "OpenAI"],
                value="Tesseract",
                label="OCR Engine"
            )
            process_btn = gr.Button("Process Document")
            image_output = gr.Gallery(label="Document Pages")
        
        with gr.Column():
            # Revert to original markdown component with label and container
            md_output = gr.Markdown(label="Extracted Text", show_label=True, container=True)
            download_output = gr.File(label="Download Results")
            gr.Markdown("Download the extracted text and images. Images are numbered as img-1.jpeg, img-2.jpeg, etc.")
    
    process_btn.click(
        fn=process_document,
        inputs=[file_input, ocr_engine],
        outputs=[image_output, md_output, download_output]
    )

if __name__ == "__main__":
    demo.launch(auth=(USERNAME, PASSWORD), share=True) 
    # demo.launch() 