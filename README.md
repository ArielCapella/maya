# Arabesque to 3D Model - Maya Plugin

A Maya plugin that transforms 2D raster images of organic arabesque patterns into beveled 3D polygon meshes.

## Features

- Load PNG / JPG images of arabesque or ornamental patterns
- Automatic contour extraction via OpenCV (adaptive threshold or Canny edge detection)
- Live contour preview with adjustable parameters
- NURBS curve generation with configurable smoothness
- Extruded polygon mesh with customisable bevel
- Full dockable UI inside Maya
- Single-step undo for the entire 3D generation

## Quick Install (Windows)

> Make sure Maya is **closed** before installing.

1. **Double-click `setup.bat`**
2. Wait for it to finish (it installs dependencies and registers the plugin automatically)
3. Open Maya
4. Go to **Windows > Settings/Preferences > Plugin Manager**
5. Find **arabesque_to_3d.py** and check **Loaded** (and **Auto-load** to keep it loaded)
6. A new **Arabesque** menu appears in the menu bar

That's it -- no terminal, no file copying, no environment variables.

## Alternative Install (all platforms)

If you prefer a terminal or are on macOS/Linux:

```
python install.py
```

This finds Maya's Python, installs the required packages, and creates a `.mod` module file.

If automatic detection fails, install manually:

```
"C:\Program Files\Autodesk\Maya2023\bin\mayapy.exe" -m pip install -r requirements.txt
```

Then copy the folders into your Maya prefs directory:

```
<Documents>/maya/2023/plug-ins/arabesque_to_3d.py
<Documents>/maya/2023/scripts/arabesque/   (entire folder)
```

## Usage

1. Click **Arabesque > Arabesque to 3D Model...** to open the dockable panel
2. Click **Browse** and select a raster image of an arabesque pattern
3. Adjust image processing parameters if needed
4. Click **Process Image** to extract and preview contours (green = outer, red = holes)
5. Adjust geometry parameters (scale, depth, bevel)
6. Click **Generate 3D Model** to create the mesh in the viewport

### Parameter Guide

| Parameter | Description |
|---|---|
| **Method** | Adaptive Threshold (better for clean images) or Canny Edge (better for photos) |
| **Threshold** | Controls edge/threshold sensitivity |
| **Blur Radius** | Gaussian blur before detection (higher = less noise, less detail) |
| **Min Area** | Ignore contours smaller than this pixel area |
| **Simplify Epsilon** | Higher = fewer points per contour, lower fidelity |
| **Scale** | Size of the generated model in Maya units |
| **Curve Smoothness** | NURBS rebuild spans (higher = smoother curves) |
| **Extrusion Depth** | How thick the 3D model is |
| **Bevel Width** | Width of the edge bevel |
| **Bevel Segments** | Subdivision count for smooth bevels |

## Supported Maya Versions

- Maya 2023
- Maya 2024
- Maya 2025

The installer automatically detects which version is installed.

## Project Structure

```
plug-ins/
  arabesque_to_3d.py          Maya plugin entry point
scripts/
  arabesque/
    __init__.py
    image_processor.py         OpenCV contour extraction
    curve_generator.py         Contour-to-NURBS conversion
    mesh_generator.py          Mesh extrusion and bevel
    ui/
      __init__.py
      main_window.py           PySide2 dockable UI
setup.bat                      One-click Windows installer
install.py                     Cross-platform installer
requirements.txt
```

## License

MIT
