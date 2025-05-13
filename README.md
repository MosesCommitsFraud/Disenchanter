# Disenchanter

A local desktop application for transcribing historical texts using OCR.

## Features

*   Accepts image files (JPG, PNG, etc.) as input.
*   (Planned) Accepts PDF files as input.
*   Transcribes text using Tesseract OCR engine.
*   Outputs transcribed text as a `.txt` file.
*   (Planned) Outputs transcribed text as a searchable PDF.
*   Modern and easy-to-use UI.

## Created by

MosesCommitsFraud

## Setup

1.  **Install Tesseract OCR:**
    Follow the installation instructions for your OS from [https://tesseract-ocr.github.io/tessdoc/Installation.html](https://tesseract-ocr.github.io/tessdoc/Installation.html).
    Ensure that Tesseract is added to your system's PATH, or update the path in `ocr.py` if needed.

2.  **Create a Python virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

```bash
python main.py
```

## Project Structure

```
Disenchanter/
├── main.py           # Main application entry point
├── ui.py             # PyQt6 UI components
├── ocr.py            # OCR processing logic (Tesseract)
├── utils.py          # File handling and output utilities
├── requirements.txt  # Python package dependencies
└── README.md         # This file
```

## Development Notes

*   The UI is built using PyQt6.
*   OCR is performed by `pytesseract`, a Python wrapper for Tesseract.
*   Image manipulation uses the Pillow library.

### Future Enhancements

*   PDF input processing (extracting images from PDFs).
*   Generating searchable PDF output.
*   Option to select Tesseract language models.
*   Support for Rescribe's specialized `.traineddata` files for historical texts.
*   Progress bar for transcription.
*   Batch processing of files. 