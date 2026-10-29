"""Match cinematic punctuation metrics and retain the full intro caption frame."""
from pathlib import Path
import re
def edit(path,before,after):
 p=Path("upstream")/path;s=p.read_text()
 if s.count(before)!=1:raise RuntimeError(f"{path}: anchor count {s.count(before)} {before[:70]!r}")
 p.write_text(s.replace(before,after,1))
edit("shapes/font.h","    Font();","    void prepare_cinematic_ascii();\n    Font();")
prepare=r'''
void Font::prepare_cinematic_ascii(){
 if(!native_face||!font_shapes)return;
 const auto* hangul=native_face->get(0xb0a1);
 auto* cap=font_shapes->get_frame('H');
 if(!hangul||hangul->bottom<hangul->top||!cap||!cap->is_rle())return;
 const int target_height=hangul->bottom-hangul->top+1;
 const int target_top=hangul->y+hangul->top;
 const int legacy_cap_top=highest-cap->get_yabove();
 const auto* native_cap=native_face->get('H');
 const int oldw=native_face->bitmap_width,oldh=native_face->bitmap_height;
 int neww=oldw,newh=oldh;
 struct Raster{KoreanPatchFont::Glyph glyph;int w,h;};
 std::map<unsigned,Raster> generated;
 for(unsigned code=32;code<127;++code){
  const auto* original=native_face->get(code);
  auto* frame=font_shapes->get_frame(code);
  if(!original&&(!frame||!frame->is_rle()))continue;
  int sw,sh,ox,oy,advance,cap_top,cap_height;
  std::vector<unsigned char> source;
  if(original){
   sw=oldw;sh=oldh;ox=original->x;oy=original->y;advance=original->advance;source=original->pixels;
   cap_top=native_cap?native_cap->y+native_cap->top:target_top;
   cap_height=native_cap?native_cap->bottom-native_cap->top+1:target_height;
  }else{
   sw=frame->get_width();sh=frame->get_height();ox=-frame->get_xleft();oy=highest-frame->get_yabove();
   advance=std::max(1,sw+hor_lead);cap_top=legacy_cap_top;cap_height=cap->get_height();
   Image_buffer8 sample(sw,sh);sample.fill8(255);
   frame->paint_rle(&sample,frame->get_xleft(),frame->get_yabove());
   source.resize(size_t(sw)*sh);
   for(int y=0;y<sh;++y)for(int x=0;x<sw;++x)source[size_t(y)*sw+x]=sample.get_pixel8(x,y);
  }
  const double scale=std::clamp(double(target_height)/std::max(1,cap_height),1.0,4.0);
  const int w=std::max(1,int(std::lround(sw*scale))),h=std::max(1,int(std::lround(sh*scale)));
  Raster raster;raster.w=w;raster.h=h;
  auto& g=raster.glyph;
  g.x=int(std::lround(ox*scale));g.y=target_top+int(std::lround((oy-cap_top)*scale));
  g.advance=std::max(1,int(std::lround(advance*scale)));
  g.pixels.assign(size_t(w)*h,255);g.left=w;g.top=h;g.right=g.bottom=-1;
  for(int y=0;y<h;++y)for(int x=0;x<w;++x){
   auto c=source[size_t(std::min(sh-1,int(y/scale)))*sw+std::min(sw-1,int(x/scale))];
   if(c==255)continue;
   g.pixels[size_t(y)*w+x]=c;
   g.left=std::min(g.left,x);g.top=std::min(g.top,y);g.right=std::max(g.right,x);g.bottom=std::max(g.bottom,y);
  }
  if(g.right>=0)g.advance=std::max(g.advance,g.x+g.right+2);
  neww=std::max(neww,w);newh=std::max(newh,h);generated.emplace(code,std::move(raster));
 }
 // All glyphs in a face share one bitmap stride. Expand the canvas without
 // changing any Hangul pixel, bearing, advance or palette colour.
 auto reframe=[&](KoreanPatchFont::Glyph&g,int w,int h){
  std::vector<unsigned char> pixels(size_t(neww)*newh,255);
  for(int y=0;y<h;++y)for(int x=0;x<w;++x)pixels[size_t(y)*neww+x]=g.pixels[size_t(y)*w+x];
  g.pixels=std::move(pixels);
 };
 for(auto& entry:native_face->glyphs)reframe(entry.second,oldw,oldh);
 for(auto& entry:generated){
  reframe(entry.second.glyph,entry.second.w,entry.second.h);
  native_face->glyphs[entry.first]=std::move(entry.second.glyph);
 }
 native_face->bitmap_width=neww;native_face->bitmap_height=newh;
 native_ascii_override=true;
}
'''
p=Path("upstream/shapes/font.cc");s=p.read_text()
s+='\n'+prepare
anchor='\tfonts[name] = font;'
if s.count(anchor)!=2:raise RuntimeError("Cinematic font manager anchors")
s=s.replace(anchor,'''    if(std::string(name)=="GUARDIAN_FONT"||std::string(name)=="SIINTRO_FONT")
        font->prepare_cinematic_ascii();
'''+anchor)
p.write_text(s)

# Translated BG blue captions are complete bitmap shapes, not text strings.
# Keep their full two-line image (including shadow) above the 200px scene edge.
p=Path("upstream/gamemgr/bggame.cc");s=p.read_text()
helper=r'''
static void paint_bg_intro_caption(Shape_manager* sman,int cx,int cy,Shape_frame* frame){
 if(!frame)return;
 int y=cy+50;
 if(legacy_korean_font_available()){
  const int below=frame->get_height()-frame->get_yabove();
  y=std::min(y,cy+100-4-below);
 }
 sman->paint_shape(cx,y,frame);
}
'''
s=s.replace('using std::rand;',helper+'\nusing std::rand;',1)
pattern=r'sman->paint_shape\(centerx, centery \+ 50, shapes.get_shape\((0x(?:15|16|17|18|19|1A|1C)), 0\)\);'
s,count=re.subn(pattern,r'paint_bg_intro_caption(sman,centerx,centery,shapes.get_shape(\1,0));',s)
if count<5:raise RuntimeError("BG blue caption anchors")
p.write_text(s)

# Centered SI subtitle pairs use their measured combined ink height, rather
# than assuming each translated line is the original 13 pixels tall.
p=Path("upstream/gamemgr/sigame.cc");s=p.read_text()
helper=r'''
static void paint_si_intro_lines(std::shared_ptr<Font> font,Image_buffer8* ibuf,
 int cx,int cy,int preferred,std::initializer_list<const char*> lines){
 if(!legacy_korean_font_available()){
  int y=preferred;
  for(const char* line:lines){font->center_text(ibuf,cx,y,line);y+=13;}
  return;
 }
 struct Row{const char* text;int top,height;};std::vector<Row> rows;int total=0;
 for(const char* line:lines){
  int l,t,w,h;font->get_text_ink_bounds(line,l,t,w,h);h=std::max(1,h);
  rows.push_back({line,t,h});total+=h;
 }
 if(rows.size()>1)total+=2*int(rows.size()-1);
 int y=std::min(preferred,cy+100-4-total);
 for(const auto& row:rows){font->center_text(ibuf,cx,y-row.top,row.text);y+=row.height+2;}
}
'''
s=s.replace('using std::', 'using std::',1)
# Place after includes, before the first normal source declaration.
anchor='using std::'
a=s.find(anchor)
if a<0:raise RuntimeError("SI helper placement")
s=s[:a]+helper+'\n'+s[a:]
pattern=r'sifont->center_text\(ibuf, centerx, centery \+ 74 \+ vlead, (get_text_msg\([^\n]+?\))\);\s*sifont->center_text\(ibuf, centerx, centery \+ 87 \+ vlead, (get_text_msg\([^\n]+?\))\);'
s,n=re.subn(pattern,r'paint_si_intro_lines(sifont,ibuf,centerx,centery,centery+74+vlead,{\1,\2});',s)
if n<5:raise RuntimeError("SI paired subtitle anchors")
p.write_text(s)
