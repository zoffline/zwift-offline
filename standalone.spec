# -*- mode: python -*-

block_cipher = None


a = Analysis(['standalone.py'],
             pathex=['/home/alexvh/Code/zoffline'],
             binaries=[],
             datas=[('ssl/*', 'ssl'), ('initialize_db.sql', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
a.datas += Tree('cdn', prefix='cdn')
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
          runtime_tmpdir=None,
          console=True )
