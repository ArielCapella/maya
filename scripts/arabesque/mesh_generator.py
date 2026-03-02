"""
Mesh generator: converts Maya NURBS curve groups into a beveled 3D polygon mesh.

Pipeline per curve group:
  1. ``planarSrf``  -- trimmed NURBS surface from outer + hole curves
  2. ``nurbsToPoly`` -- quad-dominant polygon conversion
  3. ``polyExtrudeFacet`` -- uniform depth extrusion
  4. ``polyBevel3``  -- bevel on border edges
  5. cleanup (merge verts, soften normals)

All groups are united into a single mesh at the end.
"""

from typing import List, Tuple

import maya.cmds as cmds


CurveGroupResult = Tuple[str, List[str]]


class MeshGenerator:
    """Generates a beveled 3D mesh from grouped NURBS curves."""

    def generate(
        self,
        curve_groups: List[CurveGroupResult],
        depth: float = 0.1,
        bevel_width: float = 0.01,
        bevel_segments: int = 3,
        progress_callback=None,
    ) -> str:
        """
        Build the full 3D mesh inside an undo chunk.

        Args:
            curve_groups: List of ``(outer_curve, [hole_curves])`` tuples.
            depth: Extrusion depth in world units.
            bevel_width: Offset for ``polyBevel3``.
            bevel_segments: Number of bevel subdivisions.
            progress_callback: Optional ``fn(percent: int)`` for UI updates.

        Returns:
            Name of the final combined mesh transform node.
        """
        cmds.undoInfo(openChunk=True)
        try:
            return self._generate_impl(
                curve_groups, depth, bevel_width, bevel_segments, progress_callback
            )
        finally:
            cmds.undoInfo(closeChunk=True)

    # ------------------------------------------------------------------

    def _generate_impl(
        self,
        curve_groups: List[CurveGroupResult],
        depth: float,
        bevel_width: float,
        bevel_segments: int,
        progress_callback,
    ) -> str:
        total = len(curve_groups)
        meshes: List[str] = []

        for idx, (outer, holes) in enumerate(curve_groups):
            mesh = self._process_group(
                outer, holes, depth, bevel_width, bevel_segments, idx
            )
            if mesh:
                meshes.append(mesh)

            if progress_callback:
                progress_callback(int((idx + 1) / total * 100))

        if not meshes:
            cmds.warning("No meshes were generated.")
            return ""

        if len(meshes) == 1:
            final = cmds.rename(meshes[0], "arabesque_model")
        else:
            final = cmds.polyUnite(meshes, ch=False, mergeUVSets=1, name="arabesque_model")[0]
            cmds.polyMergeVertex(final, d=0.001, am=True, ch=False)

        cmds.polySoftEdge(final, a=180, ch=False)

        self._delete_leftover_curves(curve_groups)

        cmds.select(final)
        cmds.viewFit()
        return final

    def _process_group(
        self,
        outer_curve: str,
        hole_curves: List[str],
        depth: float,
        bevel_width: float,
        bevel_segments: int,
        idx: int,
    ) -> str:
        all_curves = [outer_curve] + hole_curves
        srf = cmds.planarSrf(
            *all_curves,
            ch=False,
            d=3,
            ko=False,
            tol=0.01,
            rn=False,
            po=0,
            name=f"arabesque_srf_{idx}",
        )
        if not srf:
            cmds.warning(f"planarSrf failed for group {idx}")
            return ""
        srf = srf[0]

        poly = cmds.nurbsToPoly(
            srf,
            mnd=1,
            ch=False,
            f=2,       # quads
            pt=1,      # per-surf # of isoparms
            pc=200,    # count
            chr=0.9,
            ft=0.01,
            mel=0.001,
            d=0.1,
            ut=1,
            un=3,
            vt=1,
            vn=3,
            uch=False,
            ucr=False,
            cht=0.2,
            es=0,
            ntr=0,
            mrt=0,
            uss=True,
            name=f"arabesque_poly_{idx}",
        )
        if not poly:
            cmds.warning(f"nurbsToPoly failed for group {idx}")
            cmds.delete(srf)
            return ""
        poly = poly[0]

        cmds.delete(srf)

        num_faces = cmds.polyEvaluate(poly, f=True)
        if num_faces:
            cmds.polyExtrudeFacet(
                f"{poly}.f[0:{num_faces - 1}]",
                constructionHistory=False,
                keepFacesTogether=True,
                localTranslateZ=depth,
            )

        if bevel_width > 0 and bevel_segments > 0:
            border_edges = self._get_border_edges(poly)
            if border_edges:
                cmds.polyBevel3(
                    border_edges,
                    offset=bevel_width,
                    segments=bevel_segments,
                    depth=1,
                    mitering=0,
                    miterAlong=0,
                    chamfer=False,
                    worldSpace=True,
                    smoothingAngle=30,
                    subdivideNgons=True,
                    mergeVertices=True,
                    mergeVertexTolerance=0.0001,
                    ch=False,
                )

        cmds.polyMergeVertex(poly, d=0.001, am=True, ch=False)

        return poly

    @staticmethod
    def _get_border_edges(mesh: str) -> list:
        num_edges = cmds.polyEvaluate(mesh, e=True)
        if not num_edges:
            return []

        border = []
        for i in range(num_edges):
            edge = f"{mesh}.e[{i}]"
            faces = cmds.polyInfo(edge, edgeToFace=True)
            if faces:
                parts = faces[0].split(":")
                if len(parts) > 1:
                    face_ids = parts[1].strip().split()
                    if len(face_ids) == 1:
                        border.append(edge)
        return border

    @staticmethod
    def _delete_leftover_curves(curve_groups: List[CurveGroupResult]):
        for outer, holes in curve_groups:
            for name in [outer] + holes:
                if cmds.objExists(name):
                    cmds.delete(name)
