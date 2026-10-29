"""Compile production font drawing/measurement paths and test every Hangul glyph."""
import ast,pathlib,subprocess,tempfile
s=pathlib.Path("upstream/shapes/font.cc").read_text()
def function(start):
    a=s.index(start);brace=s.index("{",a);depth=0
    for i in range(brace,len(s)):
        if s[i]=="{":depth+=1
        elif s[i]=="}":
            depth-=1
            if depth==0:return s[a:i+1]
    raise ValueError(start)
def overloads(start):
    out=[];offset=0
    while True:
        a=s.find(start,offset)
        if a<0:return out
        # Reuse brace matching in the selected suffix.
        brace=s.index("{",a);depth=0
        for i in range(brace,len(s)):
            if s[i]=="{":depth+=1
            elif s[i]=="}":
                depth-=1
                if depth==0:
                    out.append(s[a:i+1]);offset=i+1;break
tree=ast.parse(pathlib.Path("tests/test_korean_font.py").read_text())
prefix=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="prefix" for t in n.targets))
prefix=prefix.replace("#include <cassert>","#include <cassert>\n#include <algorithm>\n#include <memory>\n#include <cmath>")
prefix=prefix.replace(" unsigned char pixels[64*64]={};",''' unsigned char pixels[64*64]={};
 Image_buffer8()=default;
 Image_buffer8(int,int){}
 void fill8(unsigned char c){std::fill(std::begin(pixels),std::end(pixels),c);}
 unsigned char get_pixel8(int x,int y){return pixels[y*64+x];}
''')
prefix=prefix.replace(" static Image_buffer8* screen;",''' static Image_buffer8* screen;
 Shape_frame():pixels({0,0,0,0,1,0,0,0,0}),w(3),h(3){}
 bool is_rle(){return true;}
 int get_width(){return w;} int get_height(){return h;}
 int get_xleft(){return 0;} int get_yabove(){return 0;}
 void paint_rle(Image_buffer8* target,int x,int y){
  auto old=screen;screen=target;paint_rle(x,y);screen=old;
 }
''')
prefix += pathlib.Path("tools/korean_patch_font.h").read_text()
prefix += "\nbool korean_patch_pack_present(){return false;}\n"
prefix+=r'''
struct Shape_file {
 Shape_frame ascii; int high_requests=0;
 Shape_frame* get_frame(unsigned c){
  if(c>=128)++high_requests;
  return c=='\n'||c==0?nullptr:&ascii;
 }
};
struct Palette {
 unsigned char get_red(int c)const{return c==1?63:0;}
 unsigned char get_green(int c)const{return c==1?63:0;}
 unsigned char get_blue(int c)const{return c==1?63:0;}
};
struct Game_window {
 Palette pal;
 static Game_window* get_instance(){static Game_window g;return &g;}
 Palette* get_pal(){return &pal;}
};
template<typename T> void ignore_unused_variable_warning(const T&){}
struct Font {
 std::shared_ptr<KoreanPatchFont> native_face;
 bool native_style(const char*,int);
 int native_width(const char*,int,int=0);
 int native_draw(Image_buffer8*,const char*,int,int,int,unsigned char*,int=0);
 void native_bounds(const char*,int&,int&,int&,int&);

 std::unique_ptr<Shape_file> font_shapes=std::make_unique<Shape_file>();
 bool legacy_korean_layout_override=false;
 int highest=10,lowest=3,hor_lead=-1,ver_lead=0;
 int paint_text(Image_buffer8*,const char*,int,int,unsigned char* =nullptr);
 int paint_text(Image_buffer8*,const char*,int,int,int,unsigned char* =nullptr);
 int paint_text_fixedwidth(Image_buffer8*,const char*,int,int,int,unsigned char* =nullptr);
 int paint_text_fixedwidth(Image_buffer8*,const char*,int,int,int,int,unsigned char* =nullptr);
 int get_text_width(const char*);
 int get_text_width(const char*,int);
 void get_text_box_dims(const char*,int&,int&,int=0);
 int find_xcursor(const char*,int,int);
 int get_text_edge_padding(const char*);
 void get_text_ink_bounds(const char*,int&,int&,int&,int&);
 int get_text_height();
 int get_text_height(const char*,int=-1);
 int get_text_baseline();
 int get_text_baseline(const char*,int=-1);
};
'''
a=s.index("static bool legacy_korean_font_enabled");b=s.index("//\tWant a more restrictive",a)
production=s[a:b]
for name in ["int Font::paint_text(","int Font::paint_text_fixedwidth(","int Font::get_text_width(","void Font::get_text_box_dims(","int Font::find_xcursor(","int Font::get_text_height(","int Font::get_text_baseline("]:
    production+="\n"+"\n".join(overloads(name))
production += "\n" + function("void Font::get_text_ink_bounds(")
production += "\n" + function("int Font::get_text_edge_padding(")
for method in ("bool Font::native_style(", "int Font::native_width(", "int Font::native_draw(", "void Font::native_bounds("):
    production += "\n" + function(method)
tests=r'''
int main(){
 constexpr int gw=11,gh=11,stride=2,size=stride*gh;
 std::vector<unsigned char> data(4+2350*size,0);
 data[2]=gw;data[3]=gh;
 for(int i=0;i<2350;++i){
  for(int bit=0;bit<12;++bit)if(i&(1<<bit)){
   const int x=bit%gw,y=bit/gw;
   data[4+i*size+y*stride+x/8]|=0x80>>(x%8);
  }
  data[4+i*size+2*stride]|=0x80; // Nonempty even for index 0.
 }
 files["data"]=data;
 set_legacy_korean_font_enabled(true);
 Font f;Image_buffer8 image;Shape_frame::screen=&image;
 const int advance=korean_font.width()-1;
 assert(advance==14);
 int checked=0;
 for(int i=0;i<2350;++i){
  std::string raw;raw+=char(0xb0+i/94);raw+=char(0xa1+i%94);
  assert(f.get_text_width(raw.c_str())==advance);
  assert(f.get_text_width(raw.data(),2)==advance);
  int il,it,iw,ih; f.get_text_ink_bounds(raw.c_str(),il,it,iw,ih);
  auto validate=[&](){
   for(int bit=0;bit<12;++bit){
    const int x=bit%gw,y=bit/gw;
    assert((image.pixels[(1+y)*64+1+x]==1)==bool(i&(1<<bit)));
   }
   assert(image.pixels[3*64+1]==1);
   for(int yy=0;yy<32;++yy)for(int xx=0;xx<32;++xx)
    if(image.pixels[yy*64+xx]!=7)
     assert(xx>=il&&xx<il+iw&&yy>=it&&yy<it+ih);
  };
  image.fill8(7);assert(f.paint_text(&image,raw.c_str(),0,0)==advance);validate();
  image.fill8(7);assert(f.paint_text(&image,raw.data(),2,0,0)==advance);validate();
  // Fixed width consumes both bytes and paints one glyph at the same origin.
  image.fill8(7);assert(f.paint_text_fixedwidth(&image,raw.c_str(),0,0,7)==15);validate();
  image.fill8(7);assert(f.paint_text_fixedwidth(&image,raw.data(),2,0,0,7)==15);validate();
  int w,h;f.get_text_box_dims(raw.c_str(),w,h);assert(w==advance&&h==f.get_text_height(raw.c_str()));
  for(int x=0;x<advance;++x)assert(f.find_xcursor(raw.data(),2,x)==0);
  assert(f.find_xcursor(raw.data(),2,advance)==-1);
  assert(korean_fixed_text_width(raw.data(),2,7)==15);
  auto mixed=std::string("\"")+raw+"!?\"";
  assert(f.get_text_width(mixed.c_str())==advance+16);
  assert(f.find_xcursor(mixed.data(),int(mixed.size()),4)==1);
  ++checked;
 }

 // Rounded noninteger scaling must retain all source edge strokes.
 // Cover every width/height, including 2->2 and 6->7.
 {
  auto& source=f.font_shapes->ascii;
  const auto saved=source.pixels;
  const int savedw=source.w,savedh=source.h;
  for(int sw=1;sw<=12;++sw)for(int sh=1;sh<=12;++sh){
   source.w=sw;source.h=sh;source.pixels.assign(sw*sh,255);
   for(int yy=0;yy<sh;++yy)for(int xx=0;xx<sw;++xx)
    if(xx==0||xx==sw-1||yy==0||yy==sh-1||(xx+yy)%3==0)
     source.pixels[yy*sw+xx]=1;
   Korean_ascii_glyph glyph(&source,-1,0);
   const int dw=std::max(1,int(std::lround(sw*11.0/9.0)));
   const int dh=std::max(1,int(std::lround(sh*11.0/9.0)));
   for(int yy=0;yy<dh;++yy)for(int xx=0;xx<dw;++xx){
    const bool expected=source.pixels[(yy*sh/dh)*sw+xx*sw/dw]==1;
    assert((glyph.pixels[(yy+1)*glyph.w+xx+1]==1)==expected);
   }
   assert(glyph.xleft<=0);
   int right=-1;
   for(int yy=0;yy<glyph.h;++yy)for(int xx=0;xx<glyph.w;++xx)
    if(glyph.pixels[yy*glyph.w+xx]!=255)right=std::max(right,xx-glyph.xleft);
   assert(glyph.advance()>right);
  }
  source.pixels=saved;source.w=savedw;source.h=savedh;
 }

 assert(f.font_shapes->high_requests==0);
 {
  auto& source=f.font_shapes->ascii;
  const auto saved=source.pixels;
  std::fill(source.pixels.begin(),source.pixels.end(),0);
  bool previous=set_legacy_korean_button_bold(true);
  Korean_ascii_glyph digit(&source,-1,0);
  assert(digit.yabove==12-(11-4)/2);
  set_legacy_korean_button_bold(previous);
  Korean_ascii_glyph ordinary(&source,-1,0);
  assert(ordinary.yabove==1); // Dialogue/other paths retain the original origin.
  source.pixels=saved;
 }
 const std::string multi=std::string("\xb0\xa1")+"\n"+"\xc8\xfe";
 int w,h;f.get_text_box_dims(multi.c_str(),w,h);assert(w==advance&&h==2*f.get_text_height(multi.c_str()));
 assert(f.get_text_baseline(multi.c_str())==12); // Ink bottom precedes baseline; shadow fits below.
 assert(f.get_text_height(multi.c_str())>=15);
 for(int highest=4;highest<20;++highest)for(int lowest=0;lowest<5;++lowest){
  f.highest=highest;f.lowest=lowest;
  for(const auto* menu:{"Video Options","UI Options","Audio Options","Game Engine","Game Display","Game Input","Save","Load","Inventory","Yes","No"}){
   assert(f.get_text_height()==highest+lowest+1);
   assert(f.get_text_height(menu)==highest+lowest+1);
   assert(f.get_text_baseline()==highest);
   assert(f.get_text_baseline(menu)==highest);
  }
 }

 std::cout<<"PASS: "<<checked<<" glyph indices, four paint paths, two width paths, multiline dimensions, fixed-width layout, and cursor boundaries\n";
}
'''
with tempfile.TemporaryDirectory() as d:
    cpp=pathlib.Path(d)/"paths.cc";exe=pathlib.Path(d)/"paths"
    cpp.write_text(prefix+production+tests)
    subprocess.run(["clang++","-O1","-std=c++17","-fsanitize=address,undefined",str(cpp),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
