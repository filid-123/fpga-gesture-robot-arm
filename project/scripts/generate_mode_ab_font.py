"""Append AB labels, preserving all existing message and font indices."""
from pathlib import Path
import re
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'native_motion/rtl/hdmi';path=folder/'mode_a_ui_text.vh'
    data=path.read_bytes();text=data.decode('utf-8')
    if "6'd46:" in text:
        print('AB labels already present');return
    glyphs={' ':0}
    for word,message in re.findall(r"line=256'h([0-9a-f]+); // ([^\r\n]*)",text):
        for char,code in zip(message,bytes.fromhex(word)):
            if char in glyphs:assert glyphs[char]==code
            glyphs[char]=code
    index=max(102,*glyphs.values())+1
    font_path=folder/'mode_a_font.mem';words=font_path.read_text('ascii').splitlines()
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',14);extra=[]
    for number,message in enumerate(('B 模式','抓取物品','补回原位'),46):
        codes=[]
        for char in message:
            if char not in glyphs:
                assert index<128;glyphs[char]=index;index+=1
                bitmap=Image.new('1',(16,16));draw=ImageDraw.Draw(bitmap);box=draw.textbbox((0,0),char,font=font)
                draw.text(((16-(box[2]-box[0]))//2-box[0],(16-(box[3]-box[1]))//2-box[1]),char,font=font,fill=1)
                for y in range(16):words[glyphs[char]*16+y]=f'{sum(int(bitmap.getpixel((x,y))!=0)<<(15-x) for x in range(16)):04x}'
            codes.append(glyphs[char])
        extra.append(f" 6'd{number}:line=256'h{bytes(codes+[0]*(32-len(codes))).hex()}; // {message}")
    newline='\r\n' if b'\r\n' in data else '\n'
    path.write_bytes(text.replace(' default:line=0;',newline.join(extra)+newline+' default:line=0;').encode('utf-8'))
    font_path.write_bytes(('\n'.join(words)+'\n').encode('ascii'))
    print('AB labels appended; glyph slots used:',index)


if __name__=='__main__':main()
