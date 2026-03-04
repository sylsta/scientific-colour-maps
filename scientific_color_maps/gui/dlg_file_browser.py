#! python3  # noqa: E265

"""
Dialog for browsing XML color map files and managing palettes in QGIS Style Manager.
"""

# standard
from pathlib import Path

# PyQGIS
from qgis.core import Qgis, QgsStyle, QgsApplication
from qgis.PyQt.QtCore import Qt, QCoreApplication, QSize
from qgis.PyQt.QtGui import QIcon, QColor, QPixmap
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QMessageBox,
    QFrame,
    QSizePolicy,
)

# project
from scientific_color_maps.__about__ import __title__, DIR_PLUGIN_ROOT
from scientific_color_maps.toolbelt import PlgLogger, PlgOptionsManager


class SortableTreeWidgetItem(QTreeWidgetItem):
    """TreeWidgetItem with custom sorting for checkbox column."""
    
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column == 0:
            self_val = self.data(0, Qt.UserRole + 1)
            other_val = other.data(0, Qt.UserRole + 1)
            if self_val is not None and other_val is not None:
                return self_val < other_val
        return super().__lt__(other)


class ColorRampBrowserDialog(QDialog):
    """Dialog to browse XML color map files and manage palettes in Style Manager."""

    TAG_NAME = "Sci.color.maps"

    def __init__(self, parent=None):
        """Initialize the dialog."""
        super().__init__(parent)
        self.log = PlgLogger().log
        self.plg_settings = PlgOptionsManager().get_plg_settings()
        self.style = QgsStyle.defaultStyle()
        self.initial_state = {}
        
        self.setup_ui()
        self.load_xml_files()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle(self.tr("Scientific Color Maps"))
        self.setMinimumSize(650, 500)
        self.resize(750, 550)
        
        # Main layout with margins
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header with icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        icon_label = QLabel()
        icon_label.setPixmap(QgsApplication.getThemeIcon("propertyicons/symbology.svg").pixmap(32, 32))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(self.tr("Color Map Palettes"))
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Status badge
        self.status_badge = QLabel()
        self.status_badge.setStyleSheet("""
            QLabel {
                background-color: #3498db;
                color: white;
                padding: 4px 10px;
                border-radius: 10px;
                font-size: 11px;
            }
        """)
        header_layout.addWidget(self.status_badge)
        
        layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #bdc3c7;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Tree widget
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels([
            self.tr("Color Ramp"),
            self.tr("Preview"),
            self.tr("Location"),
            self.tr("Size")
        ])
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setRootIsDecorated(True)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.setIndentation(20)
        self.file_tree.setAnimated(True)
        self.file_tree.setIconSize(QSize(100, 16))
        self.file_tree.itemChanged.connect(self.on_item_changed)
        
        # Style the tree (without indicator styling to keep native checkboxes)
        self.file_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
            }
            QTreeWidget::item {
                padding: 4px 2px;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #e8f4fc;
            }
            QHeaderView::section {
                background-color: #ecf0f1;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #bdc3c7;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        
        header = self.file_tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 120)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.file_tree)

        # Info bar
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)
        
        info_icon = QLabel()
        info_icon.setPixmap(QgsApplication.getThemeIcon("mIconInfo.svg").pixmap(16, 16))
        info_layout.addWidget(info_icon)
        
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        info_layout.addWidget(self.status_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Selection buttons
        select_layout = QHBoxLayout()
        select_layout.setSpacing(8)
        
        self.select_all_btn = QPushButton(self.tr(" Select All"))
        self.select_all_btn.setIcon(QgsApplication.getThemeIcon("mActionSelectAll.svg"))
        self.select_all_btn.setCursor(Qt.PointingHandCursor)
        self.select_all_btn.clicked.connect(self.select_all)
        select_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton(self.tr(" Select None"))
        self.select_none_btn.setIcon(QgsApplication.getThemeIcon("mActionDeselectAll.svg"))
        self.select_none_btn.setCursor(Qt.PointingHandCursor)
        self.select_none_btn.clicked.connect(self.select_none)
        select_layout.addWidget(self.select_none_btn)
        
        self.restore_btn = QPushButton(self.tr(" Restore"))
        self.restore_btn.setIcon(QgsApplication.getThemeIcon("mActionUndo.svg"))
        self.restore_btn.setCursor(Qt.PointingHandCursor)
        self.restore_btn.clicked.connect(self.restore_selection)
        select_layout.addWidget(self.restore_btn)
        
        select_layout.addStretch()
        layout.addLayout(select_layout)

        # Apply button style
        button_style = """
            QPushButton {
                padding: 6px 14px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QPushButton:hover {
                background-color: #ecf0f1;
                border-color: #95a5a6;
            }
            QPushButton:pressed {
                background-color: #d5dbdb;
            }
        """
        self.select_all_btn.setStyleSheet(button_style)
        self.select_none_btn.setStyleSheet(button_style)
        self.restore_btn.setStyleSheet(button_style)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.apply_btn = QPushButton(self.tr(" Apply Changes"))
        self.apply_btn.setIcon(QgsApplication.getThemeIcon("mActionSaveAllEdits.svg"))
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        self.apply_btn.clicked.connect(self.apply_changes)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                background-color: #27ae60;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        btn_layout.addWidget(self.apply_btn)

        self.close_btn = QPushButton(self.tr(" Close"))
        self.close_btn.setIcon(QgsApplication.getThemeIcon("mIconClose.svg"))
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QPushButton:hover {
                background-color: #ecf0f1;
            }
            QPushButton:pressed {
                background-color: #d5dbdb;
            }
        """)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def tr(self, message: str) -> str:
        """Get translation for a string."""
        return QCoreApplication.translate(self.__class__.__name__, message)

    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def get_ramp_name_from_filename(self, filename: str) -> str:
        """Extract ramp name from XML filename."""
        name = filename
        if name.endswith('.xml'):
            name = name[:-4]
        if name.endswith('_QGIS'):
            name = name[:-5]
        return name

    def find_matching_files(self, directory: Path, pattern: str) -> dict:
        """Find files matching the pattern in directory and first level subdirectories."""
        results = {}
        
        root_files = list(directory.glob(pattern))
        if root_files:
            results["."] = sorted(root_files, key=lambda p: p.name.lower())
        
        try:
            for subdir in sorted(directory.iterdir()):
                if subdir.is_dir() and not subdir.name.startswith('.'):
                    subdir_files = list(subdir.glob(pattern))
                    if subdir_files:
                        results[subdir.name] = sorted(subdir_files, key=lambda p: p.name.lower())
        except PermissionError as e:
            self.log(
                message=f"Permission denied accessing subdirectories: {e}",
                log_level=Qgis.MessageLevel.Warning,
            )
        
        return results

    def load_xml_files(self):
        """Load XML files from the configured directory."""
        self.file_tree.blockSignals(True)
        self.file_tree.clear()
        self.initial_state.clear()
        
        directory = DIR_PLUGIN_ROOT / self.plg_settings.default_color_maps_dir
        pattern = self.plg_settings.file_pattern
        
        if not directory.is_dir():
            self.status_label.setText(self.tr(f"Directory not found: {directory}"))
            self.status_badge.setText("Error")
            self.status_badge.setStyleSheet("background-color: #e74c3c; color: white; padding: 4px 10px; border-radius: 10px; font-size: 11px;")
            self.file_tree.blockSignals(False)
            return
        
        existing_ramps = set(self.style.colorRampNames())
        
        try:
            matching_files = self.find_matching_files(directory, pattern)
        except Exception as e:
            self.status_label.setText(self.tr(f"Error searching files: {e}"))
            self.file_tree.blockSignals(False)
            return
        
        total_files = 0
        installed_count = 0
        
        folder_icon = QgsApplication.getThemeIcon("mIconFolder.svg")
        
        for subdir_name, files in matching_files.items():
            if subdir_name == ".":
                display_name = self.tr("Root")
            else:
                display_name = subdir_name
            
            parent_item = QTreeWidgetItem(self.file_tree)
            parent_item.setIcon(0, folder_icon)
            parent_item.setText(0, f"{display_name}")
            parent_item.setText(1, "")
            parent_item.setText(2, "")
            parent_item.setText(3, f"{len(files)} items")
            parent_item.setExpanded(True)
            
            # Style folder row
            for col in range(4):
                parent_item.setBackground(col, QColor("#f0f4f7"))
            
            for file_path in files:
                file_item = SortableTreeWidgetItem(parent_item)
                
                ramp_name = self.get_ramp_name_from_filename(file_path.name)
                is_installed = ramp_name in existing_ramps
                
                file_item.setFlags(file_item.flags() | Qt.ItemIsUserCheckable)
                file_item.setCheckState(0, Qt.Checked if is_installed else Qt.Unchecked)
                file_item.setData(0, Qt.UserRole + 1, 1 if is_installed else 0)  # Sort data
                
                file_item.setData(0, Qt.UserRole, str(file_path))  # File path
                file_item.setData(1, Qt.UserRole, ramp_name)  # Ramp name
                
                self.initial_state[ramp_name] = is_installed
                
                # Display ramp name
                file_item.setText(0, ramp_name)
                
                # Load SVG preview
                svg_path = file_path.parent / f"{ramp_name}.svg"
                if svg_path.exists():
                    file_item.setIcon(1, QIcon(str(svg_path)))
                
                file_item.setText(2, subdir_name if subdir_name != "." else "")
                
                try:
                    size = file_path.stat().st_size
                    file_item.setText(3, self.format_file_size(size))
                except OSError:
                    file_item.setText(3, "—")
                
                total_files += 1
                if is_installed:
                    installed_count += 1
        
        self.file_tree.blockSignals(False)
        self.apply_btn.setEnabled(False)
        
        # Update status
        self.status_label.setText(f"{total_files} palettes available")
        self.status_badge.setText(f"{installed_count} installed")
        
        if installed_count == total_files:
            badge_color = "#27ae60"  # Green - all installed
        elif installed_count == 0:
            badge_color = "#95a5a6"  # Gray - none installed
        else:
            badge_color = "#3498db"  # Blue - some installed
            
        self.status_badge.setStyleSheet(f"""
            background-color: {badge_color};
            color: white;
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 11px;
        """)

    def on_item_changed(self, item, column):
        """Handle item check state change."""
        if column == 0:
            is_checked = item.checkState(0) == Qt.Checked
            item.setData(0, Qt.UserRole + 1, 1 if is_checked else 0)
            self.update_apply_button()

    def update_apply_button(self):
        """Enable/disable Apply button based on changes."""
        has_changes = False
        for item in self._get_file_items():
            ramp_name = item.data(1, Qt.UserRole)
            is_checked = item.checkState(0) == Qt.Checked
            initial = self.initial_state.get(ramp_name, False)
            if is_checked != initial:
                has_changes = True
                break
        self.apply_btn.setEnabled(has_changes)

    def select_all(self):
        """Select all file items."""
        self._set_all_check_state(Qt.Checked)

    def select_none(self):
        """Deselect all file items."""
        self._set_all_check_state(Qt.Unchecked)

    def restore_selection(self):
        """Restore initial selection state."""
        self.file_tree.blockSignals(True)
        for item in self._get_file_items():
            ramp_name = item.data(1, Qt.UserRole)
            initial = self.initial_state.get(ramp_name, False)
            item.setCheckState(0, Qt.Checked if initial else Qt.Unchecked)
            item.setData(0, Qt.UserRole + 1, 1 if initial else 0)
        self.file_tree.blockSignals(False)
        self.apply_btn.setEnabled(False)

    def _set_all_check_state(self, state):
        """Set check state for all file items."""
        self.file_tree.blockSignals(True)
        root = self.file_tree.invisibleRootItem()
        for i in range(root.childCount()):
            parent_item = root.child(i)
            for j in range(parent_item.childCount()):
                file_item = parent_item.child(j)
                file_item.setCheckState(0, state)
                file_item.setData(0, Qt.UserRole + 1, 1 if state == Qt.Checked else 0)
        self.file_tree.blockSignals(False)
        self.update_apply_button()

    def _get_file_items(self):
        """Get all file items from the tree."""
        items = []
        root = self.file_tree.invisibleRootItem()
        for i in range(root.childCount()):
            parent_item = root.child(i)
            for j in range(parent_item.childCount()):
                items.append(parent_item.child(j))
        return items

    def get_pending_changes(self):
        """Get lists of ramps to install and remove."""
        existing_ramps = set(self.style.colorRampNames())
        to_install = []
        to_remove = []
        
        for item in self._get_file_items():
            file_path = item.data(0, Qt.UserRole)
            ramp_name = item.data(1, Qt.UserRole)
            is_checked = item.checkState(0) == Qt.Checked
            is_installed = ramp_name in existing_ramps
            
            if is_checked and not is_installed:
                to_install.append((ramp_name, file_path))
            elif not is_checked and is_installed:
                to_remove.append(ramp_name)
        
        return to_install, to_remove

    def apply_changes(self):
        """Apply changes after confirmation."""
        to_install, to_remove = self.get_pending_changes()
        
        if not to_install and not to_remove:
            return
        
        # Build confirmation message
        msg_parts = []
        
        if to_install:
            msg_parts.append(f"<b style='color: #27ae60;'>➕ Install {len(to_install)} palette(s):</b>")
            for name, _ in to_install[:5]:
                msg_parts.append(f"&nbsp;&nbsp;&nbsp;• {name}")
            if len(to_install) > 5:
                msg_parts.append(f"&nbsp;&nbsp;&nbsp;<i>... and {len(to_install) - 5} more</i>")
        
        if to_remove:
            if msg_parts:
                msg_parts.append("<br>")
            msg_parts.append(f"<b style='color: #e74c3c;'>➖ Remove {len(to_remove)} palette(s):</b>")
            for name in to_remove[:5]:
                msg_parts.append(f"&nbsp;&nbsp;&nbsp;• {name}")
            if len(to_remove) > 5:
                msg_parts.append(f"&nbsp;&nbsp;&nbsp;<i>... and {len(to_remove) - 5} more</i>")
        
        # Show confirmation dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(self.tr("Confirm Changes"))
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText("<br>".join(msg_parts))
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg_box.setDefaultButton(QMessageBox.Cancel)
        
        if msg_box.exec_() != QMessageBox.Ok:
            return
        
        # Apply changes
        installed_count = 0
        removed_count = 0
        errors = []
        
        if to_install:
            existing_tags = self.style.tags()
            if self.TAG_NAME not in existing_tags:
                self.style.addTag(self.TAG_NAME)
        
        for ramp_name, file_path in to_install:
            try:
                if self.style.importXml(file_path):
                    self.style.tagSymbol(QgsStyle.ColorrampEntity, ramp_name, [self.TAG_NAME])
                    installed_count += 1
                else:
                    errors.append(f"Failed to import: {ramp_name}")
            except Exception as e:
                errors.append(f"Error installing {ramp_name}: {e}")
        
        for ramp_name in to_remove:
            try:
                if self.style.removeColorRamp(ramp_name):
                    removed_count += 1
                else:
                    errors.append(f"Failed to remove: {ramp_name}")
            except Exception as e:
                errors.append(f"Error removing {ramp_name}: {e}")
        
        # Report results
        status_parts = []
        if installed_count > 0:
            status_parts.append(f"✓ {installed_count} installed")
        if removed_count > 0:
            status_parts.append(f"✓ {removed_count} removed")
        if errors:
            status_parts.append(f"⚠ {len(errors)} errors")
            for err in errors:
                print(f"ERROR: {err}")
        
        if status_parts:
            self.status_label.setText(" — ".join(status_parts))
        
        self.load_xml_files()
