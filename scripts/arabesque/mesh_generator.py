"""
Mesh generator: converts Maya NURBS curve groups into a beveled 3D polygon mesh.

Pipeline per curve group:
  1. ``planarSrf``      -- trimmed NURBS surface from outer + hole curves
  2. ``nurbsToPoly``    -- general tessellation with adaptive chord height
  3. topology cleanup   -- remove degenerate faces, non-manifold geometry
  4. ``polyRemesh``     -- retopologise into clean quads (with tri+quad fallback)
  5. ``polyExtrudeFacet`` -- uniform depth extrusion
  6. ``polyBevel3``     -- bevel on border edges (selected via polySelectConstraint)
  7. cleanup            -- merge vertices, soften normals

All groups are united into a single mesh at the end.
"""

from typing import List, Tuple

import maya.cmds as cmds
import maya.mel as mel


CurveGroupResult = Tuple[str, List[str]]


class MeshGenerator:
    """Generates a beveled 3D mesh from grouped NURBS curves."""

    def generate(
        self,
        curve_groups: List[CurveGroupResult],
        depth: float = 0.1,
        bevel_width: float = 0.01,
        bevel_segments: int = 3,
        target_edge_length: float = 0.0,
        progress_callback=None,
    ) -> str:
        """
        Build the full 3D mesh inside an undo chunk.

        Args:
            curve_groups: List of ``(outer_curve, [hole_curves])`` tuples.
            depth: Extrusion depth in world units.
            bevel_width: Offset for ``polyBevel3``.
            bevel_segments: Number of bevel subdivisions.
            target_edge_length: Desired edge length for remeshing.
                ``0`` = auto-calculate from bounding box.
            progress_callback: Optional ``fn(percent: int)`` for UI updates.

        Returns:
            Name of the final combined mesh transform node.
        """
        cmds.undoInfo(openChunk=True)
        try:
            return self._generate_impl(
                curve_groups, depth, bevel_width, bevel_segments,
                target_edge_length, progress_callback,
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
        target_edge_length: float,
        progress_callback,
    ) -> str:
        total = len(curve_groups)
        meshes: List[str] = []

        for idx, (outer, holes) in enumerate(curve_groups):
            mesh = self._process_group(
                outer, holes, depth, bevel_width, bevel_segments,
                target_edge_length, idx,
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
            final = cmds.polyUnite(
                meshes, ch=False, mergeUVSets=1, name="arabesque_model"
            )[0]
            cmds.polyMergeVertex(final, d=0.0001, am=True, ch=False)

        cmds.polySoftEdge(final, a=180, ch=False)
        cmds.delete(final, constructionHistory=True)

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
        target_edge_length: float,
        idx: int,
    ) -> str:
        # --- 1. Planar surface from curves ---
        all_curves = [outer_curve] + hole_curves
        srf = cmds.planarSrf(
            *all_curves,
            ch=False,
            d=3,
            ko=False,
            tol=0.001,
            rn=False,
            po=0,
            name=f"arabesque_srf_{idx}",
        )
        if not srf:
            cmds.warning(f"planarSrf failed for group {idx}")
            return ""
        srf = srf[0]

        # --- 2. NURBS-to-poly: general tessellation ---
        poly = cmds.nurbsToPoly(
            srf,
            ch=False,
            f=3,          # general tessellation (adaptive)
            pt=1,
            ut=1,
            un=5,
            vt=1,
            vn=5,
            cht=0.01,     # tight chord-height tolerance
            d=0.1,
            mel=0.001,    # min edge length
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

        # --- 3. Topology cleanup ---
        poly = self._cleanup_topology(poly)

        # --- 4. Remesh for clean quads ---
        edge_len = target_edge_length
        if edge_len <= 0:
            edge_len = self._auto_edge_length(poly)
        poly = self._remesh(poly, edge_len)

        # --- 5. Extrude ---
        num_faces = cmds.polyEvaluate(poly, f=True)
        if num_faces:
            cmds.polyExtrudeFacet(
                f"{poly}.f[0:{num_faces - 1}]",
                constructionHistory=False,
                keepFacesTogether=True,
                localTranslateZ=depth,
                divisions=1,
            )

        # --- 6. Bevel border edges ---
        if bevel_width > 0 and bevel_segments > 0:
            border_edges = self._select_border_edges(poly)
            if border_edges:
                cmds.polyBevel3(
                    border_edges,
                    offset=bevel_width,
                    segments=bevel_segments,
                    depth=1,
                    chamfer=False,
                    worldSpace=True,
                    smoothingAngle=30,
                    subdivideNgons=True,
                    mergeVertices=True,
                    mergeVertexTolerance=0.0001,
                    ch=False,
                )

        # --- 7. Final vertex merge ---
        cmds.polyMergeVertex(poly, d=0.0001, am=True, ch=False)
        return poly

    # ------------------------------------------------------------------
    # Topology helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cleanup_topology(mesh: str) -> str:
        """Remove degenerate / non-manifold / zero-area faces."""
        cmds.select(mesh)
        mel.eval(
            'polyCleanupArgList 4 '
            '{ "0","1","1","0","1","0","0","0","0","1e-05",'
            '"0","1e-05","0","1e-05","0","-1","0","0" }'
        )
        cmds.select(clear=True)

        cmds.polyMergeVertex(mesh, d=0.0001, am=True, ch=False)
        return mesh

    @staticmethod
    def _auto_edge_length(mesh: str) -> float:
        """Compute a reasonable target edge length from the bounding box diagonal."""
        bb = cmds.exactWorldBoundingBox(mesh)
        dx = bb[3] - bb[0]
        dy = bb[4] - bb[1]
        dz = bb[5] - bb[2]
        diag = (dx * dx + dy * dy + dz * dz) ** 0.5
        return max(diag / 80.0, 0.001)

    @staticmethod
    def _remesh(mesh: str, target_edge_length: float) -> str:
        """
        Retopologise into clean quads.

        Uses ``polyRemesh`` (Maya 2020+) for an even quad-dominant layout.
        Falls back to triangulate + quadrangulate if unavailable.
        """
        try:
            cmds.polyRemesh(
                mesh,
                targetEdgeLength=target_edge_length,
                collapseThreshold=20,
                smoothStrength=0.5,
                ch=False,
            )
        except (RuntimeError, TypeError):
            cmds.polyTriangulate(mesh, ch=False)
            cmds.polyQuad(
                mesh,
                angle=40,
                keepGroupBorder=True,
                keepTextureBorders=True,
                keepHardEdges=True,
                ch=False,
            )

        cmds.polyMergeVertex(mesh, d=0.0001, am=True, ch=False)
        return mesh

    @staticmethod
    def _select_border_edges(mesh: str) -> list:
        """
        Fast border-edge selection using polySelectConstraint.

        Orders of magnitude faster than iterating every edge with polyInfo.
        """
        cmds.select(f"{mesh}.e[*]")
        cmds.polySelectConstraint(
            mode=2,       # constrained selection
            type=0x8000,  # edges
            where=1,      # border
        )
        border = cmds.ls(selection=True, flatten=True) or []
        cmds.polySelectConstraint(mode=0)  # reset
        cmds.select(clear=True)
        return border

    @staticmethod
    def _delete_leftover_curves(curve_groups: List[CurveGroupResult]):
        for outer, holes in curve_groups:
            for name in [outer] + holes:
                if cmds.objExists(name):
                    cmds.delete(name)
