# app/barcode.py
import io
import os
from typing import Optional
from PIL import Image
import barcode
from barcode.writer import ImageWriter
import qrcode

try:
    from pyzbar.pyzbar import decode as zbar_decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False


def generate_barcode_image(data: str, barcode_type: str = "code128") -> bytes:
    """Generate a barcode image (PNG bytes)"""
    barcode_class = barcode.get_barcode_class(barcode_type)
    buffer = io.BytesIO()
    code = barcode_class(data, writer=ImageWriter())
    code.write(buffer)
    buffer.seek(0)
    return buffer.read()


def generate_qr_code(data: str, size: int = 10) -> bytes:
    """Generate QR code image (PNG bytes)"""
    qr = qrcode.QRCode(version=1, box_size=size, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()


def decode_barcode_from_image(image_bytes: bytes) -> Optional[str]:
    """Decode a barcode from an uploaded image"""
    if not PYZBAR_AVAILABLE:
        raise RuntimeError("pyzbar not installed. Install with: pip install pyzbar")
    
    image = Image.open(io.BytesIO(image_bytes))
    barcodes = zbar_decode(image)
    if barcodes:
        return barcodes[0].data.decode("utf-8")
    return None


def save_barcode_file(data: str, filepath: str, barcode_type: str = "code128") -> str:
    """Save barcode to disk and return path"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    image_bytes = generate_barcode_image(data, barcode_type)
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return filepath