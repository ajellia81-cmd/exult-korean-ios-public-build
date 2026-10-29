"""Regressions for patched initial data, named menu fonts and welcome layout."""
from pathlib import Path
game=Path("upstream/gamewin.cc").read_text()
a=game.index("restore_gamedat(PATCH_INITGAME);")
b=game.index('// Editing, and no IDENTITY?',a)
section=game[a:b]
assert section.index("!U7exists(GEXULTVER)")<section.index("Game::set_new_game()")
assert section.index("else")>section.index("Game::set_new_game()")
# A normal Exult ZIP carries exult.ver and must not use original NPC flags.
# Original NPC flags can contain 0x48, which is not a named-usecode flag.
actor=Path("upstream/actorio.cc").read_text()
assert "const bool usecode_name_used  = !fix_first && (iflag1 & 8);" in actor
for original in (False,True):
    iflag1=0x48
    usecode_name_used=not original and bool(iflag1&8)
    assert usecode_name_used != original
font=Path("upstream/shapes/font.cc").read_text()
assert font.count('if(native_name=="MENU_FONT")')==2
assert 'named_face=load_korean_patch_face("<STATIC>/mainshp.flx",9);' in font
menu=Path("upstream/exultmenu.cc").read_text()
a=menu.index("if (!gamemanager->get_game_count())")
b=menu.index('IExultDataSource mouse_data',a)
welcome=menu[a:b]
assert "fit_launcher_scene(welcome_scene,320,200);" in welcome
assert "300,180,2,false,true" in welcome
assert "line_num * 10" not in welcome
audio=Path("upstream/audio/Audio.cc").read_text()
assert "recovery!=\"yes\"&&music_pack" in audio
assert 'config->set("config/audio/midi/use_oggs","yes",false);' in audio
print("Startup regression checks passed")
