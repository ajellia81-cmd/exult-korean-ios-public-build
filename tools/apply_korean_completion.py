"""Complete reviewed Korean UI and Windows Korean text semantics.
Only engine code, approved UI labels and standard CP949 mappings are emitted.
Game strings and glyph bitmaps remain in the user's installed pack.
"""
from pathlib import Path
import re
def edit(path,before,after):
 p=Path("upstream")/path;s=p.read_text()
 if s.count(before)!=1:raise RuntimeError(f"{path}: anchor count {s.count(before)}: {before[:70]!r}")
 p.write_text(s.replace(before,after,1))
def append(path,more):
 p=Path("upstream")/path;p.write_text(p.read_text()+more)
def cp(text):
 return '"'+''.join(chr(c) if 32<=c<127 and c not in (34,92) else '\\%03o'%c for c in text.encode("cp949"))+'"'
def body(s,signature):
 a=s.index(signature);b=s.index("{",a);depth=0
 for e in range(b,len(s)):
  if s[e]=="{":depth+=1
  elif s[e]=="}":
   depth-=1
   if not depth:return a,e+1
 raise RuntimeError(signature)

# Embedded fonts 0..10 are the same game font slots, not launcher fonts 90+.
edit("shapes/font.cc",
 'mapped=(index>=18&&index<=21)?95+index-18:90+index;',
 '''mapped=(index>=18&&index<=21)?95+index-18:
            (index>=0&&index<=10&&Game::get_game_type()!=NONE)?index:90+index;''')

# Approved UI text overrides, applied after the installed translations.
labels={
 0x5e7:"UI 옵션",0xb00:"크기:",0xb01:"확대 방식:",0xb02:"화면 맞춤 방식:",
 0xb03:"화면 맞춤 보간:",0xb04:"모든 화면 요소에",0xb05:"같은 설정 적용:",
 0xb06:"크게",0xb07:"보통",0xb08:"자동",0xb09:"마우스 포인터",
 0xb0a:"대화 화면",0xb0b:"검프",0xb0c:"HUD 검프",0xb0d:"텍스트 검프",
 0xb0e:"모달 검프",0xb0f:"화면 문자 효과",0xb10:"야간 색상표:",
 0xb11:"해질녘",0xb12:"투명화",0xb13:"흐림",0xb14:"안개",0xb15:"주문",
 0xb16:"촛불",0xb17:"붉은색",0xb18:"번개",0xb19:"단일 광원",0xb1a:"다중 광원",
 0x683:"화면 채우기",0x684:"화면에 맞춤",0x69a:"최근접 보간",0x69c:"쌍선형 보간"}
p=Path("upstream/shapes/items.cc");s=p.read_text()
a,b=body(s,"void Setup_text(bool si,")
overrides='\n    if(U7exists("<CONFIG>/patch/FONT0BG.FNT")||U7exists("<CONFIG>/patch/font0bg.fnt")||U7exists("<CONFIG>/patch/FONT0SI.FNT")||U7exists("<CONFIG>/patch/font0si.fnt")) {\n'
for code,text in labels.items():overrides+=f"        Set_text_msg(0x{code:X} - msg_file_start,{cp(text)});\n"
overrides+="    }\n"
s=s[:b-1]+overrides+s[b-1:];p.write_text(s)
p=Path("upstream/gumps/UIOptions_gump.cc");s=p.read_text()
s=s.replace("Image_window::get_displayname_for_scaler(Image_window::point)","get_text_msg(0x69A - msg_file_start)")
s=s.replace("Image_window::get_displayname_for_scaler(Image_window::bilinear)","get_text_msg(0x69C - msg_file_start)")
s=s.replace("scaler_text.emplace_back(Image_window::get_displayname_for_scaler(i));",
'''scaler_text.emplace_back(i==Image_window::point?get_text_msg(0x69A - msg_file_start):
                i==Image_window::bilinear?get_text_msg(0x69C - msg_file_start):
                Image_window::get_displayname_for_scaler(i));''')
p.write_text(s)

# Localize detected stock game titles for the launcher only. Paths/IDs stay
# unchanged. Names follow the installed Korean pack's established terminology.
p=Path("upstream/exultmenu.cc");s=p.read_text()
anchor="const ModManager& exultgame = game_list[i];"
addition=r'''
        std::string localized_title=exultgame.get_menu_string();
        const bool korean_pack=U7exists("<CONFIG>/patch/FONT0BG.FNT")||U7exists("<CONFIG>/patch/font0bg.fnt")
            ||U7exists("<CONFIG>/patch/FONT0SI.FNT")||U7exists("<CONFIG>/patch/font0si.fnt");
        if(korean_pack){
            if(localized_title.find("THE FORGE OF VIRTUE")!=std::string::npos
               ||localized_title.find("The Forge of Virtue")!=std::string::npos)
                localized_title=TITLE_FOV;
            else if(localized_title.find("THE SILVER SEED")!=std::string::npos
                    ||localized_title.find("The Silver Seed")!=std::string::npos)
                localized_title=TITLE_SS;
            else if(localized_title.find("THE BLACK GATE")!=std::string::npos
                    ||localized_title.find("The Black Gate")!=std::string::npos)
                localized_title=TITLE_BG;
            else if(localized_title.find("SERPENT ISLE")!=std::string::npos
                    ||localized_title.find("Serpent Isle")!=std::string::npos)
                localized_title=TITLE_SI;
        }
'''
for key,value in {"TITLE_FOV":"울티마 VII: 검은 관문\n미덕의 대장간",
 "TITLE_SS":"울티마 VII 파트 2: 큰뱀섬\n은빛 씨앗","TITLE_BG":"울티마 VII\n검은 관문",
 "TITLE_SI":"울티마 VII 파트 2\n큰뱀섬"}.items():addition=addition.replace(key,cp(value))
if s.count(anchor)!=1:raise RuntimeError("Game title anchor")
s=s.replace(anchor,anchor+addition,1)
s=s.replace("exultgame.get_menu_string().c_str(), sfxicon","localized_title.c_str(), sfxicon",1)
p.write_text(s)

# A small asset-independent text helper. CP949 -> Hangul initial indices are
# derived from the standard codec, not from copyrighted font/game resources.
header=r'''#ifndef KOREAN_RUNTIME_TEXT_H
#define KOREAN_RUNTIME_TEXT_H
#include <algorithm>
#include <string>
#include <utility>
#include <vector>
inline bool korean_text_pair(const char* p,size_t n){
 if(n<2)return false;
 unsigned a=static_cast<unsigned char>(p[0]),b=static_cast<unsigned char>(p[1]);
 return a>=0x81&&a<=0xfe&&((b>=0x41&&b<=0x5a)||(b>=0x61&&b<=0x7a)||(b>=0x81&&b<=0xfe));
}
inline std::pair<std::string,std::string> korean_split_sign(const std::string& s){
 auto p=s.find('%');
 return p==std::string::npos?std::make_pair(s,std::string()):std::make_pair(s.substr(0,p),s.substr(p+1));
}
inline std::vector<std::string> korean_caption_lines(const std::string& s){
 std::vector<std::string> out;
 if(s.empty())return out;
 size_t start=0;
 for(;;){auto p=s.find('*',start);out.push_back(s.substr(start,p==std::string::npos?p:p-start));
 if(p==std::string::npos)break;start=p+1;}
 return out;
}
inline std::string korean_serpentine(const std::string& s){
 struct Initial{unsigned code;char rune;};
 static constexpr Initial initials[]={
INITIAL_TABLE
 };
 std::string out;
 for(size_t i=0;i<s.size();){
  if(!korean_text_pair(s.data()+i,s.size()-i)){out+=s[i++];continue;}
  const unsigned code=(unsigned(static_cast<unsigned char>(s[i]))<<8)|static_cast<unsigned char>(s[i+1]);
  auto q=std::lower_bound(std::begin(initials),std::end(initials),code,
       [](const Initial& a,unsigned b){return a.code<b;});
  if(q!=std::end(initials)&&q->code==code)out+=q->rune;
  else out.append(s,i,2);
  i+=2;
 }
 return out;
}
#endif
'''
rows=[]
for lead in range(0x81,0xff):
 for trail in range(0x41,0xff):
  try:u=ord(bytes([lead,trail]).decode("cp949"))
  except (UnicodeDecodeError,TypeError):continue
  if 0xac00<=u<=0xd7a3:rows.append("{0x%04x,'%s'}"%(lead*256+trail,chr(ord('c')+(u-0xac00)//588)))
header=header.replace("INITIAL_TABLE",",\n".join(rows))
Path("upstream/shapes/korean_runtime_text.h").write_text(header)

# Keep rune conversion separate from the translation payload.
edit("gumps/Sign_gump.cc",'#include "font.h"',
 '#include "font.h"\n#include "../shapes/korean_runtime_text.h"')
edit("gumps/Sign_gump.h","bool         serpentine;","bool         serpentine;\n    std::string korean_caption;\n    std::vector<std::string> caption_rows() const;")
edit("gumps/Sign_gump.h",'#include "Text_gump.h"','#include "Text_gump.h"\n#include <vector>')
edit("gumps/Sign_gump.h","void paint() override;","void paint() override;\n    TileRect get_rect() const override;")
edit("gumps/Sign_gump.cc",
 "void Sign_gump::add_text(int line, const std::string& txt) {",
 '''void Sign_gump::add_text(int line, const std::string& input) {
    auto parts=legacy_korean_font_available()?korean_split_sign(input):
        std::make_pair(input,std::string());
    const std::string& txt=parts.first;
    if(line==0)korean_caption=parts.second;''')
append("gumps/Sign_gump.cc",r'''
std::vector<std::string> Sign_gump::caption_rows() const {
    std::vector<std::string> rows;
    if(serpentine||korean_caption.empty())return rows;
    auto face=sman->get_font(1);
    const int width=std::max(64,object_area.w-8);
    for(const auto& line:korean_caption_lines(korean_caption)){
        std::string current;
        for(size_t i=0;i<line.size();){
            const size_t n=korean_text_pair(line.data()+i,line.size()-i)?2:1;
            const std::string unit=line.substr(i,n);
            if(!current.empty()&&face->get_text_width((current+unit).c_str())>width){
                rows.push_back(current);current.clear();
            }
            current+=unit;i+=n;
        }
        rows.push_back(current);
    }
    return rows;
}
TileRect Sign_gump::get_rect() const {
    auto rect=Text_gump::get_rect();
    const auto rows=caption_rows();
    if(rows.empty())return rect;
    auto face=sman->get_font(1);int height=4;
    for(const auto& row:rows)height+=face->get_text_height(row.c_str())+2;
    return rect.add(TileRect(x+object_area.x,y+object_area.y+object_area.h+6,object_area.w,height));
}
''')
edit("gumps/Sign_gump.cc","\tx = oldx;\n\ty = oldy;",
 r'''    int caption_y=y+object_area.y+object_area.h+8;
    auto caption_face=sman->get_font(1);
    for(const auto& row:caption_rows()){
        const int height=caption_face->get_text_height(row.c_str())+2;
        caption_face->paint_text_box(gwin->get_win()->get_ib8(),row.c_str(),
             x+object_area.x,caption_y,object_area.w,height,0,false,true);
        caption_y+=height;
    }
    x = oldx;
    y = oldy;''')

# Preserve the read/unread distinction for SI's ancient script.
edit("gumps/Text_gump.cc",'#include "gamewin.h"',
 '#include "gamewin.h"\n#include "font.h"\n#include "../shapes/korean_runtime_text.h"')
edit("gumps/Text_gump.cc","void Text_gump::add_text(const char* str) {",
 '''void Text_gump::add_text(const char* str) {
    std::string ancient;
    if(font==8&&legacy_korean_font_available()){
        ancient=korean_serpentine(str);str=ancient.c_str();
    }''')

# Korean fork treats only doubled tildes as a dialogue stopping point.
edit("usecode/ucinternal.cc",'#include "game.h"','#include "game.h"\n#include "font.h"')
edit("usecode/ucinternal.cc","char* eol = strchr(str, '~');",
 '''char* eol = legacy_korean_font_available()?strstr(str,"~~"):strchr(str,'~');''')

# Include the last guardian subtitle, with an out-of-range disabled sentinel.
edit("gamemgr/bggame.cc",
 "text_index > 0 && static_cast<unsigned>(text_index) < text_num_frames",
 "text_index > 0 && static_cast<unsigned>(text_index) <= text_num_frames")
edit("gamemgr/bggame.cc",
 "text_index = text_num_frames;    // Disable subtitles",
 "text_index = text_num_frames + 1;    // Disable subtitles")

# Shortcut hit testing uses the same non-fast coordinate system as
# Gump_manager::map_game_to_gump. Consume real press/release pairs only.
edit("gumps/ShortcutBar_gump.cc",
 '\tif ((event->type == SDL_EVENT_MOUSE_BUTTON_DOWN || event->type == SDL_EVENT_MOUSE_BUTTON_UP) && handle_events) {',
 '''    if(event->type==SDL_EVENT_MOUSE_BUTTON_DOWN)handle_events=true;
    if ((event->type == SDL_EVENT_MOUSE_BUTTON_DOWN || event->type == SDL_EVENT_MOUSE_BUTTON_UP) && handle_events) {''')
edit("gumps/ShortcutBar_gump.cc",
 "if (barx >= startx && barx <= (locx + width) && bary >= starty && bary <= (starty + height)) {",
 "if (has_point(barx,bary)) {")
p=Path("upstream/gumps/ShortcutBar_gump.cc");s=p.read_text()
a,b=body(s,"void ShortcutBar_gump::sdl_mouse_up(")
part=s[a:b].replace("if (buttonItems[i].rect.has_point(mx, my)) {",
 "if (buttonItems[i].pushed && buttonItems[i].rect.has_point(mx, my)) {",1)
s=s[:a]+part+s[b:];p.write_text(s)
edit("gumps/ShortcutBar_gump.h","SDL_TimerID           timerId;","SDL_TimerID           timerId{};")


# All interactive gumps receive coordinates produced by screen_to_game with
# the active fast-mouse setting. Invert that same transform, not a different
# scaling transform, before mapping through their individual display layers.
p=Path("upstream/gumps/Gump_manager.cc");s=p.read_text()
a,b=body(s,"bool Gump_manager::map_game_to_gump(")
section=s[a:b]
before="game_to_screen(gx, gy, false, sx, sy);"
if section.count(before)!=1:raise RuntimeError("Common UI input transform anchor")
section=section.replace(before,"game_to_screen(gx, gy, gwin->get_fastmouse(), sx, sy);")
s=s[:a]+section+s[b:];p.write_text(s)

# The native 8px information font needs more room than the old 5px face.
# Use the available space above party portraits and avoid empty spacer rows.
p=Path("upstream/gumps/Newfile_gump.cc");s=p.read_text()
s,n=re.subn(r'(Newfile_gump::infoh\s*=\s*)79;',r'\g<1>92;',s)
if n!=1:raise RuntimeError("Save information height anchor")
a=s.index('char info[320]');b=s.index('if (filename)',a)
part=s[a:b].replace('\n\t\t\t\t"\\n"','')
s=s[:a]+part+s[b:];p.write_text(s)


# Text gumps paint in a local layer but hit-test in their original game-space
# coordinates, just like other gumps. Retain that origin in layer_bounds.
edit("gumps/Text_gump.cc","layer_bounds = TileRect(0, 0, w, h);","layer_bounds = r;")


# The current embedded font collection also moved guardian/endgame faces.
# Keep all named cinematic faces connected to their original Korean pack IDs.
p=Path("upstream/shapes/font.cc");s=p.read_text()
anchor='    else if(native_name=="NORMAL_FONT"||native_name=="EXULT_END_FONT")'
extra='''    else if(native_name=="GUARDIAN_FONT")
        named_face=load_korean_patch_face("<STATIC>/mainshp.flx",3);
    else if(native_name=="END2_FONT")
        named_face=load_korean_patch_face("<STATIC>/endgame.dat",4);
    else if(native_name=="END3_FONT")
        named_face=load_korean_patch_face("<STATIC>/endgame.dat",5);
'''
if s.count(anchor)!=2:raise RuntimeError("Cinematic face routing anchors")
s=s.replace(anchor,extra+anchor);p.write_text(s)
