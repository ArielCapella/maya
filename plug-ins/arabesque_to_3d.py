"""
Arabesque to 3D Model - Maya Plugin

Transforms 2D organic arabesque raster images into beveled 3D polygon meshes.
Load via Maya's Plugin Manager or MAYA_PLUG_IN_PATH.
"""

import maya.api.OpenMaya as om
import maya.cmds as cmds


maya_useNewAPI = True

MENU_NAME = "ArabesqueMenu"
COMMAND_NAME = "ArabesqueToModel"


class ArabesqueToModelCmd(om.MPxCommand):
    """Opens the Arabesque-to-3D dockable UI."""

    kPluginCmdName = COMMAND_NAME

    def __init__(self):
        super().__init__()

    @staticmethod
    def creator():
        return ArabesqueToModelCmd()

    def doIt(self, args):
        from arabesque.ui.main_window import show_window
        show_window()


def _build_menu():
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)

    cmds.menu(
        MENU_NAME,
        label="Arabesque",
        parent="MayaWindow",
        tearOff=True,
    )
    cmds.menuItem(
        label="Arabesque to 3D Model...",
        command=lambda *_: cmds.ArabesqueToModel(),
    )


def _remove_menu():
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)


def initializePlugin(plugin):
    fn = om.MFnPlugin(plugin, "Arabesque Tools", "1.0.0")
    try:
        fn.registerCommand(COMMAND_NAME, ArabesqueToModelCmd.creator)
    except Exception:
        om.MGlobal.displayError(f"Failed to register command: {COMMAND_NAME}")
        raise

    cmds.evalDeferred(_build_menu)


def uninitializePlugin(plugin):
    fn = om.MFnPlugin(plugin)
    try:
        fn.deregisterCommand(COMMAND_NAME)
    except Exception:
        om.MGlobal.displayError(f"Failed to deregister command: {COMMAND_NAME}")
        raise

    _remove_menu()
