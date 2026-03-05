#! python3  # noqa: E265

"""
Dialog for browsing XML color map files and managing palettes in QGIS Style Manager.
"""

# standard
from pathlib import Path

# PyQGIS
from qgis.core import Qgis, QgsStyle, QgsApplication
from qgis.PyQt.QtCore import Qt, QCoreApplication, QSize, QUrl
from qgis.PyQt.QtGui import QIcon, QColor, QPixmap, QDesktopServices
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
    HELP_URL = "https://www.fabiocrameri.ch/colourmaps/"

    def __init__(self, parent=None):
        """Initialize the dialog."""
        super().__init__(parent)
        self.log = PlgLogger().log
        self.plg_settings = PlgOptionsManager().get_plg_settings()
        self.style = QgsStyle.defaultStyle()
        self.initial_state = {}
        self.category_items = {}
        
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
            self.tr("Palette"),
            self.tr("Size")
        ])
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setRootIsDecorated(True)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.setIndentation(20)
        self.file_tree.setAnimated(True)
        self.file_tree.setIconSize(QSize(100, 16))
        self.file_tree.itemChanged.connect(self.on_item_changed)
        
        # Style the tree
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
        
        self.help_btn = QPushButton(self.tr(" Help"))
        self.help_btn.setIcon(QgsApplication.getThemeIcon("mActionHelpContents.svg"))
        self.help_btn.setCursor(Qt.PointingHandCursor)
        self.help_btn.clicked.connect(self.open_help)
        select_layout.addWidget(self.help_btn)
        
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
        self.help_btn.setStyleSheet(button_style)

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

    def open_help(self):
        """Open the Scientific Colour Maps website."""
        QDesktopServices.openUrl(QUrl(self.HELP_URL))

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

    def find_xml_files_by_category(self, directory: Path, pattern: str) -> dict:
        """
        Find XML files and organize them by category.
        
        Returns a dict with two keys:
        - 'General': files at the root of each palette folder
        - 'Categorical Palettes': files in CategoricalPalettes subfolders
        """
        results = {
            'General': [],
            'Categorical Palettes': []
        }
        
        try:
            for palette_dir in sorted(directory.iterdir()):
                if not palette_dir.is_dir() or palette_dir.name.startswith('+') or palette_dir.name.startswith('.'):
                    continue
                
                # XML files at root of palette -> General
                for xml_file in palette_dir.glob(pattern):
                    if xml_file.is_file():
                        results['General'].append({
                            'path': xml_file,
                            'palette_name': palette_dir.name
                        })
                
                # XML files in CategoricalPalettes subfolder -> Categorical Palettes
                categorical_dir = palette_dir / 'CategoricalPalettes'
                if categorical_dir.is_dir():
                    for xml_file in categorical_dir.glob(pattern):
                        if xml_file.is_file():
                            results['Categorical Palettes'].append({
                                'path': xml_file,
                                'palette_name': palette_dir.name
                            })
        
        except PermissionError as e:
            self.log(
                message=f"Permission denied accessing directories: {e}",
                log_level=Qgis.MessageLevel.Warning,
            )
        
        # Sort by filename
        results['General'] = sorted(results['General'], key=lambda x: x['path'].name.lower())
        results['Categorical Palettes'] = sorted(results['Categorical Palettes'], key=lambda x: x['path'].name.lower())
        
        return results

    def load_xml_files(self):
        """Load XML files from the configured directory, organized by category."""
        self.file_tree.blockSignals(True)
        self.file_tree.clear()
        self.initial_state.clear()
        self.category_items.clear()
        
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
            files_by_category = self.find_xml_files_by_category(directory, pattern)
        except Exception as e:
            self.status_label.setText(self.tr(f"Error searching files: {e}"))
            self.file_tree.blockSignals(False)
            return
        
        total_files = 0
        installed_count = 0
        
        # Category configuration
        category_config = {
            'General': {
                'icon': QgsApplication.getThemeIcon("mIconFolder.svg"),
                'color': QColor("#e8f5e9")
            },
            'Categorical Palettes': {
                'icon': QgsApplication.getThemeIcon("mIconColorSwatches.svg"),
                'color': QColor("#e3f2fd")
            }
        }
        
        # Process each category
        for category_name in ['General', 'Categorical Palettes']:
            files = files_by_category.get(category_name, [])
            
            if not files:
                continue
            
            # Create category item
            category_item = QTreeWidgetItem(self.file_tree)
            config = category_config.get(category_name)
            category_item.setIcon(0, config['icon'])
            category_item.setText(0, category_name)
            category_item.setText(1, "")
            category_item.setText(2, "")
            category_item.setText(3, f"{len(files)} items")
            category_item.setExpanded(True)
            
            # Make category checkable
            category_item.setFlags(category_item.flags() | Qt.ItemIsUserCheckable)
            category_item.setCheckState(0, Qt.Unchecked)
            
            # Store reference
            self.category_items[category_name] = category_item
            
            # Style category row
            for col in range(4):
                category_item.setBackground(col, config['color'])
            
            # Add files to category
            for file_info in files:
                file_path = file_info['path']
                palette_name = file_info['palette_name']
                
                file_item = SortableTreeWidgetItem(category_item)
                
                ramp_name = self.get_ramp_name_from_filename(file_path.name)
                is_installed = ramp_name in existing_ramps
                
                file_item.setFlags(file_item.flags() | Qt.ItemIsUserCheckable)
                file_item.setCheckState(0, Qt.Checked if is_installed else Qt.Unchecked)
                file_item.setData(0, Qt.UserRole + 1, 1 if is_installed else 0)
                
                file_item.setData(0, Qt.UserRole, str(file_path))
                file_item.setData(1, Qt.UserRole, ramp_name)
                
                self.initial_state[ramp_name] = is_installed
                
                file_item.setText(0, ramp_name)
                
                # Load SVG preview
                svg_path = file_path.parent / f"{ramp_name}.svg"
                if svg_path.exists():
                    file_item.setIcon(1, QIcon(str(svg_path)))
                
                file_item.setText(2, palette_name)
                
                try:
                    size = file_path.stat().st_size
                    file_item.setText(3, self.format_file_size(size))
                except OSError:
                    file_item.setText(3, "—")
                
                total_files += 1
                if is_installed:
                    installed_count += 1
        
        # Update category check states
        for cat_item in self.category_items.values():
            self._update_category_check_state(cat_item)
        
        self.file_tree.blockSignals(False)
        self.apply_btn.setEnabled(False)
        
        # Update status
        self.status_label.setText(f"{total_files} palettes available")
        self.status_badge.setText(f"{installed_count} installed")
        
        if installed_count == total_files:
            badge_color = "#27ae60"
        elif installed_count == 0:
            badge_color = "#95a5a6"
        else:
            badge_color = "#3498db"
            
        self.status_badge.setStyleSheet(f"""
            background-color: {badge_color};
            color: white;
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 11px;
        """)

    def _is_category_item(self, item):
        """Check if item is a category."""
        return item in self.category_items.values()

    def _update_category_check_state(self, category_item):
        """Update category checkbox based on children states."""
        if category_item is None or category_item.childCount() == 0:
            return
        
        checked = 0
        total = category_item.childCount()
        
        for i in range(total):
            if category_item.child(i).checkState(0) == Qt.Checked:
                checked += 1
        
        # Determine new state
        if checked == 0:
            new_state = Qt.Unchecked
        elif checked == total:
            new_state = Qt.Checked
        else:
            new_state = Qt.PartiallyChecked
        
        # Apply state (blockSignals should already be True from caller)
        category_item.setCheckState(0, new_state)

    def on_item_changed(self, item, column):
        """Handle item check state change."""
        if column != 0:
            return
        
        self.file_tree.blockSignals(True)
        self.file_tree.setSortingEnabled(False)
        
        if self._is_category_item(item):
            # Category clicked — propagate to all children
            state = item.checkState(0)
            
            # PartiallyChecked should not occur from a user click,
            # but if it does, treat it as Checked (select all)
            if state == Qt.PartiallyChecked:
                state = Qt.Checked
                item.setCheckState(0, Qt.Checked)
            
            # Collect all children first to avoid index shifting during sort
            children = [item.child(i) for i in range(item.childCount())]
            for child in children:
                child.setCheckState(0, state)
                child.setData(0, Qt.UserRole + 1, 1 if state == Qt.Checked else 0)
        else:
            # File item clicked — update its data and parent category
            is_checked = item.checkState(0) == Qt.Checked
            item.setData(0, Qt.UserRole + 1, 1 if is_checked else 0)
            
            parent = item.parent()
            if parent and self._is_category_item(parent):
                self._update_category_check_state(parent)
        
        self.file_tree.setSortingEnabled(True)
        self.file_tree.blockSignals(False)
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
        self.file_tree.blockSignals(True)
        self.file_tree.setSortingEnabled(False)
        for cat_item in self.category_items.values():
            children = [cat_item.child(i) for i in range(cat_item.childCount())]
            for child in children:
                child.setCheckState(0, Qt.Checked)
                child.setData(0, Qt.UserRole + 1, 1)
            cat_item.setCheckState(0, Qt.Checked)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.blockSignals(False)
        self.update_apply_button()

    def select_none(self):
        """Deselect all file items."""
        self.file_tree.blockSignals(True)
        self.file_tree.setSortingEnabled(False)
        for cat_item in self.category_items.values():
            children = [cat_item.child(i) for i in range(cat_item.childCount())]
            for child in children:
                child.setCheckState(0, Qt.Unchecked)
                child.setData(0, Qt.UserRole + 1, 0)
            cat_item.setCheckState(0, Qt.Unchecked)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.blockSignals(False)
        self.update_apply_button()

    def restore_selection(self):
        """Restore initial selection state."""
        self.file_tree.blockSignals(True)
        self.file_tree.setSortingEnabled(False)
        for item in self._get_file_items():
            ramp_name = item.data(1, Qt.UserRole)
            initial = self.initial_state.get(ramp_name, False)
            item.setCheckState(0, Qt.Checked if initial else Qt.Unchecked)
            item.setData(0, Qt.UserRole + 1, 1 if initial else 0)
        
        # Update categories
        for cat_item in self.category_items.values():
            self._update_category_check_state(cat_item)
        
        self.file_tree.setSortingEnabled(True)
        self.file_tree.blockSignals(False)
        self.apply_btn.setEnabled(False)

    def _get_file_items(self):
        """Get all file items from the tree (excluding category items)."""
        items = []
        for cat_item in self.category_items.values():
            for i in range(cat_item.childCount()):
                items.append(cat_item.child(i))
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
