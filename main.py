import sys
from PyQt6.QtWidgets import QApplication
# Assuming ui.py and ocr.py are in the same directory (root)
from ui import DisenchanterApp
from ocr import transcribe_with_all_available_models # For the test function
import os

def main():
    """Sets up and runs the PyQt6 UI application."""
    app = QApplication(sys.argv)
    window = DisenchanterApp()
    window.show()
    sys.exit(app.exec())

# This function is kept for potential direct command-line testing 
# (outside the UI) if needed for development or batch processing.
def test_all_models_on_image_cli(image_to_test: str):
    """Performs transcription with all models for a given image via CLI."""
    # Absolute paths for specific model collections, as per user's structure.
    # Ensure these paths are correct on your system if using this CLI function.
    model_locations = [
        r"C:\DEV\Disenchanter\models\frak_deu",
        r"C:\DEV\Disenchanter\models\other_models"
    ]
    print(f"\nStarting Command-Line Interface (CLI) transcription test for image: {image_to_test}")
    if not os.path.exists(image_to_test):
        print(f"Error: Test image file not found at '{image_to_test}'. Aborting CLI test.")
        return

    all_results = transcribe_with_all_available_models(image_to_test, model_locations)
    
    print("\n--- CLI Transcription Results ---")
    if all_results:
        for model_info, text_result in all_results.items():
            print(f"\nModel: {model_info}")
            print("----------------------------------------")
            if isinstance(text_result, str) and text_result.startswith("Error:"):
                print(text_result)
            else:
                # Print a snippet if the text is very long for readability in CLI
                snippet = (str(text_result)[:300] + '...') if len(str(text_result)) > 300 else str(text_result)
                print(snippet)
            print("----------------------------------------")
    else:
        print("No transcriptions were generated via CLI test. Check model paths or image content.")

if __name__ == "__main__":
    main()