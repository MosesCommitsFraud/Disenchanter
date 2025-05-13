# Placeholder for UI elements using PyQt6
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, 
    QApplication, QComboBox, QTextEdit, QSplitter
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QTextCursor, QTextCharFormat, QBrush # Added QTextCursor, QTextCharFormat, QBrush
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF # Added pyqtSignal, QPointF
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

class ImageViewer(QLabel):
    wordHovered = pyqtSignal(object) # Emits word_id (int) or None

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
        self.update()

    def set_word_data(self, word_data_list):
        self._word_data = word_data_list if word_data_list else []
        self.set_highlighted_words(set()) # Clear previous selection highlights
        if self._hovered_word_id is not None: # Clear hover state if new data is set
            self._hovered_word_id = None
            self.wordHovered.emit(None) # Notify that hover is lost
        self.update()

    def set_highlighted_words(self, word_ids: set):
        self._highlighted_word_ids = word_ids if word_ids else set()
        self.update() # Trigger repaint to show/clear highlights

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
            painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._original_pixmap.isNull():
            self._update_scaled_pixmap_and_offsets()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if not self._word_data or self._scale_factor == 0: # Ensure data exists and scale is valid
            if self._hovered_word_id is not None: # If previously hovering, clear it
                self._hovered_word_id = None
                self.wordHovered.emit(None)
                self.update()
            return

        mouse_pos = event.pos()
        # Transform mouse coordinates to original image coordinates
        original_x = (mouse_pos.x() - self._offset_x) / self._scale_factor
        original_y = (mouse_pos.y() - self._offset_y) / self._scale_factor
        
        found_word_id = None
        for word in self._word_data:
            word_rect = QRectF(word['left'], word['top'], word['width'], word['height'])
            if word_rect.contains(QPointF(original_x, original_y)):
                found_word_id = word.get('word_id')
                break
        
        if self._hovered_word_id != found_word_id:
            self._hovered_word_id = found_word_id
            self.wordHovered.emit(self._hovered_word_id)
            self.update() # Trigger repaint for hover highlight change

class DisenchanterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disenchanter - Interactive OCR")
        self.setGeometry(50, 50, 1200, 700)
        self.selected_file_path = None
        self.current_word_data = [] # Store list of word dicts (with word_id)
        self.current_text_html = "" # Store the generated HTML for QTextEdit

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
        self.output_text_area.setMouseTracking(True) # Enable mouse tracking for text hover
        self.output_text_area.cursorPositionChanged.connect(self.on_text_cursor_moved)
        self.splitter.addWidget(self.output_text_area)
        
        # Connect ImageViewer hover signal to slot
        self.image_viewer_label.wordHovered.connect(self._on_image_word_hovered)

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
            self.current_word_data = [] # Clear previous OCR data
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
        try:
            word_data_iter = iter(self.current_word_data)
            
            # Define punctuation characters for stripping (used in word comparison)
            punctuation_chars = (
                ".,;:!?()[]{}<>"
                "\\\"'`-~"
                "\u00AB\u00BB\u201E\u201C\u2013\u2014\u2019\u2018\u201A\u201D"
                "*&^%$#@+/\\|_"
            )
            
            plain_text, word_data_list = transcribe_image(self.selected_file_path, actual_model_code)
            if word_data_list is not None:
                self.current_word_data = word_data_list
                self.image_viewer_label.set_word_data(word_data_list)
                self.output_text_area.clear()
                cursor = self.output_text_area.textCursor()

                # Standard font for the text area
                base_format = QTextCharFormat()
                font = self.output_text_area.font() # Get current font from widget
                base_format.setFont(font)
                
                # Insert heading
                heading_format = QTextCharFormat(base_format)
                heading_font = heading_format.font()
                heading_font.setBold(True)
                heading_format.setFont(heading_font)
                cursor.insertText(f"Result ('{display_name_for_output}'):\\n", heading_format)
                
                # For simplicity in line breaking, we use the structure of plain_text from ocr.py
                # We assume word_data_list is in the correct reading order and matches plain_text words.
                if plain_text: # Ensure plain_text is not None
                    lines = plain_text.split('\\n')
                    for i, line_text in enumerate(lines):
                        words_in_line = line_text.split(' ')
                        for j, word_str_from_plain_text in enumerate(words_in_line):
                            if not word_str_from_plain_text: # Skip empty strings from multiple spaces
                                if j < len(words_in_line) -1: # If not the last potential word, add a space
                                     cursor.insertText(" ", base_format)
                                continue
                            
                            try:
                                current_word_info = next(word_data_iter)
                                # Basic check: does the word from plain_text somewhat match the word_data text?
                                # This isn't perfect but helps align. Tesseract sometimes has subtle differences.
                                # A more robust method would be to have ocr.py ensure word_ids map directly to segments of plain_text.
                                if word_str_from_plain_text.strip(punctuation_chars) == current_word_info['text'].strip(punctuation_chars):
                                    char_format_for_word = QTextCharFormat(base_format)
                                    char_format_for_word.setProperty(QTextCharFormat.Property.UserProperty + 1, current_word_info['word_id'])
                                    cursor.insertText(current_word_info['text'], char_format_for_word)
                                else:
                                    # Fallback: insert the word from plain_text if mismatch, apply no ID
                                    # Or try to find the next matching word_info - this can get complex.
                                    # For now, insert plain_text word and advance word_data_iter if possible.
                                    cursor.insertText(word_str_from_plain_text, base_format)
                                    # This might mean we are out of sync. To resync, one might search word_data_iter.
                                    # For now, this example assumes a mostly clean 1:1 mapping for simplicity of example.
                            except StopIteration: # Ran out of word_data items
                                cursor.insertText(word_str_from_plain_text, base_format) # Insert remaining plain_text words
                            
                            if j < len(words_in_line) - 1: # Add space if not the last word in the line
                                cursor.insertText(" ", base_format)
                        if i < len(lines) - 1: # Add newline if not the last line
                            cursor.insertBlock() # Inserts a new paragraph/block, which means a newline
                else: # OCR might have returned an error string in plain_text or empty result
                    cursor.insertText(plain_text if plain_text else "Error: OCR returned no text and no word data.", base_format)

                print(f"OK. Words: {len(word_data_list)}")
            else: # Error from transcribe_image
                self.current_word_data = []
                self.image_viewer_label.set_word_data([])
                self.output_text_area.setPlainText(plain_text) # Show error string
                print(f"OCR Err: {plain_text}")
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
        word_id_variant = char_format.property(QTextCharFormat.Property.UserProperty + 1)
        
        highlight_ids = set()
        if word_id_variant is not None and word_id_variant.isValid():
            word_id, ok = word_id_variant.toInt()
            if ok: # Check if conversion to int was successful
                 # Check if this word_id actually exists in our current_word_data as a sanity check
                if any(w['word_id'] == word_id for w in self.current_word_data):
                    highlight_ids.add(word_id)
        self.image_viewer_label.set_highlighted_words(highlight_ids)

    def _on_image_word_hovered(self, hovered_word_id):
        if not self.current_word_data: return

        doc = self.output_text_area.document()
        cursor = QTextCursor(doc) # A cursor to traverse and apply formats

        # Base format for regular text (should match what's used in transcribe_file)
        # For simplicity, recreate a basic one. Ideally, this is stored or retrieved.
        base_text_format = QTextCharFormat()
        font = self.output_text_area.font() # Use the QTextEdit's current default font
        base_text_format.setFont(font)
        base_text_format.setBackground(QBrush(Qt.GlobalColor.transparent)) # Ensure no background for normal text

        # Format for hovered text
        hover_text_format = QTextCharFormat(base_text_format)
        hover_text_format.setBackground(QBrush(HIGHLIGHT_COLOR_TEXT_BG))

        # Iterate through the document to apply/clear formats
        block = doc.firstBlock()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    fmt = fragment.charFormat()
                    frag_word_id_variant = fmt.property(QTextCharFormat.Property.UserProperty + 1)
                    if frag_word_id_variant is not None and frag_word_id_variant.isValid():
                        frag_word_id, ok = frag_word_id_variant.toInt()
                        if ok: # Check if conversion to int was successful
                            # Apply selection to the fragment to change its format
                            cursor.setPosition(fragment.position())
                            cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor)
                            if frag_word_id == hovered_word_id:
                                cursor.setCharFormat(hover_text_format)
                            else:
                                # Check if this fragment originally had a word_id property, if so, reset to base_text_format
                                # (This avoids accidentally removing bold from headings, etc. if they don't have word_id)
                                cursor.setCharFormat(base_text_format) 
                    else:
                        # If the fragment has no word_id (e.g. it's a heading or space inserted without ID)
                        # ensure it doesn't have the hover background if it somehow got it.
                        # This part might need more care if other stylings are present.
                        # For now, if it had a background from hover, this would clear it.
                        # However, our logic only applies hover to ID'd words.
                        # We might need to ensure that non-word_id text (like headings) is not affected.
                        # The current logic in transcribe_file sets heading_format explicitly.
                        # Spaces are inserted with base_format. So this branch might be less critical.
                        pass # Non-word_id fragments are left as is, unless they were previously hovered (unlikely)

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