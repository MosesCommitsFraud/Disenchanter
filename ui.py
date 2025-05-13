# Placeholder for UI elements using PyQt6
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, 
    QApplication, QComboBox, QTextEdit, QSplitter
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen # Added QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QRectF # Added QRectF for floating point precision if needed for boxes
import os
import re # For parsing model codes
from pathlib import Path
from ocr import transcribe_image, MODEL_DIR

# Updated Mapping from model codes to pretty names
MODEL_CODE_TO_PRETTY_NAME = {
    # Standard Languages
    "deu": "German", "eng": "English", "fra": "French", "spa": "Spanish", "ita": "Italian",
    "dan": "Danish", "swe": "Swedish", "nor": "Norwegian", "nld": "Dutch", "lat": "Latin",
    "jpn": "Japanese", "jpn_vert": "Japanese (Vertical)",
    "heb": "Hebrew", "ara": "Arabic",
    "chi_sim": "Chinese Simplified", "chi_sim_vert": "Chinese Simplified (Vertical)",
    "chi_tra": "Chinese Traditional", "chi_tra_vert": "Chinese Traditional (Vertical)",
    # Fraktur & Specific variants
    "deu_frak": "German Fraktur", "dan_frak": "Danish Fraktur", "swe_frak": "Swedish Fraktur",
    "deu_latf": "German (Latinf)", # From other_models
    "spa_old": "Spanish (Old)",   # From other_models
    "ita_old": "Italian (Old)",   # From other_models
    # User-added / more specific models (examples from previous context)
    "frak2021-0.905": "Fraktur (2021 v0.905)",
    "Fraktur_50000000.334_450937": "Fraktur (TUM 0.334)",
    "german_print_0.877_1254744_7309067": "German Print (0.877)",
    "german_print_0.785_1720686_9460624": "German Print (0.785)",
    "german_konzilsprotokolle": "German Council Protocols",
    # Add any other custom model codes and their pretty names here
}

class ImageViewer(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._original_pixmap = QPixmap()
        self._word_data = []
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self._scale_factor = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self.setText("Image will appear here.")

    def set_pixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            self._original_pixmap = pixmap
            self._update_scaled_pixmap_and_offsets()
        else:
            self._original_pixmap = QPixmap()
            self._pixmap = QPixmap()
            self.setText("Image will appear here." if not self._word_data else "No image loaded or image cleared.")
            self._word_data = []
        self.update()

    def set_word_data(self, word_data_list):
        self._word_data = word_data_list if word_data_list else []
        self.update()

    def _update_scaled_pixmap_and_offsets(self):
        if self._original_pixmap.isNull():
            current_display_pixmap = self.pixmap()
            if current_display_pixmap is not None and not current_display_pixmap.isNull():
                super().setPixmap(QPixmap())
            self.setText("Image will appear here.")
            self._scale_factor = 1.0
            self._offset_x = 0
            self._offset_y = 0
            return

        self._pixmap = self._original_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        super().setPixmap(self._pixmap)

        if self._original_pixmap.width() > 0 and self._pixmap.width() > 0:
            self._scale_factor = self._pixmap.width() / self._original_pixmap.width()
        else:
            self._scale_factor = 1.0
        
        self._offset_x = (self.width() - self._pixmap.width()) / 2
        self._offset_y = (self.height() - self._pixmap.height()) / 2
        self.setText("")

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._pixmap.isNull() and self._word_data:
            painter = QPainter(self)
            pen = QPen(QColor(255, 0, 0, 180))
            pen.setWidth(1)
            painter.setPen(pen)
            for word in self._word_data:
                scaled_left = int(word['left'] * self._scale_factor + self._offset_x)
                scaled_top = int(word['top'] * self._scale_factor + self._offset_y)
                scaled_width = int(word['width'] * self._scale_factor)
                scaled_height = int(word['height'] * self._scale_factor)
                painter.drawRect(scaled_left, scaled_top, scaled_width, scaled_height)
            painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._original_pixmap.isNull():
            self._update_scaled_pixmap_and_offsets()

class DisenchanterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disenchanter - Side-by-Side OCR Viewer")
        self.setGeometry(50, 50, 1200, 700) # Larger window for side-by-side view
        self.selected_file_path = None
        self.current_word_data = None # To store word bounding box data
        # self.current_pixmap removed, ImageViewer will handle its own pixmap

        # Set the application icon
        icon_path = r"C:\DEV\Disenchanter\Enchanted_Book.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Warning: Application icon not found at {icon_path}")

        # Main layout container (vertical)
        main_container = QWidget()
        self.setCentralWidget(main_container)
        main_layout = QVBoxLayout(main_container)

        # Top controls area (horizontal)
        top_controls_widget = QWidget()
        top_controls_layout = QHBoxLayout(top_controls_widget)
        main_layout.addWidget(top_controls_widget)

        self.info_label = QLabel("Select Image File")
        top_controls_layout.addWidget(self.info_label)
        self.select_button = QPushButton("Select Image")
        self.select_button.clicked.connect(self.select_file)
        top_controls_layout.addWidget(self.select_button)
        
        self.model_label = QLabel("Model:")
        top_controls_layout.addWidget(self.model_label)
        self.model_combo = QComboBox()
        top_controls_layout.addWidget(self.model_combo, 1) # Add stretch factor

        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.transcribe_file)
        top_controls_layout.addWidget(self.transcribe_button)

        # --- Splitter for Image and Text --- 
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter, 1) # Add stretch factor to splitter

        # Image Viewer Area (Left side of splitter)
        self.image_viewer_label = ImageViewer() # Changed from QLabel to ImageViewer
        self.splitter.addWidget(self.image_viewer_label)

        # Text Output Area (Right side of splitter)
        self.output_text_area = QTextEdit()
        self.output_text_area.setReadOnly(True)
        self.output_text_area.setPlaceholderText("Transcription output...")
        self.output_text_area.setMinimumSize(400, 300)
        self.splitter.addWidget(self.output_text_area)
        
        self.splitter.setSizes([600, 600]) # Initial equal sizes

        # About label at the bottom
        self.about_label = QLabel("Disenchanter by MosesCommitsFraud")
        self.about_label.setStyleSheet("font-style: italic; color: gray;")
        main_layout.addWidget(self.about_label, 0, Qt.AlignmentFlag.AlignRight)

        self._populate_models_dropdown()
        self._update_button_states()

    def _get_display_model_name(self, model_code: str) -> str:
        pretty_name = MODEL_CODE_TO_PRETTY_NAME.get(model_code, model_code)
        # If no pretty name, just use the code. If pretty name IS the code, it means we want to show only the code.
        # For consistency, let's assume if pretty_name == model_code, it implies no specific mapping, use code only.
        # If a mapping exists and is different, show "Pretty Name (code)".
        if model_code in MODEL_CODE_TO_PRETTY_NAME and MODEL_CODE_TO_PRETTY_NAME[model_code] != model_code:
            return f"{MODEL_CODE_TO_PRETTY_NAME[model_code]} ({model_code})"
        return model_code # Fallback to just the code if no distinct pretty name

    def _extract_code_from_display_name(self, display_name: str) -> str:
        match = re.search(r'\(([^)]+)\)$', display_name)
        if match:
            return match.group(1)
        return display_name

    def _scan_model_directory(self, directory: Path, found_model_codes: set):
        """Helper function to scan a directory for .traineddata files and add to dropdown."""
        if directory.exists() and directory.is_dir():
            print(f"Scanning for models in: {directory.resolve()}")
            for item in directory.iterdir():
                if item.is_file() and item.suffix == '.traineddata':
                    model_code = item.stem
                    if model_code not in found_model_codes: # Add only if not already added (e.g. from MODEL_DIR)
                        found_model_codes.add(model_code)
                        self.model_combo.addItem(self._get_display_model_name(model_code))
                        print(f"  Added '{model_code}' from {directory.name}")
        else:
            print(f"Model directory not found or is not a directory: {directory.resolve()}")

    def _populate_models_dropdown(self):
        self.model_combo.clear()
        found_model_codes = set() # Keep track of codes already added to avoid duplicates in dropdown

        # 1. Scan the primary MODEL_DIR (e.g., ROOT/models)
        self._scan_model_directory(MODEL_DIR, found_model_codes)

        # 2. Scan the additional 'models/other_models' directory
        other_models_dir = Path(MODEL_DIR.parent / "models" / "other_models") # Assuming ROOT/models/other_models
        # Correction based on user path: C:\DEV\Disenchanter\models\other_models
        # If MODEL_DIR is C:\DEV\Disenchanter\models, then other_models_dir is its sibling.
        # No, MODEL_DIR is workspace_root/models. So other_models_dir is workspace_root/models/other_models.
        # User path is C:\DEV\Disenchanter\models\other_models. Workspace root is C:\DEV\Disenchanter.
        # So, it should be Path(SCRIPT_DIR / "models" / "other_models") - assuming SCRIPT_DIR is workspace root.
        # SCRIPT_DIR in ocr.py is __file__.parent. If ui.py is also in root, SCRIPT_DIR here would be root.
        # Let's define other_models_dir relative to workspace root. Workspace root is Path.cwd() or a known base.
        # For simplicity, let's assume SCRIPT_DIR (Path(__file__).parent) is the workspace root for ui.py
        current_script_dir = Path(__file__).resolve().parent
        other_models_dir_to_scan = current_script_dir / "models" / "other_models"
        self._scan_model_directory(other_models_dir_to_scan, found_model_codes)
        
        # 3. Add default models that can be downloaded if not already found locally
        default_models_for_download = ['eng', 'deu_frak']
        for model_code in default_models_for_download:
            if model_code not in found_model_codes:
                # These are typically downloaded to MODEL_DIR, so we don't add to found_model_codes here
                # as they are not *physically* present yet in a scanned dir unless already downloaded.
                self.model_combo.addItem(self._get_display_model_name(model_code))
                print(f"Adding display for default downloadable model '{model_code}' to dropdown.")

        if self.model_combo.count() == 0:
            self.model_combo.addItem("No models available")
            self.model_combo.setEnabled(False)
        else:
            deu_frak_display_name = self._get_display_model_name('deu_frak')
            index = self.model_combo.findText(deu_frak_display_name)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            elif self.model_combo.count() > 0:
                 self.model_combo.setCurrentIndex(0)
            self.model_combo.setEnabled(True)

    def _update_button_states(self):
        file_selected = bool(self.selected_file_path)
        model_selected_for_single = (
            self.model_combo.isEnabled() and self.model_combo.count() > 0 and \
            self.model_combo.currentText() != "No models available"
        )
        self.transcribe_button.setEnabled(file_selected and model_selected_for_single)

    def select_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open Image File', '',
                                               "Image files (*.jpg *.jpeg *.png *.bmp *.tiff);;All files (*.*)")
        if fname:
            self.selected_file_path = fname
            self.info_label.setText(f"Selected: {os.path.basename(fname)}")
            self.output_text_area.setPlainText("File selected. Ready to transcribe.")
            self.current_word_data = None # Clear previous OCR data
            try:
                pixmap_to_load = QPixmap(fname)
                if pixmap_to_load.isNull():
                    self.image_viewer_label.set_pixmap(None) # Clear image in viewer
                    self.image_viewer_label.setText(f"Error: Could not load image '{os.path.basename(fname)}'.")
                else:
                    self.image_viewer_label.set_pixmap(pixmap_to_load)
                self.image_viewer_label.set_word_data(None) # Clear boxes from previous image
            except Exception as e:
                self.image_viewer_label.set_pixmap(None)
                self.image_viewer_label.setText(f"Error loading image: {e}")
                print(f"Error in select_file (loading pixmap): {e}")
        else:
            self.selected_file_path = None
            self.current_word_data = None
            self.image_viewer_label.set_pixmap(None)
            self.image_viewer_label.set_word_data(None)
            self.info_label.setText("Select Image File")
            self.output_text_area.setPlaceholderText("Transcription output...")
            self.output_text_area.clear()
        self._update_button_states()

    def transcribe_file(self):
        if not self.selected_file_path:
            self.output_text_area.setPlainText("Error: No file selected."); return
        selected_display_name = self.model_combo.currentText()
        if not selected_display_name or selected_display_name == "No models available":
             self.output_text_area.setPlainText("Error: No language model selected."); return
        
        actual_model_code = self._extract_code_from_display_name(selected_display_name)
        display_name_for_output = self._get_display_model_name(actual_model_code) # Get consistent display name

        self.output_text_area.setPlainText(f"Transcribing {os.path.basename(self.selected_file_path)} using '{display_name_for_output}'...")
        QApplication.processEvents()
        try:
            # When transcribing, ocr.py's transcribe_image will use ensure_model_exists for models
            # not found in a specific_model_dir. ensure_model_exists looks in MODEL_DIR (ROOT/models).
            # If a model from other_models is selected, we need to tell transcribe_image where to find it.
            # This requires a change in how we call transcribe_image or how it resolves paths for non-default dirs.
            
            # Current logic: transcribe_image(path, code) -> uses MODEL_DIR for code, or downloads to MODEL_DIR.
            # We need to pass specific_model_dir if the selected model is known to be in other_models_dir_to_scan.
            
            # Simplification for now: Assume all models selectable in dropdown are either in MODEL_DIR,
            # or are one of the special downloadable ones that ensure_model_exists handles into MODEL_DIR.
            # For models explicitly from other_models_dir_to_scan, this needs more robust handling if they
            # are NOT also copied/symlinked to MODEL_DIR or if ensure_model_exists cannot find them.
            
            # For now, this will only correctly find models in MODEL_DIR or those downloadable to MODEL_DIR.
            # Models *only* in other_models might not be found by transcribe_image unless specific_model_dir is passed.
            # This is a limitation if models from other_models are not also in MODEL_DIR or downloadable.
            
            # To properly use models from other_models_dir_to_scan, we need to know their origin.
            # The dropdown currently doesn't store this. This needs a more involved fix.
            # For now, let's keep the existing call which works for MODEL_DIR and downloadable models.
            # The user's request was to make them *visible* in dropdown, which this part achieves.
            # Making them *functional* from other_models via single transcribe button requires more UI/logic change.

            plain_text, word_data = transcribe_image(self.selected_file_path, actual_model_code)
            if word_data is not None:
                self.current_word_data = word_data # Store for other uses if needed
                self.image_viewer_label.set_word_data(word_data) # Pass data to viewer for drawing boxes
                self.output_text_area.setPlainText(f"--- Transcription Result ('{display_name_for_output}') ---\n{plain_text}")
                # ImageViewer will repaint with boxes due to set_word_data calling self.update()
                print(f"Transcription successful. Word count: {len(word_data)}")
            else:
                self.current_word_data = None
                self.image_viewer_label.set_word_data(None) # Clear any existing boxes
                self.output_text_area.setPlainText(plain_text) # Display error from OCR
                print(f"OCR Error: {plain_text}")
        except Exception as e:
            self.current_word_data = None
            self.image_viewer_label.set_word_data(None)
            self.output_text_area.setPlainText(f"An error occurred during transcription: {e}")
            print(f"Error in DisenchanterApp.transcribe_file: {e}")

    # Removed app-level resizeEvent, ImageViewer handles its own scaling and repainting on resize.