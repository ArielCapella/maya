"""
PySide2 dockable UI for the Arabesque-to-3D plugin.

Provides image loading, contour preview, and all processing / geometry
parameters with Process Image and Generate 3D Model actions.
"""

import traceback
from typing import List, Optional

import cv2
import numpy as np

from PySide2 import QtCore, QtGui, QtWidgets
import maya.cmds as cmds
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance

from arabesque.image_processor import (
    ImageProcessor,
    ContourGroup,
    METHOD_ADAPTIVE,
    METHOD_CANNY,
)
from arabesque.curve_generator import CurveGenerator
from arabesque.mesh_generator import MeshGenerator

WORKSPACE_CONTROL_NAME = "arabesqueToModelWorkspaceControl"
WINDOW_TITLE = "Arabesque to 3D Model"


def show_window():
    """Create or show the dockable workspace control."""
    if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, exists=True):
        cmds.deleteUI(WORKSPACE_CONTROL_NAME)

    cmds.workspaceControl(
        WORKSPACE_CONTROL_NAME,
        label=WINDOW_TITLE,
        widthProperty="preferred",
        initialWidth=420,
        minimumWidth=380,
    )

    ptr = omui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
    if ptr is None:
        cmds.warning("Could not find workspace control widget.")
        return

    parent_widget = wrapInstance(int(ptr), QtWidgets.QWidget)
    widget = ArabesqueWidget(parent=parent_widget)
    parent_widget.layout().addWidget(widget)


class ArabesqueWidget(QtWidgets.QWidget):
    """Main UI widget for arabesque processing."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._processor = ImageProcessor()
        self._curve_gen = CurveGenerator()
        self._mesh_gen = MeshGenerator()
        self._contour_groups: List[ContourGroup] = []

        self._build_ui()
        self._connect_signals()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # --- File picker ---
        file_group = QtWidgets.QGroupBox("Image File")
        file_lay = QtWidgets.QHBoxLayout(file_group)
        self._path_edit = QtWidgets.QLineEdit()
        self._path_edit.setPlaceholderText("Path to arabesque image...")
        self._browse_btn = QtWidgets.QPushButton("Browse...")
        file_lay.addWidget(self._path_edit, 1)
        file_lay.addWidget(self._browse_btn)
        root.addWidget(file_group)

        # --- Image preview ---
        preview_group = QtWidgets.QGroupBox("Preview")
        preview_lay = QtWidgets.QVBoxLayout(preview_group)
        self._preview_label = QtWidgets.QLabel("No image loaded")
        self._preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self._preview_label.setMinimumHeight(240)
        self._preview_label.setStyleSheet(
            "QLabel { background-color: #2b2b2b; border: 1px solid #555; }"
        )
        preview_lay.addWidget(self._preview_label)
        root.addWidget(preview_group)

        # --- Image processing parameters ---
        proc_group = QtWidgets.QGroupBox("Image Processing")
        proc_form = QtWidgets.QFormLayout(proc_group)
        proc_form.setLabelAlignment(QtCore.Qt.AlignRight)

        self._method_combo = QtWidgets.QComboBox()
        self._method_combo.addItems(["Adaptive Threshold", "Canny Edge"])
        proc_form.addRow("Method:", self._method_combo)

        self._threshold_slider = self._labeled_slider(1, 255, 127)
        proc_form.addRow("Threshold:", self._threshold_slider["layout"])

        self._blur_slider = self._labeled_slider(1, 31, 5, step=2)
        proc_form.addRow("Blur Radius:", self._blur_slider["layout"])

        self._min_area_spin = QtWidgets.QDoubleSpinBox()
        self._min_area_spin.setRange(0, 100000)
        self._min_area_spin.setValue(100)
        self._min_area_spin.setSuffix(" px")
        proc_form.addRow("Min Area:", self._min_area_spin)

        self._epsilon_spin = QtWidgets.QDoubleSpinBox()
        self._epsilon_spin.setRange(0.0001, 0.1)
        self._epsilon_spin.setValue(0.001)
        self._epsilon_spin.setDecimals(4)
        self._epsilon_spin.setSingleStep(0.0005)
        proc_form.addRow("Simplify Epsilon:", self._epsilon_spin)

        root.addWidget(proc_group)

        # --- Geometry parameters ---
        geo_group = QtWidgets.QGroupBox("Geometry")
        geo_form = QtWidgets.QFormLayout(geo_group)
        geo_form.setLabelAlignment(QtCore.Qt.AlignRight)

        self._scale_spin = QtWidgets.QDoubleSpinBox()
        self._scale_spin.setRange(0.01, 1000.0)
        self._scale_spin.setValue(10.0)
        self._scale_spin.setDecimals(2)
        geo_form.addRow("Scale:", self._scale_spin)

        self._smoothness_spin = QtWidgets.QSpinBox()
        self._smoothness_spin.setRange(4, 500)
        self._smoothness_spin.setValue(50)
        geo_form.addRow("Curve Smoothness:", self._smoothness_spin)

        self._depth_spin = QtWidgets.QDoubleSpinBox()
        self._depth_spin.setRange(0.001, 100.0)
        self._depth_spin.setValue(0.5)
        self._depth_spin.setDecimals(3)
        geo_form.addRow("Extrusion Depth:", self._depth_spin)

        self._bevel_width_spin = QtWidgets.QDoubleSpinBox()
        self._bevel_width_spin.setRange(0.0, 50.0)
        self._bevel_width_spin.setValue(0.05)
        self._bevel_width_spin.setDecimals(3)
        geo_form.addRow("Bevel Width:", self._bevel_width_spin)

        self._bevel_seg_spin = QtWidgets.QSpinBox()
        self._bevel_seg_spin.setRange(1, 10)
        self._bevel_seg_spin.setValue(3)
        geo_form.addRow("Bevel Segments:", self._bevel_seg_spin)

        root.addWidget(geo_group)

        # --- Action buttons ---
        btn_lay = QtWidgets.QHBoxLayout()
        self._process_btn = QtWidgets.QPushButton("Process Image")
        self._process_btn.setMinimumHeight(32)
        self._generate_btn = QtWidgets.QPushButton("Generate 3D Model")
        self._generate_btn.setMinimumHeight(32)
        self._generate_btn.setEnabled(False)
        btn_lay.addWidget(self._process_btn)
        btn_lay.addWidget(self._generate_btn)
        root.addLayout(btn_lay)

        # --- Progress bar ---
        self._progress = QtWidgets.QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # --- Status ---
        self._status_label = QtWidgets.QLabel("")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        root.addStretch()

    # ==================================================================
    # Signals
    # ==================================================================

    def _connect_signals(self):
        self._browse_btn.clicked.connect(self._on_browse)
        self._process_btn.clicked.connect(self._on_process)
        self._generate_btn.clicked.connect(self._on_generate)

    # ==================================================================
    # Slots
    # ==================================================================

    def _on_browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Arabesque Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;All Files (*)",
        )
        if path:
            self._path_edit.setText(path)

    def _on_process(self):
        path = self._path_edit.text().strip()
        if not path:
            self._set_status("Please select an image file first.", error=True)
            return

        try:
            self._processor.load_image(path)
        except FileNotFoundError as exc:
            self._set_status(str(exc), error=True)
            return

        method = METHOD_ADAPTIVE if self._method_combo.currentIndex() == 0 else METHOD_CANNY

        self._contour_groups = self._processor.process(
            threshold=self._threshold_slider["slider"].value(),
            blur_radius=self._blur_slider["slider"].value(),
            method=method,
            min_area=self._min_area_spin.value(),
            epsilon_factor=self._epsilon_spin.value(),
        )

        total_contours = sum(1 + len(g.holes) for g in self._contour_groups)
        self._set_status(
            f"Found {len(self._contour_groups)} contour group(s) "
            f"({total_contours} curves total)."
        )

        preview = self._processor.get_preview_image(self._contour_groups, max_size=400)
        self._show_preview(preview)

        self._generate_btn.setEnabled(len(self._contour_groups) > 0)

    def _on_generate(self):
        if not self._contour_groups:
            self._set_status("No contours to generate. Process an image first.", error=True)
            return

        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._generate_btn.setEnabled(False)
        self._process_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            curve_groups = self._curve_gen.create_curves(
                self._contour_groups,
                image_width=self._processor.width,
                image_height=self._processor.height,
                scale=self._scale_spin.value(),
                smoothness=self._smoothness_spin.value(),
            )

            result = self._mesh_gen.generate(
                curve_groups,
                depth=self._depth_spin.value(),
                bevel_width=self._bevel_width_spin.value(),
                bevel_segments=self._bevel_seg_spin.value(),
                progress_callback=self._update_progress,
            )

            self._set_status(f"Generated mesh: {result}")
        except Exception:
            self._set_status(
                f"Error during generation:\n{traceback.format_exc()}", error=True
            )
        finally:
            self._progress.setVisible(False)
            self._generate_btn.setEnabled(True)
            self._process_btn.setEnabled(True)

    # ==================================================================
    # Helpers
    # ==================================================================

    def _show_preview(self, bgr_image: np.ndarray):
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self._preview_label.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    def _update_progress(self, value: int):
        self._progress.setValue(value)
        QtWidgets.QApplication.processEvents()

    def _set_status(self, text: str, error: bool = False):
        color = "#ff6666" if error else "#cccccc"
        self._status_label.setStyleSheet(f"QLabel {{ color: {color}; }}")
        self._status_label.setText(text)

    @staticmethod
    def _labeled_slider(
        minimum: int,
        maximum: int,
        default: int,
        step: int = 1,
    ) -> dict:
        layout = QtWidgets.QHBoxLayout()
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)
        slider.setSingleStep(step)
        value_label = QtWidgets.QLabel(str(default))
        value_label.setMinimumWidth(30)
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        layout.addWidget(slider, 1)
        layout.addWidget(value_label)
        return {"layout": layout, "slider": slider, "label": value_label}
