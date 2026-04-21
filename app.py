import os
import io
import zipfile
import shutil
from datetime import datetime
import gradio as gr
from rembg import remove
from PIL import Image, ImageColor
import numpy as np

# --- Constants ---
STANDARD_SIZES = {
    "favicon_16x16": (16, 16),
    "favicon_32x32": (32, 32),
    "favicon_48x48": (48, 48),
    "website_vertical_160x160": (160, 160),
    "website_horizontal_250x150": (250, 150),
    "website_horizontal_350x75": (350, 75),
    "website_horizontal_400x100": (400, 100),
    "social_profile_small_200x200": (200, 200),
    "social_profile_standard_400x400": (400, 400),
    "social_profile_large_800x800": (800, 800),
    "instagram_post_square_1080x1080": (1080, 1080),
}

# --- Utility Functions ---

def resize_and_pad(img, target_size):
    tw, th = target_size
    img_ratio = img.width / img.height
    target_ratio = tw / th

    if img_ratio > target_ratio:
        new_width = tw
        new_height = int(tw / img_ratio)
    else:
        new_height = th
        new_width = int(th * img_ratio)

    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    new_img = Image.new("RGBA", target_size, (0, 0, 0, 0))
    paste_x = (tw - new_width) // 2
    paste_y = (th - new_height) // 2
    new_img.paste(resized_img, (paste_x, paste_y))
    return new_img

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def apply_color_to_alpha(img, target_hex, sensitivity):
    """
    Converts pixels matching target_hex to transparent within a sensitivity threshold.
    """
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    data = np.array(img)
    target_rgb = hex_to_rgb(target_hex)
    
    # Calculate Euclidean distance in RGB space
    rgb_data = data[:, :, :3]
    diff = rgb_data - target_rgb
    dist = np.sqrt(np.sum(diff**2, axis=2))
    
    # Sensitivity range 0-255 (Euclidean max is ~441, but 0-255 is more intuitive)
    # We map 0-100% sensitivity to a range
    threshold = (sensitivity / 100.0) * 441.67 
    
    mask = dist <= threshold
    data[mask, 3] = 0 # Set alpha to 0
    
    return Image.fromarray(data)

def auto_detect_bg_color(image):
    if image is None: return "#FFFFFF"
    # Sample top-left pixel
    rgb_img = image.convert("RGB")
    pixel = rgb_img.getpixel((0, 0))
    return '#{:02x}{:02x}{:02x}'.format(*pixel)

def process_preview(input_image, use_matting, remove_internal, target_color, sensitivity, backdrop_color):
    if input_image is None:
        return None, "Please upload an image."
    
    try:
        # Step 1: Rembg (Base removal)
        # Note: We trigger rembg again if settings change, but ideally we'd cache the raw mask.
        # For simplicity in this script, we run it.
        params = {}
        if use_matting:
            params = {
                "alpha_matting": True,
                "alpha_matting_foreground_threshold": 240,
                "alpha_matting_background_threshold": 10,
                "alpha_matting_erode_size": 10
            }
        
        result = remove(input_image, **params)
        
        # Step 2: Internal Color Removal
        if remove_internal:
            result = apply_color_to_alpha(result, target_color, sensitivity)
            
        # Step 3: Cropping for preview (so the logo is centered and clean)
        bbox = result.getbbox()
        final_logo = result.crop(bbox) if bbox else result
        
        # Step 4: Visualization Backdrop
        if backdrop_color == "Transparent":
            preview_display = final_logo
        else:
            # Create a solid background image
            bg_color_map = {
                "Black": (0, 0, 0, 255),
                "White": (255, 255, 255, 255),
                "Magenta": (255, 0, 255, 255),
                "Gray": (128, 128, 128, 255)
            }
            bg_fill = bg_color_map.get(backdrop_color, (0, 0, 0, 0))
            canvas = Image.new("RGBA", final_logo.size, bg_fill)
            canvas.alpha_composite(final_logo)
            preview_display = canvas
            
        return preview_display, final_logo, "Preview updated."

    except Exception as e:
        return None, None, f"Error: {str(e)}"

def generate_final_assets(final_logo, project_name, progress=gr.Progress()):
    if final_logo is None:
        raise gr.Error("Please refine your logo and generate a preview first.")
    
    if not project_name or project_name.strip() == "":
        project_name = f"logo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    base_name = project_name.strip().replace(" ", "_")
    
    try:
        os.makedirs("input", exist_ok=True)
        os.makedirs("output", exist_ok=True)
        
        project_output_dir = os.path.join("output", base_name)
        if os.path.exists(project_output_dir):
            shutil.rmtree(project_output_dir)
        os.makedirs(project_output_dir)
        
        # Save original cropped versions
        progress(0.1, desc="Saving master versions...")
        orig_png_name = f"{base_name} - original_transparent.png"
        orig_webp_name = f"{base_name} - original_transparent.webp"
        final_logo.save(os.path.join(project_output_dir, orig_png_name), format="PNG")
        final_logo.save(os.path.join(project_output_dir, orig_webp_name), format="WebP", lossless=True)
        
        # Iterative Resizing
        total_sizes = len(STANDARD_SIZES)
        for i, (size_name, size) in enumerate(STANDARD_SIZES.items()):
            progress((i / total_sizes) * 0.8 + 0.1, desc=f"Resizing {size_name}...")
            resized = resize_and_pad(final_logo, size)
            resized.save(os.path.join(project_output_dir, f"{base_name} - {size_name}.png"), format="PNG")
            resized.save(os.path.join(project_output_dir, f"{base_name} - {size_name}.webp"), format="WebP", lossless=True)
            
        # ZIP
        progress(0.95, desc="Zipping assets...")
        zip_path = os.path.join("output", f"{base_name}_assets.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(project_output_dir):
                for file in files:
                    zipf.write(os.path.join(root, file), file)
        
        return zip_path, f"Done! Files saved to: {os.path.abspath(project_output_dir)}"
    except Exception as e:
        raise gr.Error(f"Export failed: {str(e)}")

# --- UI ---

with gr.Blocks(title="Logo Processor V2") as app:
    # State to hold the binary logo across Stage 1 and Stage 2
    final_logo_state = gr.State()
    
    gr.Markdown("# 🎨 Logo Processor (Interactive V2)")
    
    with gr.Row():
        # LEFT: Inputs & Controls
        with gr.Column(scale=1):
            gr.Markdown("### 1. Upload & Settings")
            input_img = gr.Image(type="pil", label="Upload Source Image")
            project_name = gr.Textbox(label="Project Name", placeholder="MyBrandLogo")
            
            with gr.Group():
                gr.Markdown("**Background Removal Options**")
                use_matting = gr.Checkbox(label="Refine Edges (Alpha Matting)", value=True)
                remove_internal = gr.Checkbox(label="Remove Matching Internal Colors", value=False)
                
                with gr.Row():
                    target_color = gr.ColorPicker(label="Color to Remove", value="#FFFFFF")
                    detect_btn = gr.Button("🔍 Auto-detect", size="sm")
                
                sensitivity = gr.Slider(label="Removal Sensitivity", minimum=0, maximum=100, value=10)
            
            preview_btn = gr.Button("🔄 Update Preview", variant="primary")
            
        # CENTER: Interactive Preview
        with gr.Column(scale=2):
            gr.Markdown("### 2. Interactive Preview")
            with gr.Row():
                backdrop = gr.Dropdown(
                    label="Preview Canvas Color (Visualization)", 
                    choices=["Transparent", "Black", "White", "Magenta", "Gray"], 
                    value="Transparent"
                )
            
            preview_display = gr.Image(type="pil", label="Current Result", elem_id="preview_pane")
            status_text = gr.Markdown("*Ready*")

        # RIGHT: Final Export
        with gr.Column(scale=1):
            gr.Markdown("### 3. Final Export")
            export_btn = gr.Button("📦 Generate All Sizes", variant="secondary")
            output_file = gr.File(label="Download Assets (.zip)")
            final_status = gr.Textbox(label="Export Status", interactive=False)

    # --- Interactions ---
    
    detect_btn.click(
        fn=auto_detect_bg_color,
        inputs=input_img,
        outputs=target_color
    )
    
    preview_btn.click(
        fn=process_preview,
        inputs=[input_img, use_matting, remove_internal, target_color, sensitivity, backdrop],
        outputs=[preview_display, final_logo_state, status_text]
    )
    
    # Auto-update preview when backdrop changes (if we already have a result)
    backdrop.change(
        fn=process_preview,
        inputs=[input_img, use_matting, remove_internal, target_color, sensitivity, backdrop],
        outputs=[preview_display, final_logo_state, status_text]
    )

    export_btn.click(
        fn=generate_final_assets,
        inputs=[final_logo_state, project_name],
        outputs=[output_file, final_status]
    )

if __name__ == "__main__":
    app.launch(theme=gr.themes.Soft())
