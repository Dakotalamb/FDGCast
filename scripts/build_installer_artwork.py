"""Regenerate repository-native installer artwork with Inkscape.
SPDX-License-Identifier: GPL-2.0-or-later
"""
import base64
from pathlib import Path
import subprocess
import struct

root=Path(__file__).resolve().parent.parent
out=root/'packaging'/'installer'
icon=(root/'packaging'/'FDGCast.ico').read_bytes()
count=struct.unpack_from('<H',icon,4)[0]
frames=[struct.unpack_from('<BBBBHHII',icon,6+i*16) for i in range(count)]
frame=max(frames,key=lambda f:(f[0] or 256)*(f[1] or 256))
logo=base64.b64encode(icon[frame[7]:frame[7]+frame[6]]).decode()
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="164" height="314" viewBox="0 0 164 314">
<rect width="164" height="314" fill="#151719"/>
<path d="M0 0H164V4H0Z" fill="#ff5a1f"/>
<path d="M164 125L18 269H164Z" fill="#202427"/>
<path d="M164 173L70 267H164Z" fill="#282a2b"/>
<path d="M164 255L106 314H164Z" fill="#ff5a1f"/>
<text x="18" y="31" fill="#fff3df" font-family="DejaVu Sans,Segoe UI,sans-serif" font-weight="bold" font-size="15" letter-spacing="1">FDGCAST</text>
<text x="19" y="44" fill="#b8b8b5" font-family="DejaVu Sans,Segoe UI,sans-serif" font-size="5.5" letter-spacing="1.2">FORGED DESTINY GAMING</text>
<image x="15" y="66" width="82" height="82" xlink:href="data:image/png;base64,{logo}"/>
<text x="19" y="177" fill="#fff3df" font-family="DejaVu Sans,Segoe UI,sans-serif" font-weight="bold" font-size="20">Your stream.</text>
<text x="19" y="204" fill="#ff5a1f" font-family="DejaVu Sans,Segoe UI,sans-serif" font-weight="bold" font-size="23">Together.</text>
<path d="M20 223H49" stroke="#ff5a1f" stroke-width="2"/>
<text x="19" y="245" fill="#d4d5d0" font-family="DejaVu Sans,Segoe UI,sans-serif" font-size="8.5">Multistream. Multichat.</text>
<text x="19" y="260" fill="#d4d5d0" font-family="DejaVu Sans,Segoe UI,sans-serif" font-size="8.5">Create in every format.</text>
<text x="19" y="297" fill="#b8b8b5" font-family="DejaVu Sans,Segoe UI,sans-serif" font-size="6.5" letter-spacing="1">BUILT FOR CREATORS</text>
</svg>'''
(out/'welcome.svg').write_text(svg,encoding='utf-8')
subprocess.run(['inkscape',str(out/'welcome.svg'),'--export-type=png','--export-width=656','--export-filename='+str(out/'welcome.png')],check=True)
