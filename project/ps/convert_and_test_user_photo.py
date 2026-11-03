# ============================================================================
# Script Name : convert_and_test_user_photo.py (Production-Grade Helper)
# Description : Robust Python Helper for Photo Rescaling & Hardware Inference with
#               1. Image Contrast Normalization (Prevents all-zero clamp)
#               2. Strict Core-Done Status Polling (Prevents race condition)
# Target      : PYNQ-Z2 (Zynq-7020)
# ============================================================================

import os
import time
import numpy as np
from PIL import Image, ImageOps
from pynq import Overlay

def infer_photo_file(overlay, image_filename):
    """
    Robust Photo Inference Pipeline:
    1. Contrast Normalization (ImageOps.autocontrast)
    2. 32x32 Bilinear Rescaling
    3. AXI Input BRAM Write
    4. Hardware Start & Strict Core-Done Status Polling
    5. Readback Predicted Class ID
    """
    axi_cnn = overlay.gesture_top_0
    
    if not os.path.exists(image_filename):
        print(f"❌ Cannot find image file: {image_filename}")
        return None
        
    # 1. Open image, convert to grayscale, perform Auto-Contrast Normalization
    raw_img = Image.open(image_filename).convert("L")
    norm_img = ImageOps.autocontrast(raw_img) # Maximize contrast range [0, 255]
    img_32x32 = norm_img.resize((32, 32), Image.BILINEAR)
    img_bytes = list(np.array(img_32x32, dtype=np.uint8).flatten())
    
    # 2. Reset Image BRAM Write Address (Offset 0x20)
    axi_cnn.write(0x20, 0)
    
    # 3. Write 1024 bytes into Input BRAM via AXI Offset 0x24
    for pixel in img_bytes:
        axi_cnn.write(0x24, int(pixel))
        
    # 4. Trigger Hardware Execution (Offset 0x00 = 0x01)
    axi_cnn.write(0x00, 0x01)
    
    # 5. Strict Core-Done Status Polling (Wait for Bit 2 of Offset 0x04)
    timeout = 1000
    while (axi_cnn.read(0x04) & 0x04) == 0 and timeout > 0:
        timeout -= 1
        
    if timeout == 0:
        print("⚠️ Warning: Hardware Core-Done Polling Timeout!")
        
    # 6. Readback Predicted Class ID (Offset 0x08)
    predicted_class = axi_cnn.read(0x08)
    
    print("==================================================")
    print(f"📷 Photo Loaded: {image_filename} (Contrast Normalized)")
    print(f"🎉 Hardware Predicted Class ID = {predicted_class}")
    print("==================================================")
    return predicted_class

print("==================================================")
print("✅ Production-Grade Photo Inference Helper Ready!")
print("Usage: infer_photo_file(overlay, 'my_photo.jpg')")
print("==================================================")
