"""Run cinematic typography/layout against production code with synthetic glyphs."""
from pathlib import Path
import runpy,subprocess,tempfile
base=runpy.run_path("tests/test_korean_followup.py")
method=base["method"]
font=Path("upstream/shapes/font.cc").read_text()
bg=Path("upstream/gamemgr/bggame.cc").read_text()
si=Path("upstream/gamemgr/sigame.cc").read_text()
h=base["harness"]
h=h[:h.rindex('int main(){')]
h=h.replace('#include <cstdio>','#include <cstdio>\n#include <cmath>\n#include <initializer_list>')
h=h.replace('Image_buffer8*get_ib8(){return this;}',
 '''void fill8(unsigned char c){std::fill(p.begin(),p.end(),c);}
 unsigned char get_pixel8(int x,int y){return p[size_t(y)*w+x];}
 Image_buffer8*get_ib8(){return this;}''')
h=h.replace('void paint_rle_remapped(int x,int y,unsigned char*)',
 '''void paint_rle(Image_buffer8*b,int x,int y){auto*old=active;active=b;paint_rle(x,y);active=old;}
 void paint_rle_remapped(int x,int y,unsigned char*)''')
h=h.replace('} fixture_font;',''' void prepare_cinematic_ascii();
 int center_text(Image_buffer8*,int,int,const char*,unsigned char* =nullptr);
 int get_text_width(const char*t){return native_width(t,-1);}
 int draw_text(Image_buffer8*b,int x,int y,const char*t,unsigned char*tr){return paint_text(b,t,x,y,tr);}
} fixture_font;''')
h=h.replace('Font*get_font(int n)', '''int caption_x=-1,caption_y=-1;
 void paint_shape(int x,int y,Shape_frame*){caption_x=x;caption_y=y;}
 Font*get_font(int n)''')
h=h.replace('bool legacy_korean_font_available(){return true;}',
 'bool korean_enabled=true;bool legacy_korean_font_available(){return korean_enabled;}')
h+=method(font,'void Font::prepare_cinematic_ascii(')
h+=method(font,'int Font::center_text(')
h+=method(bg,'static void paint_bg_intro_caption(')
h+=method(si,'static void paint_si_intro_lines(')
h+=r'''
void tall_hangul(){
 auto face=fixture_font.native_face;
 const int w=face->bitmap_width,oldh=face->bitmap_height;
 for(auto&v:face->glyphs)v.second.pixels.resize(size_t(w)*16,255);
 auto&g=face->glyphs[0xb0a1];g.left=0;g.top=0;g.right=6;g.bottom=11;
 for(int y=0;y<12;++y)for(int x=0;x<7;++x)g.pixels[size_t(y)*w+x]=(x==0||y==0||y==11)?0:255;
 face->bitmap_height=16;face->height=12;
}
void exercise(bool native_ascii){
 fixture_font.native_ascii_override=false;
 load_fixture("\xb0\xa1");tall_hangul();
 auto face=fixture_font.native_face;
 if(!native_ascii)for(unsigned c=32;c<127;++c)face->glyphs.erase(c);
 // A second colour represents original outline/foreground separation.
 fixture_font.font_shapes->frames['!'].p[1]=1;
 const auto before=face->glyphs[0xb0a1];
 int oldw=face->bitmap_width,oldh=face->bitmap_height;
 fixture_font.prepare_cinematic_ascii();
 assert(fixture_font.native_ascii_override);
 const auto&after=face->glyphs[0xb0a1];
 assert(after.x==before.x&&after.y==before.y&&after.advance==before.advance);
 for(int y=0;y<oldh;++y)for(int x=0;x<oldw;++x)
  assert(after.pixels[size_t(y)*face->bitmap_width+x]==before.pixels[size_t(y)*oldw+x]);
 for(unsigned c:std::string("!?.,:;\"'()-")){
  auto*g=face->get(c);assert(g&&g->right>=g->left);
  if(c=='!'||c=='?')assert(g->bottom-g->top+1>=10);
  assert(g->advance>g->x+g->right);
 }
 if(!native_ascii){
  auto*g=face->get('!');
  assert(std::find(g->pixels.begin(),g->pixels.end(),1)!=g->pixels.end());
  assert(std::find(g->pixels.begin(),g->pixels.end(),0)!=g->pixels.end());
 }
 auto*g=Game_window::get_instance();
 for(auto rows:{std::initializer_list<const char*>{"\xb0\xa1!"},
                std::initializer_list<const char*>{"\xb0\xa1!","\xb0\xa1?"},
                std::initializer_list<const char*>{"\xb0\xa1!","\xb0\xa1?","\xb0\xa1..."}}){
  fixture_font.calls.clear();
  std::shared_ptr<Font> f(&fixture_font,[](Font*){});
  paint_si_intro_lines(f,&g->target,100,100,187,rows);
  int bottom=0;
  for(const auto&row:fixture_font.calls){
   assert(row.top>=bottom&&row.top+row.height<=196);
   bottom=row.top+row.height;
  }
  assert(fixture_font.calls.size()==rows.size());
 }
}
int main(){
 exercise(false);exercise(true);
 // The choice bullet is code 127, with an explicit optical centre.
 auto face=fixture_font.native_face;
 assert(face->get(127));
 auto*bullet=face->get(127);auto*hangul=face->get(0xb0a1);
 assert(std::abs(bullet->y+bullet->top+(bullet->bottom-bullet->top)/2.0 -
                 (hangul->y+hangul->top+(hangul->bottom-hangul->top)/2.0))<=2);
 Shape_frame caption;caption.h=70;caption.above=0;
 auto*sm=Shape_manager::get_instance();
 paint_bg_intro_caption(sm,160,100,&caption);
 assert(sm->caption_y+caption.h-caption.above==196);
 caption.h=30;
 paint_bg_intro_caption(sm,160,100,&caption);
 assert(sm->caption_y==150);
 korean_enabled=false;caption.h=70;
 paint_bg_intro_caption(sm,160,100,&caption);
 assert(sm->caption_y==150);
}
'''
with tempfile.TemporaryDirectory() as folder:
 cpp=Path(folder)/"cinematic.cpp";binary=Path(folder)/"cinematic";cpp.write_text(h)
 subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined","-Iupstream/shapes",str(cpp),"-o",str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
assert font.count('font->prepare_cinematic_ascii();')==2
assert 'paint_bg_intro_caption(sman,centerx,centery,shapes.get_shape(0x15,0));' in bg
assert si.count('paint_si_intro_lines(sifont,ibuf,centerx,centery,')>=5
print("PASS: cinematic punctuation cap-height/baseline/spacing/palette, native Hangul preserved; BG bitmap captions and SI multiline blocks inside scene")

assert 'index!=8' in font
print("PASS: shared named/direct text routing, choice bullet included, ancient rune exceptions retained")
