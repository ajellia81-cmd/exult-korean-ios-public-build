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

}
'''
with tempfile.TemporaryDirectory() as folder:
 cpp=Path(folder)/"followup.cpp";binary=Path(folder)/"followup";cpp.write_text(code)
 subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined","-fno-omit-frame-pointer",
  "-Iupstream/shapes",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
print("PASS: native center dispatch and CP949-safe column wrapping")


save=Path("upstream/gumps/Newfile_gump.cc").read_text()
assert re.search(r'Newfile_gump::infoh\s*=\s*72;',save)
assert save.count('paint_save_information(info, x + infox, y + infoy, infow, infoh);')==2
assert '"%04i-%02i-%02i %02i:%02i"' in save
assert 'Strings::ordinal_numeral_suffix(details->real_day)' not in save
paint=method(save,"static void paint_save_information(")
assert 'sample' not in paint and 'korean_fit_pixels' not in paint
assert 'paint_text_box' in paint  # English-only fallback remains.
assert 'face->get_text_ink_bounds(' in paint
assert 'face->paint_text(' in paint

# Execute the real native font selection/measure/draw code, real .FNT parser
# and real clipped pixel primitive. Only bitmap fixtures are synthetic.
def lit(s):
 return '"'+''.join('\\%03o'%b for b in s.encode('cp949'))+'"'
fixture=[
 '아바타: AvatarTest','경험: 300  생명: 18','힘: 18  민첩: 18','지능: 18  훈련: 3',
 '게임 일수: 0  09:54','저장 횟수: 17','2026-10-29 22:41','파일: exult00bg.sav']
joined='\n'.join(fixture)
put_pixel=method(Path("upstream/imagewin/ibuf8.h").read_text(),"void put_pixel8(").replace(" override","")
native='\n'.join(method(font,sign) for sign in (
 'bool Font::native_style(','int Font::native_width(','int Font::native_draw(','void Font::native_bounds('))
snprintf_start=save.index('snprintf(',save.index('char info[320]'))
snprintf_end=save.index('info[std::size(info) - 1]',snprintf_start)
format_code=save[snprintf_start:snprintf_end]
harness=r'''
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <vector>
#include "korean_patch_font.h"
#include "korean_runtime_text.h"
using std::string;
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
 Image_buffer8(int a,int b):w(a),h(b),p(size_t(a)*b,42),clip(0,0,a,b),bits(p.data()),line_width(a),clipw(a),cliph(b){}
 struct Clip{
 Image_buffer8*b;TileRect old;TileRect Rect()const{return old;}
 ~Clip(){b->set_clip(old.x,old.y,old.w,old.h);}
 };
 Clip SaveClip(){return {this,clip};}
 void set_clip(int x,int y,int w,int h){clip={x,y,w,h};clipx=x;clipy=y;clipw=w;cliph=h;}
 PRODUCTION_PUT
 Image_buffer8*get_ib8(){return this;}
};
Image_buffer8* active=nullptr;
struct Shape_frame{
 std::vector<unsigned char> p;int w=0,h=0,left=0,above=0;
 Shape_frame()=default;
 Shape_frame(unsigned char*s,int ww,int hh,int l,int a,bool):p(s,s+ww*hh),w(ww),h(hh),left(l),above(a){}
 int get_width(){return w;}int get_height(){return h;}
 int get_xleft(){return left;}int get_yabove(){return above;}
 bool is_rle(){return true;}
 void paint_rle(int x,int y){
  assert(active);
  for(int yy=0;yy<h;++yy)for(int xx=0;xx<w;++xx){
   auto c=p[size_t(yy)*w+xx];if(c!=255)active->put_pixel8(c,x-left+xx,y-above+yy);
  }
 }
 void paint_rle_remapped(int x,int y,unsigned char*){paint_rle(x,y);}
};
struct Shape_file{
 Shape_frame frames[128];
 Shape_file(){
  for(int c=0;c<128;++c){
   auto&f=frames[c];f.w=3;f.h=5;f.left=0;f.above=4;f.p.assign(15,255);
   if(c!=' ')for(int y=0;y<5;++y)for(int x=0;x<3;++x)
    if(x==0||y==0||y==4||((c>>(x+y)%6)&1))f.p[y*3+x]=0;
  }
 }
 Shape_frame*get_frame(unsigned c){return c<128?&frames[c]:nullptr;}
};
bool legacy_korean_layout_override=false;
struct Korean_layout_scope{
 bool&slot;bool previous;
 Korean_layout_scope(bool&s,bool v):slot(s),previous(s){s=s||v;}
 ~Korean_layout_scope(){slot=previous;}
};
struct Font{
 std::shared_ptr<KoreanPatchFont> native_face=std::make_shared<KoreanPatchFont>();
 std::unique_ptr<Shape_file> font_shapes=std::make_unique<Shape_file>();
 int hor_lead=1,highest=4;
 bool native_ascii_override=false;
 bool set_native_ascii_override(bool v){bool old=native_ascii_override;native_ascii_override=v;return old;}
 struct Call{std::string text;int left,top,width,height;};
 std::vector<Call> calls;
 bool native_style(const char*,int);
 int native_width(const char*,int,int=0);
 int native_draw(Image_buffer8*,const char*,int,int,int,unsigned char*,int=0);
 void native_bounds(const char*,int&,int&,int&,int&);
 void get_text_ink_bounds(const char*t,int&l,int&y,int&w,int&h){native_bounds(t,l,y,w,h);}
 int paint_text(Image_buffer8*b,const char*t,int x,int y,unsigned char*trans=nullptr){
  int l,top,w,h;native_bounds(t,l,top,w,h);
  calls.push_back({t,x+l,y+top,w,h});
  return native_draw(b,t,-1,x,y,trans);
 }
} fixture_font;
PRODUCTION_NATIVE
struct Game_window{
 Image_buffer8 target{256,256};
 Game_window(){active=&target;}
 static Game_window*get_instance(){static Game_window g;return &g;}
 Image_buffer8*get_win(){return &target;}
};
struct Shape_manager{
 static Shape_manager*get_instance(){static Shape_manager m;return &m;}
 Font*get_font(int n){assert(n==4);return &fixture_font;}
 void paint_text_box(int,const char*,int,int,int,int){assert(false);}
};
bool legacy_korean_font_available(){return true;}
PRODUCTION_PAINT
void append16(std::vector<unsigned char>&v,unsigned n){v.push_back(n&255);v.push_back(n>>8);}
void load_fixture(const std::string&text){
 std::vector<unsigned> codes;
 for(unsigned c=32;c<127;++c)codes.push_back(c);
 for(size_t i=0;i<text.size();){
  if(KoreanPatchFont::pair(text.data()+i,int(text.size()-i))){
   codes.push_back(unsigned(static_cast<unsigned char>(text[i]))*256+static_cast<unsigned char>(text[i+1]));i+=2;
  }else ++i;
 }
 std::sort(codes.begin(),codes.end());codes.erase(std::unique(codes.begin(),codes.end()),codes.end());
 std::vector<unsigned char> data{0x45,0x33,0x22,0x11,8,8,8,8,0,0,0,0};
 append16(data,codes.size());
 for(auto c:codes){append16(data,c);data.push_back(255);data.push_back(254);data.push_back(c<128?4:8);}
 for(auto c:codes){
  std::vector<unsigned char> pix(64,0);
  int w=c<128?3:7,h=7;
  if(c!=' ')for(int y=0;y<h;++y)for(int x=0;x<w;++x)
   if(x==0||x==w-1||y==0||y==h-1||((c>>(x+y)%9)&1))pix[y*8+x]=1;
  for(int p=0;p<64;p+=4)data.push_back((pix[p]<<6)|(pix[p+1]<<4)|(pix[p+2]<<2)|pix[p+3]);
 }
 assert(fixture_font.native_face->load(data));
}
struct Strings{
 STRING_FUNCTIONS
};
struct Party{const char*name="AvatarTest";int exp=300,health=18,str=18,dext=18,intel=18,training=3;};
struct Details{int game_day=0,game_hour=9,game_minute=54,save_count=17,real_year=2026,real_month=10,real_day=29,real_hour=22,real_minute=41;};
void check_panel(const std::string&text,int expected){
 auto*g=Game_window::get_instance();
 std::fill(g->target.p.begin(),g->target.p.end(),42);fixture_font.calls.clear();
 paint_save_information(text.c_str(),120,40,92,72);
 assert(int(fixture_font.calls.size())==expected);
 int bottom=40;
 for(const auto&c:fixture_font.calls){
  assert(c.left>=120&&c.left+c.width<=212);
  assert(c.top>=bottom&&c.top+c.height<=112);
  assert(c.width>0&&c.height>0);
  int ink=0;
  for(int yy=c.top;yy<c.top+c.height;++yy)for(int xx=c.left;xx<c.left+c.width;++xx)
   if(g->target.p[size_t(yy)*256+xx]==0)++ink;
  assert(ink>0);
  bottom=c.top+c.height;
 }
 int ink=0,background=0;
 for(int y=0;y<256;++y)for(int x=0;x<256;++x){
  auto c=g->target.p[size_t(y)*256+x];
  if(x<120||x>=212||y<40||y>=112)assert(c==42);
  else{assert(c==0||c==42);if(c==0)++ink;else ++background;}
 }
 assert(ink>100&&background>100);
 assert(!legacy_korean_layout_override);
 assert(!fixture_font.native_ascii_override);
 assert(g->target.clip.w==256&&g->target.clip.h==256);
}
int main(){
 const std::string expected=FIXTURE;
 load_fixture(expected);
 check_panel(expected,8);
 assert(fixture_font.calls[6].text=="2026-10-29 22:41");
 assert(fixture_font.calls[6].height==7); // Native digits, not the 5px legacy font.
 assert(fixture_font.calls[7].text.find("exult00bg.sav")!=std::string::npos);
 // Long values must preserve native pixels, stop at complete CP949 units and
 // use an ellipsis. Neither the source nor the saved name is edited.
 std::string long_text=expected;
 long_text.insert(long_text.find('\n'),std::string(100,'A'));
 check_panel(long_text,8);
 assert(fixture_font.calls[0].text.substr(fixture_font.calls[0].text.size()-3)=="...");
 Party party[1];Details d;Details*details=&d;char info[320];
 PRODUCTION_FORMAT
 std::string formatted=info;
 assert(std::count(formatted.begin(),formatted.end(),'\n')==6);
 assert(formatted.substr(formatted.size()-16)=="2026-10-29 22:41");
 formatted+="\n"+std::string(FILE_LABEL)+": exult00bg.sav";
 check_panel(formatted,8);
}
'''
string_values={'Avatar':'아바타','Exp':'경험','Hp':'생명','Str':'힘','Dxt':'민첩','Int':'지능','Trn':'훈련',
 'GameDay':'게임 일수','GameTime':'게임 시간','SaveCount':'저장 횟수'}
functions='\n'.join('static const char* '+k+'(){return '+lit(v)+';}' for k,v in string_values.items())
harness=harness.replace('PRODUCTION_PUT',put_pixel).replace('PRODUCTION_NATIVE',native).replace('PRODUCTION_PAINT',paint)
harness=harness.replace('STRING_FUNCTIONS',functions).replace('PRODUCTION_FORMAT',format_code)
harness=harness.replace('FILE_LABEL',lit('파일')).replace('FIXTURE',lit(joined))
with tempfile.TemporaryDirectory() as folder:
 cpp=Path(folder)/"native_panel.cpp";binary=Path(folder)/"native_panel";cpp.write_text(harness)
 subprocess.run(["clang++","-std=c++17","-Werror=format","-fsanitize=address,undefined","-fno-omit-frame-pointer",
  "-Iupstream/shapes",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
print("PASS: actual FNT parser/native width/bounds/draw with Korean+Latin+digits, negative bearings, nine complete rows, long names, real snprintf")

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
print("PASS: reviewed translations and launcher constraints retained; save raster scaling removed")
