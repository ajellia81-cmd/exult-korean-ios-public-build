"""Exercise the production Korean_font class using synthetic, non-font bitmap data."""
import pathlib, subprocess, tempfile
source = pathlib.Path("upstream/shapes/font.cc").read_text()
start = source.index("static bool legacy_korean_font_enabled")
end = source.index("static unsigned char korean_ink_colour", start)
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

struct Shape_frame {
 static Image_buffer8* screen;
 std::vector<unsigned char> pixels; int w,h;
 Shape_frame(unsigned char* p,int w_,int h_,int,int,bool):pixels(p,p+w_*h_),w(w_),h(h_){}
 void paint_rle(int x,int y) { paint_rle_remapped(x,y,nullptr); }
 void paint_rle_remapped(int x,int y,unsigned char* trans) {
  for(int r=0;r<h;++r) for(int c=0;c<w;++c)
   if(pixels[r*w+c]!=255) screen->put_pixel8(trans?trans[pixels[r*w+c]]:pixels[r*w+c],x+c,y+r);
 }
};
Image_buffer8* Shape_frame::screen=nullptr;

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
 assert(korean_font.width()==13 && korean_font.height()==7);
 assert(!korean_font.is_pair(first,1));
 assert(!korean_font.is_pair("\xb0\0",2));
 assert(!korean_font.is_pair("\xcf\xa1",2));
 Image_buffer8 image;
 Shape_frame::screen=&image;
 std::fill(std::begin(image.pixels),std::end(image.pixels),7);
 korean_font.paint(&image,2,4,first,nullptr);
 assert(image.pixels[5*64+3]==1 && image.pixels[5*64+11]==1);
 assert(image.pixels[4*64+2]==0); // Outline at padded corner.
 assert(image.pixels[5*64+4]==0); // Border beside first stroke.
 assert(image.pixels[5*64+6]==7); // Transparent gap preserves background.
 unsigned char trans[256]={};trans[1]=42;
 korean_font.paint(&image,2,4,first,trans);
 assert(image.pixels[5*64+3]==42);
 korean_font.paint(&image,2,4,last,nullptr);
 assert(image.pixels[7*64+11]==1); // Last glyph and padded row stride.
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
 assert(korean_font.width()==20 && korean_font.height()==20);
 std::cout<<"PASS: production loader/renderer synthetic regression checks\n";
}
'''
with tempfile.TemporaryDirectory() as d:
    cpp = pathlib.Path(d)/"font-test.cc"
    exe = pathlib.Path(d)/"font-test"
    cpp.write_text(prefix+production+tests)
    subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined","-g",str(cpp),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
