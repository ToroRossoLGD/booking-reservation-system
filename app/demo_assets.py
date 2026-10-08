"""Original vector demo illustrations; no photographs or third-party assets."""

from fastapi import HTTPException

PALETTES = {
    "demo/river": ("#c4d9df", "#365f70", "#dcb88c"),
    "demo/garden": ("#d9e2cd", "#597958", "#cfad83"),
    "demo/home": ("#e7d7cc", "#a17165", "#c3a778"),
}


def illustration(key):
    if key not in PALETTES:
        raise HTTPException(404, "Demo illustration not found")
    wall, sofa, wood = PALETTES[key]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">
<rect width="960" height="640" fill="{wall}"/>
<path d="M0 455H960V640H0Z" fill="{wood}"/>
<rect x="540" y="65" width="290" height="290" rx="8" fill="#f8faf7"/>
<rect x="555" y="80" width="260" height="260" fill="#b1d7e4"/>
<path d="M555 290L650 195L740 265L815 175V340H555Z" fill="#7c9d8a"/>
<path d="M685 80V340M555 210H815" stroke="#fff" stroke-width="12"/>
<rect x="100" y="325" width="335" height="170" rx="28" fill="{sofa}"/>
<rect x="80" y="400" width="375" height="100" rx="18" fill="{sofa}"/>
<path d="M110 500V535M425 500V535" stroke="#473e35" stroke-width="15"/>
<ellipse cx="660" cy="490" rx="120" ry="35" fill="#f4ede2"/>
<path d="M585 495L565 570M735 495L755 570" stroke="#51473c" stroke-width="12"/>
<rect x="170" y="135" width="170" height="125" fill="#f5eedf"/>
<circle cx="255" cy="195" r="37" fill="{sofa}"/>
<text x="40" y="605" font-family="sans-serif" font-size="22" fill="#292f2c">
BOOKICA DEMO / ILLUSTRATION</text>
</svg>'''.encode()
