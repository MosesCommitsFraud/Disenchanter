# Placeholder for UI elements using PyQt6
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, 
    QApplication, QComboBox, QTextEdit, QSplitter
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QTextCursor, QTextCharFormat, QBrush, QMouseEvent # Added QMouseEvent here
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF # Removed QMouseEvent from here
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

# Define highlight colors
HIGHLIGHT_COLOR_BOX = QColor(0, 255, 0, 180)  # Bright Green for box highlight
HIGHLIGHT_COLOR_TEXT_BG = QColor(200, 255, 200) # Light Green for text background highlight
DEFAULT_BOX_COLOR = QColor(255, 0, 0, 180) # Red for default boxes
HOVER_HIGHLIGHT_COLOR_BOX = QColor(255, 165, 0, 200) # Orange for hover highlight
ROI_BOX_COLOR = QColor(0, 0, 255, 150) # Blue for ROI box
ROI_DRAWING_PEN_STYLE = Qt.PenStyle.DashLine

class ImageViewer(QLabel):
    wordHovered = pyqtSignal(object) # Emits word_id (int) or None
    roiDefined = pyqtSignal(object) # Emits QRectF (original image coordinates) or None for clear

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
        self._highlighted_word_ids = set() # Store IDs of words to highlight (from text cursor)
        self._hovered_word_id = None # Store ID of word currently under mouse hover
        
        # ROI Attributes
        self._is_defining_roi = False
        self._roi_selection_start_pos = None # QPoint, widget coordinates
        self._current_roi_visual_rect = None # QRectF, widget coordinates, for live drawing
        self._defined_roi_original_coords = None # QRectF, original image coordinates

        self.setMouseTracking(True)

    def set_pixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            self._original_pixmap = pixmap
            self._update_scaled_pixmap_and_offsets()
        else:
            self._original_pixmap = QPixmap()
            self._pixmap = QPixmap()
            self.setText("Image will appear here." if not self._word_data else "No image loaded or image cleared.")
            self._word_data = []
        self.clear_defined_roi(emit_signal=False) # Clear ROI if image changes
        self.update()

    def set_word_data(self, word_data_list):
        self._word_data = word_data_list if word_data_list else []
        self.set_highlighted_words(set()) # Clear previous selection highlights
        if self._hovered_word_id is not None:
            self._hovered_word_id = None
            self.wordHovered.emit(None)
        # ROI is independent of word data, so don't clear it here necessarily.
        # However, if OCR is re-run, UI might clear and re-set ROI based on new context.
        self.update()

    def start_roi_definition(self):
        if self._original_pixmap.isNull():
            print("Cannot define ROI: No image loaded.")
            return
        self.clear_defined_roi(emit_signal=True) # Clear any previous ROI first and notify
        self._is_defining_roi = True
        self._roi_selection_start_pos = None
        self._current_roi_visual_rect = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        print("ImageViewer: ROI definition started. Drag to define region.")
        self.update()

    def clear_defined_roi(self, emit_signal=True):
        self._defined_roi_original_coords = None
        self._current_roi_visual_rect = None # Clear visual cue for live drawing too
        if self._is_defining_roi: # If was in definition mode, stop it
            self._is_defining_roi = False
            self.unsetCursor()
        if emit_signal:
            self.roiDefined.emit(None) # Emit None to signal ROI clearance
        self.update()

    def set_highlighted_words(self, word_ids: set):
        self._highlighted_word_ids = word_ids if word_ids else set()
        self.update() # Trigger repaint to show/clear highlights

    def _update_scaled_pixmap_and_offsets(self):
        if self._original_pixmap.isNull():
            current_display_pixmap = self.pixmap()
            if current_display_pixmap is not None and not current_display_pixmap.isNull():
                super().setPixmap(QPixmap()) # Clear the QLabel's pixmap
            self.setText("Image will appear here.")
            self._scale_factor = 1.0
            self._offset_x = 0
            self._offset_y = 0
            self.clear_defined_roi(emit_signal=False) # Clear ROI if image is cleared
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
        painter = QPainter(self) # Start painter once

        # Draw ROI first, so word boxes can be on top if needed, or change order
        if self._defined_roi_original_coords and not self._original_pixmap.isNull() and self._scale_factor > 0:
            # Scale defined ROI (original coords) to current widget display coords
            scaled_roi_left = self._defined_roi_original_coords.left() * self._scale_factor + self._offset_x
            scaled_roi_top = self._defined_roi_original_coords.top() * self._scale_factor + self._offset_y
            scaled_roi_width = self._defined_roi_original_coords.width() * self._scale_factor
            scaled_roi_height = self._defined_roi_original_coords.height() * self._scale_factor
            
            pen = QPen(ROI_BOX_COLOR)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(QRectF(scaled_roi_left, scaled_roi_top, scaled_roi_width, scaled_roi_height))

        elif self._is_defining_roi and self._current_roi_visual_rect and not self._current_roi_visual_rect.isNull():
            # Draw the live ROI rectangle (already in widget coordinates)
            pen = QPen(ROI_BOX_COLOR)
            pen.setWidth(1)
            pen.setStyle(ROI_DRAWING_PEN_STYLE)
            painter.setPen(pen)
            painter.drawRect(self._current_roi_visual_rect)

        if not self._pixmap.isNull() and self._word_data:
            # Word drawing logic (painter already started)
            for word in self._word_data:
                word_id = word.get('word_id')
                pen_color = DEFAULT_BOX_COLOR
                pen_width = 1

                if word_id == self._hovered_word_id:
                    pen_color = HOVER_HIGHLIGHT_COLOR_BOX
                    pen_width = 2
                elif word_id in self._highlighted_word_ids:
                    pen_color = HIGHLIGHT_COLOR_BOX
                    pen_width = 2
                
                pen = QPen(pen_color)
                pen.setWidth(pen_width)
                painter.setPen(pen)
                
                scaled_left = int(word['left'] * self._scale_factor + self._offset_x)
                scaled_top = int(word['top'] * self._scale_factor + self._offset_y)
                scaled_width = int(word['width'] * self._scale_factor)
                scaled_height = int(word['height'] * self._scale_factor)
                painter.drawRect(scaled_left, scaled_top, scaled_width, scaled_height)
        
        # No need to call painter.end() if painter is local to paintEvent and goes out of scope
        # However, explicit painter.end() is good practice if painter was passed or member. Here it's local.

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._original_pixmap.isNull():
            self._update_scaled_pixmap_and_offsets()

    def mousePressEvent(self, event: QMouseEvent): # Added QMouseEvent type hint
        if self._is_defining_roi and event.button() == Qt.MouseButton.LeftButton and not self._original_pixmap.isNull():
            self._roi_selection_start_pos = event.pos() # This is a QPoint
            # Convert QPoint to QPointF for QRectF constructor
            start_pos_f = QPointF(self._roi_selection_start_pos)
            # Ensure the rect is valid even if it's just a point initially
            self._current_roi_visual_rect = QRectF(start_pos_f, start_pos_f)
            self.update()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent): # Added QMouseEvent type hint
        if self._is_defining_roi and self._roi_selection_start_pos and not self._original_pixmap.isNull():
            if event.buttons() & Qt.MouseButton.LeftButton: # Check if left button is held down
                # event.pos() is QPoint, convert to QPointF for setBottomRight with QRectF
                self._current_roi_visual_rect.setBottomRight(QPointF(event.pos()))
                self.update()
                return # Don't do word hover logic while actively drawing ROI

        # Existing word hover logic (if not defining ROI)
        if not self._is_defining_roi: # Only do hover if not defining ROI
            if not self._word_data or self._scale_factor == 0:
                if self._hovered_word_id is not None:
                    self._hovered_word_id = None
                    self.wordHovered.emit(None)
                    self.update()
                return

            mouse_pos = event.pos()
            original_x = (mouse_pos.x() - self._offset_x) / self._scale_factor if self._scale_factor != 0 else 0
            original_y = (mouse_pos.y() - self._offset_y) / self._scale_factor if self._scale_factor != 0 else 0
            
            found_word_id = None
            for word in self._word_data:
                word_rect = QRectF(word['left'], word['top'], word['width'], word['height'])
                if word_rect.contains(QPointF(original_x, original_y)):
                    found_word_id = word.get('word_id')
                    break
            
            if self._hovered_word_id != found_word_id:
                self._hovered_word_id = found_word_id
                self.wordHovered.emit(self._hovered_word_id)
                self.update()
        else: # If defining ROI, but not dragging (e.g. just moving mouse after click but before release)
            super().mouseMoveEvent(event) # Allow base class to handle if needed

    def mouseReleaseEvent(self, event: QMouseEvent): # Added QMouseEvent type hint
        if self._is_defining_roi and self._roi_selection_start_pos and event.button() == Qt.MouseButton.LeftButton and not self._original_pixmap.isNull():
            if self._current_roi_visual_rect and not self._current_roi_visual_rect.isNull() and self._scale_factor > 0:
                # Normalize the rectangle (top-left, bottom-right)
                final_visual_rect = self._current_roi_visual_rect.normalized()

                # Check if the visual rect has a valid size (e.g., > 1x1 pixel)
                if final_visual_rect.width() > 1 and final_visual_rect.height() > 1:
                    # Convert visual rect (widget coords) to original image coordinates
                    orig_x = (final_visual_rect.left() - self._offset_x) / self._scale_factor
                    orig_y = (final_visual_rect.top() - self._offset_y) / self._scale_factor
                    orig_width = final_visual_rect.width() / self._scale_factor
                    orig_height = final_visual_rect.height() / self._scale_factor

                    # Clamp ROI to image boundaries (original coordinates)
                    img_w = self._original_pixmap.width()
                    img_h = self._original_pixmap.height()

                    orig_x = max(0, orig_x)
                    orig_y = max(0, orig_y)
                    
                    # Calculate clamped bottom-right coordinates
                    orig_br_x = min(img_w, orig_x + orig_width)
                    orig_br_y = min(img_h, orig_y + orig_height)

                    # Update width and height based on clamped bottom-right
                    orig_width = orig_br_x - orig_x
                    orig_height = orig_br_y - orig_y
                    
                    if orig_width > 0 and orig_height > 0:
                         self._defined_roi_original_coords = QRectF(orig_x, orig_y, orig_width, orig_height)
                         print(f"ImageViewer: ROI defined (original coords): {self._defined_roi_original_coords}")
                         self.roiDefined.emit(self._defined_roi_original_coords)
                    else: # ROI became invalid after clamping
                        print("ImageViewer: Defined ROI has zero or negative size after clamping to image boundaries.")
                        self._defined_roi_original_coords = None # Ensure it's cleared
                        self.roiDefined.emit(None) # Signal that ROI definition failed or resulted in nothing
                else: # Visual rect was too small
                    print("ImageViewer: Selected ROI visual area is too small.")
                    self._defined_roi_original_coords = None
                    self.roiDefined.emit(None) # Signal that ROI definition failed or resulted in nothing

            else: # Scale factor is zero or visual rect is null
                print("ImageViewer: Cannot finalize ROI (invalid scale or rect).")
                self._defined_roi_original_coords = None
                self.roiDefined.emit(None)
            
            self._is_defining_roi = False
            self._roi_selection_start_pos = None
            self._current_roi_visual_rect = None # Clear the live drawing rect
            self.unsetCursor()
            self.update()
        else:
            super().mouseReleaseEvent(event)

class DisenchanterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disenchanter - Interactive OCR")
        self.setGeometry(50, 50, 1200, 700)
        self.selected_file_path = None
        self.current_word_data = [] # Store list of word dicts (with word_id)
        self.current_text_html = "" # Store the generated HTML for QTextEdit
        self.current_roi: QRectF | None = None # Store the current ROI (original image coordinates)

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

        # ROI Buttons
        self.define_roi_button = QPushButton("Define Page/ROI")
        self.define_roi_button.setToolTip("Click, then drag on the image to define a region for OCR.")
        self.define_roi_button.setEnabled(False) # Enabled when image is loaded
        self.define_roi_button.clicked.connect(self._start_roi_definition_mode)
        top_controls_layout.addWidget(self.define_roi_button)

        self.clear_roi_button = QPushButton("Clear ROI")
        self.clear_roi_button.setToolTip("Remove the defined OCR region.")
        self.clear_roi_button.setEnabled(False) # Enabled when ROI is set
        self.clear_roi_button.clicked.connect(self._clear_current_roi)
        top_controls_layout.addWidget(self.clear_roi_button)

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
        self.output_text_area.setMouseTracking(True) # Enable mouse tracking for text hover
        self.output_text_area.cursorPositionChanged.connect(self.on_text_cursor_moved)
        self.splitter.addWidget(self.output_text_area)
        
        # Connect ImageViewer hover signal to slot
        self.image_viewer_label.wordHovered.connect(self._on_image_word_hovered)
        # Connect ImageViewer ROI defined signal
        self.image_viewer_label.roiDefined.connect(self._on_roi_defined)

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
        self.define_roi_button.setEnabled(file_selected) # Can define ROI if image is loaded
        self.clear_roi_button.setEnabled(file_selected and self.current_roi is not None) # Can clear if ROI is set

    def select_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open Image File', '',
                                               "Image files (*.jpg *.jpeg *.png *.bmp *.tiff);;All files (*.*)")
        if fname:
            self.selected_file_path = fname
            self.info_label.setText(f"Selected: {os.path.basename(fname)}")
            self.output_text_area.setPlainText("File selected. Ready to transcribe.")
            self.current_word_data = [] # Clear previous OCR data
            self._clear_current_roi(emit_signal_from_viewer=False) # Clear ROI when new file is selected

            try:
                pixmap_to_load = QPixmap(fname)
                if pixmap_to_load.isNull():
                    self.image_viewer_label.set_pixmap(None) # Clear image in viewer
                    self.image_viewer_label.setText(f"Error: Could not load image '{os.path.basename(fname)}'.")
                else:
                    self.image_viewer_label.set_pixmap(pixmap_to_load)
                self.image_viewer_label.set_word_data([]) # Clear boxes from previous image
            except Exception as e:
                self.image_viewer_label.set_pixmap(None)
                self.image_viewer_label.setText(f"Error loading image: {e}")
                print(f"Error in select_file (loading pixmap): {e}")
        else:
            self.selected_file_path = None
            self.current_word_data = []
            self._clear_current_roi(emit_signal_from_viewer=False) # Clear ROI if file selection is cancelled/cleared
            self.image_viewer_label.set_pixmap(None)
            self.image_viewer_label.set_word_data([])
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
        display_name_for_output = self._get_display_model_name(actual_model_code)

        self.output_text_area.setHtml(f"Transcribing with <i>'{display_name_for_output}'</i>...")
        QApplication.processEvents()
        
        roi_to_pass = None
        if self.current_roi:
            # Convert QRectF to tuple (x, y, width, height) for ocr.py
            roi_to_pass = (
                int(self.current_roi.x()), 
                int(self.current_roi.y()), 
                int(self.current_roi.width()), 
                int(self.current_roi.height())
            )
            print(f"UI: Passing ROI to transcribe_image: {roi_to_pass}")

        try:
            # Define punctuation characters for stripping (used in word comparison)
            # This might be less critical now as we are not matching against plain_text for IDs
            # punctuation_chars = (
            #     ".,;:!?()[]{}<>"
            #     "\\\"'`-~" # Escaped backslash and double quote
            #     "\u00AB\u00BB\u201E\u201C\u2013\u2014\u2019\u2018\u201A\u201D"
            #     "*&^%$#@+/\\|_" # Escaped backslash
            # )

            plain_text, word_data_list = transcribe_image(
                self.selected_file_path, 
                actual_model_code,
                roi=roi_to_pass # Pass the ROI tuple
            )
            if word_data_list is not None:
                self.current_word_data = word_data_list # Update with new data
                self.image_viewer_label.set_word_data(word_data_list)
                self.output_text_area.clear()
                cursor = self.output_text_area.textCursor()

                base_format = QTextCharFormat()
                font = self.output_text_area.font()
                base_format.setFont(font)
                
                # Insert heading
                heading_format = QTextCharFormat(base_format)
                heading_font = heading_format.font()
                heading_font.setBold(True)
                heading_format.setFont(heading_font)
                cursor.insertText(f"Result ('{display_name_for_output}'):\n", heading_format) # Note: \n here will be a literal backslash-n
                cursor.insertBlock() # Actual newline after heading

                if not word_data_list: # No words returned from OCR
                    fallback_text = plain_text if plain_text else "OCR returned no words."
                    if not fallback_text.strip(): fallback_text = "OCR returned empty result."
                    cursor.insertText(fallback_text, base_format)
                else:
                    last_block = -1
                    last_par = -1
                    last_line = -1
                    first_word_in_document = True

                    for word_idx, word_info in enumerate(word_data_list):
                        current_block = word_info['block_num']
                        current_par = word_info['par_num']
                        current_line = word_info['line_num']

                        if not first_word_in_document:
                            # Check for new block, paragraph, or line
                            if current_block > last_block or \
                               current_par > last_par or \
                               current_line > last_line:
                                cursor.insertBlock() # Newline for new line/paragraph/block
                                # Heuristic: If it's a new block or paragraph, maybe add an extra empty line (visual spacing)
                                # This is a simple heuristic; real paragraph spacing is more complex.
                                if current_block > last_block or current_par > last_par:
                                    pass # Could insert another block here if desired: cursor.insertBlock()
                            else: # Same line, different word
                                cursor.insertText(" ", base_format) # Space between words on the same line
                        
                        char_format_for_word = QTextCharFormat(base_format)
                        char_format_for_word.setProperty(QTextCharFormat.Property.UserProperty + 1, word_info['word_id'])
                        cursor.insertText(word_info['text'], char_format_for_word)
                        
                        last_block, last_par, last_line = current_block, current_par, current_line
                        first_word_in_document = False

                print(f"OK. Words processed for text area: {len(word_data_list)}")
            else: # Error from transcribe_image (word_data_list is None)
                self.current_word_data = []
                self.image_viewer_label.set_word_data([])
                error_message = plain_text if plain_text else "Unknown OCR error."
                self.output_text_area.setPlainText(error_message) # Show error string
                print(f"OCR Err: {error_message}")
        except Exception as e:
            self.current_word_data = []
            self.image_viewer_label.set_word_data([])
            self.output_text_area.setPlainText(f"Error: {e}")
            print(f"Transcription Error: {e}")

    def on_text_cursor_moved(self):
        if not self.current_word_data:
            self.image_viewer_label.set_highlighted_words(set()) # Clear if no data
            return
        
        cursor = self.output_text_area.textCursor()
        char_format = cursor.charFormat()
        # Retrieve the custom property. It might be an int directly, or None if not set.
        word_id_prop = char_format.property(QTextCharFormat.Property.UserProperty + 1)
        
        highlight_ids = set()
        if isinstance(word_id_prop, int): # Check if it's an integer
            # Check if this word_id actually exists in our current_word_data as a sanity check
            if any(w['word_id'] == word_id_prop for w in self.current_word_data):
                highlight_ids.add(word_id_prop)
        
        self.image_viewer_label.set_highlighted_words(highlight_ids)

    def _on_image_word_hovered(self, hovered_word_id):
        if not self.current_word_data: return

        doc = self.output_text_area.document()
        cursor = QTextCursor(doc)

        block = doc.firstBlock()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    original_char_format = fragment.charFormat()
                    # Retrieve the custom property. It might be an int directly, or None if not set.
                    frag_word_id_prop = original_char_format.property(QTextCharFormat.Property.UserProperty + 1)

                    if isinstance(frag_word_id_prop, int): # Check if it's an integer
                        frag_word_id = frag_word_id_prop # Use the integer directly
                        
                        # This fragment is a word with an ID
                        new_char_format = QTextCharFormat(original_char_format)
                        cursor.setPosition(fragment.position())
                        cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor)

                        if frag_word_id == hovered_word_id:
                            new_char_format.setBackground(QBrush(HIGHLIGHT_COLOR_TEXT_BG))
                        else:
                            new_char_format.setBackground(QBrush(Qt.GlobalColor.transparent))
                        
                        cursor.setCharFormat(new_char_format)
                    # else: (Fragment does not have a word_id, or property is not an int)
                        # We leave its formatting untouched by this hover logic.
                        pass

                iterator += 1
            block = block.next()

    # Removed _highlight_text_spans as it's not implemented and we are focusing on image highlighting

    # Placeholder for anchor clicked if using QTextBrowser and <a href="word_id_N\">
    # def on_text_anchor_clicked(self, link_url):
    #     try: word_id = int(str(link_url.toString()).replace("word_id_",""))
    #     except ValueError: return
    #     self.image_viewer_label.set_highlighted_words({word_id})
    #     self._highlight_text_spans({word_id}) # Also highlight in text area

    # Removed app-level resizeEvent, ImageViewer handles its own scaling and repainting on resize.

    # --- ROI Handling Slots ---
    def _start_roi_definition_mode(self):
        if self.selected_file_path and not self.image_viewer_label._original_pixmap.isNull():
            self.info_label.setText("Defining ROI: Drag on image. Transcribe again to use.")
            self.image_viewer_label.start_roi_definition()
            # Buttons states will be updated via _on_roi_defined or when ROI is cleared.
        else:
            self.info_label.setText("Select an image first to define an ROI.")

    def _on_roi_defined(self, roi_rect_original_coords: QRectF | None):
        if roi_rect_original_coords and roi_rect_original_coords.isValid():
            self.current_roi = roi_rect_original_coords
            self.info_label.setText(f"ROI defined. Transcribe to apply. ({roi_rect_original_coords.x():.0f},{roi_rect_original_coords.y():.0f}, {roi_rect_original_coords.width():.0f}x{roi_rect_original_coords.height():.0f})")
            print(f"App: ROI successfully defined: {self.current_roi}")
        else: # ROI was cleared or definition failed/cancelled
            self.current_roi = None
            # If image viewer itself cleared it, it might be because a new image was loaded, or user cleared.
            # If ROI definition was active and user cancelled (e.g. small rect), ImageViewer emits None.
            if self.image_viewer_label._is_defining_roi: # Still in defining mode, but it resulted in None (e.g. tiny drag)
                self.info_label.setText("ROI definition cancelled or area too small. Try again.")
            elif self.selected_file_path: # Image present, but ROI cleared
                 self.info_label.setText(f"Selected: {os.path.basename(self.selected_file_path)}. ROI cleared.")
            else: # No image selected
                 self.info_label.setText("Select Image File")

            print("App: ROI cleared or definition failed.")
        self._update_button_states()

    def _clear_current_roi(self, emit_signal_from_viewer=True):
        """Clears the current ROI in the app and tells the image viewer to clear its visual."""
        self.current_roi = None
        if emit_signal_from_viewer:
            # This will trigger _on_roi_defined(None) eventually if viewer emits the signal
            self.image_viewer_label.clear_defined_roi() 
        else:
            # Called when we don't want image_viewer to re-emit roiDefined(None)
            # e.g. when a new file is loaded, select_file itself calls this.
            self.image_viewer_label._defined_roi_original_coords = None # Directly clear viewer's stored ROI
            self.image_viewer_label.update() # Repaint viewer
        
        if self.selected_file_path:
             self.info_label.setText(f"Selected: {os.path.basename(self.selected_file_path)}. ROI cleared.")
        else:
            self.info_label.setText("Select Image File")
        print("App: Current ROI cleared by user action or programmatically.")
        self._update_button_states()
        
    # --- End ROI Handling Slots ---