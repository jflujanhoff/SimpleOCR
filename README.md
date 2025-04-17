# OCR Text Extraction App

This is a simple OCR (Optical Character Recognition) application that uses Tesseract OCR, EasyOCR, Mistral AI, or OpenAI to extract text from PDFs and images, displaying the results in markdown format.

## Prerequisites

1. Install Tesseract OCR on your system (Optional, if you only plan to use other engines):

    - For macOS: `brew install tesseract`
    - For Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
    - For Windows: Download and install from [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

2. Install Python dependencies:

    ```bash
    pip install -r requirements.txt
    ```

    _Note: `requirements.txt` includes packages like `torch` and `torchvision` needed for EasyOCR._

3. Set up environment variables (Optional, only if using API-based engines):
    - Create a `.env` file in the project root (though the app now supports entering keys via the UI)
    - Add your API keys if you want to use Mistral or OpenAI:
    ```
    MISTRAL_API_KEY=your_mistral_key_here
    OPENAI_API_KEY=your_openai_key_here
    ```
    _(You can also enter/manage API keys directly in the app's UI)_

## Usage

1. Run the application:

    ```bash
    python app.py
    ```

2. The application will open in your default web browser
3. Upload a PDF or image containing text
4. Choose your preferred OCR engine from the available options:
    - Tesseract: Free, open-source engine running locally. Requires installation (see Prerequisites).
    - EasyOCR: Free, open-source engine running locally. Generally good accuracy, installed via pip.
    - Mistral: AI-powered OCR. Requires a Mistral API key.
    - OpenAI: AI-powered OCR (uses GPT-4 Vision model). Requires an OpenAI API key.
5. The extracted text will be displayed in markdown format
    - For PDFs, each page's text will be separated by a line of equal signs
    - For images, the text will be displayed as is
6. Download the results in either TXT or MD format

## Features

-   Simple and intuitive interface
-   Supports both PDF and image files
-   Handles multi-page PDFs
-   Displays results in markdown format
-   Multiple OCR engine options:
    -   Tesseract OCR (free, open-source, local, requires separate install)
    -   EasyOCR (free, open-source, local, installed via pip)
    -   Mistral AI OCR (AI-powered, requires API key)
    -   OpenAI OCR (AI-powered via GPT-4 Vision, requires API key)
-   Download results in multiple formats
-   Preserves document layout and formatting (primarily with Tesseract/EasyOCR)
-   API Key management directly within the UI for Mistral and OpenAI.
