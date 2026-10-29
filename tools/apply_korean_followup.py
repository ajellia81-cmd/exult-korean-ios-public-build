"""Reviewed follow-up localization and bounded UI text rendering.
No installed game strings or font pixels are bundled.
"""
from pathlib import Path
import re
def edit(path,before,after):
 p=Path("upstream")/path;s=p.read_text()
 if s.count(before)!=1:raise RuntimeError(f"{path}: expected unique anchor {before[:80]!r}, got {s.count(before)}")
 p.write_text(s.replace(before,after,1))
def cp(text):
 return '"'+''.join(chr(c) if 32<=c<127 and c not in (34,92) else '\\%03o'%c for c in text.encode("cp949"))+'"'
def korean_literal(original,translated):
 return "(legacy_korean_font_available()?"+cp(translated)+':"'+original+'")'

# Finish the approved message IDs missing from the installed engine-message file.
labels={0x5d8:"내장 글꼴:",0x5d9:"원본",0x5da:"명조체",0x634:"개선 기능:",
 0x698:"현재 모드:",0x699:"현재 크기:",0x602:"고급 설정",
 0x66a:"날짜",0x66b:"시간",0x66c:"파일",
 0x5a0:"MIDI 시험 음악을 재생하지 못했습니다.",0x5a1:"OGG 시험 음악을 재생하지 못했습니다.",
 0x5fb:"설정에는 중복된 값을 지정할 수 없습니다.",
 0x5fd:"설정에는 값을 하나 이상 지정해야 합니다."}
p=Path("upstream/shapes/items.cc");s=p.read_text()
anchor='        Set_text_msg(0x5E7 - msg_file_start,'
a=s.index(anchor);b=s.index('\n    }',a)
s=s[:b]+''.join(f'\n        Set_text_msg(0x{k:X} - msg_file_start,{cp(v)});' for k,v in labels.items())+s[b:]
p.write_text(s)
# No translated prefix is needed in Korean; the setting label precedes the sentence.
p=Path("upstream/gumps/ConfigSetting_widget.cc");s=p.read_text()
if '#include "font.h"' not in s:s='#include "font.h"\n'+s
for original,replacement in [
 ('return Strings::Allvaluesfor() + (" " + setting.label + " ") + Strings::settingmustbeunique_();',
  'return legacy_korean_font_available()?setting.label+" "+Strings::settingmustbeunique_():Strings::Allvaluesfor() + (" " + setting.label + " ") + Strings::settingmustbeunique_();'),
 ('return Strings::AtleastOnevaluefor() + (" " + setting.label + " ") + Strings::settingmustbeset_();',
  'return legacy_korean_font_available()?setting.label+" "+Strings::settingmustbeset_():Strings::AtleastOnevaluefor() + (" " + setting.label + " ") + Strings::settingmustbeset_();')]:
 if s.count(original)!=1:raise RuntimeError("Setting validation anchor changed")
 s=s.replace(original,replacement,1)
p.write_text(s)
edit("gumps/AudioOptions_gump.cc",
 'Strings::Advancedsettingsfor() + ("\\n" + midi_driver_name + " ") + Strings::mididriver_()',
 'legacy_korean_font_available() ? midi_driver_name + "\\n" + Strings::Advancedsettingsfor() : Strings::Advancedsettingsfor() + ("\\n" + midi_driver_name + " ") + Strings::mididriver_()')
# font.h is needed for the Korean pack predicate in this source.
p=Path("upstream/gumps/AudioOptions_gump.cc");s=p.read_text()
if '#include "font.h"' not in s:s=s.replace('#include "game.h"','#include "game.h"\n#include "font.h"')
s=s.replace('{"None", "GS"}','{'+korean_literal("None","없음")+', "GS"}')
p.write_text(s)

# Pure helpers shared by launcher wrapping and save-panel fitting.
p=Path("upstream/shapes/korean_runtime_text.h");s=p.read_text()
helpers=r'''
template<class Measure>
inline std::string korean_wrap_columns(const std::string& input,int width,Measure measure){
 std::string out,line;
 auto flush=[&](){if(!out.empty())out+='\n';out+=line;line.clear();};
 for(size_t i=0;i<input.size();){
  if(input[i]=='\n'){flush();++i;continue;}
  size_t n=korean_text_pair(input.data()+i,input.size()-i)?2:1;
  std::string unit=input.substr(i,n);
  if(!line.empty()&&measure(line+unit)>width){
   // Prefer word boundaries, but never split a CP949 code unit.
   size_t space=line.rfind(' ');
   if(space!=std::string::npos&&space>0){
    std::string tail=line.substr(space+1);line.resize(space);flush();line=tail;
   }else flush();
   if(unit==" "&&line.empty()){i+=n;continue;}
   if(!line.empty()&&measure(line+unit)>width)flush();
  }
  line+=unit;i+=n;
 }
 flush();return out;
}
struct Korean_fit_raster{int width=0,height=0;std::vector<unsigned char> pixels;};
inline Korean_fit_raster korean_fit_pixels(const std::vector<unsigned char>& src,int sw,int sh,int mw,int mh){
 Korean_fit_raster out;
 if(sw<=0||sh<=0||mw<=0||mh<=0||src.size()!=size_t(sw)*sh)return out;
 out.width=sw;out.height=sh;
 if(sw>mw||sh>mh){
  if(static_cast<long long>(mw)*sh<=static_cast<long long>(mh)*sw){
   out.width=mw;out.height=std::max(1,int(static_cast<long long>(sh)*mw/sw));
  }else{
   out.height=mh;out.width=std::max(1,int(static_cast<long long>(sw)*mh/sh));
  }
 }
 out.pixels.assign(size_t(out.width)*out.height,255);
 for(int y=0;y<out.height;++y)for(int x=0;x<out.width;++x){
  // Coverage sampling keeps thin black strokes when an information block shrinks.
  int x0=x*sw/out.width,x1=((x+1)*sw+out.width-1)/out.width;
  int y0=y*sh/out.height,y1=((y+1)*sh+out.height-1)/out.height;
  auto& dst=out.pixels[size_t(y)*out.width+x];
  for(int sy=y0;sy<std::min(y1,sh);++sy)for(int sx=x0;sx<std::min(x1,sw);++sx){
   auto c=src[size_t(sy)*sw+sx];if(c!=255)dst=c;
  }
 }
 return out;
}
'''
s=s.replace('\n#endif','\n'+helpers+'\n#endif');p.write_text(s)

# The native width path was followed by legacy draw_text. Draw and center the
# same native ink bounds, for every caller (signs, books, menus, cinematics).
edit("shapes/font.cc",
 'int Font::center_text(Image_buffer8* win, int x, int y, const char* s, unsigned char* trans) {',
 '''int Font::center_text(Image_buffer8* win, int x, int y, const char* s, unsigned char* trans) {
    if(native_face){
        int left,top,width,height;native_bounds(s,left,top,width,height);
        return native_draw(win,s,-1,x-left-width/2,y,trans);
    }''')

# Wrap titles within their real half-screen columns, reserving the sound icon.
# Both highlighted and normal glyph bounds must fit; never stretch the launcher.
edit("menulist.cc",'#include "menulist.h"',
 '#include "menulist.h"\n#include "shapes/korean_runtime_text.h"')
p=Path("upstream/menulist.cc");s=p.read_text()
a=s.index('MenuGameEntry::MenuGameEntry(');b=s.index('void MenuGameEntry::paint',a)
part=s[a:b]
part=part.replace('sfxicon       = sfx;',r'''sfxicon       = sfx;
    auto* iw=Game_window::get_instance()->get_win();
    const int column_width=iw->get_full_width()/2;
    const int column=std::clamp((xpos-iw->get_start_x())/column_width,0,1);
    const int icon_width=sfx?sfx->get_width()+3:0;
    const int column_left=iw->get_start_x()+column*column_width+icon_width+4;
    const int column_right=iw->get_start_x()+(column+1)*column_width-4;
    const int available=std::max(16,column_right-column_left-4);
    text=korean_wrap_columns(text,available,[&](const std::string& line){
        return std::max(font->get_text_width(line.c_str()),font_on->get_text_width(line.c_str()))
          +2*std::max(font->get_text_edge_padding(line.c_str()),font_on->get_text_edge_padding(line.c_str()));
    });''',1)
part=part.replace('std::string localcopy = txt;','std::string localcopy = text;')
part=part.replace('x2       = x1 + max_width + 1;',r'''x1=std::clamp(x1,column_left,std::max(column_left,column_right-max_width-1));
    x2       = x1 + max_width + 1;''')
s=s[:a]+part+s[b:];p.write_text(s)
# Use natural title lines, rather than a long first line which wraps mid-word.
p=Path("upstream/exultmenu.cc");s=p.read_text()
s=s.replace(cp("울티마 VII 파트 2: 큰뱀섬\n은빛 씨앗"),cp("울티마 VII 파트 2\n큰뱀섬: 은빛 씨앗"))
# Rows containing unusually long user/mod titles also reserve the actual height.
s=s.replace('for (int i = first; i < last; i++) {','int title_row_height=45;\n\tfor (int i = first; i < last; i++) {',1)
s=s.replace('menu->add_entry(entry);\n\t\tif (exultgame.has_mods()) {',
 'menu->add_entry(entry);\n        title_row_height=std::max(title_row_height,entry->get_height()+24);\n\t\tif (exultgame.has_mods()) {',1)
s=s.replace('ypos += 45;','ypos += title_row_height;\n            title_row_height=45;',1)
p.write_text(s)

# Render all save information into the actual skin panel, not the larger region
# above the portraits. Preserve all fields and scale only when the block overflows.
p=Path("upstream/gumps/Newfile_gump.cc");s=p.read_text()
s=s.replace('#include "touchui.h"','#include "touchui.h"\n#include "font.h"\n#include "ibuf8.h"\n#include "../shapes/korean_runtime_text.h"')
s=re.sub(r'(Newfile_gump::infoh\s*=\s*)92;',r'\g<1>79;',s)
helper=r'''
static void paint_save_information(const char* text,int x,int y,int width,int height){
 auto* gw=Game_window::get_instance();
 auto* sm=Shape_manager::get_instance();
 if(!legacy_korean_font_available()){
  sm->paint_text_box(4,text,x,y,width,height);return;
 }
 Image_buffer8 sample(width,1024);sample.fill8(255);
 auto* previous=gw->push_render_target(&sample);
 sm->paint_text_box(4,text,0,0,width,1024);
 gw->pop_render_target(previous);
 int right=-1,bottom=-1;
 for(int sy=0;sy<1024;++sy)for(int sx=0;sx<width;++sx)
  if(sample.get_pixel8(sx,sy)!=255){right=std::max(right,sx);bottom=std::max(bottom,sy);}
 if(bottom<0)return;
 const int sw=right+1,sh=bottom+1;
 std::vector<unsigned char> source(size_t(sw)*sh,255);
 for(int sy=0;sy<sh;++sy)for(int sx=0;sx<sw;++sx)
  source[size_t(sy)*sw+sx]=sample.get_pixel8(sx,sy);
 const auto fitted=korean_fit_pixels(source,sw,sh,width,height);
 auto* target=gw->get_win()->get_ib8();
 auto clip=target->SaveClip();
 auto r=clip.Rect().intersect(TileRect(x,y,width,height));
 target->set_clip(r.x,r.y,r.w,r.h);
 // The raw copy_transparent8 API treats palette 0 as transparent.
 // Our glyph raster uses 255 for transparency and 0 for opaque black.
 for(int yy=0;yy<fitted.height;++yy)for(int xx=0;xx<fitted.width;++xx){
  const auto colour=fitted.pixels[size_t(yy)*fitted.width+xx];
  if(colour!=255)target->put_pixel8(colour,x+xx,y+yy);
 }
}
'''
s=s.replace('class Strings : public GumpStrings {',helper+'\nclass Strings : public GumpStrings {',1)
s=s.replace('sman->paint_text_box(4, info, x + infox, y + infoy, infow, infoh);',
 'paint_save_information(info, x + infox, y + infoy, infow, infoh);')
s=s.replace('"%s: %i%s %s %04i\\n"','"%s: %04i-%02i-%02i\\n"')
old='''Strings::SaveCount(), details->save_count, Strings::Date(), details->real_day,
\t\t\t\tStrings::ordinal_numeral_suffix(details->real_day), Strings::month_Abbreviation(details->real_month - 1),
\t\t\t\tdetails->real_year, Strings::Time(), details->real_hour, details->real_minute'''
new='''Strings::SaveCount(), details->save_count, Strings::Date(), details->real_year,
                details->real_month, details->real_day, Strings::Time(), details->real_hour, details->real_minute'''
if old not in s:raise RuntimeError("Save date arguments changed")
s=s.replace(old,new,1)
for original,korean in {
 "Quick Save":"빠른 저장","Empty Slot":"빈 슬롯","No Info":"정보 없음",
 "Unreadable":"읽을 수 없는","Savegame":"저장 파일",
 "Okay to write over existing saved game?":"기존 저장 파일을 덮어쓰시겠습니까?",
 "Okay to delete saved game?":"저장 파일을 삭제하시겠습니까?"}.items():
 s=s.replace('"'+original+'"',korean_literal(original,korean))
p.write_text(s)
