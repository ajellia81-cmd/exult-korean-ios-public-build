"""Synthetic-only coverage for installed canonical NPC display labels."""
from pathlib import Path
import subprocess,tempfile
def method(s,start):
 a=s.index(start);b=s.index("{",a);depth=0
 for i in range(b,len(s)):
  if s[i]=="{":depth+=1
  elif s[i]=="}":
   depth-=1
   if not depth:return s[a:i+1]
 raise RuntimeError(start)
actors=Path("upstream/actors.cc").read_text()
objects=Path("upstream/objs/objnames.cc").read_text()
assert 'return !get_flag(Obj_flags::met) ? Game_object::get_name() : get_npc_name();' in actors
assert 'korean_actor_display_name(npc_num,name)' in actors
assert 'npc->get_npc_name_string()' not in objects
assert 'npc->get_npc_name()' in objects
itemmenu=Path('upstream/gumps/ItemMenu_gump.cc').read_text()
layout=method(itemmenu,'void Itemmenu_gump::fix_position(')
read=method(actors,'static std::vector<unsigned char> korean_initial_npcs(')
h=r'''
#include <algorithm>
#include <cassert>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include "korean_npc_names.h"
struct TileRect{int x,y,w,h;};
struct Game_window{
 int width=320,height=200;
 static Game_window* get_instance(){static Game_window win;return &win;}
 int get_width(){return width;} int get_height(){return height;}
};
struct Itemmenu_gump{
 int x=0,y=0,width=66,height=88;
 TileRect get_rect(){return {x+10,y,width,height};}
 void fix_position(int num_elements);
};
std::map<std::string,std::vector<unsigned char>> files;
bool U7exists(const char*p){return files.count(p);}
class IDataSource {};
struct IFileDataSource : public IDataSource {
 std::vector<unsigned char> data;
 IFileDataSource(const char*p,bool):data(files[p]){}
 bool good(){return true;}
 size_t getSize(){return data.size();}
 void read(unsigned char*p,size_t n){std::copy_n(data.begin(),n,p);}
};
'''+layout+('\n#ifdef HAVE_ZIP_SUPPORT\n#include "files/zip/unzip.h"\n#endif\n')+read+r'''
void u32(std::vector<unsigned char>&b,size_t p,unsigned n){
 for(unsigned i=0;i<4;++i)b[p+i]=(n>>(8*i))&255;
}
int main(){
 std::vector<unsigned char> source(48,0),target(48,0);
 const std::string en="NameOne",ko="\xb0\xa1\xb0\xa2";
 std::copy(en.begin(),en.end(),source.begin()+4);
 std::copy(ko.begin(),ko.end(),target.begin()+8);
 const Korean_name_entry entries[]={{1,4,8,7,4},{0,4,8,7,4},{2,99,8,7,4},{3,4,99,7,4}};
 auto names=korean_index_names(source,target,korean_name_hash(source),korean_name_hash(target),entries,4);
 assert(names.size()==1);
 assert(korean_resolve_name(names,1,en)==ko);
 assert(korean_resolve_name(names,0,en)==en);
 assert(korean_resolve_name(names,2,en)==en);
 assert(korean_resolve_name(names,1,"Renamed")=="Renamed");
 assert(korean_resolve_name(names,1,ko)==ko);
 assert(korean_index_names(source,target,0,korean_name_hash(target),entries,4).empty());
 auto original_source=source,original_target=target;
 assert(korean_resolve_name(names,1,en)==ko);
 assert(source==original_source&&target==original_target);

 Korean_name_map reviewed;
 korean_apply_reviewed_names(reviewed,true);
 assert(reviewed.size()==22);
 assert(korean_name_high(korean_resolve_name(reviewed,278,"Davros Illomen")));
 assert(korean_resolve_name(reviewed,278,"Custom")=="Custom");
 assert(korean_resolve_name(reviewed,0,"Doug")=="Doug");
 assert(korean_resolve_name(reviewed,231,"Larry")=="Larry");
 reviewed.clear();korean_apply_reviewed_names(reviewed,false);
 assert(reviewed.size()==21);
 assert(korean_name_high(korean_resolve_name(reviewed,258,"steve_powers")));
 assert(korean_resolve_name(reviewed,257,"Doug")=="Doug"); // game separation
 std::map<std::string,std::string> terms={{"Abraham",ko},{"Meryl",ko}};
 korean_reuse_names(reviewed,source,terms,false);
 assert(korean_resolve_name(reviewed,299,"Abraham")==ko);
 assert(korean_resolve_name(reviewed,234,"Meryl")==ko);
 assert(korean_reference_text(target,korean_name_hash(target),8,4)==ko);
 assert(korean_reference_text(target,0,8,4).empty());
 assert(korean_reference_text(target,korean_name_hash(target),99,4).empty());
 // Real production placement, including a translated button wider than
 // the former fixed 100px estimate, at each screen edge.
 for(int width:{66,100,180,300})for(int height:{22,88,176})
  for(int px:{-200,0,240,500})for(int py:{-80,0,160,300}){
   Itemmenu_gump menu;menu.x=px;menu.y=py;menu.width=width;menu.height=height;
   menu.fix_position(4);const auto rect=menu.get_rect();
   assert(rect.x>=0&&rect.y>=0&&rect.x+rect.w<=320&&rect.y+rect.h<=200);
  }

 // Flex archive reading is bounded and read-only, also when the NPC member
 // is not the first member or malformed table entries precede it.
 std::vector<unsigned char> flex(256,0);
 u32(flex,84,2);u32(flex,128,999);u32(flex,132,64);
 u32(flex,136,176);u32(flex,140,13+target.size());
 std::memcpy(flex.data()+176,"npc.dat",8);
 std::copy(target.begin(),target.end(),flex.begin()+189);
 files["fixture"]=flex;
 assert(korean_initial_npcs("fixture")==target);
 assert(files["fixture"]==flex);
 assert(korean_initial_npcs("missing").empty());
 u32(files["fixture"],84,0xffffffff);
 assert(korean_initial_npcs("fixture").empty());
 for(const auto& e:korean_blackgate_names)assert(e.npc>0);
 for(const auto& e:korean_serpentisle_names)assert(e.npc>0);
}
'''
with tempfile.TemporaryDirectory() as folder:
 cpp=Path(folder)/"names.cpp";binary=Path(folder)/"names";cpp.write_text(h)
 subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined","-Iupstream/shapes",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
 subprocess.run(["clang++","-std=c++17","-DHAVE_ZIP_SUPPORT","-fsyntax-only","-Iupstream","-Iupstream/shapes",str(cpp)],check=True)
print("PASS: canonical BG/SI metadata, hash/bounds guards, Avatar/custom/localized names preserved, read-only Flex member access and display routes")
