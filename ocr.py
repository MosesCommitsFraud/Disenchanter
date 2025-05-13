# Placeholder for OCR logic using pytesseract
import pytesseract
from PIL import Image
import os
import requests # For downloading models
from pathlib import Path # For cross-platform path handling
import shutil # For saving downloaded file

# --- Define models directory relative to this file (which is in workspace root) ---
SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_DIR = SCRIPT_DIR / "models" # Default models will be stored in ROOT/models

# --- User specific: Point pytesseract to the Tesseract executable if not in PATH ---
# Please ensure this path is correct for your system.
try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    # Attempt to get version to confirm Tesseract command is working
    tesseract_check_version = pytesseract.get_tesseract_version()
    print(f"Successfully set Tesseract command. Version: {tesseract_check_version}")
except pytesseract.TesseractNotFoundError:
    print(f"WARNING: Tesseract not found at {pytesseract.pytesseract.tesseract_cmd}. Please ensure Tesseract is installed and the path is correct.")
except Exception as e:
    print(f"WARNING: An issue occurred while setting Tesseract command or getting version: {e}")

def ensure_model_exists(lang_code: str):
    """Checks if a Tesseract model exists in the local MODEL_DIR, downloads it if not."""
    model_filename = f"{lang_code}.traineddata"
    model_path = MODEL_DIR / model_filename
    # Standard Tesseract models repository
    model_url = f"https://github.com/tesseract-ocr/tessdata/raw/main/{model_filename}"

    if model_path.exists():
        print(f"Model '{lang_code}' found in local directory: {model_path}")
        return str(MODEL_DIR.resolve()) # Return the directory path

    print(f"Model '{lang_code}' not found in {MODEL_DIR}. Attempting to download from {model_url}...")
    tmp_model_path = None
    try:
        MODEL_DIR.mkdir(parents=True, exist_ok=True) # Ensure MODEL_DIR exists
        response = requests.get(model_url, stream=True, timeout=60)
        response.raise_for_status()

        tmp_model_path = MODEL_DIR / f"{model_filename}.tmp"
        with open(tmp_model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        shutil.move(str(tmp_model_path), str(model_path))
        print(f"Model '{lang_code}' downloaded successfully to {model_path}")
        return str(MODEL_DIR.resolve())
    except requests.exceptions.RequestException as e:
        print(f"Error downloading model '{lang_code}': {e}")
        if tmp_model_path and tmp_model_path.exists():
            tmp_model_path.unlink() # Clean up temporary file
        return None
    except Exception as e:
        print(f"An unexpected error occurred during model download for '{lang_code}': {e}")
        if tmp_model_path and tmp_model_path.exists():
            tmp_model_path.unlink()
        return None

def transcribe_image(image_path: str, language_code: str, specific_model_dir: Path | None = None):
    """Transcribes text from an image file using the specified language model and Tesseract settings."""
    original_tessdata_prefix = os.environ.get('TESSDATA_PREFIX')
    try:
        # Confirm Tesseract executable is accessible (based on tesseract_cmd setting)
        try:
            tesseract_version = pytesseract.get_tesseract_version()
            print(f"Using Tesseract version: {tesseract_version}")
        except pytesseract.TesseractNotFoundError:
            error_msg = (
                f"Tesseract not found or not configured correctly. "
                f"Current tesseract_cmd: '{pytesseract.pytesseract.tesseract_cmd}'. "
                "Please install Tesseract and/or set the correct path in ocr.py."
            )
            print(f"Error: {error_msg}")
            return f"Error: {error_msg}"
        except Exception as e: # Catch other potential errors from get_tesseract_version
            error_msg = f"Error accessing Tesseract: {e}. Check Tesseract installation and configuration."
            print(f"Error: {error_msg}")
            return f"Error: {error_msg}"

        if not os.path.exists(image_path):
            return f"Error: Image file not found at {image_path}"

        img = Image.open(image_path)
        tessdata_dir_to_use: Path

        if specific_model_dir:
            # Using a specific directory provided for this model
            model_file_path = specific_model_dir / f"{language_code}.traineddata"
            if not model_file_path.is_file():
                error_msg = f"Error: Model file '{model_file_path.name}' not found or is not a file in the specified directory '{specific_model_dir.resolve()}'."
                print(error_msg)
                return error_msg
            tessdata_dir_to_use = specific_model_dir.resolve()
            print(f"Using specific model '{language_code}' from custom directory: {tessdata_dir_to_use}")
        else:
            # Using default MODEL_DIR, attempt to ensure model exists (download if needed)
            resolved_model_dir_str = ensure_model_exists(language_code)
            if not resolved_model_dir_str:
                return f"Error: Failed to ensure language model '{language_code}' exists in default location ({MODEL_DIR.resolve()})."
            tessdata_dir_to_use = Path(resolved_model_dir_str)
            print(f"Using model '{language_code}' from default directory: {tessdata_dir_to_use}")

        # Set TESSDATA_PREFIX to the directory containing the .traineddata files
        os.environ['TESSDATA_PREFIX'] = str(tessdata_dir_to_use)
        print(f"Temporarily set TESSDATA_PREFIX to: {tessdata_dir_to_use}")

        # Configure Tesseract: use forward slashes for --tessdata-dir and no quotes if path has no spaces
        tessdata_path_for_config = tessdata_dir_to_use.as_posix()
        custom_config = f'--tessdata-dir {tessdata_path_for_config}'
        
        print(f"Using Tesseract config: {custom_config} with lang '{language_code}'")
        text = pytesseract.image_to_string(img, lang=language_code, config=custom_config)
        
        # The calling function in ui.py will format the full message
        return text
    except pytesseract.TesseractError as e:
        error_detail = str(e).replace("\n", " ") # Clean up error message
        print(f"Tesseract error during transcription for lang '{language_code}': {error_detail}")
        return f"Error during OCR for lang '{language_code}': {error_detail}"
    except Exception as e:
        error_detail = str(e).replace("\n", " ")
        print(f"An unexpected error occurred during transcription for lang '{language_code}': {error_detail}")
        return f"Error: An unexpected error occurred for lang '{language_code}': {error_detail}"
    finally:
        # Restore original TESSDATA_PREFIX
        if original_tessdata_prefix is not None:
            os.environ['TESSDATA_PREFIX'] = original_tessdata_prefix
        elif 'TESSDATA_PREFIX' in os.environ:
            del os.environ['TESSDATA_PREFIX']
        # print(f"Restored TESSDATA_PREFIX to: {os.environ.get('TESSDATA_PREFIX')}") # Optional: for debugging

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
    processed_model_files = set() # To avoid re-processing if models are in multiple listed paths

    for dir_path_str in model_search_paths:
        try:
            model_dir = Path(dir_path_str).resolve() # Resolve to absolute path
            if not model_dir.is_dir():
                print(f"Warning: Provided model search path '{dir_path_str}' (resolved to '{model_dir}') is not a directory or does not exist. Skipping.")
                continue
        except Exception as e:
            print(f"Warning: Could not resolve path '{dir_path_str}': {e}. Skipping.")
            continue

        print(f"Scanning for models in: {model_dir}")
        for item in model_dir.iterdir():
            if item.is_file() and item.suffix == '.traineddata':
                model_file_abs = item.resolve()

                if model_file_abs in processed_model_files:
                    # print(f"Skipping already processed model file: {model_file_abs}") # Optional: for debugging
                    continue
                
                language_code = item.stem  # e.g., "deu_frak" from "deu_frak.traineddata"
                actual_model_directory = model_file_abs.parent # The directory where this .traineddata file resides
                
                print(f"Found model '{language_code}' in '{actual_model_directory}'. Attempting transcription...")
                
                transcription_result = transcribe_image(
                    image_path=image_path,
                    language_code=language_code,
                    specific_model_dir=actual_model_directory # Pass the specific directory
                )
                
                # Use a clear key for results, including the source directory
                result_key = f"{language_code} (from {actual_model_directory.as_posix()})"
                results[result_key] = transcription_result
                processed_model_files.add(model_file_abs)
                # print(f"Finished transcription attempt for model '{language_code}' from '{actual_model_directory.as_posix()}'.") # Optional: for debugging
                
    if not results:
        print("No .traineddata files found in the specified search directories, or all attempts failed.")
    return results

def transcribe_with_specific_model_files(image_path: str, model_file_paths: list[str]) -> dict[str, str]:
    """
    Transcribes an image using a specific list of .traineddata model files.
    Args:
        image_path: Path to the image file.
        model_file_paths: A list of absolute string paths to .traineddata files.
    Returns:
        A dictionary where keys are 'model_code (from /full/path/to/model.traineddata)'
        and values are the transcription results.
    """
    results = {}
    if not model_file_paths:
        print("No model files provided for transcription.")
        return {"Info": "No model files were selected for testing."}

    print(f"Attempting transcription with {len(model_file_paths)} specific model files.")
    for model_file_str_path in model_file_paths:
        try:
            model_file = Path(model_file_str_path)
            if not model_file.is_file() or model_file.suffix != '.traineddata':
                print(f"Warning: Skipping invalid or non-.traineddata file: {model_file_str_path}")
                results[f"Invalid file ({model_file.name})"] = f"Error: Not a valid .traineddata file path: {model_file_str_path}"
                continue

            language_code = model_file.stem
            specific_model_dir = model_file.parent
            
            print(f"Attempting transcription with model '{language_code}' from file: {model_file}")
            
            transcription_result = transcribe_image(
                image_path=image_path,
                language_code=language_code,
                specific_model_dir=specific_model_dir
            )
            
            # Use the full model file path in the key for clarity, as these are custom selections
            result_key = f"{language_code} (from file: {model_file.as_posix()})"
            results[result_key] = transcription_result
            print(f"Finished transcription attempt for model file: {model_file}")

        except Exception as e:
            error_key = f"Error processing {os.path.basename(model_file_str_path)}"
            results[error_key] = f"General error processing model file {model_file_str_path}: {e}"
            print(f"Error processing model file {model_file_str_path}: {e}")
            
    if not results: # Should not happen if model_file_paths was not empty, due to try/except adding error keys
        print("No specific model files were processed, or all attempts failed.")
        # results["Info"] = "No specific model files processed or all failed." # Redundant if try/except adds error keys

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