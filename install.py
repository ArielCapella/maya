"""
Installer for the Arabesque-to-3D Maya plugin.

Detects Maya's ``mayapy``, installs Python packages, and creates a
``.mod`` module file so Maya discovers the plugin automatically.

Can be run two ways:
    - Double-click ``setup.bat`` (recommended for Windows users)
    - ``python install.py`` from a terminal
"""

import os
import subprocess
import sys
import platform
import shutil

MAYA_VERSIONS = ["2025", "2024", "2023"]

WINDOWS_PATHS = [
    rf"C:\Program Files\Autodesk\Maya{v}\bin\mayapy.exe" for v in MAYA_VERSIONS
]
MACOS_PATHS = [
    f"/Applications/Autodesk/maya{v}/Maya.app/Contents/bin/mayapy" for v in MAYA_VERSIONS
]
LINUX_PATHS = [
    f"/usr/autodesk/maya{v}/bin/mayapy" for v in MAYA_VERSIONS
]


def find_mayapy():
    """Return (mayapy_path, version) or ("", "")."""
    system = platform.system()
    if system == "Windows":
        candidates = WINDOWS_PATHS
    elif system == "Darwin":
        candidates = MACOS_PATHS
    else:
        candidates = LINUX_PATHS

    for path, ver in zip(candidates, MAYA_VERSIONS):
        if os.path.isfile(path):
            return path, ver

    found = shutil.which("mayapy")
    if found:
        return found, MAYA_VERSIONS[0]

    return "", ""


def install_packages(mayapy: str):
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    cmd = [mayapy, "-m", "pip", "install", "--user", "-r", req_file]
    print(f"  Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)


def get_modules_dir(version: str) -> str:
    system = platform.system()
    if system == "Windows":
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        return os.path.join(docs, "maya", version, "modules")
    elif system == "Darwin":
        return os.path.expanduser(
            f"~/Library/Preferences/Autodesk/maya/{version}/modules"
        )
    else:
        return os.path.expanduser(f"~/maya/{version}/modules")


def create_module_file(version: str):
    """
    Write a ``.mod`` file that tells Maya where this plugin lives.

    This avoids having to copy files or set environment variables.
    The .mod file format:  ``+ ModuleName version path``
    Maya then looks for ``plug-ins/`` and ``scripts/`` inside that path.
    """
    modules_dir = get_modules_dir(version)
    os.makedirs(modules_dir, exist_ok=True)

    plugin_root = os.path.dirname(os.path.abspath(__file__))
    mod_path = os.path.join(modules_dir, "arabesque.mod")

    with open(mod_path, "w") as f:
        f.write(f"+ Arabesque 1.0 {plugin_root}\n")

    print(f"  Module file created: {mod_path}")
    return mod_path


def main():
    print()
    print("  Arabesque-to-3D Plugin Installer")
    print("  =================================")
    print()

    mayapy, version = find_mayapy()
    if not mayapy:
        print(
            "  ERROR: Could not locate Maya (2023-2025).\n"
            "  Install packages manually:\n"
            "    <path-to-mayapy> -m pip install -r requirements.txt\n"
        )
        sys.exit(1)

    print(f"  Found Maya {version}: {mayapy}\n")

    print("  Step 1/2: Installing Python packages...")
    install_packages(mayapy)
    print("  Done.\n")

    print("  Step 2/2: Creating Maya module file...")
    mod_path = create_module_file(version)
    print("  Done.\n")

    print("  ===================================")
    print("  Installation complete!")
    print("  ===================================\n")
    print("  Next steps:")
    print(f"    1. Open Maya {version}")
    print("    2. Windows > Settings/Preferences > Plugin Manager")
    print("    3. Find 'arabesque_to_3d.py' and check 'Loaded'")
    print("    4. Use the new 'Arabesque' menu in the menu bar\n")


if __name__ == "__main__":
    main()
