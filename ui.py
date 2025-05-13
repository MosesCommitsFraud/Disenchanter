# Placeholder for UI elements using PyQt6
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, 
    QApplication, QComboBox, QTextEdit
)
import os
from pathlib import Path
from ocr import transcribe_image, MODEL_DIR, transcribe_with_all_available_models

class DisenchanterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disenchanter")
        self.setGeometry(100, 100, 700, 600) # Adjusted height for better layout
        self.selected_file_path = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.info_label = QLabel("Welcome to Disenchanter! Select an image file to transcribe.")
        self.layout.addWidget(self.info_label)

        self.select_button = QPushButton("Select Image File")
        self.select_button.clicked.connect(self.select_file)
        self.layout.addWidget(self.select_button)

        # MODEL_DIR is imported from ocr.py (e.g., ROOT/models)
        self.model_label = QLabel(f"Select Language Model (from '{MODEL_DIR.name}' folder for single transcription):")
        self.layout.addWidget(self.model_label)

        self.model_combo = QComboBox()
        self.layout.addWidget(self.model_combo)

        self.transcribe_button = QPushButton("Transcribe with Selected Model")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.transcribe_file)
        self.layout.addWidget(self.transcribe_button)
        
        self.test_all_button = QPushButton("Test All Available Models")
        self.test_all_button.setEnabled(False)
        self.test_all_button.clicked.connect(self.run_all_models_test)
        self.layout.addWidget(self.test_all_button)

        self.output_text_area = QTextEdit()
        self.output_text_area.setReadOnly(True)
        self.output_text_area.setPlaceholderText("Transcription output will appear here...")
        self.layout.addWidget(self.output_text_area)

        self.about_label = QLabel("Disenchanter by MosesCommitsFraud")
        self.about_label.setStyleSheet("font-style: italic; color: gray;")
        self.layout.addWidget(self.about_label)

        # Populate dropdown and then update button states after all elements are initialized
        self._populate_models_dropdown()
        self._update_button_states()

    def _populate_models_dropdown(self):
        self.model_combo.clear()
        default_models_for_download = ['eng', 'deu_frak'] # Common models, ensure_model_exists can handle them
        found_local_models = set()

        # Populate with models found in the primary MODEL_DIR (ROOT/models)
        if MODEL_DIR.exists() and MODEL_DIR.is_dir():
            for item in MODEL_DIR.iterdir():
                if item.is_file() and item.suffix == '.traineddata':
                    model_name = item.stem
                    found_local_models.add(model_name)
                    self.model_combo.addItem(model_name)
            print(f"Found models in default models directory ({MODEL_DIR}): {found_local_models}")
        else:
            print(f"Default models directory not found: {MODEL_DIR}. It will be created if models are downloaded.")
            # Directory will be created by ensure_model_exists if needed

        for model in default_models_for_download:
            if model not in found_local_models:
                self.model_combo.addItem(model) # User can select to trigger download via ensure_model_exists
                print(f"Adding default model '{model}' to dropdown for potential download to {MODEL_DIR}.")

        if self.model_combo.count() == 0:
            self.model_combo.addItem("No models available")
            self.model_combo.setEnabled(False)
        else:
            # Try to pre-select 'deu_frak' or the first available model
            index = self.model_combo.findText('deu_frak')
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            elif self.model_combo.count() > 0:
                 self.model_combo.setCurrentIndex(0)
            self.model_combo.setEnabled(True)
        # Note: self._update_button_states() is NOT called here anymore.
        # It's called at the end of __init__ after this method runs and all UI elements are ready.

    def _update_button_states(self):
        file_selected = bool(self.selected_file_path)
        model_selected_for_single = (
            self.model_combo.isEnabled() and \
            self.model_combo.count() > 0 and \
            self.model_combo.currentText() != "No models available"
        )

        self.transcribe_button.setEnabled(file_selected and model_selected_for_single)
        self.test_all_button.setEnabled(file_selected)

    def select_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open Image File', '',
                                               "Image files (*.jpg *.jpeg *.png *.bmp *.tiff);;All files (*.*)")
        if fname:
            self.selected_file_path = fname
            self.info_label.setText(f"Selected File: {os.path.basename(self.selected_file_path)}")
            self.output_text_area.setPlainText("File selected. Ready to transcribe.")
        else:
            self.selected_file_path = None
            self.info_label.setText("Welcome to Disenchanter! Select an image file to transcribe.")
            self.output_text_area.setPlaceholderText("Transcription output will appear here...")
            self.output_text_area.clear()
        self._update_button_states() # Update states whenever a file is selected or deselected

    def transcribe_file(self):
        if not self.selected_file_path:
            self.output_text_area.setPlainText("Error: No file selected.")
            return
        
        selected_model = self.model_combo.currentText()
        if not selected_model or selected_model == "No models available":
             self.output_text_area.setPlainText("Error: No language model selected from dropdown.")
             return

        self.output_text_area.setPlainText(f"Transcribing {os.path.basename(self.selected_file_path)} using '{selected_model}'...")
        QApplication.processEvents() # Update UI

        try:
            file_ext = os.path.splitext(self.selected_file_path)[1].lower()
            if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                # transcribe_image will use default MODEL_DIR (and ensure_model_exists for listed defaults)
                result = transcribe_image(self.selected_file_path, selected_model)
                self.output_text_area.setPlainText(f"--- Transcription Result ('{selected_model}') ---\n{result}")
            elif file_ext == '.pdf':
                self.output_text_area.setPlainText("PDF transcription is not yet implemented.")
            else:
                self.output_text_area.setPlainText(f"Error: Unsupported file type: {file_ext}. Please select an image.")
        except Exception as e:
            self.output_text_area.setPlainText(f"An error occurred during single model transcription: {e}")
            print(f"Error in DisenchanterApp.transcribe_file: {e}")

    def run_all_models_test(self):
        if not self.selected_file_path:
            self.output_text_area.setPlainText("Error: No file selected for 'Test All Models'.")
            return

        self.output_text_area.setPlainText(f"Starting 'Test All Models' for {os.path.basename(self.selected_file_path)}... This may take some time.")
        QApplication.processEvents() # Update UI

        # Absolute paths for specific model collections, as per user's structure
        model_locations_for_test_all = [
            r"C:\DEV\Disenchanter\models\frak_deu",
            r"C:\DEV\Disenchanter\models\other_models"
            # Add other absolute paths to model directories here if needed
        ]
        
        try:
            all_results = transcribe_with_all_available_models(self.selected_file_path, model_locations_for_test_all)
            
            output_display_text = f"--- Results from 'Test All Models' for {os.path.basename(self.selected_file_path)} ---\n\n"
            if all_results:
                for model_info, text_result in all_results.items():
                    output_display_text += f"Model: {model_info}\n"
                    output_display_text += "----------------------------------------\n"
                    if isinstance(text_result, str) and text_result.startswith("Error:"):
                        output_display_text += f"{text_result}\n"
                    else:
                        output_display_text += f"{str(text_result)}\n" # Ensure result is string
                    output_display_text += "----------------------------------------\n\n"
            else:
                output_display_text += "No transcriptions were generated. Check model paths and file content."
            
            self.output_text_area.setPlainText(output_display_text)
            
        except Exception as e:
            self.output_text_area.setPlainText(f"An error occurred during 'Test All Models': {e}")
            print(f"Error in DisenchanterApp.run_all_models_test: {e}") 