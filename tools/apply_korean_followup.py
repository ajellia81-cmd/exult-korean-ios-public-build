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

# Keep ASCII-only rows in the same installed face as mixed Korean rows.
edit("shapes/font.h","public:\n    Font();",'''    bool native_ascii_override=false;
public:
    bool set_native_ascii_override(bool value){
        const bool old=native_ascii_override;native_ascii_override=value;return old;
    }
    Font();''')
edit("shapes/font.cc",
 "if(legacy_korean_layout_override)return true;",
 "if(native_ascii_override||legacy_korean_layout_override)return true;")

# Draw each save-info line at its native pixel size inside the skin panel.
# Date and time share one unambiguous ISO row; filenames and user names are never modified.
p=Path("upstream/gumps/Newfile_gump.cc");s=p.read_text()
s=s.replace('#include "touchui.h"','#include "touchui.h"\n#include "font.h"\n#include "ibuf8.h"\n#include "../shapes/korean_runtime_text.h"')
s=re.sub(r'(Newfile_gump::infoh\s*=\s*)92;',r'\g<1>79;',s)
helper=r'''
static void paint_save_information(const char* text,int x,int y,int width,int height){
 height=std::min(height,72); // Inner skin limit, leaving bottom margin.
 auto* gw=Game_window::get_instance();
 auto* sm=Shape_manager::get_instance();
 if(!legacy_korean_font_available()){
  sm->paint_text_box(4,text,x,y,width,height);return;
 }
 auto face=sm->get_font(4);
 struct Native_ascii_scope{
  Font& face;bool previous;
  ~Native_ascii_scope(){face.set_native_ascii_override(previous);}
 } native_ascii{*face,face->set_native_ascii_override(true)};
 struct Row{std::string text;int left=0,top=0,width=0,height=0;};
 std::vector<Row> rows;
 const std::string input=text?text:"";
 size_t start=0;
 while(start<input.size()){
  const auto end=input.find('\n',start);
  Row row;row.text=input.substr(start,end==std::string::npos?end:end-start);
  start=end==std::string::npos?input.size():end+1;
  if(row.text.empty())continue;
  face->get_text_ink_bounds(row.text.c_str(),row.left,row.top,row.width,row.height);
  if(row.width>width){
   std::string prefix=row.text;
   do{
    size_t last=0;
    for(size_t i=0;i<prefix.size();){last=i;i+=korean_text_pair(prefix.data()+i,prefix.size()-i)?2:1;}
    prefix.resize(last);row.text=prefix+"...";
    face->get_text_ink_bounds(row.text.c_str(),row.left,row.top,row.width,row.height);
   }while(!prefix.empty()&&row.width>width);
  }
  rows.push_back(std::move(row));
 }
 // Preserve native pixels. Measure each complete line, including bearings,
 // instead of resizing a raster or reflowing a mixed-script paragraph.
 int ink_height=0;for(const auto& row:rows)ink_height+=std::max(1,row.height);
 const int gap=rows.size()>1?std::min(1,std::max(0,(height-ink_height)/int(rows.size()-1))):0;
 auto* target=gw->get_win()->get_ib8();
 auto clip=target->SaveClip();
 auto r=clip.Rect().intersect(TileRect(x,y,width,height));
 target->set_clip(r.x,r.y,r.w,r.h);
 int pen=y;
 for(const auto& row:rows){
  if(pen+row.height>y+height)break;
  face->paint_text(target,row.text.c_str(),x-row.left,pen-row.top);
  pen+=std::max(1,row.height)+gap;
 }
}
'''
s=s.replace('class Strings : public GumpStrings {',helper+'\nclass Strings : public GumpStrings {',1)
s=s.replace('sman->paint_text_box(4, info, x + infox, y + infoy, infow, infoh);',
 'paint_save_information(info, x + infox, y + infoy, infow, infoh);')
# Share the game day/time row rather than spreading text down to the skin edge.
old_game='"%s: %i\\n"\n\t\t\t\t"%s: %02i:%02i\\n"'
if s.count(old_game)!=1:raise RuntimeError("Game time row anchor")
s=s.replace(old_game,'"%s: %i  %02i:%02i\\n"',1)
s=s.replace('Strings::GameDay(), details->game_day, Strings::GameTime(), details->game_hour, details->game_minute,',
            'Strings::GameDay(), details->game_day, details->game_hour, details->game_minute,',1)
old_date='"%s: %i%s %s %04i\\n"\n\t\t\t\t"%s: %02i:%02i"'
if s.count(old_date)!=1:raise RuntimeError("Save date format anchor changed")
s=s.replace(old_date,'"%04i-%02i-%02i %02i:%02i"',1)
old='''Strings::SaveCount(), details->save_count, Strings::Date(), details->real_day,
\t\t\t\tStrings::ordinal_numeral_suffix(details->real_day), Strings::month_Abbreviation(details->real_month - 1),
\t\t\t\tdetails->real_year, Strings::Time(), details->real_hour, details->real_minute'''
new='''Strings::SaveCount(), details->save_count, details->real_year,
                details->real_month, details->real_day, details->real_hour, details->real_minute'''
if old not in s:raise RuntimeError("Save date arguments changed")
s=s.replace(old,new,1)
for original,korean in {
 "Quick Save":"빠른 저장","Empty Slot":"빈 슬롯","No Info":"정보 없음",
 "Unreadable":"읽을 수 없는","Savegame":"저장 파일",
 "Okay to write over existing saved game?":"기존 저장 파일을 덮어쓰시겠습니까?",
 "Okay to delete saved game?":"저장 파일을 삭제하시겠습니까?"}.items():
 s=s.replace('"'+original+'"',korean_literal(original,korean))
p.write_text(s)
