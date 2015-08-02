from distutils.core import setup
import os, sys
import py2exe
from glob import glob
import PyQt5

NAME="FotoWoman"

# data_files = [("Microsoft.VC90.CRT", glob(r'C:\Program Files\Microsoft Visual Studio 9.0\VC\redist\x86\Microsoft.VC90.CRT\*.*'))]
data_files = []
# mfcdir = r"C:\Python34\Lib\site-packages\pythonwin"
# data_files.append([os.path.join(mfcdir, i) for i in ["mfc90.dll", "mfc90u.dll", "mfcm90.dll", "mfcm90u.dll", "Microsoft.VC90.MFC.manifest"]])
qt_platform_plugins = [("platforms", glob(PyQt5.__path__[0] + r'\plugins\platforms\*.*'))]
data_files.extend(qt_platform_plugins)
msvc_dlls = [('.', glob(r'C:\Windows\System32\msvc?100.dll'))]
data_files.extend(msvc_dlls)
# print(data_files)

sys.argv.append('py2exe')

setup(
	data_files=data_files,
	# windows=["pyftp1.py",],
	windows=[
		{
			"script": "pyftp1.py",
			"icon_resources": [(1, "resources/favicon.ico")]
		}
	],
	# zipfile=None,
	options={
		"py2exe": {
			"includes":["sip", "atexit",],
			# "packages": ['PyQt5'],
			"compressed": True,
			"dist_dir": "dist/" + NAME,
			# "bundle_files": 0,
			# "zipfile": None,
			"optimize": 2,
		}
	}
)