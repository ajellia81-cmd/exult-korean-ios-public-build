"""Compile production Korean compatibility helpers and shortcut release logic."""
from pathlib import Path
import subprocess,tempfile,re
def method(s,start):
 a=s.index(start);b=s.index("{",a);depth=0
 for i in range(b,len(s)):
  if s[i]=="{":depth+=1
  elif s[i]=="}":
   depth-=1
   if depth==0:return s[a:i+1]
 raise RuntimeError(start)
font=Path("upstream/shapes/font.cc").read_text()
a=font.index("    int mapped=-1;",font.index("static std::shared_ptr<KoreanPatchFont> load_korean_patch_face"))
b=font.index("    if(mapped<0)return {};",a)
route=font[a:b]+"\nreturn mapped;\n}"
sign=Path("upstream/gumps/Sign_gump.cc").read_text()
shortcut=Path("upstream/gumps/ShortcutBar_gump.cc").read_text()
release=method(shortcut,"void ShortcutBar_gump::sdl_mouse_up(")
preamble=r"""
#include <cassert>
#include <cstring>
#include <iterator>
#include <vector>
#include <string>
#include "korean_runtime_text.h"
enum {NONE,BLACK_GATE,SERPENT_ISLE};
namespace Game{int game=NONE;int get_game_type(){return game;}}
int font_route(const std::string& source,int index){
"""
harness=preamble+route+r"""
struct TileRect{
 int x,y,w,h;
 TileRect(int xx=0,int yy=0,int ww=0,int hh=0):x(xx),y(yy),w(ww),h(hh){}
 bool has_point(int xx,int yy)const{return xx>=x&&yy>=y&&xx<x+w&&yy<y+h;}
 TileRect add(TileRect r)const{
  int l=std::min(x,r.x),t=std::min(y,r.y),rr=std::max(x+w,r.x+r.w),bb=std::max(y+h,r.y+r.h);
  return {l,t,rr-l,bb-t};
 }
};
struct Face{
 int get_text_width(const char* s){int w=0;for(size_t i=0,n=strlen(s);i<n;){size_t k=korean_text_pair(s+i,n-i)?2:1;i+=k;w+=k==2?10:5;}return w;}
 int get_text_height(const char*){return 10;}
} face;
struct Manager{Face*get_font(int){return &face;}} manager;
struct Text_gump{TileRect get_rect()const{return {0,0,200,100};}};
struct Sign_gump:Text_gump{
 bool serpentine=false;std::string korean_caption;Manager*sman=&manager;
 int x=0,y=0;TileRect object_area{0,4,196,92};
 std::vector<std::string>caption_rows()const;TileRect get_rect()const;
};
"""
harness+=method(sign,"std::vector<std::string> Sign_gump::caption_rows() const")
harness+=method(sign,"TileRect Sign_gump::get_rect() const")
harness+=r"""
using SDL_TimerID=unsigned;using sintptr=long;
struct SDL_Event{struct{int clicks=1;}button;};
void ignore_unused_variable_warning(SDL_Event*){}
void SDL_RemoveTimer(unsigned){}
unsigned SDL_AddTimer(int,void*,void*){return 1;}
void* didMouseUp=nullptr;
struct ShortcutBar_gump{
 struct Item{TileRect rect;bool pushed=false;};
 Item buttonItems[10];int numButtons=9;unsigned timerId=0;int clicks=0,last=-1;
 void onItemClicked(int n,bool){clicks++;last=n;}
 void sdl_mouse_up(SDL_Event*,int,int);
};
"""
harness+=release+r"""
int main(){
 auto s=korean_split_sign("RUNE%caption*second");
 assert(s.first=="RUNE"&&s.second=="caption*second");
 assert(korean_caption_lines(s.second).size()==2);
 assert(korean_split_sign("plain").second.empty());
 assert(korean_caption_lines("").empty());
 assert(korean_text_pair("\x81\x41",2));
 assert(!korean_text_pair("\x81",1));
 assert(korean_serpentine("\xb0\xa1")=="c"); // ga, initial giyeok
 assert(korean_serpentine("\xc7\xcf")=="u"); // ha, initial hieuh
 assert(korean_serpentine("A*\xb0\xa1~")=="A*c~");
 assert(korean_serpentine("\xb0")=="\xb0"); // truncated byte is preserved safely
 Game::game=BLACK_GATE;
 for(int i=0;i<=10;i++)assert(font_route("<BUNDLE>/exult.flx",i)==i);
 for(int i=18;i<=21;i++)assert(font_route("<BUNDLE>/exult.flx",i)==i+77);
 Game::game=NONE;assert(font_route("<BUNDLE>/exult.flx",0)==90);
 Sign_gump sign;
 assert(sign.get_rect().h==100);
 sign.korean_caption="caption*second";
 assert(sign.caption_rows().size()==2&&sign.get_rect().h>120);
 sign.serpentine=true;
 assert(sign.caption_rows().empty()&&sign.get_rect().h==100);
 ShortcutBar_gump bar;SDL_Event event;
 for(int i=0;i<9;i++)bar.buttonItems[i].rect={i*35,0,35,25};
 event.button.clicks=2;
 // Every visible slot, especially the last three, accepts its own center.
 for(int i=0;i<9;i++){
  bar.buttonItems[i].pushed=true;
  bar.sdl_mouse_up(&event,i*35+17,12);assert(bar.last==i);
 }
 int count=bar.clicks;
 bar.sdl_mouse_up(&event,300,12);assert(bar.clicks==count); // no prior down
 bar.buttonItems[7].pushed=true;
 bar.sdl_mouse_up(&event,8*35+17,12);assert(bar.clicks==count); // dragged into neighbor
 bar.buttonItems[8].pushed=true;
 bar.sdl_mouse_up(&event,315,12);assert(bar.clicks==count); // exclusive right edge
}
"""
with tempfile.TemporaryDirectory() as folder:
 path=Path(folder);(path/"korean_runtime_text.h").write_text(Path("upstream/shapes/korean_runtime_text.h").read_text())
 cpp=path/"compat.cpp";binary=path/"compat";cpp.write_text(harness)
 subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
assert "event->button.y, gwin->get_fastmouse(), x, y);" in shortcut
assert "if (has_point(barx,bary))" in shortcut
assert "if(event->type==SDL_EVENT_MOUSE_BUTTON_DOWN)handle_events=true;" in shortcut
assert "timerId{}" in Path("upstream/gumps/ShortcutBar_gump.h").read_text()
assert "strstr(str,\"~~\")" in Path("upstream/usecode/ucinternal.cc").read_text()
bg=Path("upstream/gamemgr/bggame.cc").read_text()
assert "text_index > 0 && static_cast<unsigned>(text_index) <= text_num_frames" in bg
assert "text_index = text_num_frames + 1;    // Disable subtitles" in bg
print("PASS: native save-font routing; sign captions and clipping bounds; ancient script; all nine shortcut slots; release/drag boundaries")

manager=Path("upstream/gumps/Gump_manager.cc").read_text()
mapping=method(manager,"bool Gump_manager::map_game_to_gump(")
assert "game_to_screen(gx, gy, gwin->get_fastmouse(), sx, sy);" in mapping
image=Path("upstream/imagewin/imagewin.cc").read_text()
forward=method(image,"void Image_window::screen_to_game(")
backward=method(image,"void Image_window::game_to_screen(")
prefix=r"""
#include <cassert>
#include <cmath>
#include <initializer_list>
struct Mouse{
 static Mouse*mouse(){static Mouse m;return &m;}
 void apply_fast_offset(int&x,int&y){x+=3;y-=2;}
 void unapply_fast_offset(int&x,int&y){x-=3;y+=2;}
};
struct Image_window{
 bool scene_mode=false;int active_scene_layer=-1;
 int inter_width=640,inter_height=400,scale=2,display_width=1536,display_height=707;
 int get_start_x(){return -24;}int get_start_y(){return -8;}
 int get_display_width(){return display_width;}int get_display_height(){return display_height;}
 void screen_to_layer(int,int x,int y,int&a,int&b){a=x;b=y;}
 void layer_to_screen(int,int x,int y,int&a,int&b){a=x;b=y;}
 void screen_to_game(int,int,bool,int&,int&);
 void game_to_screen(int,int,bool,int&,int&);
} image;
struct Bounds{int x=100,y=40;};
struct Gump{int render_layer=1,render_layer2=-1;Bounds layer_bounds,layer_bounds2;};
struct Window{
 bool fast=false;
 Image_window*get_win(){return &image;}bool get_fastmouse(){return fast;}
 bool layer_is_visible(int){return true;}
 bool screen_to_layer(int,int x,int y,int&a,int&b){
 a=(x-120)/3;b=(y-60)/3;return x>=120&&y>=60&&x<1080&&y<660;
 }
} window;
Window*gwin=&window;
struct Gump_manager{bool map_game_to_gump(const Gump*,int,int,int&,int&)const;};
"""
run=prefix+forward+backward+mapping+r"""
int main(){
 Gump_manager manager;Gump g;
 for(bool fast:{false,true})for(int w:{1536,2868}){
  window.fast=fast;image.display_width=w;
  for(int sx:{180,360,720,1020})for(int sy:{90,240,540}){
   int gx,gy,lx,ly;image.screen_to_game(sx,sy,fast,gx,gy);
   assert(manager.map_game_to_gump(&g,gx,gy,lx,ly));
   // Normal-mode input is quantized to the game grid before this API.
   // Bound that unavoidable error by one game pixel, mapped to this UI scale.
   const int tx=fast?0:((image.scale*w+image.inter_width-1)/image.inter_width+2)/3;
   const int ty=fast?0:((image.scale*image.display_height+image.inter_height-1)/image.inter_height+2)/3;
   assert(std::abs(lx-((sx-120)/3+100))<=tx);
   assert(std::abs(ly-((sy-60)/3+40))<=ty);
  }
 }
}
"""
with tempfile.TemporaryDirectory() as folder:
 cpp=Path(folder)/"ui.cpp";binary=Path(folder)/"ui";cpp.write_text(run)
 subprocess.run(["clang++","-std=c++17",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
print("PASS: common gump layer input round trips, normal/fast mode, phone display sizes")

text_gump=Path("upstream/gumps/Text_gump.cc").read_text()
assert "layer_bounds = r;" in method(text_gump,"bool Text_gump::begin_layer_paint(")
assert "korean_serpentine(str)" in text_gump
save=Path("upstream/gumps/Newfile_gump.cc").read_text()
assert re.search(r'Newfile_gump::infoh\s*=\s*92;',save)
print("PASS: book/scroll/sign layer origins and save information room")

for name in ("GUARDIAN_FONT","END2_FONT","END3_FONT","SIINTRO_FONT","MENU_FONT"):
 assert font.count('native_name=="'+name+'"')==2
assert 'load_korean_patch_face("<STATIC>/endgame.dat",4)' in font
assert 'load_korean_patch_face("<STATIC>/endgame.dat",5)' in font
print("PASS: guardian, BG/SI menu and endgame named font routing")

items=Path("upstream/shapes/items.cc").read_text()
lines=[l for l in items.splitlines() if re.search(r'Set_text_msg\(0x[0-9A-F]+ - msg_file_start,',l)]
assert len(lines)>=30
code='#include <cassert>\nconstexpr unsigned msg_file_start=0x400;\nint count=0;\nvoid Set_text_msg(unsigned,const char* s){assert(s&&*s);++count;}\nint main(){\n'+'\n'.join(lines)+'\nassert(count>=30);}\n'
with tempfile.TemporaryDirectory() as folder:
 cpp=Path(folder)/"labels.cpp";binary=Path(folder)/"labels";cpp.write_text(code)
 subprocess.run(["clang++","-std=c++17",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
print("PASS: all reviewed CP949 label literals compile as production C++")
