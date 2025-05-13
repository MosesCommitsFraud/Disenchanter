# Placeholder for OCR logic using pytesseract
import pytesseract
from PIL import Image
import os
import requests # For downloading models
from pathlib import Path # For cross-platform path handling
import shutil # For saving downloaded file

# --- UPDATED: Define models directory relative to this file --- 
# Get the directory where ocr.py is located
SCRIPT_DIR = Path(__file__).resolve().parent
# Define the models directory path relative to the script directory
MODEL_DIR = SCRIPT_DIR / "models"
# CACHE_DIR = Path.home() / ".Disenchanter" / "tessdata" # Old cache dir
# ------------------------------------------------------------

# Optional: Point pytesseract to the Tesseract executable if not in PATH
# Example for Windows:
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Example for Linux/macOS (if installed in non-standard location):
# pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'

def ensure_model_exists(lang_code: str):
    """Checks if a Tesseract model exists in the local models/ dir, downloads it if not."""
    model_filename = f"{lang_code}.traineddata"
    model_path = MODEL_DIR / model_filename # Use local models dir
    model_url = f"https://github.com/tesseract-ocr/tessdata/raw/main/{model_filename}"

    if model_path.exists():
        print(f"Model '{lang_code}' found in local directory: {model_path}")
        # Normalize the path for Tesseract
        return str(MODEL_DIR.resolve()) # Return the resolved, normalized directory path

    print(f"Model '{lang_code}' not found in {MODEL_DIR}. Downloading from {model_url}...")
    tmp_model_path = None
    try:
        # Ensure local models directory exists
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        # Download the model
        response = requests.get(model_url, stream=True, timeout=60)
        response.raise_for_status()

        # Save the model to a temporary file first
        tmp_model_path = MODEL_DIR / f"{model_filename}.tmp"
        with open(tmp_model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Move temporary file to final destination
        shutil.move(str(tmp_model_path), str(model_path))

        print(f"Model '{lang_code}' downloaded successfully to {model_path}")
        # Normalize the path for Tesseract
        return str(MODEL_DIR.resolve()) # Return the resolved, normalized directory path

    except requests.exceptions.RequestException as e:
        print(f"Error downloading model '{lang_code}': {e}")
        if tmp_model_path and tmp_model_path.exists():
            tmp_model_path.unlink()
        return None
    except Exception as e:
        print(f"An unexpected error occurred during model download: {e}")
        if tmp_model_path and tmp_model_path.exists():
            tmp_model_path.unlink()
        return None

def transcribe_image(image_path: str, language_code: str, specific_model_dir: Path | None = None):
    """Transcribes text from a single image file using the specified language model."""
    original_tessdata_prefix = os.environ.get('TESSDATA_PREFIX')
    try:
        # Check if Tesseract executable is accessible (keep this check)
        try:
            tesseract_version = pytesseract.get_tesseract_version()
            print(f"Using Tesseract version: {tesseract_version}")
        except pytesseract.TesseractNotFoundError:
            error_msg = (
                "Tesseract is not installed or not in your PATH. "
                "Please install Tesseract OCR: https://github.com/tesseract-ocr/tesseract#installing-tesseract "
                "and ensure it's added to your system's PATH or set the path in ocr.py."
            )
            print(f"Error: {error_msg}")
            return f"Error: {error_msg}"

        if not os.path.exists(image_path):
            return f"Error: File not found at {image_path}"

        img = Image.open(image_path)

        # --- Language Model Handling ---
        tessdata_dir_to_use: Path

        if specific_model_dir:
            # Use the provided specific model directory
            model_file = specific_model_dir / f"{language_code}.traineddata"
            if not model_file.is_file(): # Check if it's a file
                error_msg = f"Error: Model file '{model_file}' not found or is not a file in specified directory {specific_model_dir.resolve()}"
                print(error_msg)
                return error_msg
            tessdata_dir_to_use = specific_model_dir.resolve()
            print(f"Using specific model '{language_code}' from directory: {tessdata_dir_to_use}")
        else:
            # Fallback to default behavior: ensure model exists in MODEL_DIR (and download if necessary)
            # ensure_model_exists returns the directory path as a string
            resolved_model_dir_str = ensure_model_exists(language_code)
            if not resolved_model_dir_str:
                return f"Error: Failed to download or find language model '{language_code}' in default location."
            tessdata_dir_to_use = Path(resolved_model_dir_str) # Convert string path to Path object

        # Set TESSDATA_PREFIX environment variable for the current process
        # This should be the directory containing the .traineddata files (e.g., tessdata/)
        os.environ['TESSDATA_PREFIX'] = str(tessdata_dir_to_use)
        print(f"Temporarily set TESSDATA_PREFIX to: {tessdata_dir_to_use}")

        # Configure pytesseract to use the local models/ directory
        # The --tessdata-dir might be redundant if TESSDATA_PREFIX works, but can be kept as a fallback.
        tessdata_path_as_posix = tessdata_dir_to_use.as_posix() # Normalize to forward slashes
        custom_config = f'--tessdata-dir {tessdata_path_as_posix}' # Removed explicit quotes around the path
        print(f"Using Tesseract config: {custom_config} with lang '{language_code}'")

        text = pytesseract.image_to_string(img, lang=language_code, config=custom_config)
        # -----------------------------

        result_message = (
            f"Transcription result for {os.path.basename(image_path)}:\n"
            f"---\n"
            f"{text}\n"
            f"---"
        )
        print(result_message)
        return text
    except pytesseract.TesseractError as e:
        print(f"Tesseract error during transcription: {e}")
        return f"Error during OCR: {e}"
    except Exception as e:
        print(f"An unexpected error occurred during transcription: {e}")
        return f"Error: An unexpected error occurred: {e}"
    finally:
        # Restore original TESSDATA_PREFIX if it was set
        if original_tessdata_prefix is not None:
            os.environ['TESSDATA_PREFIX'] = original_tessdata_prefix
        elif 'TESSDATA_PREFIX' in os.environ:
            del os.environ['TESSDATA_PREFIX'] # Remove if we set it and it wasn't there before
        # Conditional print to avoid KeyError if TESSDATA_PREFIX was deleted and not originally set
        current_tessdata_prefix = os.environ.get('TESSDATA_PREFIX')
        print(f"Restored TESSDATA_PREFIX to: {current_tessdata_prefix}")

def transcribe_with_all_available_models(image_path: str, model_search_paths: list[str]) -> dict[str, str]:
    """
    Transcribes an image using all .traineddata models found in the specified directories.

    Args:
        image_path: Path to the image file.
        model_search_paths: A list of string paths to directories containing .traineddata files.

    Returns:
        A dictionary where keys are 'model_name (from /path/to/directory)'
        and values are the transcription results.
    """
    results = {}
    # Using a set for resolved absolute paths of model files to avoid re-processing
    # if dirs overlap or model files are symlinked/duplicated.
    processed_model_files = set()

    for dir_path_str in model_search_paths:
        model_dir = Path(dir_path_str)
        if not model_dir.is_dir():
            print(f"Warning: Provided model search path '{dir_path_str}' is not a directory or does not exist. Skipping.")
            continue

        print(f"Scanning for models in: {model_dir.resolve()}")
        for item in model_dir.iterdir():
            if item.is_file() and item.suffix == '.traineddata':
                model_file_abs = item.resolve() # Get absolute path of the .traineddata file

                if model_file_abs in processed_model_files:
                    print(f"Skipping already processed model file: {model_file_abs}")
                    continue
                
                language_code = item.stem  # e.g., "deu_frak" from "deu_frak.traineddata"
                # The directory for this specific model is its parent directory
                actual_model_directory = model_file_abs.parent
                
                print(f"Found model '{language_code}' in '{actual_model_directory}'. Attempting transcription...")
                
                # Call the modified transcribe_image, providing the specific directory for this model
                transcription_result = transcribe_image(
                    image_path=image_path,
                    language_code=language_code,
                    specific_model_dir=actual_model_directory
                )
                
                result_key = f"{language_code} (from {actual_model_directory.as_posix()})"
                results[result_key] = transcription_result
                processed_model_files.add(model_file_abs) # Add after successful processing attempt
                print(f"Finished transcription attempt for model '{language_code}' from '{actual_model_directory.as_posix()}'.")
                
    if not results:
        print("No .traineddata files found in the specified search directories or all attempts failed.")
    return results

# Placeholder for PDF processing
# def transcribe_pdf(pdf_path):
#     """Extracts images from a PDF and transcribes them."""
#     # Requires a library like PyMuPDF (fitz) or pdf2image
#     # 1. Extract images from PDF
#     # 2. Call transcribe_image on each extracted image
#     # 3. Combine results
#     print(f"PDF transcription placeholder for {pdf_path}")
#     return "PDF transcription not yet implemented." 