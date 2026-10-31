#! python3  # noqa: E265

"""
Dialog for browsing XML color map files and managing palettes in QGIS Style Manager.
"""

# standard
from pathlib import Path

# PyQGIS
from qgis.core import Qgis, QgsStyle, QgsApplication
from qgis.PyQt.QtCore import Qt, QCoreApplication, QSize, QUrl
from qgis.PyQt.QtGui import QIcon, QDesktopServices, QFont
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
    QFrame
)
from qgis.utils import iface as qgis_iface

# project
from scientific_color_maps.__about__ import DIR_PLUGIN_ROOT
from scientific_color_maps.toolbelt import PlgLogger, PlgOptionsManager

# Custom data role used to sort items by their checked state.
# Fully-qualified enums are required by PyQt6 and also accepted by PyQt5.
SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 1
# Custom data role flagging a ramp whose name is already used in the user's
# style by a ramp NOT installed by this plugin (left untouched).
CONFLICT_ROLE = SORT_ROLE + 1


class SortableTreeWidgetItem(QTreeWidgetItem):
    """TreeWidgetItem with custom sorting for checkbox column."""

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column == 0:
            self_val = self.data(0, SORT_ROLE)
            other_val = other.data(0, SORT_ROLE)
            if self_val is not None and other_val is not None:
                return self_val < other_val
        return super().__lt__(other)


class ColorRampBrowserDialog(QDialog):
    """Dialog to browse XML color map files and manage palettes in Style Manager."""

    TAG_NAME = "Sci.color.maps"
    # Style Manager smart group listing the ramps installed by this plugin
    # (condition: tagged TAG_NAME). Deleted as soon as it would be empty.
    SMART_GROUP_NAME = "Scientific Color Maps v8"

    # Status badge colours: saturated backgrounds with white text stay readable
    # on both light and dark QGIS themes. Every other widget uses the active
    # theme (palette / application stylesheet) instead of hard-coded colours.
    BADGE_COLORS = {
        "all": "#27ae60",
        "some": "#3498db",
        "none": "#7f8c8d",
        "error": "#e74c3c",
    }
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
        title_font = QFont(title_label.font())
        title_font.setPointSizeF(title_font.pointSizeF() * 1.3)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Status badge
        self.status_badge = QLabel()
        self._set_badge("", "some")
        header_layout.addWidget(self.status_badge)

        layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
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

        header = self.file_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 120)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.file_tree)

        # Info bar
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)

        info_icon = QLabel()
        info_icon.setPixmap(QgsApplication.getThemeIcon("mIconInfo.svg").pixmap(16, 16))
        info_layout.addWidget(info_icon)

        self.status_label = QLabel()
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Selection buttons
        select_layout = QHBoxLayout()
        select_layout.setSpacing(8)

        self.select_all_btn = QPushButton(self.tr("Select All"))
        self.select_all_btn.setIcon(QgsApplication.getThemeIcon("mActionSelectAll.svg"))
        self.select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_all_btn.clicked.connect(self.select_all)
        select_layout.addWidget(self.select_all_btn)

        self.select_none_btn = QPushButton(self.tr("Select None"))
        self.select_none_btn.setIcon(QgsApplication.getThemeIcon("mActionDeselectAll.svg"))
        self.select_none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_none_btn.clicked.connect(self.select_none)
        select_layout.addWidget(self.select_none_btn)

        self.restore_btn = QPushButton(self.tr("Restore"))
        self.restore_btn.setIcon(QgsApplication.getThemeIcon("mActionUndo.svg"))
        self.restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_btn.clicked.connect(self.restore_selection)
        select_layout.addWidget(self.restore_btn)

        select_layout.addStretch()

        self.style_manager_btn = QPushButton(self.tr("Style Manager"))
        self.style_manager_btn.setIcon(QgsApplication.getThemeIcon("propertyicons/symbology.svg"))
        self.style_manager_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.style_manager_btn.clicked.connect(self.open_style_manager)
        select_layout.addWidget(self.style_manager_btn)

        self.help_btn = QPushButton(self.tr("Help"))
        self.help_btn.setIcon(QgsApplication.getThemeIcon("mActionHelpContents.svg"))
        self.help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_btn.clicked.connect(self.open_help)
        select_layout.addWidget(self.help_btn)

        layout.addLayout(select_layout)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.apply_btn = QPushButton(self.tr("Apply Changes"))
        self.apply_btn.setIcon(QgsApplication.getThemeIcon("mActionSaveAllEdits.svg"))
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self.apply_changes)
        self.apply_btn.setEnabled(False)
        apply_font = QFont(self.apply_btn.font())
        apply_font.setBold(True)
        self.apply_btn.setFont(apply_font)
        btn_layout.addWidget(self.apply_btn)

        self.close_btn = QPushButton(self.tr("Close"))
        self.close_btn.setIcon(QgsApplication.getThemeIcon("mIconClose.svg"))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def tr(self, message: str) -> str:
        """Get translation for a string."""
        return QCoreApplication.translate(self.__class__.__name__, message)

    def _set_badge(self, text: str, state: str):
        """Update the status badge text and colour.

        :param text: text displayed in the badge
        :param state: one of the BADGE_COLORS keys ("all", "some", "none", "error")
        """
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            "QLabel {"
            f" background-color: {self.BADGE_COLORS[state]};"
            " color: white;"
            " padding: 4px 10px;"
            " border-radius: 10px;"
            "}"
        )

    def open_help(self):
        """Open the Scientific Colour Maps website."""
        QDesktopServices.openUrl(QUrl(self.HELP_URL))

    def open_style_manager(self):
        """Open the QGIS Style Manager dialog."""
        try:
            qgis_iface.showStyleManager()
        except Exception as e:
            self.log(
                message=f"Could not open Style Manager: {e}",
                log_level=Qgis.MessageLevel.Warning,
            )

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

    def _plugin_ramp_names(self) -> set:
        """Names of the color ramps installed by this plugin (tagged TAG_NAME).

        Only these ramps are considered "installed" and may be removed: a ramp
        with the same name created or imported by the user is never touched.
        """
        if self.TAG_NAME not in self.style.tags():
            return set()
        tag_id = self.style.tagId(self.TAG_NAME)
        return set(
            self.style.symbolsWithTag(QgsStyle.StyleEntity.ColorrampEntity, tag_id)
        )

    def _sync_smart_group(self):
        """Create the smart group if plugin ramps exist, delete it if none remain."""
        has_ramps = bool(self._plugin_ramp_names())
        exists = self.SMART_GROUP_NAME in self.style.smartgroupNames()

        if has_ramps and not exists:
            group_id = self.style.addSmartgroup(
                self.SMART_GROUP_NAME, "AND", [self.TAG_NAME], [], [], []
            )
            if not group_id:
                self.log(
                    message=f"Could not create smart group: {self.SMART_GROUP_NAME}",
                    log_level=Qgis.MessageLevel.Warning,
                )
        elif not has_ramps and exists:
            group_id = self.style.smartgroupId(self.SMART_GROUP_NAME)  # 0 if not found
            if group_id and not self.style.remove(
                QgsStyle.StyleEntity.SmartgroupEntity, group_id
            ):
                self.log(
                    message=f"Could not remove smart group: {self.SMART_GROUP_NAME}",
                    log_level=Qgis.MessageLevel.Warning,
                )

    @staticmethod
    def _is_conflict(item) -> bool:
        """True if the item's ramp name is already used by a non-plugin ramp."""
        return bool(item.data(0, CONFLICT_ROLE))

    def load_xml_files(self):
        """Load XML files from the configured directory, organized by category."""
        self.file_tree.blockSignals(True)
        self.file_tree.clear()
        self.initial_state.clear()
        self.category_items.clear()

        # keep the Style Manager smart group in line with the installed ramps
        self._sync_smart_group()

        directory = DIR_PLUGIN_ROOT / self.plg_settings.default_color_maps_dir
        pattern = self.plg_settings.file_pattern

        if not directory.is_dir():
            self.status_label.setText(self.tr("Directory not found: {}").format(directory))
            self._set_badge(self.tr("Error"), "error")
            self.file_tree.blockSignals(False)
            return

        existing_ramps = set(self.style.colorRampNames())
        plugin_ramps = self._plugin_ramp_names()

        try:
            files_by_category = self.find_xml_files_by_category(directory, pattern)
        except Exception as e:
            self.status_label.setText(self.tr("Error searching files: {}").format(e))
            self.file_tree.blockSignals(False)
            return

        total_files = 0
        installed_count = 0
        conflict_count = 0

        # Category configuration
        category_config = {
            'General': {
                'icon': QgsApplication.getThemeIcon("mIconFolder.svg"),
            },
            'Categorical Palettes': {
                'icon': QgsApplication.getThemeIcon("mIconColorSwatches.svg"),
            }
        }

        # Displayed (translated) category labels; dict keys stay untranslated
        category_labels = {
            'General': self.tr("General"),
            'Categorical Palettes': self.tr("Categorical Palettes"),
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
            category_item.setText(0, category_labels[category_name])
            category_item.setText(1, "")
            category_item.setText(2, "")
            category_item.setText(3, self.tr("{} items").format(len(files)))
            category_item.setExpanded(True)

            # Make category checkable
            category_item.setFlags(category_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            category_item.setCheckState(0, Qt.CheckState.Unchecked)

            # Store reference
            self.category_items[category_name] = category_item

            # Style category row: bold text, colours follow the active theme
            category_font = QFont(category_item.font(0))
            category_font.setBold(True)
            for col in range(4):
                category_item.setFont(col, category_font)

            # Add files to category
            for file_info in files:
                file_path = file_info['path']
                palette_name = file_info['palette_name']

                file_item = SortableTreeWidgetItem(category_item)

                ramp_name = self.get_ramp_name_from_filename(file_path.name)
                is_installed = ramp_name in plugin_ramps
                # same name already used by a ramp the plugin did not install
                is_conflict = ramp_name in existing_ramps and not is_installed

                file_item.setFlags(file_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                file_item.setCheckState(
                    0, Qt.CheckState.Checked if is_installed else Qt.CheckState.Unchecked
                )
                file_item.setData(0, SORT_ROLE, 1 if is_installed else 0)

                file_item.setData(0, Qt.ItemDataRole.UserRole, str(file_path))
                file_item.setData(1, Qt.ItemDataRole.UserRole, ramp_name)
                file_item.setData(0, CONFLICT_ROLE, is_conflict)

                if is_conflict:
                    # never overwrite nor remove the user's own ramp
                    file_item.setDisabled(True)
                    tooltip = self.tr(
                        "A color ramp named '{}' already exists in your style and was "
                        "not installed by this plugin. It is left untouched."
                    ).format(ramp_name)
                    for col in range(4):
                        file_item.setToolTip(col, tooltip)

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

                if is_conflict:
                    conflict_count += 1
                else:
                    total_files += 1
                if is_installed:
                    installed_count += 1

        # Update category check states
        for cat_item in self.category_items.values():
            self._update_category_check_state(cat_item)

        self.file_tree.blockSignals(False)
        self.apply_btn.setEnabled(False)

        # Update status
        if conflict_count:
            self.status_label.setText(
                self.tr("{} palettes available ({} unavailable: name already used)").format(
                    total_files, conflict_count
                )
            )
        else:
            self.status_label.setText(self.tr("{} palettes available").format(total_files))

        if installed_count == total_files:
            badge_state = "all"
        elif installed_count == 0:
            badge_state = "none"
        else:
            badge_state = "some"

        self._set_badge(self.tr("{} installed").format(installed_count), badge_state)

    def _is_category_item(self, item):
        """Check if item is a category."""
        return item in self.category_items.values()

    def _update_category_check_state(self, category_item):
        """Update category checkbox based on children states."""
        if category_item is None or category_item.childCount() == 0:
            return

        children = [
            category_item.child(i)
            for i in range(category_item.childCount())
            if not self._is_conflict(category_item.child(i))
        ]
        total = len(children)
        if total == 0:
            category_item.setCheckState(0, Qt.CheckState.Unchecked)
            return

        checked = sum(1 for c in children if c.checkState(0) == Qt.CheckState.Checked)

        # Determine new state
        if checked == 0:
            new_state = Qt.CheckState.Unchecked
        elif checked == total:
            new_state = Qt.CheckState.Checked
        else:
            new_state = Qt.CheckState.PartiallyChecked

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
            if state == Qt.CheckState.PartiallyChecked:
                state = Qt.CheckState.Checked
                item.setCheckState(0, Qt.CheckState.Checked)

            # Collect all children first to avoid index shifting during sort
            children = [item.child(i) for i in range(item.childCount())]
            for child in children:
                if self._is_conflict(child):
                    continue
                child.setCheckState(0, state)
                child.setData(0, SORT_ROLE, 1 if state == Qt.CheckState.Checked else 0)
        else:
            # File item clicked — update its data and parent category
            is_checked = item.checkState(0) == Qt.CheckState.Checked
            item.setData(0, SORT_ROLE, 1 if is_checked else 0)

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
            ramp_name = item.data(1, Qt.ItemDataRole.UserRole)
            is_checked = item.checkState(0) == Qt.CheckState.Checked
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
                if self._is_conflict(child):
                    continue
                child.setCheckState(0, Qt.CheckState.Checked)
                child.setData(0, SORT_ROLE, 1)
            self._update_category_check_state(cat_item)
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
                if self._is_conflict(child):
                    continue
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, SORT_ROLE, 0)
            self._update_category_check_state(cat_item)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.blockSignals(False)
        self.update_apply_button()

    def restore_selection(self):
        """Restore initial selection state."""
        self.file_tree.blockSignals(True)
        self.file_tree.setSortingEnabled(False)
        for item in self._get_file_items():
            ramp_name = item.data(1, Qt.ItemDataRole.UserRole)
            initial = self.initial_state.get(ramp_name, False)
            item.setCheckState(0, Qt.CheckState.Checked if initial else Qt.CheckState.Unchecked)
            item.setData(0, SORT_ROLE, 1 if initial else 0)

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
        """Get lists of ramps to install and remove.

        Only ramps tagged by this plugin can be removed, and a ramp is installed
        only if no ramp with the same name exists yet (state re-read from the
        style, in case it changed since the dialog was loaded).
        """
        existing_ramps = set(self.style.colorRampNames())
        plugin_ramps = self._plugin_ramp_names()
        to_install = []
        to_remove = []

        for item in self._get_file_items():
            if self._is_conflict(item):
                continue
            file_path = item.data(0, Qt.ItemDataRole.UserRole)
            ramp_name = item.data(1, Qt.ItemDataRole.UserRole)
            is_checked = item.checkState(0) == Qt.CheckState.Checked

            if is_checked and ramp_name not in existing_ramps:
                to_install.append((ramp_name, file_path))
            elif not is_checked and ramp_name in plugin_ramps:
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
            msg_parts.append(
                "<b style='color: #27ae60;'>➕ {}</b>".format(
                    self.tr("Install {} palette(s):").format(len(to_install))
                )
            )
            for name, _ in to_install[:5]:
                msg_parts.append(f"&nbsp;&nbsp;&nbsp;• {name}")
            if len(to_install) > 5:
                msg_parts.append(
                    "&nbsp;&nbsp;&nbsp;<i>{}</i>".format(
                        self.tr("... and {} more").format(len(to_install) - 5)
                    )
                )

        if to_remove:
            if msg_parts:
                msg_parts.append("<br>")
            msg_parts.append(
                "<b style='color: #e74c3c;'>➖ {}</b>".format(
                    self.tr("Remove {} palette(s):").format(len(to_remove))
                )
            )
            for name in to_remove[:5]:
                msg_parts.append(f"&nbsp;&nbsp;&nbsp;• {name}")
            if len(to_remove) > 5:
                msg_parts.append(
                    "&nbsp;&nbsp;&nbsp;<i>{}</i>".format(
                        self.tr("... and {} more").format(len(to_remove) - 5)
                    )
                )

        # Show confirmation dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(self.tr("Confirm Changes"))
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText("<br>".join(msg_parts))
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Cancel)

        # exec() works on both PyQt5 and PyQt6 (exec_() was removed in PyQt6).
        # Its return value is an int under PyQt6, so compare the clicked button
        # instead of the return code to stay independent of enum/int semantics.
        msg_box.exec()
        if msg_box.standardButton(msg_box.clickedButton()) != QMessageBox.StandardButton.Ok:
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
                    self.style.tagSymbol(
                        QgsStyle.StyleEntity.ColorrampEntity, ramp_name, [self.TAG_NAME]
                    )
                    # the XML files declare favorite="1": plugin ramps must not
                    # be added to the user's favorites
                    self.style.removeFavorite(
                        QgsStyle.StyleEntity.ColorrampEntity, ramp_name
                    )
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
            status_parts.append("✓ " + self.tr("{} installed").format(installed_count))
        if removed_count > 0:
            status_parts.append("✓ " + self.tr("{} removed").format(removed_count))
        if errors:
            status_parts.append("⚠ " + self.tr("{} errors").format(len(errors)))
            for err in errors:
                print(f"ERROR: {err}")

        if status_parts:
            self.status_label.setText(" — ".join(status_parts))

        self.load_xml_files()
