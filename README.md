# OCR Text Extraction App

This is a simple OCR (Optical Character Recognition) application that uses either Tesseract OCR or Mistral AI to extract text from PDFs and images, displaying the results in markdown format.

## Prerequisites

1. Install Tesseract OCR on your system:

    - For macOS: `brew install tesseract`
    - For Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
    - For Windows: Download and install from [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

2. Install Python dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Set up environment variables:
    - Create a `.env` file in the project root
    - Add your Mistral API key if you want to use Mistral OCR:
    ```
    MISTRAL_API_KEY=your_api_key_here
    ```

## Usage

1. Run the application:

    ```bash
    python app.py
    ```

2. The application will open in your default web browser
3. Upload a PDF or image containing text
4. Choose your preferred OCR engine:
    - Tesseract: Free, open-source OCR engine
    - Mistral: AI-powered OCR with potentially better accuracy
5. The extracted text will be displayed in markdown format
    - For PDFs, each page's text will be separated by a line of equal signs
    - For images, the text will be displayed as is
6. Download the results in either TXT or MD format

## Features

-   Simple and intuitive interface
-   Supports both PDF and image files
-   Handles multi-page PDFs
-   Displays results in markdown format
-   Two OCR engine options:
    -   Tesseract OCR (free, open-source)
    -   Mistral AI OCR (AI-powered, requires API key)
-   Download results in multiple formats
-   Preserves document layout and formatting
