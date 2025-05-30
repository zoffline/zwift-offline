# -*- mode: python -*-

block_cipher = None

import sys
sys.modules['FixTk'] = None
import xml.etree.ElementTree as ET
version = ET.parse('cdn/gameassets/Zwift_Updates_Root/Zwift_ver_cur.xml').getroot().get('version')

a = Analysis(['standalone.py'],
             pathex=['protobuf'],
             binaries=[],
             datas=[('ssl/*', 'ssl'), ('data/*', 'data')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=['FixTk', 'tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter', 'pkg_resources'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
a.binaries = [x for x in a.binaries if not 'Java_Temurin' in x[1]]
a.datas += Tree('cdn', prefix='cdn')
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='zoffline_' + version,
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=['greenlet\\*.pyd', '_uuid.pyd', 'python3.dll'],
          runtime_tmpdir=None,
          console=True )

import subprocess
subprocess.call(['C:\\Program Files (x86)\\Windows Kits\\10\\App Certification Kit\\signtool.exe', 'sign',
                '/f', 'ssl\\cert-zwift-com.p12', '/fd', 'sha1',
                '/t', 'http://timestamp.digicert.com',
                'dist\\zoffline_%s.exe' % version])
