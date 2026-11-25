#! python3  # noqa: E265

"""
Keep the Style Manager in line with the color ramps installed by the plugin.

The plugin tags every ramp it installs with TAG_NAME. A smart group named
SMART_GROUP_NAME (condition: has tag TAG_NAME) lists them in the Style Manager.
The smart group must exist as long as at least one plugin ramp is installed.
As soon as none remains, whatever removed them (this plugin, the Style Manager,
a script...), the smart group is deleted, and so is the tag itself, unless
another style item (symbol, text format...) still uses it.
"""

# PyQGIS
from qgis.core import Qgis, QgsStyle

# project
from scientific_color_maps.toolbelt.log_handler import PlgLogger

TAG_NAME = "Sci.color.maps"
SMART_GROUP_NAME = "Scientific Color Maps v8"

# Style item types that can carry tags (TagEntity / SmartgroupEntity cannot)
TAGGABLE_ENTITIES = (
    QgsStyle.StyleEntity.SymbolEntity,
    QgsStyle.StyleEntity.ColorrampEntity,
    QgsStyle.StyleEntity.TextFormatEntity,
    QgsStyle.StyleEntity.LabelSettingsEntity,
    QgsStyle.StyleEntity.LegendPatchShapeEntity,
    QgsStyle.StyleEntity.Symbol3DEntity,
)

_syncing = False  # re-entrancy guard: adding/removing a group emits groupsModified


def plugin_ramp_names(style: QgsStyle) -> set:
    """Names of the color ramps installed by this plugin (tagged TAG_NAME).

    :param style: style to inspect, usually QgsStyle.defaultStyle()
    :return: set of color ramp names
    """
    if TAG_NAME not in style.tags():
        return set()
    tag_id = style.tagId(TAG_NAME)
    return set(style.symbolsWithTag(QgsStyle.StyleEntity.ColorrampEntity, tag_id))


def _tag_in_use(style: QgsStyle, tag_id: int) -> bool:
    """True if any style item (of any taggable type) carries the tag."""
    return any(style.symbolsWithTag(entity, tag_id) for entity in TAGGABLE_ENTITIES)


def sync_smart_group(style: QgsStyle) -> None:
    """Create the smart group if plugin ramps exist; when none remain, delete
    the smart group and the TAG_NAME tag (if nothing else uses it).

    :param style: style to update, usually QgsStyle.defaultStyle()
    """
    global _syncing
    if _syncing:
        return
    _syncing = True
    try:
        has_ramps = bool(plugin_ramp_names(style))
        exists = SMART_GROUP_NAME in style.smartgroupNames()

        if has_ramps and not exists:
            if not style.addSmartgroup(SMART_GROUP_NAME, "AND", [TAG_NAME], [], [], []):
                PlgLogger.log(
                    message=f"Could not create smart group: {SMART_GROUP_NAME}",
                    log_level=Qgis.MessageLevel.Warning,
                )
        elif not has_ramps and exists:
            group_id = style.smartgroupId(SMART_GROUP_NAME)  # 0 if not found
            if group_id and not style.remove(QgsStyle.StyleEntity.SmartgroupEntity, group_id):
                PlgLogger.log(
                    message=f"Could not remove smart group: {SMART_GROUP_NAME}",
                    log_level=Qgis.MessageLevel.Warning,
                )

        if not has_ramps:
            tag_id = style.tagId(TAG_NAME)  # 0 if not found
            if tag_id and not _tag_in_use(style, tag_id):
                if not style.remove(QgsStyle.StyleEntity.TagEntity, tag_id):
                    PlgLogger.log(
                        message=f"Could not remove tag: {TAG_NAME}",
                        log_level=Qgis.MessageLevel.Warning,
                    )
    finally:
        _syncing = False
