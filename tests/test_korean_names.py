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
read=method(actors,'static std::vector<unsigned char> korean_initial_npcs(')
h=r'''
#include <algorithm>
#include <cassert>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include "korean_npc_names.h"
std::map<std::string,std::vector<unsigned char>> files;
bool U7exists(const char*p){return files.count(p);}
struct IFileDataSource {
 std::vector<unsigned char> data;
 IFileDataSource(const char*p,bool):data(files[p]){}
 bool good(){return true;}
 size_t getSize(){return data.size();}
 void read(unsigned char*p,size_t n){std::copy_n(data.begin(),n,p);}
};
'''+read+r'''
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
print("PASS: canonical BG/SI metadata, hash/bounds guards, Avatar/custom/localized names preserved, read-only Flex member access and display routes")
