## How to build dupeGuru for Linux

### Prerequisites

- [Python 3.5+][http://www.python.org/]
- [Build.py][https://pypi.org/project/build.py/]

### With build.py (preferred)

To build with a different python version 3.5 vs 3.6 or 32 bit vs 64 bit specify that version instead of -3.5 to the `py` command below.  If you want to build additional versions while keeping all virtual environments setup use a different location for each virtual environment.
```
cd <dupeGuru directory>
git submodule init
git submodule update
# py -3.5 -m venv .\env
# .\env\Scripts\activate
pip3 install -r requirements.txt -r requirements-extra.txt
python3 build.py
python3 run.py
```
### Run app

To run it `python3 run.py`

### With makefile

It is possible to build dupeGuru with the makefile on Linux using a compatable POSIX environment.  The following steps have been tested using [msys2][msys2]. Before running make:
1. Install msys2 or other POSIX environment
2. Install PyQt5 globally via pip
3. Use the respective console for msys2 it is `msys2 msys`

Then the following execution of the makefile should work.  Pass the correct value for PYTHON to the makefile if not on the path as python3.

```
    cd dupeguru/
    make PYTHON='py -3.5'
    make run
```

You might also try: `make PYTHON='py'` or just `make`.

#### Build Essentials

If you see: `Makefile:58: *** "Python 3.4+ required. Aborting.".  Stop.` then install python:

```
sudo apt-get install python3.4
sudo apt-get install pythonpy
sudo apt-get install python3-venv
sudo apt-get install python3-pip
pip3 install PyQt5
pip3 install tox
pip3 install pyqt5
sudo apt install -f --reinstall python3-minimal
```

You may see missing modules errors:
- `/bin/sh: 1: pyrcc5: not found` then... (needs work)
- `ModuleNotFoundError: No module named 'PyQt5'` then...  (needs work)
- `ModuleNotFoundError: No module named 'send2trash'` then...  (needs work)
- Hopefully you will see `Build complete! You can run dupeGuru with 'make run'`
- `dpkg-checkbuilddeps: error: Unmet build dependencies: debhelper (>= 7)` then... (needs work)
- maybe try `dpkg-source --before-build .`
- `FileExistsError: [Errno 17] File exists: 'build/dupeguru-4.0.3~trusty/modules'` then you might need to do `rm -rf build/`

### Generate Linux Installer Packages

You need to use the respective x86 or x64 version of python to build the 32 bit and 64 bit versions.  The build scripts will automatically detect the python architecture for you. When using build.py make sure the resulting python works before continuing to package.py.  NOTE: package.py looks for the 'makensis' executable in the default location for a 64 bit Linux system.  Run the following in the respective virtual environment.
```
python3 package.py
```

### Running tests

The complete test suite can be run with tox just like on linux.

[python]: http://www.python.org/
[tox]: https://tox.readthedocs.io/en/latest/install.html

### Compiling on Linux with py_compile
```
python -O -m py_compile package.py
python -m py_compile package.py
chmod a+x pkg/dupeguru.desktop
```

If you are compiling because you want speed, you can also add the -O flag, like python -O -m py_compile, which will “turn on basic optimizations”. It mainly strips out assert statements and if __debug__ code, so for most code it has no effect. See man python and “What does Python optimization … do?” for details.
