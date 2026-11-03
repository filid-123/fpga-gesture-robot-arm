"""Append metric glyphs without changing the frozen v012 Chinese glyphs."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=ROOT/'native_motion/rtl/hdmi/mode_a_font.mem';words=p.read_text('ascii').splitlines()
 font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',14)
 # Existing glyphs 0..86 stay byte-for-byte unchanged.
 for index,char in enumerate('0123456789LCAm s',87):
  im=Image.new('1',(16,16));d=ImageDraw.Draw(im);box=d.textbbox((0,0),char,font=font)
  d.text(((16-(box[2]-box[0]))//2-box[0],(16-(box[3]-box[1]))//2-box[1]),char,font=font,fill=1)
  for y in range(16):words[index*16+y]=f'{sum(int(im.getpixel((x,y))!=0)<<(15-x) for x in range(16)):04x}'
 p.write_text('\n'.join(words)+'\n','ascii')
if __name__=='__main__':main()
