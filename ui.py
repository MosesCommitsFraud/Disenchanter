# Placeholder for UI elements using PyQt6
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, 
    QApplication, QComboBox
)
import os
from pathlib import Path
from ocr import transcribe_image, MODEL_DIR

class DisenchanterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disenchanter")
        self.setGeometry(100, 100, 600, 450) # Increased height slightly
        self.selected_file_path = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.label = QLabel("Welcome to Disenchanter! Select a file to transcribe.")
        self.layout.addWidget(self.label)

        self.select_button = QPushButton("Select File")
        self.select_button.clicked.connect(self.select_file)
        self.layout.addWidget(self.select_button)

        self.model_label = QLabel("Select Language Model (from project 'models' folder):")
        self.layout.addWidget(self.model_label)

        self.model_combo = QComboBox()
        self.layout.addWidget(self.model_combo)
        self._populate_models_dropdown() # Populate dropdown at startup

        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.transcribe_file)
        self.layout.addWidget(self.transcribe_button)

        self.output_label = QLabel("Output will appear here...")
        self.output_label.setWordWrap(True)
        self.layout.addWidget(self.output_label)

        self.about_label = QLabel("Made by MosesCommitsFraud")
        self.about_label.setStyleSheet("font-style: italic; color: gray;")
        self.layout.addWidget(self.about_label)

    def _populate_models_dropdown(self):
        """Scans the local project 'models' directory and populates the model dropdown."""
        self.model_combo.clear()
        default_models = ['eng', 'deu_frak']
        found_models = set()

        if MODEL_DIR.exists() and MODEL_DIR.is_dir():
            for item in MODEL_DIR.iterdir():
                if item.is_file() and item.suffix == '.traineddata':
                    model_name = item.stem
                    found_models.add(model_name)
                    self.model_combo.addItem(model_name)
            print(f"Found models in local project directory ({MODEL_DIR}): {found_models}")
        else:
            print(f"Local models directory not found or is not a directory: {MODEL_DIR}")
            try:
                MODEL_DIR.mkdir(parents=True, exist_ok=True)
                print(f"Created local models directory: {MODEL_DIR}")
            except Exception as e:
                print(f"Could not create local models directory {MODEL_DIR}: {e}")

        for model in default_models:
            if model not in found_models:
                self.model_combo.addItem(model)
                print(f"Adding default model '{model}' to dropdown for potential download to {MODEL_DIR}.")

        if self.model_combo.count() == 0:
            self.model_combo.addItem("No models found")
            self.model_combo.setEnabled(False)
            self.transcribe_button.setEnabled(False)
        else:
            index = self.model_combo.findText('deu_frak')
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            elif self.model_combo.count() > 0:
                 self.model_combo.setCurrentIndex(0)
            self.model_combo.setEnabled(True)

    def select_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open file', '', "Image files (*.jpg *.png *.jpeg *.bmp *.tiff);;PDF files (*.pdf);;All files (*.*)")
        if fname:
            self.selected_file_path = fname
            self.label.setText(f"Selected: {self.selected_file_path}")
            self.transcribe_button.setEnabled(self.model_combo.isEnabled())
            self.output_label.setText("Ready to transcribe.")
        else:
            self.selected_file_path = None
            self.label.setText("Welcome to Disenchanter! Select a file to transcribe.")
            self.transcribe_button.setEnabled(False)
            self.output_label.setText("Output will appear here...")

    def transcribe_file(self):
        if not self.selected_file_path:
            self.output_label.setText("Error: No file selected.")
            return
        
        selected_model = self.model_combo.currentText()
        if not selected_model or selected_model == "No models found":
             self.output_label.setText("Error: No language model selected or available.")
             return

        self.output_label.setText(f"Transcribing {os.path.basename(self.selected_file_path)} using '{selected_model}'...")
        QApplication.processEvents()

        try:
            file_ext = os.path.splitext(self.selected_file_path)[1].lower()
            if file_ext in ['.jpg', '.png', '.jpeg', '.bmp', '.tiff']:
                result = transcribe_image(self.selected_file_path, selected_model)
                self.output_label.setText(f"Transcription Result ({selected_model}):\n---\n{result}")
            elif file_ext == '.pdf':
                self.output_label.setText("PDF transcription not yet implemented.")
            else:
                self.output_label.setText(f"Error: Unsupported file type: {file_ext}")

        except Exception as e:
            self.output_label.setText(f"An error occurred during transcription: {e}")
            print(f"Error in transcribe_file: {e}") 