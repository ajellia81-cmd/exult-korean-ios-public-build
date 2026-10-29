"""Rebase Korean data support onto the installed 2026 BG/SI .FNT packs.
No game data, glyph pixels or translation strings are distributed here.
"""
from pathlib import Path
import re
def edit(path,before,after):
 p=Path("upstream")/path;t=p.read_text()
 if t.count(before)!=1:raise RuntimeError(f"{path}: expected unique {before[:70]!r}")
 p.write_text(t.replace(before,after,1))
p=Path("upstream/shapes/korean_patch_font.h")
p.write_text(Path("tools/korean_patch_font.h").read_text())
edit("shapes/font.h","class U7multiobject;","class U7multiobject;\nclass KoreanPatchFont;")
edit("shapes/font.h","public:\n\tFont();",r"""
    std::shared_ptr<KoreanPatchFont> native_face;
    bool native_style(const char* text, int length);
    int native_width(const char* text, int length, int cell = 0);
    int native_draw(Image_buffer8* win, const char* text, int length, int x, int y,
                    unsigned char* trans, int cell = 0);
    void native_bounds(const char* text, int& l, int& t, int& w, int& h);
public:
    Font();""")
edit("shapes/font.cc",'#include "font.h"',
 '#include "font.h"\n#include "korean_patch_font.h"\n#include "game.h"')
p=Path("upstream/shapes/font.cc");text=p.read_text()
a=text.index("FontManager fontManager;")
loader=r"""
static bool korean_patch_pack_present() {
    return U7exists("<CONFIG>/patch/font0bg.fnt")
        || U7exists("<CONFIG>/patch/FONT0BG.FNT")
        || (is_system_path_defined("<PATCH>") &&
            (U7exists("<PATCH>/font0bg.fnt") || U7exists("<PATCH>/font0si.fnt")));
}
static std::shared_ptr<KoreanPatchFont> load_korean_patch_face(const std::string& source,int index) {
    int mapped=-1;
    if(source=="<STATIC>/fonts.vga")mapped=index;
    else if(source=="<STATIC>/mainshp.flx")mapped=10+index;
    else if(source=="<STATIC>/intro.dat"||source=="<STATIC>/endgame.dat")mapped=20+index;
    else if(source.find("exult.flx")!=std::string::npos)
        mapped=(index>=18&&index<=21)?95+index-18:90+index;
    if(mapped<0)return {};
    const char* game=Game::get_game_type()==BLACK_GATE?"bg":
                     Game::get_game_type()==SERPENT_ISLE?"si":"ex";
    for(const auto* suffix:{game,"ex"}) for(const auto* root:{"<CONFIG>/patch/","<PATCH>/"}) {
        if(std::string(root)=="<PATCH>/"&&!is_system_path_defined("<PATCH>"))continue;
        std::string name="font"+std::to_string(mapped)+suffix+".fnt";
        for(int upper=0;upper<2;++upper){
            if(upper)for(auto& c:name)c=static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
            const auto path=std::string(root)+name;
            if(!U7exists(path))continue;
            IFileDataSource input(path.c_str(),true);
            if(!input.good()||input.getSize()>4*1024*1024)continue;
            std::vector<unsigned char> bytes(input.getSize());
            input.read(bytes.data(),bytes.size());
            auto face=std::make_shared<KoreanPatchFont>();
            if(face->load(bytes))return face;
        }
    }
    if(source=="<STATIC>/fonts.vga"&&index!=0)
        return load_korean_patch_face(source,index==3||index==6?1:0);
    return {};
}
"""
text=text[:a]+loader+"\n"+text[a:]
text=text.replace("return korean_font.is_pair(\"\\xb0\\xa1\", 2);",
                  "return korean_patch_pack_present() || korean_font.is_pair(\"\\xb0\\xa1\", 2);",1)
# All CP949 Hangul, jamo, Hanja and punctuation are recognized by the new face.
a=text.index("static bool contains_legacy_korean(");b=text.index("struct Korean_layout_scope",a)
text=text[:a]+r"""static bool contains_legacy_korean(const char* text,int length) {
 if(!text)return false;
 if(length<0)length=static_cast<int>(std::strlen(text));
 for(int i=0;i<length;++i){
  if(korean_patch_pack_present()&&KoreanPatchFont::pair(text+i,length-i))return true;
  if(korean_font.is_pair(text+i,length-i))return true;
 }
 return false;
}
""" +text[b:]
# Per-font face selection uses the same file/index routing as the Korean author.
for signature in ["int Font::load(const File_spec& fname0, int index, int hlead, int vlead)",
 "int Font::load(const File_spec& fname0, const File_spec& fname1, int index, int hlead, int vlead)"]:
 a=text.index(signature);b=text.index("\tclean_up();",a)+len("\tclean_up();")
 text=text[:b]+"\n    native_face = load_korean_patch_face(fname0.name,index);"+text[b:]
# Early native paths keep the modern engine's event/layer code and the audited
# layout functions, replacing only glyph selection, advance and painting.
for name in ["paint_text","paint_text_fixedwidth","get_text_width","find_xcursor","get_text_box_dims",
             "get_text_height","get_text_baseline","get_text_ink_bounds"]:
 matches=list(re.finditer(r"(?:int|void) Font::"+name+r"\(",text))
 for match in reversed(matches):
  brace=text.index("{",match.start());params=text[match.start():brace]
  bounded="textlen" in params;length="textlen" if bounded else "-1"
  addition=""
  if name=="paint_text":
   addition=f"if(native_face)return native_draw(win,text,{length},xoff,yoff,trans);"
  elif name=="paint_text_fixedwidth":
   addition=f"if(native_face)return native_draw(win,text,{length},xoff,yoff,trans,width);"
  elif name=="get_text_width":
   addition=f"if(native_face)return native_width(text,{length});"
  elif name=="find_xcursor":
   addition=r"""if(native_face){
    int x=0;for(int i=0;i<textlen;){
      const int n=KoreanPatchFont::pair(text+i,textlen-i)?2:1;
      const int w=native_width(text+i,n);
      if(cx>=x&&cx<x+w)return i;
      x+=w;i+=n;
    }return -1;
   }"""
  elif name=="get_text_box_dims":
   addition=r"""if(native_face){
    width=height=0;const char* line=text;
    for(const char* p=text;;++p)if(*p=='\n'||!*p){
      std::string part(line,p);
      width=std::max(width,native_width(part.c_str(),int(part.size())));
      height+=get_text_height(part.c_str())+vert_lead+ver_lead;
      if(!*p)break;line=p+1;
    }return;
   }"""
  elif name=="get_text_height" and "const char*" in params:
   addition=r"""if(native_face){
    int l,t,w,h;native_bounds(text,l,t,w,h);
    return std::max(highest+lowest+1,std::max(native_face->height,t+h));
   }"""
  elif name=="get_text_baseline" and "const char*" in params:
   addition="if(native_face)return highest;"
  elif name=="get_text_ink_bounds":
   addition="if(native_face){native_bounds(text,left,top,width,height);return;}"
  if addition:text=text[:brace+1]+"\n    "+addition+"\n"+text[brace+1:]
# Existing page splitting must consume whole CP949 units, including extension
# syllables whose trailing byte is an ASCII letter.
for signature in ["int Font::paint_text_box(","int Font::paint_text_box_fixedwidth(","int Font::find_cursor("]:
 a=text.index(signature);brace=text.index("{",a);depth=0
 for b in range(brace,len(text)):
  if text[b]=="{":depth+=1
  elif text[b]=="}":
   depth-=1
   if not depth:break
 section=text[a:b+1]
 section=re.sub(r"korean_font\.is_pair\((next|text), static_cast<int>\(ewrd - \1\)\)",
  r"(native_face ? KoreanPatchFont::pair(\1, static_cast<int>(ewrd - \1)) : korean_font.is_pair(\1, static_cast<int>(ewrd - \1)))",section)
 section=section.replace("!korean_font.is_pair(text, 2)",
                        "!(native_face ? KoreanPatchFont::pair(text, 2) : korean_font.is_pair(text, 2))")
 # Fixed-width line layout uses the matching native advances.
 section=re.sub(r"korean_fixed_text_width\(text, static_cast<int>\((ewrd|next) - text\), char_width, font_shapes.get\(\), legacy_korean_layout_override, hor_lead\)",
  r"(native_face ? native_width(text, static_cast<int>(\1 - text), char_width) : \g<0>)",section)
 text=text[:a]+section+text[b+1:]
# Padding scanner must use the same CP949 code units as draw/measure.
a=text.index("int Font::get_text_edge_padding(")
text=text[:a]+text[a:].replace("korean_font.is_pair(text + i, 2)",
 "(native_face ? KoreanPatchFont::pair(text + i, 2) : korean_font.is_pair(text + i, 2))")
text+=r"""
bool Font::native_style(const char* text,int length) {
 if(legacy_korean_layout_override)return true;
 if(length<0)length=int(std::strlen(text));
 for(int i=0;i<length;++i)if(KoreanPatchFont::pair(text+i,length-i))return true;
 return false;
}
int Font::native_width(const char* text,int length,int cell) {
 if(!text)return 0;
 if(length<0)length=int(std::strlen(text));
 const bool style=native_style(text,length);int width=0;
 for(int i=0;i<length;){
  const int n=KoreanPatchFont::pair(text+i,length-i)?2:1;
  const unsigned code=n==2?(unsigned(static_cast<unsigned char>(text[i]))<<8)
        |static_cast<unsigned char>(text[i+1]):static_cast<unsigned char>(text[i]);
  auto* glyph=(n==2||style)?native_face->get(code):nullptr;
  auto* ascii=font_shapes?font_shapes->get_frame(n==2?'?':code):nullptr;
  const int advance=glyph?glyph->advance:ascii?ascii->get_width()+hor_lead:0;
  width+=cell?std::max(n*cell,advance):advance;i+=n;
 }
 return width;
}
int Font::native_draw(Image_buffer8* win,const char* text,int length,int x,int y,
                      unsigned char* trans,int cell) {
 (void)win;
 if(!text)return 0;
 if(length<0)length=int(std::strlen(text));
 const bool style=native_style(text,length);const int start=x;
 for(int i=0;i<length;){
  const int n=KoreanPatchFont::pair(text+i,length-i)?2:1;
  const unsigned code=n==2?(unsigned(static_cast<unsigned char>(text[i]))<<8)
        |static_cast<unsigned char>(text[i+1]):static_cast<unsigned char>(text[i]);
  auto* glyph=(n==2||style)?native_face->get(code):nullptr;
  auto* ascii=font_shapes?font_shapes->get_frame(n==2?'?':code):nullptr;
  const int advance=glyph?glyph->advance:ascii?ascii->get_width()+hor_lead:0;
  const int step=cell?std::max(n*cell,advance):advance;
  const int dx=x+(step-advance)/2;
  if(glyph){
   auto pixels = glyph->pixels;
   Shape_frame frame(pixels.data(),native_face->bitmap_width,
       native_face->bitmap_height,-glyph->x,-glyph->y,true);
   if(trans)frame.paint_rle_remapped(dx,y,trans);else frame.paint_rle(dx,y);
  }else if(ascii&&ascii->is_rle()){
   if(trans)ascii->paint_rle_remapped(dx,y+highest,trans);
   else ascii->paint_rle(dx,y+highest);
  }
  x+=step;i+=n;
 }
 return x-start;
}
void Font::native_bounds(const char* text,int& l,int& t,int& w,int& h) {
 l=t=w=h=0;if(!text)return;
 const int length=int(std::strlen(text));const bool style=native_style(text,length);
 int pen=0,r=0,b=0;bool found=false;
 auto include=[&](int x,int y,int rr,int bb){
  if(rr<x||bb<y)return;
  if(!found){l=x;t=y;r=rr;b=bb;found=true;}
  else {l=std::min(l,x);t=std::min(t,y);r=std::max(r,rr);b=std::max(b,bb);}
 };
 for(int i=0;i<length;){
  const int n=KoreanPatchFont::pair(text+i,length-i)?2:1;
  const unsigned code=n==2?(unsigned(static_cast<unsigned char>(text[i]))<<8)
        |static_cast<unsigned char>(text[i+1]):static_cast<unsigned char>(text[i]);
  auto* glyph=(n==2||style)?native_face->get(code):nullptr;
  if(glyph){
   if(glyph->right>=0)include(pen+glyph->x+glyph->left,glyph->y+glyph->top,
       pen+glyph->x+glyph->right,glyph->y+glyph->bottom);
   pen+=glyph->advance;
  }else{
   auto* ascii=font_shapes?font_shapes->get_frame(n==2?'?':code):nullptr;
   if(ascii){include(pen-ascii->get_xleft(),highest-ascii->get_yabove(),
       pen-ascii->get_xleft()+ascii->get_width()-1,
       highest-ascii->get_yabove()+ascii->get_height()-1);
       pen+=ascii->get_width()+hor_lead;}
  }i+=n;
 }
 if(found){w=r-l+1;h=b-t+1;}
}
"""
p.write_text(text)

# CP949 byte streams must bypass the upstream UTF-8 accent conversion.
p=Path("upstream/shapes/font_map.cc");text=p.read_text()
text=text.replace("if (lead < 0xb0 || lead > 0xc8 || trail < 0xa1 || trail > 0xfe) return false;",
 """if (lead < 0x81 || lead > 0xfe ||
        !((trail>=0x41&&trail<=0x5a)||(trail>=0x61&&trail<=0x7a)||(trail>=0x81&&trail<=0xfe))) return false;""")
p.write_text(text)

# Native glyphs may carry a negative top bearing; reserve it inside the outer
# text-box clip. The cursor follows exactly the same adjusted origin.
p=Path("upstream/shapes/font.cc");text=p.read_text()
for signature in ("int Font::paint_text_box(", "int Font::paint_text_box_fixedwidth(", "int Font::find_cursor("):
 a=text.index(signature);b=text.index("x += edge; w -= 2 * edge;",a)+len("x += edge; w -= 2 * edge;")
 text=text[:b]+"""
    if(native_face){
        int il,it,iw,ih;native_bounds(text,il,it,iw,ih);
        if(it<0){y-=it;h=std::max(0,h+it);}
    }
"""+text[b:]
p.write_text(text)

# Text buttons use the patch's black UI face rather than a dialogue face.
edit("shapes/font.h", "class Font {\nprivate:", "class Font {\n    friend class FontManager;\nprivate:")
p=Path("upstream/shapes/font.cc");text=p.read_text()
needle="\tfonts[name] = font;"
if text.count(needle)!=2:raise RuntimeError("FontManager routing anchors changed")
text=text.replace(needle,'''    if(std::string(name)=="SMALL_BLACK_FONT") {
        auto face=load_korean_patch_face("<STATIC>/fonts.vga",2);
        if(face)font->native_face=std::move(face);
    }
'''+needle)
p.write_text(text)


# Load the installed pack's engine messages after the stock fallback messages.
p=Path("upstream/shapes/items.cc")
text=p.read_text()
if '#include "font_map.h"' not in text:
    p.write_text('#include "font_map.h"\n'+text)
p=Path("upstream/shapes/items.cc");text=p.read_text()
anchor="\t// Exult new-style messages?"
if text.count(anchor)!=1:raise RuntimeError("Global Korean messages anchor changed")
text=text.replace(anchor,'''    for(const auto* file:{"<CONFIG>/patch/exultmsg.txt","<CONFIG>/patch/EXULTMSG.TXT"}) {
        if(U7exists(file)) {
            set_font_map_legacy_korean(true);
            exultmsgs.emplace_back(file,0);
            break;
        }
    }

'''+anchor,1)
p.write_text(text)
# Latest initgame packs contain translated NPC names. Preserve those names
# directly; the old hash/offset resolver remains only for the old data pack.
p=Path("upstream/gumps/ItemMenu_gump.cc");text=p.read_text()
anchor="    const std::string original = object->get_name();"
text=text.replace(anchor,anchor+'''
    if(U7exists("<CONFIG>/patch/font0bg.fnt")||U7exists("<CONFIG>/patch/FONT0BG.FNT"))
        return original;''',1)
p.write_text(text)


# The pack omits curly quotes and ellipsis from its bitmap table. Use explicit
# punctuation fallbacks rather than indexing a high byte as an ASCII frame.
p=Path("upstream/shapes/font.cc");text=p.read_text()
text=text.replace("const bool style=native_style(text,length);int width=0;",
 """const bool style=native_style(text,length);
 Korean_layout_scope context(legacy_korean_layout_override,style);int width=0;""")
text=text.replace("const bool style=native_style(text,length);const int start=x;",
 """const bool style=native_style(text,length);
 Korean_layout_scope context(legacy_korean_layout_override,style);const int start=x;""")
text=text.replace("const int length=int(std::strlen(text));const bool style=native_style(text,length);",
 """const int length=int(std::strlen(text));const bool style=native_style(text,length);
 Korean_layout_scope context(legacy_korean_layout_override,style);""")
# Keep the source codepoint for native lookup; normalize only missing glyphs.
text=text.replace("font_shapes->get_frame(n==2?'?':code)",
 "font_shapes->get_frame(code==0xa1b0||code==0xa1b1?'\"':code==0xa1a6?'.':n==2?'?':code)")
p.write_text(text)

p=Path("upstream/shapes/font.cc");text=p.read_text()
for signature,extra in [
 ("int Font::native_width(",'''  if(code==0xa1a6&&!glyph){width+=native_width("...",3,cell);i+=n;continue;}
'''),
 ("int Font::native_draw(",'''  if(code==0xa1a6&&!glyph){x+=native_draw(win,"...",3,x,y,trans,cell);i+=n;continue;}
'''),
 ("void Font::native_bounds(",'''  if(code==0xa1a6&&!glyph){
   int ll,tt,ww,hh;native_bounds("...",ll,tt,ww,hh);
   if(ww&&hh)include(pen+ll,tt,pen+ll+ww-1,tt+hh-1);
   pen+=native_width("...",3);i+=n;continue;
  }
''')]:
 a=text.index(signature)
 b=text.index("auto* glyph=(n==2||style)?native_face->get(code):nullptr;",a)
 b=text.index(";",b)+1
 text=text[:b]+"\n"+extra+text[b:]
p.write_text(text)


# Match native metrics in generic UI row layout as well as text-specific boxes.
p=Path("upstream/shapes/font.cc");text=p.read_text()
anchor="int Font::get_text_height() { return highest + lowest + 1; }"
if text.count(anchor)!=1:raise RuntimeError("Native UI metric anchor changed")
text=text.replace(anchor,'''int Font::get_text_height() {
    return native_face ? std::max(highest+lowest+1,native_face->height)
                       : highest+lowest+1;
}''',1)
text=text.replace("if(native_face){\n    int x=0;for(int i=0;i<textlen;){",
'''if(native_face){
    Korean_layout_scope context(legacy_korean_layout_override,native_style(text,textlen));
    int x=0;for(int i=0;i<textlen;){''',1)
# Respect explicitly bounded spans when calculating native line height.
text=text.replace("if(native_face){\n    int l,t,w,h;native_bounds(text,l,t,w,h);",
'''if(native_face){
    std::string bounded;
    if(text&&length>=0){bounded.assign(text,length);text=bounded.c_str();}
    int l,t,w,h;native_bounds(text,l,t,w,h);''',1)
p.write_text(text)


# Font-mode checks run in inner layout loops. Probe the filesystem once per
# game selection, not once per byte.
p=Path("upstream/shapes/font.cc");text=p.read_text()
a=text.index("static bool korean_patch_pack_present() {")
b=text.index("\n}",a)+2
text=text[:a]+'''static bool korean_patch_pack_present() {
    static int checked_game=-999;
    static bool present=false;
    const int selected=static_cast<int>(Game::get_game_type());
    if(checked_game==selected)return present;
    checked_game=selected;
    present=U7exists("<CONFIG>/patch/font0bg.fnt")
        || U7exists("<CONFIG>/patch/FONT0BG.FNT")
        || (is_system_path_defined("<PATCH>") &&
            (U7exists("<PATCH>/font0bg.fnt") || U7exists("<PATCH>/font0si.fnt")));
    return present;
}'''+text[b:]
p.write_text(text)


# Reading a sign uppercases Latin runes; never uppercase the ASCII-valued
# trailing byte of a CP949 extension syllable.
p=Path("upstream/gumps/Sign_gump.cc");text=p.read_text()
text=text.replace('#include "font.h"','#include "font.h"\n#include "korean_patch_font.h"',1)
anchor="\t\tfor (const auto& ch : txt) {"
if text.count(anchor)!=1:raise RuntimeError("CP949 sign-case anchor changed")
text=text.replace(anchor,'''        for(size_t i=0;i<txt.size();++i) {
            if(KoreanPatchFont::pair(txt.data()+i,static_cast<int>(txt.size()-i))) {
                lines[line].append(txt,i,2);++i;continue;
            }
            const auto ch=txt[i];''',1)
p.write_text(text)
