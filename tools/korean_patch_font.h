/*
 * Korean .FNT format originally documented by wonst719's GPL Exult port.
 * Copyright (C) 2026 Exult Korean iOS contributors.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#ifndef EXULT_KOREAN_PATCH_FONT_H
#define EXULT_KOREAN_PATCH_FONT_H
#include <algorithm>
#include <cstdint>
#include <map>
#include <vector>
#include <string>
class KoreanPatchFont {
public:
 struct Glyph {
  int x=0,y=0,advance=0;
  std::vector<unsigned char> pixels;
  int left=0,top=0,right=-1,bottom=-1;
 };
 int width=0,height=0,bitmap_width=0,bitmap_height=0;
 std::map<unsigned,Glyph> glyphs;
 static bool pair(const char* text,int remaining) {
  if (!text || remaining<2) return false;
  const unsigned a=static_cast<unsigned char>(text[0]),b=static_cast<unsigned char>(text[1]);
  return a>=0x81&&a<=0xfe&&((b>=0x41&&b<=0x5a)||(b>=0x61&&b<=0x7a)||(b>=0x81&&b<=0xfe));
 }
 const Glyph* get(unsigned code) const {
  auto i=glyphs.find(code);return i==glyphs.end()?nullptr:&i->second;
 }
 bool load(const std::vector<unsigned char>& data) {
  glyphs.clear();width=height=bitmap_width=bitmap_height=0;
  if(data.size()<14)return false;
  auto u16=[&](size_t p){return unsigned(data[p])|(unsigned(data[p+1])<<8);};
  const unsigned magic=u16(0)|(u16(2)<<16);
  if(magic!=0x11223345&&magic!=0x11223344)return false;
  width=data[4];height=data[5];bitmap_width=data[6];bitmap_height=data[7];
  if(!width||!height||!bitmap_width||!bitmap_height||bitmap_width%4)return false;
  size_t p=8;int default_x=0,default_y=0,default_advance=0;
  if(magic==0x11223344){
   if(data.size()<18)return false;
   default_x=int(int8_t(data[p++]));default_y=int(int8_t(data[p++]));
   default_advance=int(int16_t(u16(p)));p+=2;
  }
  unsigned char palette[4];for(auto& c:palette)c=data[p++];
  const unsigned count=u16(p);p+=2;
  const size_t entry=magic==0x11223345?5:2;
  const size_t pixels=size_t(bitmap_width)*bitmap_height,packed=pixels/4;
  if(count==0||count>65535||data.size()!=p+size_t(count)*(entry+packed))return false;
  const size_t bitmap_start=p+count*entry;
  for(unsigned i=0;i<count;++i){
   const unsigned code=u16(p);p+=2;Glyph g;
   g.x=default_x;g.y=default_y;g.advance=default_advance;
   if(magic==0x11223345){
    g.x=int(int8_t(data[p++]));g.y=int(int8_t(data[p++]));g.advance=data[p++];
   }
   if(g.advance<0||g.advance>128||glyphs.count(code)){glyphs.clear();return false;}
   g.pixels.assign(pixels,255);g.left=bitmap_width;g.top=bitmap_height;
   for(size_t j=0;j<pixels;++j){
    const unsigned c=(data[bitmap_start+i*packed+j/4]>>(6-2*(j%4)))&3;
    if(!c)continue;
    // Slot zero is transparent; palette index zero is opaque black.
    g.pixels[j]=palette[c];
    const int x=int(j%bitmap_width),y=int(j/bitmap_width);
    g.left=std::min(g.left,x);g.top=std::min(g.top,y);
    g.right=std::max(g.right,x);g.bottom=std::max(g.bottom,y);
   }
   glyphs.emplace(code,std::move(g));
  }
  return true;
 }
};
#endif
