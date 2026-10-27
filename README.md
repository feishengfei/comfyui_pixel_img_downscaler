# comfyui‑pixel‑img‑downscaler
ComfyUI custom node for pixel‑style image downscaling & color‑quantization, reduce image file size.

## Features
- Two nodes: single image processing / batch folder processing
- Image downscale, max size 256×256
- Resample filter: `NEAREST` / `BILINEAR` / `BICUBIC` / `LANCZOS`
- Color modes: `rgba`, `rgb`, `grayscale`, `indexed_palette`
- Load external `.gpl` palette exported from Aseprite(Sprite → Save Palette → GIMP Palette *.gpl)
- PNG forced output, optional extra BMP export
- PNG compression level configurable(0‑9, default=4, same as ComfyUI SaveImage)
- Single‑image node supports ComfyUI frontend image preview via `ui` return
- Batch node with `trigger` input for disk‑write sequencing lock

> Limitations
> 1. BMP does **not support indexed‑P‑mode and alpha channel**. If input is indexed‑palette, BMP output will auto downgrade to RGB and lose palette/transparency.
> 2. Only read `.gpl` palette format. **No support for `.ase` / `.aseprite` binary format**.
> 3. Front‑end preview works best under ComfyUI `output/` directory; absolute external paths may fail browser cross‑domain preview, but disk files generate normally.

## Install
```bash
git clone https://github.com/feishengfei/comfyui_pixel_img_downscaler
cd comfyui_pixel_img_downscaler
pip install -e .
```
Restart ComfyUI. Nodes appear under category `PixelTools`.

## Node List
### Pixel‑Downscale‑Quantize 单图
Inputs
- `image`: IMAGE tensor from LoadImage
- `resize_width` / `resize_height`: 8‑256
- `resize_filter`: resample algorithm, pixel‑art recommend `NEAREST`
- `color_mode`: rgba / rgb / grayscale / indexed_palette
- `num_index_colors`: color count for quantize(2‑256, only indexed_palette)
- `palette_gpl_path`: absolute path to Aseprite exported `.gpl` palette file, empty for auto‑quantize
- `png_compression_level`: 0‑9, default=4
- `enable_bmp`: bool, extra output bmp file
- `output_dir`: absolute output directory
- `output_filename`: output base filename without extension

Outputs
- `output_png_path`: absolute path of saved png file
- UI preview: ComfyUI frontend preview rendered image

### Pixel‑Downscale‑Quantize 批量目录
Inputs
- `source_dir`: absolute source folder with png sequence
- `file_prefix`: filename prefix, match pattern `prefix_0000x_.png`
- `appendix`: fixed `png`
- `resize_width` / `resize_height`: 8‑256
- `resize_filter`: resample algorithm
- `color_mode`: rgba / rgb / grayscale / indexed_palette
- `num_index_colors`: color count for quantize
- `palette_gpl_path`: absolute `.gpl` palette file path
- `png_compression_level`: 0‑9
- `enable_bmp`: bool
- `output_dir`: absolute output directory
- `trigger`: trigger port for sequential disk processing

Outputs
- No data output, only write files to disk.

## Aseprite Palette Usage
1. Open your palette inside Aseprite
2. Menu: `Sprite` → `Save Palette`
3. Select format: **GIMP Palette(*.gpl)**
4. Copy absolute file path into node input `palette_gpl_path`. Leave empty for auto‑color quantization.

## Dependencies
- pillow >= 10.0.0
- comfyui environment (python >=3.10)

## License
MIT
