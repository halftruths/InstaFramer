from PIL import Image, ImageOps
import os
from io import BytesIO

# Instagram dimensions (max resolution)
# Square: 1080 x 1080 (1:1)
# Portrait: 1080 x 1350 (4:5)
# Landscape: 1080 x 566 (1.91:1)
IG_WIDTH = 1080
IG_MAX_HEIGHT = 1350

def parse_color(color_str):
    if color_str.startswith('#'):
        return color_str
    # Convert rgb/rgba strings if needed, or simple names
    return color_str

def process_image(
    input_path: str,
    output_path: str = None,
    border_inner_width: int = 0,
    border_inner_color: str = "#ffffff",
    border_outer_width: int = 0,
    border_outer_color: str = "#000000",
    fit_instagram: bool = True,
    aspect_ratio: str = "4:5", # "1:1", "4:5", "1.91:1", or "original"
    preview: bool = False
):
    """
    Process image with borders and Instagram resizing.
    If preview is True, returns a BytesIO object with a JPEG instead of saving.
    """
    try:
        with Image.open(input_path) as img:
            # Convert to RGB to ensure we can save as JPEG safely
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Apply inner border
            if border_inner_width > 0:
                img = ImageOps.expand(img, border=border_inner_width, fill=parse_color(border_inner_color))
            
            # Apply outer border (which acts as a stylistic middle border if fit_instagram is True)
            if border_outer_width > 0:
                img = ImageOps.expand(img, border=border_outer_width, fill=parse_color(border_outer_color))
            
            # Fit to Instagram Canvas
            if fit_instagram and aspect_ratio != "original":
                target_w = IG_WIDTH
                if aspect_ratio == "1:1":
                    target_h = IG_WIDTH
                elif aspect_ratio == "1.91:1":
                    target_h = 566
                else: # Default 4:5
                    target_h = IG_MAX_HEIGHT
                
                # Downsample main image if it's larger than the target canvas
                # We want the image to fit *inside* the canvas without being cropped
                img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
                
                # Create the background canvas (this will act as the final 'outermost' padding to fill IG dimension)
                # Usually we'd use the outer border color, or a specific background color
                canvas = Image.new('RGB', (target_w, target_h), parse_color(border_outer_color))
                
                # Paste the image in the center of the canvas
                paste_x = (target_w - img.width) // 2
                paste_y = (target_h - img.height) // 2
                canvas.paste(img, (paste_x, paste_y))
                
                img = canvas
            else:
                # Still downsample to max width 1080 to save space, keeping original aspect ratio
                if img.width > IG_WIDTH:
                    ratio = IG_WIDTH / img.width
                    new_h = int(img.height * ratio)
                    img = img.resize((IG_WIDTH, new_h), Image.Resampling.LANCZOS)

            
            if preview:
                # Return bytes for API
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=85)
                buf.seek(0)
                return buf
            else:
                # Save to disk
                if not output_path:
                    base, ext = os.path.splitext(input_path)
                    output_path = f"{base}_framed.jpg"
                img.save(output_path, format="JPEG", quality=95)
                return output_path
                
    except Exception as e:
        print(f"Error processing image {input_path}: {e}")
        return None

def batch_process(
    input_folder: str,
    output_folder: str,
    **kwargs
):
    """
    Process all supported images in a folder.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    supported_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')
    processed_files = []
    
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(supported_exts):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, f"IG_{filename}")
            
            # Force output extension to jpg
            base, _ = os.path.splitext(output_path)
            output_path = f"{base}.jpg"
            
            res = process_image(input_path, output_path=output_path, preview=False, **kwargs)
            if res:
                processed_files.append(res)
                
    return processed_files
