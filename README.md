# TICPY-Runtime
TICPY Runtime is a python writted alternative runtime to TIC-80, it executes your cartridges with total compatibility (there are some limitations, but if you don't use the banks or the VRAM, it should work) and fidelity, like in TIC-80.

# Usage
Use this command to deschiper your cartridge:
``python
python tic2py.py game.tic game.py
``
then, execute your cartridge:
``python
python main.py game.py
``
and play!

# Controls
The btn function uses WASD and the arrows, the buttons are ZXC.

# How to package
If you use PyInstaller for your count, package the *pyinstallermain.py* file, it's the same init, but with compatibility for PyInstaller, and **if you publish the game, make sure that you have distributed the Python, Pyglet and TIC-80 licenses.**

Python for the embedded runtime (with the third party, make sure that is the same one of the installation that PyInstaller uses on the build, it's on the root (e. g.): "%LOCALAPPDATA%\Programs\Python\Python314\LICENSE.txt" or the correct version.

Pyglet for the library used in this engine, it's a library like Pygame but without libraries, only Python with ctypes, the only license is the main license.

TIC-80 for the font used in the *audio.py* file, it's only the MIT License (the license of the project), not its third party, because is a font, not code with libraries.

# License
This project is under the BSL-1.0 License (Boost), this license haves an exception for the binary distributions.
