"""
Image processing pipeline for arabesque contour extraction.

Uses OpenCV to load raster images, detect edges / threshold,
extract contours with hierarchy, simplify them, and group
outer boundaries with their holes.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np


METHOD_ADAPTIVE = "adaptive"
METHOD_CANNY = "canny"


@dataclass
class ContourGroup:
    """An outer contour with its associated hole contours."""
    outer: np.ndarray
    holes: List[np.ndarray] = field(default_factory=list)


class ImageProcessor:
    """Loads a raster image and extracts arabesque contours."""

    def __init__(self):
        self._image: Optional[np.ndarray] = None
        self._gray: Optional[np.ndarray] = None
        self.width: int = 0
        self.height: int = 0

    def load_image(self, path: str) -> np.ndarray:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {path}")
        self._image = img
        self._gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        self.height, self.width = img.shape[:2]
        return img

    @property
    def image(self) -> Optional[np.ndarray]:
        return self._image

    def process(
        self,
        threshold: int = 127,
        blur_radius: int = 5,
        method: str = METHOD_ADAPTIVE,
        min_area: float = 100.0,
        epsilon_factor: float = 0.001,
    ) -> List[ContourGroup]:
        """
        Run the full contour-extraction pipeline.

        Args:
            threshold: Global threshold value (used by adaptive fallback).
            blur_radius: Gaussian blur kernel size (must be odd).
            method: ``"adaptive"`` or ``"canny"``.
            min_area: Contours with area below this are discarded.
            epsilon_factor: Multiplied by arc length for ``approxPolyDP``.

        Returns:
            List of :class:`ContourGroup` objects ready for curve generation.
        """
        if self._gray is None:
            raise RuntimeError("No image loaded. Call load_image() first.")

        blur_k = max(blur_radius, 1) | 1  # ensure odd
        blurred = cv2.GaussianBlur(self._gray, (blur_k, blur_k), 0)

        if method == METHOD_CANNY:
            binary = self._detect_canny(blurred, threshold)
        else:
            binary = self._detect_adaptive(blurred, threshold)

        contours, hierarchy = cv2.findContours(
            binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )

        if hierarchy is None:
            return []

        hierarchy = hierarchy[0]

        simplified = []
        for cnt in contours:
            eps = epsilon_factor * cv2.arcLength(cnt, True)
            simplified.append(cv2.approxPolyDP(cnt, eps, True))

        return self._group_contours(simplified, hierarchy, min_area)

    def get_preview_image(
        self, groups: List[ContourGroup], max_size: int = 512
    ) -> np.ndarray:
        """Return a copy of the loaded image with contours drawn on it."""
        if self._image is None:
            raise RuntimeError("No image loaded.")

        preview = self._image.copy()

        for grp in groups:
            cv2.drawContours(preview, [grp.outer], -1, (0, 255, 0), 2)
            for hole in grp.holes:
                cv2.drawContours(preview, [hole], -1, (0, 0, 255), 1)

        h, w = preview.shape[:2]
        scale = max_size / max(h, w)
        if scale < 1.0:
            preview = cv2.resize(
                preview,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_AREA,
            )
        return preview

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_adaptive(blurred: np.ndarray, threshold: int) -> np.ndarray:
        block_size = max(threshold | 1, 3)  # must be odd and >= 3
        binary = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            block_size,
            5,
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        return binary

    @staticmethod
    def _detect_canny(blurred: np.ndarray, threshold: int) -> np.ndarray:
        low = max(threshold // 2, 1)
        edges = cv2.Canny(blurred, low, threshold)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=1)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        return edges

    @staticmethod
    def _group_contours(
        contours: list,
        hierarchy: np.ndarray,
        min_area: float,
    ) -> List[ContourGroup]:
        """
        Group contours using RETR_CCOMP hierarchy.

        RETR_CCOMP gives a two-level hierarchy:
          hierarchy[i] = [next, prev, first_child, parent]
        Top-level contours (parent == -1) are outer boundaries.
        Their children are holes.
        """
        groups: List[ContourGroup] = []

        for i, cnt in enumerate(contours):
            parent = hierarchy[i][3]
            if parent != -1:
                continue  # it's a hole, will be collected by its parent

            if cv2.contourArea(cnt) < min_area:
                continue

            group = ContourGroup(outer=cnt)

            child_idx = hierarchy[i][2]
            while child_idx != -1:
                child_cnt = contours[child_idx]
                if cv2.contourArea(child_cnt) >= min_area:
                    group.holes.append(child_cnt)
                child_idx = hierarchy[child_idx][0]

            groups.append(group)

        return groups
