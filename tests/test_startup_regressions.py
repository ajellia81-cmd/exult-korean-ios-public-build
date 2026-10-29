"""Regressions for patched initial data, named menu fonts and welcome layout."""
from pathlib import Path
game=Path("upstream/gamewin.cc").read_text()
a=game.index("restore_gamedat(PATCH_INITGAME);")
b=game.index('// Editing, and no IDENTITY?',a)
section=game[a:b]
assert section.index("!U7exists(GEXULTVER)")<section.index("Game::set_new_game()")
assert section.index("else")>section.index("Game::set_new_game()")
# A normal Exult ZIP carries exult.ver and must not use original NPC flags.
# Original NPC flags can contain 0x48, which is not a named-usecode flag.
actor=Path("upstream/actorio.cc").read_text()
assert "const bool usecode_name_used  = !fix_first && (iflag1 & 8);" in actor
for original in (False,True):
    iflag1=0x48
    usecode_name_used=not original and bool(iflag1&8)
    assert usecode_name_used != original
font=Path("upstream/shapes/font.cc").read_text()
assert font.count('if(native_name=="MENU_FONT")')==2
assert 'named_face=load_korean_patch_face("<STATIC>/mainshp.flx",9);' in font
menu=Path("upstream/exultmenu.cc").read_text()
a=menu.index("if (!gamemanager->get_game_count())")
b=menu.index('IExultDataSource mouse_data',a)
welcome=menu[a:b]
assert "fit_launcher_scene(welcome_scene,320,200);" in welcome
assert "300,180,2,false,true" in welcome
assert "line_num * 10" not in welcome
audio=Path("upstream/audio/Audio.cc").read_text()
assert "recovery!=\"yes\"&&music_pack" in audio
assert 'config->set("config/audio/midi/use_oggs","yes",false);' in audio
print("Startup regression checks passed")

# Verify the production aspect helper across portrait/landscape and ultrawide
# targets; this runs its actual C++ function, rather than a duplicate formula.
import subprocess,tempfile
a=menu.index("static void fit_launcher_scene(")
b=menu.index("\n}\n",a)+2
helper=menu[a:b]
harness=r"""
#include <cassert>
#include <cmath>
struct Win {
 int w=1536,h=707;
 int get_display_width(){return w;}
 int get_display_height(){return h;}
} win;
struct Game_window {
 int x,y,w,h;
 static Game_window* get_instance();
 Win* get_win(){return &win;}
 void layer_set_dest(int,int xx,int yy,int ww,int hh){x=xx;y=yy;w=ww;h=hh;}
} window;
Game_window* Game_window::get_instance(){return &window;}
struct Scene_view{int get_handle(){return 0;}};
"""
harness+=helper
harness+=r"""
int main(){
 Scene_view scene;
 for(auto dims: {std::pair<int,int>{1536,707},{2868,1320},{1024,768},{707,1536}}){
  win.w=dims.first;win.h=dims.second;
  for(auto src: {std::pair<int,int>{320,200},{360,225}}){
   fit_launcher_scene(scene,src.first,src.second);
   assert(window.w<=win.w&&window.h<=win.h);
   assert(window.x>=0&&window.y>=0);
   assert(std::abs(window.w*src.second-window.h*src.first)<=src.first);
  }
 }
}
"""
harness="#include <utility>\n#include <initializer_list>\n"+harness
with tempfile.TemporaryDirectory() as folder:
 cpp=Path(folder)/"aspect.cpp";binary=Path(folder)/"aspect"
 cpp.write_text(harness)
 subprocess.run(["clang++","-std=c++17",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
# Every pre-selection full-screen scene has an explicit native-aspect fit.
for name in ("welcome_scene","mods_scene","logo_scene","*menu_scene"):
 assert "fit_launcher_scene("+name in menu
assert 'EXULT_FLX_FONTS_ORIGINAL_VGA), PATCH_ORIGINAL_FONTS, 18, 1' in menu
assert 'mapped=(index>=18&&index<=21)?95+index-18:90+index;' in font
entries=Path("upstream/menulist.cc").read_text()
assert entries.count("font_on->get_text_edge_padding")>=3
print("Launcher scene aspect and text-bound checks passed")
