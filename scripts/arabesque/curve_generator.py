"""
Curve generator: converts OpenCV contour data into Maya NURBS curves.

Handles coordinate system mapping (image Y-down -> Maya XZ plane)
and curve smoothing via ``rebuildCurve``.
"""

from typing import List, Tuple

import numpy as np
import maya.cmds as cmds

from arabesque.image_processor import ContourGroup


CurveGroupResult = Tuple[str, List[str]]


class CurveGenerator:
    """Creates Maya NURBS curves from extracted contour groups."""

    def create_curves(
        self,
        groups: List[ContourGroup],
        image_width: int,
        image_height: int,
        scale: float = 1.0,
        smoothness: int = 50,
    ) -> List[CurveGroupResult]:
        """
        Build NURBS curves in Maya for every contour group.

        Args:
            groups: Contour groups from :class:`ImageProcessor`.
            image_width: Source image width in pixels.
            image_height: Source image height in pixels.
            scale: World-unit scale factor applied after normalisation.
            smoothness: Number of spans used by ``rebuildCurve``.

        Returns:
            List of ``(outer_curve_name, [hole_curve_names])`` tuples.
        """
        results: List[CurveGroupResult] = []

        for idx, grp in enumerate(groups):
            outer_name = self._contour_to_curve(
                grp.outer,
                image_width,
                image_height,
                scale,
                smoothness,
                f"arabesque_outer_{idx}",
            )

            hole_names: List[str] = []
            for h_idx, hole in enumerate(grp.holes):
                name = self._contour_to_curve(
                    hole,
                    image_width,
                    image_height,
                    scale,
                    smoothness,
                    f"arabesque_hole_{idx}_{h_idx}",
                )
                hole_names.append(name)

            results.append((outer_name, hole_names))

        return results

    # ------------------------------------------------------------------

    def _contour_to_curve(
        self,
        contour: np.ndarray,
        img_w: int,
        img_h: int,
        scale: float,
        smoothness: int,
        name: str,
    ) -> str:
        points = self._map_coordinates(contour, img_w, img_h, scale)

        # Close the curve by appending the first point
        if len(points) > 1:
            points.append(points[0])

        crv = cmds.curve(d=1, p=points, name=name)

        crv = cmds.rebuildCurve(
            crv,
            ch=False,
            rpo=True,
            rt=0,
            end=1,
            kr=0,
            kcp=False,
            kep=True,
            kt=False,
            s=smoothness,
            d=3,
            tol=0.01,
        )[0]

        cmds.closeCurve(crv, ch=False, ps=0, rpo=True, bb=0.5, bki=False, p=0.1)

        return crv

    @staticmethod
    def _map_coordinates(
        contour: np.ndarray,
        img_w: int,
        img_h: int,
        scale: float,
    ) -> list:
        """
        Map image pixel coordinates to Maya world space on the XZ plane,
        centered at the origin.
        """
        half_w = img_w / 2.0
        half_h = img_h / 2.0

        points = []
        for pt in contour:
            px, py = float(pt[0][0]), float(pt[0][1])
            x = (px - half_w) / img_w * scale
            z = (half_h - py) / img_h * scale  # flip Y
            points.append((x, 0.0, z))

        return points
