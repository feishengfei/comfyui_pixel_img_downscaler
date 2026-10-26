import os
import re
import numpy as np
from pathlib import Path
from inspect import cleandoc
from PIL import Image

def parse_gpl_palette(gpl_file_path: str):
    """
    读取Aseprite导出的 .gpl (GIMP Palette)调色板文件
    返回pillow可使用的一维palette列表 [r,g,b,r,g,b...]，最多256色
    注意：只解析RGB，不解析alpha；空路径返回None
    """
    p = Path(gpl_file_path).absolute()
    if not p.exists() or not p.is_file():
        return None
    palette = []
    with open(p, "r", encoding="utf‑8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("GIMP Palette"):
                continue
            parts = line.split()
            if len(parts) >=3:
                try:
                    r = int(parts[0])
                    g = int(parts[1])
                    b = int(parts[2])
                    palette.extend([r,g,b])
                except ValueError:
                    continue
    # 补齐到256色长度（pillow P模式要求768字节 =256*3）
    while len(palette) < 768:
        palette.extend([0,0,0])
    return palette


def process_one_pil_image(pil_img: Image.Image,
                           resize_width:int,
                           resize_height:int,
                           resize_filter:str,
                           color_mode:str,
                           num_index_colors:int,
                           palette_gpl:str):
    """
    公共处理逻辑：缩放 + 色彩模式转换
    resize_filter: NEAREST / BILINEAR / BICUBIC / LANCZOS
    color_mode: rgba / rgb / grayscale / indexed_palette
    palette_gpl: gpl调色板绝对路径，空字符串使用自适应量化
    返回处理完成PIL Image对象
    """
    filter_map = {
        "NEAREST": Image.Resampling.NEAREST,
        "BILINEAR": Image.Resampling.BILINEAR,
        "BICUBIC": Image.Resampling.BICUBIC,
        "LANCZOS": Image.Resampling.LANCZOS
    }
    pil_img = pil_img.resize((resize_width, resize_height), resample=filter_map[resize_filter])

    if color_mode == "rgba":
        pil_img = pil_img.convert("RGBA")
    elif color_mode == "rgb":
        pil_img = pil_img.convert("RGB")
    elif color_mode == "grayscale":
        pil_img = pil_img.convert("L")
    elif color_mode == "indexed_palette":
        gpl_data = parse_gpl_palette(palette_gpl) if palette_gpl.strip() else None
        if gpl_data is not None:
            # 使用外部GPL调色板
            pal_img = Image.new("P", (1,1))
            pal_img.putpalette(gpl_data)
            pil_img = pil_img.quantize(palette=pal_img, colors=num_index_colors)
        else:
            # 图片自身自适应调色板
            pil_img = pil_img.quantize(colors=num_index_colors)
    return pil_img


def save_multi_formats(pil_img:Image.Image, out_base:Path, enable_bmp:bool, png_compression_level:int):
    """
    PNG强制总是输出；可选额外输出BMP
    注意：P(indexed)模式保存BMP会自动降级RGB，丢失调色板与透明
    :param png_compression_level: 0‑9 png压缩等级，4为ComfyUI默认
    返回：png输出完整路径
    """
    png_path = out_base.with_suffix(".png")
    pil_img.save(png_path, format="PNG", compress_level=png_compression_level)
    print(f"💾 Saved png: {png_path} | compression_level={png_compression_level}")

    if enable_bmp:
        bmp_path = out_base.with_suffix(".bmp")
        if pil_img.mode == "P":
            # indexed模式BMP不支持，降级RGB
            bmp_img = pil_img.convert("RGB")
            bmp_img.save(bmp_path, format="BMP")
            print(f"💾 Saved bmp (P‑mode downgraded to RGB): {bmp_path}")
        else:
            pil_img.save(bmp_path, format="BMP")
            print(f"💾 Saved bmp: {bmp_path}")
    return str(png_path)


class ImageDownscaleQuantizeSingle:
    """
    单图下采样&色彩量化节点：接收ComfyUI IMAGE张量
    - 缩放尺寸最大256px
    - 支持rgba/rgb/grayscale/indexed_palette
    - 可加载Aseprite导出 .gpl调色板
    - PNG强制输出；可额外输出BMP；支持png压缩等级
    - 实现ui返回结构，ComfyUI前端可预览生成图片
    注意：
      1. indexed(P模式)仅PNG完整保存调色板+透明；BMP会降级丢失调色板与透明；
      2. Aseprite: Sprite‑>Save Palette导出 .gpl(GIMP Palette)，不支持ase/act；
      3. 像素画优先resize_filter=NEAREST；照片使用LANCZOS
      4. png_compression_level: 0无压缩，9最大压缩，ComfyUI原生SaveImage默认=4
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip":"来自Load Image，取batch第0张图片"}),
                "resize_width": ("INT", {
                    "default":128, "min":8, "max":256, "step":1, "display":"number",
                    "tooltip":"输出图片宽度，上限256"
                }),
                "resize_height": ("INT", {
                    "default":128, "min":8, "max":256, "step":1, "display":"number",
                    "tooltip":"输出图片高度，上限256"
                }),
                "resize_filter": (["NEAREST","BILINEAR","BICUBIC","LANCZOS"],
                                  {"default":"NEAREST","tooltip":"像素画选NEAREST；照片选LANCZOS"}),
                "color_mode": (["rgba","rgb","grayscale","indexed_palette"],
                               {"default":"rgba","tooltip":"色彩模式；indexed_palette为调色板模式"}),
                "num_index_colors": ("INT", {
                    "default":16, "min":2, "max":256, "step":1, "display":"number",
                    "tooltip":"仅indexed_palette生效，自适应调色板颜色数量"
                }),
                "palette_gpl_path": ("STRING", {
                    "default":"", "multiline":False,
                    "tooltip":"Aseprite导出gpl调色板绝对路径；留空使用图片自适应quantize"
                }),
            },
            "optional":{
                "png_compression_level": ("INT", {
                    "default":4, "min":0, "max":9, "step":1, "display":"number",
                    "tooltip":"PNG压缩等级，0=无压缩，9=最高压缩；ComfyUI SaveImage默认4"
                }),
                "enable_bmp": ("BOOLEAN", {"default":False, "tooltip":"额外输出bmp文件；PNG总是强制输出"}),
                "output_dir": ("STRING", {"default":"", "multiline":False, "tooltip":"输出目录绝对路径"}),
                "output_filename": ("STRING", {"default":"out", "multiline":False, "tooltip":"输出文件名，不带后缀"}),
            }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_png_path",)
    FUNCTION = "run"
    CATEGORY = "PixelTools"
    OUTPUT_NODE = True
    DESCRIPTION = cleandoc(__doc__)

    async def run(self,
                  image,
                  resize_width,
                  resize_height,
                  resize_filter,
                  color_mode,
                  num_index_colors,
                  palette_gpl_path,
                  png_compression_level=4,
                  enable_bmp=False,
                  output_dir="",
                  output_filename="out"):

        out_dir = Path(output_dir).absolute()
        os.makedirs(out_dir, exist_ok=True)
        out_base = out_dir / output_filename

        # ComfyUI IMAGE tensor [B,H,W,C] float 0‑1 → PIL
        img_np = (image[0].cpu().numpy() * 255).astype(np.uint8)
        pil_img = Image.fromarray(img_np)

        processed = process_one_pil_image(
            pil_img,
            resize_width=resize_width,
            resize_height=resize_height,
            resize_filter=resize_filter,
            color_mode=color_mode,
            num_index_colors=num_index_colors,
            palette_gpl=palette_gpl_path
        )
        png_path = save_multi_formats(processed, out_base, enable_bmp, png_compression_level)

        # --- 构造ComfyUI前端ui预览数据，对齐SaveImage格式
        png_p = Path(png_path)
        subfolder = str(png_p.parent.relative_to(Path(os.getcwd())))
        ui_result = {
            "images": [
                {
                    "filename": png_p.name,
                    "subfolder": subfolder,
                    "type": "output"
                }
            ]
        }
        return {"ui": ui_result, "result": (png_path,)}


class ImageDownscaleQuantizeBatchFolder:
    """
    批量磁盘目录处理节点，不接收IMAGE张量，读取本地png序列图片
    文件匹配范式： {file_prefix}_0000x_.png  例如 img_00001_.png
    trigger时序端口，等待上游磁盘写入完成；仅落盘无数据输出，无UI预览
    注意：
      1. indexed(P模式)仅PNG完整保存调色板+透明；BMP会降级丢失调色板与透明；
      2. Aseprite: Sprite‑>Save Palette导出 .gpl(GIMP Palette)，不支持ase/act；
      3. 像素画优先resize_filter=NEAREST；照片使用LANCZOS
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "source_dir": ("STRING", {"default":"","multiline":False,"tooltip":"源图片目录绝对路径，只读取png文件"}),
                "file_prefix": ("STRING", {"default":"img","tooltip":"匹配 img_00001_.png 这类命名"}),
                "appendix": ("STRING", {"default":"png","tooltip":"源文件后缀，固定png，不要修改"}),
                "resize_width": ("INT", {
                    "default":128, "min":8, "max":256, "step":1, "display":"number",
                    "tooltip":"输出图片宽度，上限256"
                }),
                "resize_height": ("INT", {
                    "default":128, "min":8, "max":256, "step":1, "display":"number",
                    "tooltip":"输出图片高度，上限256"
                }),
                "resize_filter": (["NEAREST","BILINEAR","BICUBIC","LANCZOS"],
                                  {"default":"NEAREST","tooltip":"像素画选NEAREST；照片选LANCZOS"}),
                "color_mode": (["rgba","rgb","grayscale","indexed_palette"],
                               {"default":"rgba","tooltip":"色彩模式；indexed_palette为调色板模式"}),
                "num_index_colors": ("INT", {
                    "default":16, "min":2, "max":256, "step":1, "display":"number",
                    "tooltip":"仅indexed_palette生效，自适应调色板颜色数量"
                }),
                "palette_gpl_path": ("STRING", {
                    "default":"", "multiline":False,
                    "tooltip":"Aseprite导出gpl调色板绝对路径；留空使用图片自适应quantize"
                }),
            },
            "optional":{
                "png_compression_level": ("INT", {
                    "default":4, "min":0, "max":9, "step":1, "display":"number",
                    "tooltip":"PNG压缩等级，0=无压缩，9=最高压缩；ComfyUI SaveImage默认4"
                }),
                "enable_bmp": ("BOOLEAN", {"default":False, "tooltip":"额外输出bmp文件；PNG总是强制输出"}),
                "output_dir": ("STRING", {"default":"","multiline":False, "tooltip":"输出目录绝对路径"}),
                "trigger": ("*", {"tooltip":"时序触发端口，等待上游磁盘写入完成再执行处理"}),
            }
        }
    RETURN_TYPES = ()
    FUNCTION = "run"
    CATEGORY = "PixelTools"
    OUTPUT_NODE = True
    DESCRIPTION = cleandoc(__doc__)

    async def run(self,
                  source_dir,
                  file_prefix,
                  appendix,
                  resize_width,
                  resize_height,
                  resize_filter,
                  color_mode,
                  num_index_colors,
                  palette_gpl_path,
                  png_compression_level=4,
                  enable_bmp=False,
                  output_dir="",
                  trigger=None):

        src_dir = Path(source_dir).absolute()
        if not src_dir.is_dir():
            raise NotADirectoryError(f"源目录不存在：{src_dir}")
        out_dir = Path(output_dir).absolute()
        os.makedirs(out_dir, exist_ok=True)

        # 匹配范式 img_00001_.png
        escaped_pre = re.escape(file_prefix)
        pat = re.compile(rf"^{escaped_pre}_(\d+)_\.{re.escape(appendix)}$", re.IGNORECASE)
        matched = []
        for fname in os.listdir(src_dir):
            m = pat.match(fname)
            if m:
                seq = int(m.group(1))
                matched.append((seq, fname))
        if len(matched) == 0:
            raise FileNotFoundError(f"目录 {src_dir} 未找到 {file_prefix}_xxxx_.{appendix}")
        matched.sort(key=lambda x:x[0])
        print(f"\n==== ImageDownscaleQuantizeBatchFolder 共找到 {len(matched)} 张待处理图片 ====")

        for seq, fname in matched:
            src_file = src_dir / fname
            pil_img = Image.open(src_file).convert("RGBA")
            processed = process_one_pil_image(
                pil_img,
                resize_width=resize_width,
                resize_height=resize_height,
                resize_filter=resize_filter,
                color_mode=color_mode,
                num_index_colors=num_index_colors,
                palette_gpl=palette_gpl_path
            )
            # 沿用原文件名，不带后缀
            base_name = Path(fname).stem
            out_base = out_dir / base_name
            save_multi_formats(processed, out_base, enable_bmp, png_compression_level)
            print(f"  > processed: {fname}")

        print(f"==== ImageDownscaleQuantizeBatchFolder 全部处理完成 ====\n")
        return {}


NODE_CLASS_MAPPINGS = {
    "ImageDownscaleQuantizeSingle": ImageDownscaleQuantizeSingle,
    "ImageDownscaleQuantizeBatchFolder": ImageDownscaleQuantizeBatchFolder
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageDownscaleQuantizeSingle": "Pixel‑Downscale‑Quantize 单图",
    "ImageDownscaleQuantizeBatchFolder": "Pixel‑Downscale‑Quantize 批量目录"
}
