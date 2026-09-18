import argparse
import os
import sys
import zipfile
from io import BytesIO
from PIL import Image, ImageOps

# --- LBIMG5 encoder/decoder --- #

def encode_lbimg(png_path):
    """Encodes PNG at 100% quality and physically rotates pixels if vertical."""
    with Image.open(png_path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGBA")
        
        output = BytesIO()
        img.save(output, format="PNG", quality=100, optimize=True, icc_profile=None)
        return output.getvalue()

# --- LBIX builder --- #

def save_lbix(output_path, input_img_path, script_text):
    """Encodes the PNG and packs it with the script into a .lbix archive."""
    main_data = encode_lbimg(input_img_path)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("image.lbimg", main_data)
        z.writestr("main.lbscript", script_text)

# --- CLI Entry Point --- #

def main():
    parser = argparse.ArgumentParser(
        prog="lbixsuite",
        description="CLI tool to compile images and LBScripts into .lbix archive containers."
    )
    
    parser.add_argument(
        "-o", "--output", 
        dest="output_lbix", 
        required=True, 
        metavar="<image.lbix>",
        help="Path to the output .lbix file"
    )
    parser.add_argument(
        "-s", "--script", 
        dest="script_file", 
        required=True, 
        metavar="<script.lbscript>",
        help="Path to the LBScript source file"
    )
    parser.add_argument(
        "-i", "--input", 
        dest="input_image", 
        required=True, 
        metavar="<input.png>",
        help="Path to the input PNG image"
    )

    args = parser.parse_args()

    # File validations
    if not os.path.exists(args.input_image):
        print(f"Error: Input image file '{args.input_image}' not found.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.script_file):
        print(f"Error: Script file '{args.script_file}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.script_file, "r", encoding="utf-8") as sf:
            script_text = sf.read()

        save_lbix(args.output_lbix, args.input_image, script_text)
        print(f"Successfully compiled '{args.output_lbix}'.")

    except Exception as e:
        print(f"Failed to build LBIX package: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
