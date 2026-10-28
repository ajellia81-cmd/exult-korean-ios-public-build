"""Exhaustive EUC-KR regression against the pinned upstream font map."""
import pathlib,subprocess,tempfile,json,os
s=pathlib.Path("upstream/shapes/font_map.cc").read_text()
a=s.index("static bool font_map_legacy_korean")
b=s.index("// Mode used by translate_usecode_text",a)
production=s[a:b]
original=subprocess.check_output(["git","-C","upstream","show","HEAD:shapes/font_map.cc"],text=True)
a=original.index("void translate_utf8_to_font_hex(")
b=original.index("// Mode used by translate_usecode_text",a)
baseline=original[a:b].replace("translate_utf8_to_font_hex","baseline_translate",1)
maps={"builtin":{},"original":{}}
section=None
for line in pathlib.Path("upstream/data/fonts/font_map.txt").read_text().splitlines():
    if line.startswith("%%section "): section=line.split()[1]
    elif line.startswith("%%endsection"): section=None
    elif section in maps and line.startswith(":") and "/" in line:
        key,val=line[1:].split("/",1)
        maps[section][bytes.fromhex(key)]=bytes([int(val,16)]) if section=="builtin" else val.encode()
def literal(b): return '"'+"".join("\\x%02x"%c for c in b)+'"'
init=""
for section,name in [("builtin","utf8_to_font_special"),("original","utf8_to_font_ascii")]:
    for k,v in maps[section].items(): init+=name+"["+literal(k)+"]="+literal(v)+";\n"
prefix=r'''
#include <string>
#include <string_view>
#include <unordered_map>
#include <iostream>
#include <vector>
#include <cassert>
#include <algorithm>
using std::size_t;
std::unordered_map<std::string,std::string> utf8_to_font_special,utf8_to_font_ascii;
void ensure_font_maps_loaded() {}
'''
main=r'''
int main(){
 INIT
 std::vector<std::string> glyphs;
 std::vector<int> damaged;
 for(int lead=0xb0;lead<=0xc8;++lead) for(int trail=0xa1;trail<=0xfe;++trail) {
  std::string g;g+=static_cast<char>(lead);g+=static_cast<char>(trail);glyphs.push_back(g);
 }
 assert(glyphs.size()==2350);
 set_font_map_legacy_korean(true);
 for(int i=0;i<2350;++i) {
  bool old_bad=false;
  for(bool mode:{false,true}) {
   std::string old=glyphs[i];baseline_translate(old,mode);
   old_bad=old_bad || old!=glyphs[i];
   for(const auto& raw : {glyphs[i],std::string("\"")+glyphs[i]+"!?\"",std::string("^")+glyphs[i]+"\n"+glyphs[i]}) {
    auto copy=raw;translate_utf8_to_font_hex(copy,mode);assert(copy==raw);
   }
   for(int c=32;c<127;++c){
    auto raw=std::string(1,char(c))+glyphs[i]+std::string(1,char(c));
    auto copy=raw;translate_utf8_to_font_hex(copy,mode);assert(copy==raw);
   }
  }
  if(old_bad) damaged.push_back(i);
 }
 long long combinations=0, old_pair_damage=0, boundary_only=0;
 std::vector<int> boundary_first;
 std::vector<std::pair<int,int>> boundary_examples;
 int first_index=-1;
 for(const auto& first:glyphs) { ++first_index; int second_index=-1;
 for(const auto& second:glyphs) { ++second_index;
  const auto raw=first+second;
  bool old_bad=false, singles_ok=true;
  for(bool mode:{false,true}){
   auto prior=raw;baseline_translate(prior,mode);old_bad=old_bad || prior!=raw;
   auto a=first,b=second;baseline_translate(a,mode);baseline_translate(b,mode);
   singles_ok=singles_ok && a==first && b==second;
  }
  if(old_bad)++old_pair_damage;
  if(old_bad && singles_ok){
   ++boundary_only;
   if(std::find(boundary_first.begin(),boundary_first.end(),first_index)==boundary_first.end())boundary_first.push_back(first_index);
   if(boundary_examples.size()<8)boundary_examples.emplace_back(first_index,second_index);
  }
  for(bool mode:{false,true}) { auto copy=raw;translate_utf8_to_font_hex(copy,mode);assert(copy==raw); }
  ++combinations;
 }}
 // A malformed pair must not be accepted as complete Korean text.
 assert(!is_legacy_korean_text(std::string("\xb0",1)));
 assert(!is_legacy_korean_text(std::string("\xb0" "A",2)));
 assert(!is_legacy_korean_text("ASCII"));
 for(bool mode:{false,true}) {
  const auto& map=mode?utf8_to_font_special:utf8_to_font_ascii;
  set_font_map_legacy_korean(false);
  for(const auto& entry:map){
   auto copy=entry.first;translate_utf8_to_font_hex(copy,mode);assert(copy==entry.second);
  }
 }
 std::cout<<"{\"glyphs\":2350,\"ordered_pairs\":"<<combinations<<",\"map_modes\":2,\"damaged_indices\":[";
 for(size_t i=0;i<damaged.size();++i){if(i)std::cout<<",";std::cout<<damaged[i];}
 std::cout<<"],\"previously_corrupted_pairs\":"<<old_pair_damage<<",\"boundary_only_pairs\":"<<boundary_only<<",\"boundary_first_indices\":[";
 for(size_t i=0;i<boundary_first.size();++i){if(i)std::cout<<",";std::cout<<boundary_first[i];}
 std::cout<<"],\"boundary_examples\":[";
 for(size_t i=0;i<boundary_examples.size();++i){if(i)std::cout<<",";std::cout<<"["<<boundary_examples[i].first<<","<<boundary_examples[i].second<<"]";}
 std::cout<<"]}\n";
}
'''
main=main.replace(" INIT",init)
with tempfile.TemporaryDirectory() as d:
    cpp=pathlib.Path(d)/"encoding.cc";exe=pathlib.Path(d)/"encoding"
    cpp.write_text(prefix+production+baseline+main)
    subprocess.run(["clang++","-O2","-std=c++17","-fsanitize=address,undefined",str(cpp),"-o",str(exe)],check=True)
    result=json.loads(subprocess.check_output([str(exe)],text=True))
result["previously_corrupted_characters"]="".join(bytes((0xb0+i//94,0xa1+i%94)).decode("euc_kr") for i in result.pop("damaged_indices"))
result["previously_corrupted_count"]=len(result["previously_corrupted_characters"])
def syllable(i): return bytes((0xb0+i//94,0xa1+i%94)).decode("euc_kr")
result["boundary_vulnerable_characters"]="".join(syllable(i) for i in result.pop("boundary_first_indices"))
result["boundary_vulnerable_character_count"]=len(result["boundary_vulnerable_characters"])
result["boundary_examples"]=["".join(syllable(i) for i in pair) for pair in result["boundary_examples"]]
result["unsupported_cp949_hangul"]=sum(not(0xb0<=c.encode("cp949")[0]<=0xc8 and 0xa1<=c.encode("cp949")[1]<=0xfe) for c in map(chr,range(0xac00,0xd7a4)))
pathlib.Path("korean-audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
summary=os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary,"a") as f:f.write("## Korean encoding audit\n\n"+json.dumps(result,ensure_ascii=False,indent=2)+"\n")
