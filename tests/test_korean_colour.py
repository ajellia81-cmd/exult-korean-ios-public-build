"""Check selection of text ink instead of outline using production code."""
import pathlib, subprocess, tempfile
s = pathlib.Path("upstream/shapes/font.cc").read_text()
a = s.index("static unsigned char korean_ink_colour")
b = s.index("struct Korean_ascii_glyph", a)
helper = s[a:b]
prefix = r'''
#include <vector>
#include <algorithm>
#include <cassert>
struct Image_buffer8 {
 int w,h; std::vector<unsigned char> p;
 Image_buffer8(int w_,int h_):w(w_),h(h_),p(w_*h_){}
 void fill8(unsigned char c){std::fill(p.begin(),p.end(),c);}
 unsigned char get_pixel8(int x,int y){return p[y*w+x];}
};
struct Palette {
 unsigned char get_red(int c)const {return c==14?63:0;}
 unsigned char get_green(int c)const {return c==14?50:0;}
 unsigned char get_blue(int)const {return 0;}
};
struct Game_window {
 Palette pal;
 static Game_window* get_instance(){static Game_window g;return &g;}
 Palette* get_pal(){return &pal;}
};
struct Shape_frame {
 bool valid=true;
 std::vector<unsigned char> pixels={1,1,1,1,14,1,1,1,255};
 bool is_rle(){return valid;}
 int get_width(){return 3;}
 int get_height(){return 3;}
 int get_xleft(){return 0;}
 int get_yabove(){return 0;}
 void paint_rle(Image_buffer8* p,int,int){p->p=pixels;}
};
struct Shape_file {
 Shape_frame frame;
 Shape_frame* get_frame(int){return &frame;}
};
'''
tests = r'''
int main(){
 Shape_file f;
 assert(korean_ink_colour(&f)==14);
 assert(korean_ink_colour(&f,true)==1);
 f.frame.pixels.assign(9,1);
 assert(korean_ink_colour(&f)==1);
 f.frame.pixels.assign(9,255);
 assert(korean_ink_colour(&f)==1);
 f.frame.valid=false;
 assert(korean_ink_colour(&f)==1);
}
'''
with tempfile.TemporaryDirectory() as d:
    cpp=pathlib.Path(d)/"colour.cc"
    exe=pathlib.Path(d)/"colour"
    cpp.write_text(prefix+helper+tests)
    subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined",str(cpp),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print("PASS: outline, golden foreground, monochrome and empty reference")
