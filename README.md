# 🎨 Logo Processor V2

A powerful Python-based tool built with Gradio for professional logo preparation. This tool automates background removal, refined-edge processing, and multi-format resizing for web and social media.

## ✨ Features

- **Interactive Workflow**: Refine your logo in real-time before exporting.
- **Smart Background Removal**: Powered by `rembg` (U2-Net).
- **Refined Edges**: Optional Alpha Matting to eliminate fringes.
- **Internal Color Removal**: Selective transparency for internal areas with a sensitivity slider.
- **Backdrop Proofing**: Switch between Black, White, and Magenta backgrounds to verify transparency.
- **Batch Export**: Generates 11 standard sizes in both **PNG** and **lossless WebP**.
- **Automatic Organization**: Saves originals to `input/` and final assets to `output/{ProjectName}/`.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the App
```bash
python app.py
```

## 📂 Folder Structure
- `input/`: Archive of your original uploaded logos.
- `output/`: Processed folders for each project, including a convenient ZIP export.

---
Built with Python, Gradio, and PIL.
