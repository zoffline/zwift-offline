# -*- mode: python -*-

block_cipher = None

import sys
sys.modules['FixTk'] = None

a = Analysis(['standalone.py'],
             pathex=['/home/alexvh/Code/zoffline'],
             binaries=[],
             datas=[('ssl/*', 'ssl'), ('initialize_db.sql', '.'), ('start_lines.csv', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=['FixTk', 'tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
a.datas += Tree('cdn', prefix='cdn')
a.datas += Tree('pace_partners', prefix='pace_partners')
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='zoffline',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude="vcruntime140.dll",
          runtime_tmpdir=None,
          console=True )

import subprocess
subprocess.call(['C:\\Program Files (x86)\\Windows Kits\\10\\App Certification Kit\\signtool.exe', 'sign',
                '/f', 'ssl\cert-zwift-com.p12',
                '/t', 'http://timestamp.digicert.com',
                'dist\zoffline.exe'])
