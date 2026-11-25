#! python3  # noqa: E265

"""Main plugin module."""

# standard
from functools import partial
from pathlib import Path

# PyQGIS
from qgis.core import Qgis, QgsApplication, QgsSettings, QgsStyle
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QLocale, QTimer, QTranslator, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon, QKeySequence

try:
    # Qt6 (QGIS 4): QAction lives in QtGui
    from qgis.PyQt.QtGui import QAction
except ImportError:
    # Qt5 (QGIS 3): QAction lives in QtWidgets
    from qgis.PyQt.QtWidgets import QAction

# project
from scientific_color_maps.__about__ import (
    DIR_PLUGIN_ROOT,
    __icon_path__,
    __title__,
    __uri_homepage__,
    __version__,
)
from scientific_color_maps.gui.dlg_settings import PlgOptionsFactory
from scientific_color_maps.gui.dlg_file_browser import ColorRampBrowserDialog

from scientific_color_maps.toolbelt import PlgLogger
from scientific_color_maps.toolbelt.style_sync import sync_smart_group

# ############################################################################
# ########## Classes ###############
# ##################################


class ScientificColorMap:
    def __init__(self, iface: QgisInterface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class which \
        provides the hook by which you can manipulate the QGIS application at run time.
        :type iface: QgsInterface
        """
        self.iface = iface
        self.log = PlgLogger().log
        self.file_browser_dialog = None
        self.toolbar = None
        self.style = None
        self.style_signals = ()
        self.style_sync_pending = False

        # translation
        # initialize the locale
        self.locale: str = QgsSettings().value("locale/userLocale", QLocale().name())[0:2]
        locale_path: Path = (
            DIR_PLUGIN_ROOT / "resources" / "i18n" / f"plugin_translation_{self.locale}.qm"
        )

        # Info level: only written to the QGIS log panel in debug mode
        self.log(
            message=f"{__title__} {__version__} loaded - translation: {self.locale}, "
            f"{locale_path} ({'found' if locale_path.exists() else 'not found'})",
            log_level=Qgis.MessageLevel.Info,
        )

        if locale_path.exists():
            self.translator = QTranslator()
            self.translator.load(str(locale_path.resolve()))
            QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        """Set up plugin UI elements."""

        # settings page within the QGIS preferences menu
        self.options_factory = PlgOptionsFactory()
        self.iface.registerOptionsWidgetFactory(self.options_factory)

        # -- Style Manager smart group: create/delete it now, then follow every
        # change of the default style (ramps added, removed, (un)tagged, tags or
        # groups edited), whether made by this plugin or in the Style Manager.
        self.style = QgsStyle.defaultStyle()
        sync_smart_group(self.style)
        self.style_signals = (
            self.style.entityAdded,
            self.style.entityRemoved,
            self.style.entityTagsChanged,
            self.style.groupsModified,
        )
        for signal in self.style_signals:
            signal.connect(self.on_style_changed)

        # -- Actions
        self.action_help = QAction(
            QgsApplication.getThemeIcon("mActionHelpContents.svg"),
            self.tr("Help"),
            self.iface.mainWindow(),
        )
        self.action_help.triggered.connect(
            partial(QDesktopServices.openUrl, QUrl(__uri_homepage__))
        )

        self.action_settings = QAction(
            QgsApplication.getThemeIcon("console/iconSettingsConsole.svg"),
            self.tr("Settings"),
            self.iface.mainWindow(),
        )
        self.action_settings.triggered.connect(
            lambda: self.iface.showOptionsDialog(
                currentPage="mOptionsPage{}".format(__title__)
            )
        )

        self.action_file_browser = QAction(
            QgsApplication.getThemeIcon("mActionFileOpen.svg"),
            self.tr("Browse XML Color Maps"),
            self.iface.mainWindow(),
        )
        self.action_file_browser.setShortcut(QKeySequence("Ctrl+Alt+S"))
        self.action_file_browser.triggered.connect(self.open_file_browser)

        # -- Menu
        self.iface.addPluginToMenu(__title__, self.action_file_browser)
        self.iface.addPluginToMenu(__title__, self.action_settings)
        self.iface.addPluginToMenu(__title__, self.action_help)

        # -- Plugin menu icon
        plugin_menu = self.iface.pluginMenu()
        for action in plugin_menu.actions():
            if action.text() == __title__:
                action.setIcon(QIcon(str(__icon_path__)))
                break

        # -- Toolbar: a single button with the plugin icon opening the browser
        self.toolbar = self.iface.addToolBar(__title__)
        self.toolbar.setObjectName("ScientificColorMapsToolbar")
        self.action_toolbar_browser = QAction(
            QIcon(str(__icon_path__)),
            self.tr("Browse XML Color Maps"),
            self.iface.mainWindow(),
        )
        self.action_toolbar_browser.triggered.connect(self.open_file_browser)
        self.toolbar.addAction(self.action_toolbar_browser)

        # -- Help menu

        # documentation
        self.iface.pluginHelpMenu().addSeparator()
        self.action_help_plugin_menu_documentation = QAction(
            QIcon(str(__icon_path__)),
            self.tr("{} - Documentation").format(__title__),
            self.iface.mainWindow(),
        )
        self.action_help_plugin_menu_documentation.triggered.connect(
            partial(QDesktopServices.openUrl, QUrl(__uri_homepage__))
        )

        self.iface.pluginHelpMenu().addAction(
            self.action_help_plugin_menu_documentation
        )

    def tr(self, message: str) -> str:
        """Get the translation for a string using Qt translation API.

        :param message: string to be translated.
        :type message: str

        :returns: Translated version of message.
        :rtype: str
        """
        return QCoreApplication.translate(self.__class__.__name__, message)

    def on_style_changed(self, *args):
        """Schedule a smart group / tag sync once the current style operation ends.

        The sync must NOT run synchronously: QgsStyle emits its signals in the
        middle of operations (e.g. tagSymbol() creates the tag, emits
        groupsModified, and only then attaches it to the ramp). Deferring also
        merges the many signals of a batch install/removal into a single sync.
        """
        if not self.style_sync_pending:
            self.style_sync_pending = True
            QTimer.singleShot(0, self.run_style_sync)

    def run_style_sync(self):
        """Run the deferred sync (no-op if the plugin was unloaded meanwhile)."""
        self.style_sync_pending = False
        if self.style is not None:
            sync_smart_group(self.style)

    def unload(self):
        """Cleans up when plugin is disabled/uninstalled."""
        # -- Stop following the style
        for signal in self.style_signals:
            try:
                signal.disconnect(self.on_style_changed)
            except TypeError:
                pass
        self.style_signals = ()
        self.style = None  # a sync still scheduled will do nothing
        # -- Clean up menu
        self.iface.removePluginMenu(__title__, self.action_help)
        self.iface.removePluginMenu(__title__, self.action_settings)
        self.iface.removePluginMenu(__title__, self.action_file_browser)

        # -- Clean up preferences panel in QGIS settings
        self.iface.unregisterOptionsWidgetFactory(self.options_factory)

        # remove from QGIS help/extensions menu
        if self.action_help_plugin_menu_documentation:
            self.iface.pluginHelpMenu().removeAction(
                self.action_help_plugin_menu_documentation
            )

        # remove actions
        del self.action_settings
        del self.action_help
        del self.action_file_browser

        # remove the toolbar
        if self.toolbar:
            self.toolbar.removeAction(self.action_toolbar_browser)
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = None
        del self.action_toolbar_browser

        # close dialog if open
        if self.file_browser_dialog:
            self.file_browser_dialog.close()
            self.file_browser_dialog = None

    def open_file_browser(self):
        """Open the color ramp browser dialog."""
        if self.file_browser_dialog is None:
            # first opening: the dialog loads the ramps in its constructor
            self.file_browser_dialog = ColorRampBrowserDialog(self.iface.mainWindow())
        elif not self.file_browser_dialog.isVisible():
            # reopening a hidden dialog: reload from the style, which may have
            # changed meanwhile (Style Manager, another script...). Not done if
            # the dialog is already visible, to keep the user's pending selection.
            self.file_browser_dialog.load_xml_files()

        self.file_browser_dialog.show()
        self.file_browser_dialog.raise_()
        self.file_browser_dialog.activateWindow()
