"""Exercise the production Korean_font class using synthetic, non-font bitmap data."""
import pathlib, subprocess, tempfile
source = pathlib.Path("upstream/shapes/font.cc").read_text()
start = source.index("static bool legacy_korean_font_enabled")
end = source.index("//\tWant a more restrictive", start)
production = source[start:end]
prefix = r'''
#include <cassert>
#include <cstring>
#include <iostream>
#include <map>
#include <string>
#include <vector>
using std::size_t;
#define PATCH_KOREAN_FONT "patch"
#define STATIC_KOREAN_FONT "static"
#define KOREAN_FONT "data"
std::map<std::string, std::vector<unsigned char>> files;
std::string get_system_path(const char* p) { return p; }
bool U7exists(const char* p) { return files.count(p); }
struct IFileDataSource {
 const std::vector<unsigned char>& b; size_t pos=0; bool ok=true;
 IFileDataSource(const char* p): b(files.at(p)) {}
 bool good() const { return ok; }
 size_t getSize() const { return b.size(); }
 size_t getAvail() const { return pos<=b.size()?b.size()-pos:0; }
 void skip(size_t n) { pos+=n; }
 unsigned read1() { if(pos>=b.size()){ok=false;return 0;} return b[pos++]; }
 void read(void* p,size_t n) { if(getAvail()<n){ok=false;return;} std::memcpy(p,b.data()+pos,n);pos+=n; }
};
struct Image_buffer8 {
 unsigned char pixels[64*64]={};
 void put_pixel8(unsigned char c,int x,int y) {
  if(x>=0 && x<64 && y>=0 && y<64) pixels[y*64+x]=c;
 }
};
'''
tests = r'''
std::vector<unsigned char> fixture(int w=9,int h=3) {
 std::vector<unsigned char> b(4+2350*((w+7)/8)*h,0);
 b[2]=w;b[3]=h;b[4]=0x80;b[5]=0x80;b.back()=0x80;
 return b;
}
int main() {
 const char first[]="\xb0\xa1",last[]="\xc8\xfe";
 assert(!korean_font.is_pair("A",1));
 assert(!korean_font.is_pair(first,2)); // Menu before DATA is available.
 files["data"]=fixture();
 set_legacy_korean_font_enabled(true);
 assert(korean_font.is_pair(first,2));
 assert(korean_font.width()==9 && korean_font.height()==3);
 assert(!korean_font.is_pair(first,1));
 assert(!korean_font.is_pair("\xb0\0",2));
 assert(!korean_font.is_pair("\xcf\xa1",2));
 Image_buffer8 image;
 korean_font.paint(&image,2,4,first,nullptr);
 assert(image.pixels[4*64+2]==255 && image.pixels[4*64+10]==255);
 assert(image.pixels[4*64+3]==0);
 unsigned char trans[256]={};trans[255]=42;
 korean_font.paint(&image,2,4,first,trans);
 assert(image.pixels[4*64+2]==42);
 korean_font.paint(&image,2,4,last,nullptr);
 assert(image.pixels[6*64+10]==255); // Last glyph and padded row stride.
 set_legacy_korean_font_enabled(false);
 assert(!korean_font.is_pair(first,2));
 set_legacy_korean_font_enabled(true);
 files["patch"]={0,0,9}; // Short header falls through.
 assert(korean_font.is_pair(first,2));
 for (auto malformed : {std::vector<unsigned char>{0,0,0,3},
                        std::vector<unsigned char>{0,0,33,3},
                        std::vector<unsigned char>{0,0,9,3,0}}) {
  files.clear();files["data"]=malformed;
  set_legacy_korean_font_enabled(true);
  assert(!korean_font.is_pair(first,2));
 }
 files["data"]=fixture();files["data"].push_back(0);
 set_legacy_korean_font_enabled(true);
 assert(!korean_font.is_pair(first,2));
 files["data"]=fixture();
 std::fill(files["data"].begin()+4,files["data"].end(),0);
 set_legacy_korean_font_enabled(true);
 assert(!korean_font.is_pair(first,2));
 files["data"]=fixture(16,16);
 set_legacy_korean_font_enabled(true);
 assert(korean_font.is_pair(first,2));
 assert(korean_font.width()==16 && korean_font.height()==16);
 std::cout<<"PASS: production loader/renderer synthetic regression checks\n";
}
'''
with tempfile.TemporaryDirectory() as d:
    cpp = pathlib.Path(d)/"font-test.cc"
    exe = pathlib.Path(d)/"font-test"
    cpp.write_text(prefix+production+tests)
    subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined","-g",str(cpp),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
