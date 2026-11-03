"""Append restock labels; preserve every existing glyph and message."""
from pathlib import Path
import re
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
 h=ROOT/'native_motion/rtl/hdmi';p=h/'mode_a_ui_text.vh';text=p.read_text('utf-8')
 if "6'd38:" in text:
  print('Restock labels already present; no files changed');return
 glyphs={' ':0}
 for word,comment in re.findall(r"line=256'h([0-9a-f]+); // (.*)",text):
  for c,code in zip(comment,bytes.fromhex(word)):
   if c in glyphs:assert glyphs[c]==code,(c,code,glyphs[c])
   glyphs[c]=code
 font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',14)
 fp=h/'mode_a_font.mem';words=fp.read_text('ascii').splitlines();lines=[];new=103
 for index,message in enumerate(('补回红槽','补回黄槽','补回蓝槽','补料中','取料中','放回中','返回中','退回料点'),38):
  codes=[]
  for c in message:
   if c not in glyphs:
    glyphs[c]=new;new+=1;im=Image.new('1',(16,16));draw=ImageDraw.Draw(im);box=draw.textbbox((0,0),c,font=font)
    draw.text(((16-(box[2]-box[0]))//2-box[0],(16-(box[3]-box[1]))//2-box[1]),c,font=font,fill=1)
    for y in range(16):words[glyphs[c]*16+y]=f'{sum(int(im.getpixel((x,y))!=0)<<(15-x) for x in range(16)):04x}'
   codes.append(glyphs[c])
  word=bytes(codes+[0]*(32-len(codes))).hex();lines.append(f" 6'd{index}:line=256'h{word}; // {message}")
 assert new<=128
 p.write_text(text.replace(' default:line=0;', '\n'.join(lines)+'\n default:line=0;'),'utf-8')
 fp.write_text('\n'.join(words)+'\n','ascii');print('Appended labels; used glyphs',new)
if __name__=='__main__':main()
