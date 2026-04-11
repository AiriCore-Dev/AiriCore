import random
import os
from pathlib import Path

resources_dir: Path = Path(__file__).parent / "resources"

marker_img_path: Path = resources_dir / "images" / "marker.png"
'''
bg_img_path: Path = resources_dir / "images" / "background"
bg_img_path: Path = resources_dir / "images" / "background" / random.choice(os.listdir(bg_img_path))
baotu_font_path: Path = resources_dir / "fonts" / "baotu.ttf"
spicy_font_path: Path = resources_dir / "fonts" / "SpicyRice-Regular.ttf"
adlam_font_path: Path = resources_dir / "fonts" / "ADLaMDisplay-Regular.ttf"
'''
baotu_font_path: Path = resources_dir / "fonts" / "ADLaMDisplay-Regular.ttf"
spicy_font_path: Path = resources_dir / "fonts" / "ADLaMDisplay-Regular.ttf"
adlam_font_path: Path = resources_dir / "fonts" / "ADLaMDisplay-Regular.ttf"



