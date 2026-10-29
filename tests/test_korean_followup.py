"""Remote regression tests for reviewed localization and bounded rendering."""
from pathlib import Path
import re,subprocess,tempfile
def method(s,start):
 a=s.index(start);b=s.index("{",a);depth=0
 for i in range(b,len(s)):
  if s[i]=="{":depth+=1
  elif s[i]=="}":
   depth-=1
   if not depth:return s[a:i+1]
 raise RuntimeError(start)
font=Path("upstream/shapes/font.cc").read_text()
center=method(font,"int Font::center_text(")
code=r'''
#include <algorithm>
#include <cassert>
#include <cstring>
#include <memory>
#include <string>
#include <vector>
#include "korean_runtime_text.h"
struct Image_buffer8{};
struct Font{
 bool native_face=true;int lastx=-999,native_calls=0,legacy_calls=0;
 void native_bounds(const char*,int&l,int&t,int&w,int&h){l=3;t=-2;w=21;h=10;}
 int native_draw(Image_buffer8*,const char*,int,int x,int,unsigned char*,int=0){lastx=x;++native_calls;return 24;}
 int get_text_width(const char*){return 24;}
 int draw_text(Image_buffer8*,int x,int,const char*,unsigned char*){lastx=x;++legacy_calls;return 24;}
 int center_text(Image_buffer8*,int,int,const char*,unsigned char*);
};
'''+center+r'''
int width(const std::string&s){
 int w=0;for(size_t i=0;i<s.size();){size_t n=korean_text_pair(s.data()+i,s.size()-i)?2:1;i+=n;w+=n==2?10:6;}
 return w;
}
int main(){
 Image_buffer8 image;Font f;
 assert(f.center_text(&image,100,20,"abc",nullptr)==24);
 assert(f.lastx==87&&f.native_calls==1&&f.legacy_calls==0);
 f.native_face=false;f.center_text(&image,100,20,"abc",nullptr);
 assert(f.lastx==88&&f.native_calls==1&&f.legacy_calls==1);
 std::string cp;for(int i=0;i<12;++i)cp+="\xb0\xa1";
 for(const auto& title:std::vector<std::string>{cp,"ULTIMA VII PART 2 "+cp+"\n"+cp,"Mod with a very long title and words"}){
  auto wrapped=korean_wrap_columns(title,110,width);
  for(size_t start=0;start<wrapped.size();){
   size_t end=wrapped.find('\n',start);
   auto row=wrapped.substr(start,end==std::string::npos?end:end-start);
   assert(width(row)<=110);
   for(size_t i=0;i<row.size();){size_t n=korean_text_pair(row.data()+i,row.size()-i)?2:1;
    if(static_cast<unsigned char>(row[i])>=0x81)assert(n==2);
    i+=n;
   }
   if(end==std::string::npos)break;start=end+1;
  }
 }
 for(int sw:{30,92,120})for(int sh:{8,79,96,160,500}){
  std::vector<unsigned char> src(size_t(sw)*sh,255);
  src[0]=0;src.back()=0;
  auto fit=korean_fit_pixels(src,sw,sh,92,79);
  assert(fit.width>0&&fit.width<=92&&fit.height>0&&fit.height<=79);
  assert(fit.pixels.front()==0&&fit.pixels.back()==0);
  assert(fit.pixels.size()==size_t(fit.width)*fit.height);
 }
 assert(korean_fit_pixels({},0,0,92,79).pixels.empty());
}
'''
with tempfile.TemporaryDirectory() as folder:
 cpp=Path(folder)/"followup.cpp";binary=Path(folder)/"followup";cpp.write_text(code)
 subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined","-fno-omit-frame-pointer",
  "-Iupstream/shapes",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
print("PASS: native center dispatch, CP949-safe column wrapping, bounded raster fitting")

save=Path("upstream/gumps/Newfile_gump.cc").read_text()
assert re.search(r'Newfile_gump::infoh\s*=\s*79;',save)
assert save.count('paint_save_information(info, x + infox, y + infoy, infow, infoh);')==2
assert '"%s: %04i-%02i-%02i\\n"' in save
assert 'Strings::ordinal_numeral_suffix(details->real_day)' not in save
assert 'details->real_month, details->real_day, Strings::Time()' in save
assert 'target->set_clip(r.x,r.y,r.w,r.h);' in save

# Compile and execute the production save rendering helper with deterministic
# buffers. A tall block must fit while leaving every pixel outside the skin intact.
paint=method(save,"static void paint_save_information(")
# Use the real production pixel primitive, not a test-only transparency rule.
put_pixel=method(Path("upstream/imagewin/ibuf8.h").read_text(),"void put_pixel8(").replace(" override","")
raw_copy=method(Path("upstream/imagewin/ibuf8.cc").read_text(),"void Image_buffer8::copy_transparent8(")
assert "if (chr)" in raw_copy  # This API skips 0, unlike the font raster's 255.
assert "copy_transparent8(" not in paint
assert "if(colour!=255)target->put_pixel8(" in paint
harness=r'''
#include <algorithm>
#include <cassert>
#include <cstring>
#include <vector>
#include "korean_runtime_text.h"
struct TileRect{
 int x=0,y=0,w=256,h=256;
 TileRect()=default;TileRect(int a,int b,int c,int d):x(a),y(b),w(c),h(d){}
 TileRect intersect(TileRect r)const{
 int l=std::max(x,r.x),t=std::max(y,r.y);
 return {l,t,std::max(0,std::min(x+w,r.x+r.w)-l),std::max(0,std::min(y+h,r.y+r.h)-t)};
 }
};
struct Image_buffer8{
 int w,h;std::vector<unsigned char> p;TileRect clip;
 unsigned char*bits;int line_width,clipx=0,clipy=0,clipw,cliph;
 Image_buffer8(int a,int b):w(a),h(b),p(size_t(a)*b,255),clip(0,0,a,b),bits(p.data()),line_width(a),clipw(a),cliph(b){}
 void fill8(unsigned char c){std::fill(p.begin(),p.end(),c);}
 unsigned char get_pixel8(int x,int y){return p[size_t(y)*w+x];}
 struct Clip{
 Image_buffer8*b;TileRect old;TileRect Rect()const{return old;}
 ~Clip(){b->set_clip(old.x,old.y,old.w,old.h);}
 };
 Clip SaveClip(){return {this,clip};}
 void set_clip(int x,int y,int w,int h){clip={x,y,w,h};clipx=x;clipy=y;clipw=w;cliph=h;}
 PRODUCTION_PUT_PIXEL
 Image_buffer8*get_ib8(){return this;}
};
struct Game_window{
 Image_buffer8 target{256,256};Image_buffer8*active=&target;
 static Game_window*get_instance(){static Game_window g;return &g;}
 Image_buffer8*push_render_target(Image_buffer8*p){auto*old=active;active=p;return old;}
 void pop_render_target(Image_buffer8*p){active=p;}
 Image_buffer8*get_win(){return active;}
};
struct Shape_manager{
 static Shape_manager*get_instance(){static Shape_manager m;return &m;}
 void paint_text_box(int,const char*,int,int,int w,int){
 auto*b=Game_window::get_instance()->active;
 for(int y=0;y<160;++y)for(int x=0;x<w;++x)if(y%8==0||x%9==0)b->p[size_t(y)*b->w+x]=0;
 }
};
bool legacy_korean_font_available(){return true;}
'''.replace('PRODUCTION_PUT_PIXEL',put_pixel)+paint+r'''
int main(){
 auto*g=Game_window::get_instance();g->target.fill8(42);
 paint_save_information("many rows",120,40,92,79);
 int count=0,background=0;
 for(int y=0;y<256;++y)for(int x=0;x<256;++x){
 auto c=g->target.get_pixel8(x,y);
 if(x<120||x>=212||y<40||y>=119)assert(c==42);
 else {assert(c!=255);if(c==0)++count;else if(c==42)++background;}
 }
 assert(count>100&&background>100);
 assert(g->active==&g->target);
 assert(g->target.clip.w==256&&g->target.clip.h==256);
}
'''
with tempfile.TemporaryDirectory() as folder:
 cpp=Path(folder)/"panel.cpp";binary=Path(folder)/"panel";cpp.write_text(harness)
 subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined","-Iupstream/shapes",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
print("PASS: production put_pixel8 preserves opaque black and transparent background; restores clip/target; bounds portraits")

# Check all reviewed messages really enter the final generated source.
items=Path("upstream/shapes/items.cc").read_text()
for n in (0x5d8,0x5d9,0x5da,0x634,0x698,0x699,0x602,0x66a,0x66b,0x66c,0x5a0,0x5a1,0x5fb,0x5fd):
 assert f'Set_text_msg(0x{n:X} - msg_file_start,' in items
for word in ("Empty Slot","Quick Save","No Info","Unreadable","Savegame",
 "Okay to write over existing saved game?","Okay to delete saved game?"):
 assert ':"'+word+'")' in save
menu=Path("upstream/menulist.cc").read_text()
assert 'text=korean_wrap_columns(text,available,' in menu
assert 'std::string localcopy = text;' in menu
assert 'x1=std::clamp(x1,column_left,' in menu
print("PASS: reviewed translations, skin bounds and launcher column constraints")
