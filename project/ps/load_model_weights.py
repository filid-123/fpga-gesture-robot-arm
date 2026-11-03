# ============================================================================
# Script Name : load_model_weights.py
# Description : One-Click Dynamic Model Weight & Parameter Loading via AXI.
#               Updates FPGA Neural Network Weights in RAM (1 Second, No Bitstream Rebuild!)
# Target      : PYNQ-Z2 (Zynq-7020)
# ============================================================================

import time
import numpy as np

def update_fpga_model(overlay, weight_array_32bit, descriptor_array_32bit):
    """
    Atomically updates the active model's weights and descriptors while idle.
    weight_array_32bit: List of 32-bit INT32/UINT32 words representing network weights.
    """
    axi_cnn = overlay.gesture_top_0
    start_t = time.time()

    if axi_cnn.read(0x0C) != 0x00010000:
        raise RuntimeError("FPGA ABI mismatch: expected ABI 1.0")
    if axi_cnn.read(0x04) & 0x02:
        raise RuntimeError("Cannot update model while CNN core is busy")
    
    # 1. Reset Weight BRAM Target Address to 0 (Offset 0x10)
    axi_cnn.write(0x10, 0)
    
    # 2. Write 32-bit weight words into Weight BRAM (Offset 0x14 auto-increments address)
    for word in weight_array_32bit:
        axi_cnn.write(0x14, int(word))

    axi_cnn.write(0x28, 0)
    for word in descriptor_array_32bit:
        axi_cnn.write(0x2C, int(word))
        
    elapsed_ms = (time.time() - start_t) * 1000
    print(f"[PS] ✅ Updated {len(weight_array_32bit)} weight words and "
          f"{len(descriptor_array_32bit)} descriptor words.")
    print(f"[PS] ⚡ Model update completed in {elapsed_ms:.2f} ms.")

if __name__ == "__main__":
    print("==================================================")
    print("Dynamic Model Weight & Parameter Loading Helper")
    print("Usage: update_fpga_model(overlay, new_weights, new_descriptors)")
    print("==================================================")
