"""Synthetic native .FNT parser and CP949 coverage; run only in Actions."""
from pathlib import Path
import subprocess,tempfile
source=r'''
#include "korean_patch_font.h"
#include <cassert>
#include <iostream>
int main(){
 // New-format metadata, transparent slot and opaque palette-zero outline.
 std::vector<unsigned char> b={0x45,0x33,0x22,0x11,12,12,4,4,0,51,58,0,2,0};
 auto entry=[&](unsigned c){b.push_back(c&255);b.push_back(c>>8);
 b.push_back(255);b.push_back(254);b.push_back(12);};
 entry(0xb0a1);entry(0x8141);
 b.insert(b.end(),{0x60,0x30,0x0c,0x03,0x60,0x30,0x0c,0x03});
 KoreanPatchFont face;assert(face.load(b));assert(face.glyphs.size()==2);
 auto* g=face.get(0x8141);assert(g&&g->x==-1&&g->y==-2&&g->advance==12);
 assert(g->pixels[0]==51&&g->pixels[1]==58);
 assert(g->pixels[4]==255&&g->pixels[6]==0);
 assert(g->left==0&&g->right==3);
 for(size_t n=0;n<b.size();++n){
  std::vector<unsigned char> shortfile(b.begin(),b.begin()+n);
  assert(!face.load(shortfile));
 }
 assert(face.load(b));auto bad=b;bad[19]=bad[14];bad[20]=bad[15];
 assert(!face.load(bad));bad=b;bad[6]=3;assert(!face.load(bad));
 for(int a=0x81;a<=0xfe;++a)for(int c=0;c<256;++c){
  char s[3]={char(a),char(c),0};
  assert(KoreanPatchFont::pair(s,2)==bool(
   (c>=0x41&&c<=0x5a)||(c>=0x61&&c<=0x7a)||(c>=0x81&&c<=0xfe)));
  assert(!KoreanPatchFont::pair(s,1));
 }
 std::cout<<"PASS: native v45 metadata, 2bpp palette, negative bearings, truncations, duplicate codes, CP949 boundaries\n";
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/"native.cc").write_text(source)
 subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined",
 "-I"+str(Path("tools").resolve()),str(p/"native.cc"),"-o",str(p/"native")],check=True)
 subprocess.run([str(p/"native")],check=True)
