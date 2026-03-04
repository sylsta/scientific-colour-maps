from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication, QTranslator, QLocale
from qgis.core import QgsApplication
import os

class SToolsPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.translator = None
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        # Charger la traduction
        self.load_translations()

        # Créer le menu principal "STools"
        self.menu = self.iface.pluginMenu()
        self.stools_menu = self.menu.addMenu(self.tr("STools"))

        # Créer le sous-menu "Option"
        self.option_menu = self.stools_menu.addMenu(self.tr("Option"))

        # Ajouter une action pour ouvrir la boîte de dialogue "Hello World"
        self.hello_action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            self.tr("Hello World"),
            self.iface.mainWindow()
        )
        self.hello_action.triggered.connect(self.show_hello_dialog)
        self.option_menu.addAction(self.hello_action)

    def unload(self):
        # Supprimer le menu et les actions lors du déchargement du plugin
        self.menu.removeAction(self.stools_menu.menuAction())

    def show_hello_dialog(self):
        # Afficher une boîte de dialogue "Hello World"
        QMessageBox.information(
            self.iface.mainWindow(),
            self.tr("STools"),
            self.tr("Hello World!")
        )

    def tr(self, message):
        # Fonction pour traduire les chaînes de caractères
        return QCoreApplication.translate("SToolsPlugin", message)

    def load_translations(self):
        # Charger les fichiers de traduction en fonction de la locale de QGIS
        locale = QLocale.system().name()
        translator = QTranslator()
        translation_path = os.path.join(self.plugin_dir, "i18n", locale, "LC_MESSAGES", "stools_{}.qm".format(locale))
        if os.path.exists(translation_path):
            translator.load(translation_path)
            QCoreApplication.installTranslator(translator)
