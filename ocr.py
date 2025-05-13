# Placeholder for OCR logic using pytesseract
import pytesseract
from PIL import Image, ImageDraw # Added ImageDraw for future box drawing (though not used in this step directly in ocr.py)
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
    """
    Transcribes text from an image, returning plain text and structured word data.
    Returns:
        tuple: (plain_text: str, word_data: list[dict]) or (error_message_str, None) in case of error.
        word_data is a list of dicts: [{'text', 'left', 'top', 'width', 'height', 'conf'} ...]
    """
    original_tessdata_prefix = os.environ.get('TESSDATA_PREFIX')
    try:
        try:
            tesseract_version = pytesseract.get_tesseract_version()
            # print(f"Using Tesseract version: {tesseract_version}") # Less verbose
        except pytesseract.TesseractNotFoundError:
            error_msg = f"Tesseract not found (cmd: '{pytesseract.pytesseract.tesseract_cmd}'). Set path in ocr.py."
            return error_msg, None
        except Exception as e:
            return f"Error accessing Tesseract: {e}", None

        if not os.path.exists(image_path):
            return f"Error: Image file not found at {image_path}", None

        # img_pil = Image.open(image_path) # Opened later for pytesseract
        tessdata_dir_to_use: Path
        if specific_model_dir:
            model_file_path = specific_model_dir / f"{language_code}.traineddata"
            if not model_file_path.is_file():
                return f"Error: Model '{model_file_path.name}' not in '{specific_model_dir.resolve()}'.", None
            tessdata_dir_to_use = specific_model_dir.resolve()
        else:
            resolved_model_dir_str = ensure_model_exists(language_code)
            if not resolved_model_dir_str:
                return f"Error: Failed to ensure model '{language_code}' in {MODEL_DIR.resolve()}.", None
            tessdata_dir_to_use = Path(resolved_model_dir_str)

        os.environ['TESSDATA_PREFIX'] = str(tessdata_dir_to_use)
        # print(f"Temp TESSDATA_PREFIX: {tessdata_dir_to_use}") # Less verbose

        tessdata_path_for_config = tessdata_dir_to_use.as_posix()
        custom_config = f'--tessdata-dir {tessdata_path_for_config}'
        # print(f"Tesseract config: {custom_config} with lang '{language_code}'") # Less verbose

        # Use image_to_data to get detailed information including bounding boxes
        # Output.DICT returns a dictionary where keys are headers like 'level', 'text', 'left', etc.
        data = pytesseract.image_to_data(image_path, lang=language_code, config=custom_config, output_type=pytesseract.Output.DICT)
        
        word_data = []
        plain_text_lines = []
        current_line_words = []
        last_block_num, last_par_num, last_line_num = -1, -1, -1

        n_boxes = len(data['level'])
        for i in range(n_boxes):
            # We are interested in word-level data (level 5)
            if int(data['level'][i]) == 5 and data['text'][i].strip(): # level 5 is word
                conf = int(float(data['conf'][i])) # Ensure conf is int
                if conf > -1: # -1 means it's not a valid word box (e.g. control character)
                    word_info = {
                        'text': data['text'][i],
                        'left': int(data['left'][i]),
                        'top': int(data['top'][i]),
                        'width': int(data['width'][i]),
                        'height': int(data['height'][i]),
                        'conf': conf
                    }
                    word_data.append(word_info)

                    # Reconstruct plain text maintaining approximate line breaks
                    block_num = int(data['block_num'][i])
                    par_num = int(data['par_num'][i])
                    line_num = int(data['line_num'][i])

                    if last_line_num != -1 and (block_num != last_block_num or par_num != last_par_num or line_num != last_line_num):
                        plain_text_lines.append(" ".join(current_line_words))
                        current_line_words = []
                    current_line_words.append(data['text'][i])
                    
                    last_block_num, last_par_num, last_line_num = block_num, par_num, line_num
        
        if current_line_words: # Append any remaining words from the last line
            plain_text_lines.append(" ".join(current_line_words))

        plain_text = "\n".join(plain_text_lines)
        return plain_text, word_data

    except pytesseract.TesseractError as e:
        return f"OCR Error ({language_code}): {str(e).replace('\n', ' ')}", None
    except Exception as e:
        return f"Unexpected OCR Error ({language_code}): {str(e).replace('\n', ' ')}", None
    finally:
        if original_tessdata_prefix is not None:
            os.environ['TESSDATA_PREFIX'] = original_tessdata_prefix
        elif 'TESSDATA_PREFIX' in os.environ:
            del os.environ['TESSDATA_PREFIX']

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