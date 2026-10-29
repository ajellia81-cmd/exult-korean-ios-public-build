"""Apply bounded iOS diagnostics to the pinned upstream revision."""
from pathlib import Path

def replace(path, before, after):
    p = Path("upstream") / path
    text = p.read_text()
    if text.count(before) != 1:
        raise RuntimeError("Expected unique anchor in " + path)
    p.write_text(text.replace(before, after, 1))

replace("exult.cc", '#\tinclude "ios_utils.h"',
        '#\tinclude "ios_utils.h"\nextern void KoreanIOSDiagnostics();')
replace("exult.cc", '\tconst char* launchFlag = iOS_GetLaunchGameFlag();',
        '\tKoreanIOSDiagnostics();\n\tconst char* launchFlag = iOS_GetLaunchGameFlag();')
replace("ios/ios_utils.mm", '#import <UIKit/UIKit.h>',
        '#import <UIKit/UIKit.h>\n#import <AVFoundation/AVFoundation.h>\n#include <cstdio>\n#include <string>')

p = Path("upstream/ios/ios_utils.mm")
p.write_text(p.read_text() + r'''

// This log contains engine diagnostics, not copied game or font data.
void KoreanIOSDiagnostics() {
    std::string base(IOSGetDocumentsDir());
    std::freopen((base + "/exult-ios-stdout.txt").c_str(), "w", stdout);
    std::freopen((base + "/exult-ios-stderr.txt").c_str(), "w", stderr);
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    std::setvbuf(stderr, nullptr, _IONBF, 0);
    fprintf(stderr, "Korean iOS diagnostics build 2; font mode=EUC-KR bitmap\n");
    AVAudioSession* session = [AVAudioSession sharedInstance];
    NSError* error = nil;
    BOOL categoryOK = [session setCategory:AVAudioSessionCategoryPlayback error:&error];
    fprintf(stderr, "iOS playback category=%d error=%s\n", categoryOK,
            error ? error.localizedDescription.UTF8String : "none");
    error = nil;
    BOOL activeOK = [session setActive:YES error:&error];
    fprintf(stderr, "iOS audio active=%d error=%s volume=%.3f sample_rate=%.0f\n",
            activeOK, error ? error.localizedDescription.UTF8String : "none",
            session.outputVolume, session.sampleRate);
    for (AVAudioSessionPortDescription* port in session.currentRoute.outputs) {
        fprintf(stderr, "iOS output type=%s\n", port.portType.UTF8String);
    }
}
''')
replace("audio/Audio.cc", '\tif (!audio_enabled) {\n\t\treturn;\n\t}\n\n\tmixer = std::make_unique<AudioMixer>',
        '\tstd::cerr << "Audio diagnostic: enabled=" << audio_enabled\n'
        '\t          << " music=" << music_enabled << " effects=" << effects_enabled\n'
        '\t          << " speech=" << speech_enabled << " sfx_volume=" << sfx_volume\n'
        '\t          << " speech_volume=" << speech_volume << std::endl;\n'
        '\tif (!audio_enabled) {\n\t\treturn;\n\t}\n\n\tmixer = std::make_unique<AudioMixer>')
replace("audio/AudioMixer.cc", '\tSDL_InitSubSystem(SDL_INIT_AUDIO);',
        '\tif (!SDL_InitSubSystem(SDL_INIT_AUDIO)) {\n'
        '\t\tstd::cerr << "SDL audio init failed: " << SDL_GetError() << std::endl;\n'
        '\t}')
replace("audio/AudioMixer.cc", '\taudio_ok = (stream != nullptr);',
        '\taudio_ok = (stream != nullptr);\n'
        '\tif (!audio_ok) std::cerr << "SDL audio stream failed: " << SDL_GetError() << std::endl;\n'
        '\tstd::cerr << "SDL audio driver: " << (SDL_GetCurrentAudioDriver() ? SDL_GetCurrentAudioDriver() : "none") << std::endl;')
replace("audio/AudioMixer.cc", '\t\t\tSDL_ResumeAudioDevice(dev);',
        '\t\t\tif (!SDL_ResumeAudioDevice(dev)) {\n'
        '\t\t\t\tstd::cerr << "SDL audio resume failed: " << SDL_GetError() << std::endl;\n'
        '\t\t\t}')

# Draw Korean through the same active screen/RLE path as ordinary font shapes.
p = Path("upstream/shapes/font.cc")
text = p.read_text()
before = 'const unsigned char colour = trans ? trans[255] : 255;'
after = '''std::vector<unsigned char> pixels(glyph_width * glyph_height, 255);
        const unsigned char colour = ink_colour;'''
assert text.count(before) == 1
text = text.replace(before, after)
text = text.replace('const char* text, unsigned char* trans) {',
                    'const char* text, unsigned char* trans, unsigned char ink_colour = 1) {', 1)
text = text.replace('win->put_pixel8(colour, x + col, y + row);',
                    'pixels[row * glyph_width + col] = colour;', 1)
needle = '\nprivate:\n\tstatic constexpr int glyph_count'
assert text.count(needle) == 1
text = text.replace(needle, '''
        // Palette 255 is transparency in shape encoding, so ink must use the
        // current font colour. Route through Shape_frame's active screen.
''' + needle, 1)
# Insert shape draw before the end of paint(), not after it.
needle = '\t}\nprivate:\n\tstatic constexpr int glyph_count'
# Comment above was inserted between these anchors; instead insert before comment.
anchor = '\n        // Palette 255 is transparency'
text = text.replace(anchor, anchor, 1)
# Locate paint method's closing brace via the following comment.
comment = text.index('        // Palette 255 is transparency')
paint_end = text.rfind('\t}', 0, comment)
text = text[:paint_end] + '''        Shape_frame frame(pixels.data(), glyph_width, glyph_height, 0, 0, true);
        if (trans) frame.paint_rle_remapped(x, y, trans);
        else frame.paint_rle(x, y);
''' + text[paint_end:]
# Sample an existing ASCII letter from this font into a temporary buffer.
helper = '''
static unsigned char korean_ink_colour(Shape_file* shapes) {
    Shape_frame* reference = shapes->get_frame('A');
    if (!reference || !reference->is_rle()) return 1;
    const int w = reference->get_width(), h = reference->get_height();
    Image_buffer8 sample(w, h);
    sample.fill8(255);
    reference->paint_rle(&sample, reference->get_xleft(), reference->get_yabove());
    // The first opaque pixel is often the black outline. Select the
    // brightest colour actually present in the reference letter instead.
    unsigned char selected = 1;
    int best = -1;
    const Palette* palette = Game_window::get_instance()->get_pal();
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            const unsigned char colour = sample.get_pixel8(x, y);
            if (colour == 255) continue;
            const int luminance = 299 * palette->get_red(colour)
                                + 587 * palette->get_green(colour)
                                + 114 * palette->get_blue(colour);
            if (luminance > best) { best = luminance; selected = colour; }
        }
    }
    return selected;
}
'''
anchor = '//\tWant a more restrictive test for space.'
assert text.count(anchor) == 1
text = text.replace(anchor, helper + '\n' + anchor)
text = text.replace('korean_font.paint(win, x, yoff - korean_font.height() + 1, text, trans);',
                    'korean_font.paint(win, x, yoff - get_text_baseline(), text, trans, korean_ink_colour(font_shapes.get()));')
# Only grow height when a valid enabled Korean font is loaded.
text = text.replace('return highest + lowest + 1;', '''return legacy_korean_font_enabled && korean_font.is_pair("\\xb0\\xa1", 2)
        ? std::max(highest, korean_font.height() - 1) + lowest + 1 : highest + lowest + 1;''', 1)
p.write_text(text)

# One-time audio recovery. Preserve the user's configuration before changing it.
replace("ios/ios_utils.mm", '    AVAudioSession* session = [AVAudioSession sharedInstance];',
'''    NSString* cfg = [NSString stringWithUTF8String:(base + "/exult.cfg").c_str()];
    NSString* backup = [NSString stringWithUTF8String:(base + "/exult-before-audio-repair.cfg").c_str()];
    NSFileManager* manager = [NSFileManager defaultManager];
    if ([manager fileExistsAtPath:cfg] && ![manager fileExistsAtPath:backup]) {
        NSError* backupError = nil;
        if (![manager copyItemAtPath:cfg toPath:backup error:&backupError])
            fprintf(stderr, "Config backup failed: %s\\n", backupError.localizedDescription.UTF8String);
    }
    AVAudioSession* session = [AVAudioSession sharedInstance];''')
replace("audio/Audio.cc", '\tconfig->value("config/audio/enabled", s, "yes");',
'''    std::string repair_done;
    config->value("config/audio/korean_audio_repair_v1", repair_done, "no");
    if (repair_done != "yes") {
        config->set("config/audio/enabled", "yes", false);
        config->set("config/audio/midi/enabled", "yes", false);
        config->set("config/audio/midi/use_oggs", "no", false);
        config->set("config/audio/midi/driver", "FMOpl", false);
        config->set("config/audio/korean_audio_repair_v1", "yes", false);
        std::cerr << "Audio recovery: enabled FMOpl music once" << std::endl;
    }
\tconfig->value("config/audio/enabled", s, "yes");''')

replace("shapes/font.cc", '#include "font.h"', '#include "font.h"\n#include "gamewin.h"\n#include "palette.h"')
replace("shapes/font.cc", '\treturn highest;\n}', '''    return legacy_korean_font_enabled && korean_font.is_pair("\\xb0\\xa1", 2)
        ? std::max(highest, korean_font.height() - 1) : highest;
}''')

# Use a padded, outlined bitmap and account for the border in layout.
p = Path("upstream/shapes/font.cc")
text = p.read_text()
text = text.replace('int width() const { return glyph_width; }',
                    'int width() const { return glyph_width + 2; }')
text = text.replace('int height() const { return glyph_height; }',
                    'int height() const { return glyph_height + 2; }')
start = text.index('\tvoid paint(Image_buffer8* win,')
end = text.index('\nprivate:', start)
text = text[:start] + r'''
    void paint(Image_buffer8* win, int x, int y, const char* text,
               unsigned char* trans, unsigned char ink_colour = 1,
               unsigned char outline_colour = 0) {
        const auto lead = static_cast<unsigned char>(text[0]);
        const auto trail = static_cast<unsigned char>(text[1]);
        const auto index = (lead - 0xb0) * 94 + (trail - 0xa1);
        const auto* glyph = glyphs.data() + index * bytes_per_glyph;
        const int w = width(), h = height();
        std::vector<unsigned char> pixels(w * h, 255);
        // Paint a one-pixel border, then the foreground. Separate passes
        // prevent a later border pixel from erasing an earlier stroke.
        if (outline_colour != ink_colour) {
        for (int row = 0; row < glyph_height; ++row) {
            for (int col = 0; col < glyph_width; ++col) {
                if (!(glyph[row * bytes_per_row + col / 8] & (0x80 >> (col % 8)))) continue;
                for (int dy = 0; dy < 3; ++dy)
                    for (int dx = 0; dx < 3; ++dx)
                        pixels[(row + dy) * w + col + dx] = outline_colour;
            }
        }
        }
        for (int row = 0; row < glyph_height; ++row)
            for (int col = 0; col < glyph_width; ++col)
                if (glyph[row * bytes_per_row + col / 8] & (0x80 >> (col % 8)))
                    pixels[(row + 1) * w + col + 1] = ink_colour;
        Shape_frame frame(pixels.data(), w, h, 0, 0, true);
        if (trans) frame.paint_rle_remapped(x, y, trans);
        else frame.paint_rle(x, y);
    }
''' + text[end:]
text = text.replace('korean_ink_colour(Shape_file* shapes)', 'korean_ink_colour(Shape_file* shapes, bool outline = false)')
text = text.replace('unsigned char selected = 1;\n    int best = -1;',
                    'unsigned char selected = outline ? 0 : 1;\n    int best = outline ? 1000000 : -1;')
text = text.replace('if (luminance > best) { best = luminance; selected = colour; }',
                    'if (outline ? luminance < best : luminance > best) { best = luminance; selected = colour; }')
text = text.replace('trans, korean_ink_colour(font_shapes.get()));',
                    'trans, korean_ink_colour(font_shapes.get()), korean_ink_colour(font_shapes.get(), true));')
p.write_text(text)

# Preserve EUC-KR before the upstream UTF-8 accent map can consume its bytes.
replace("shapes/font.h", "void set_legacy_korean_font_enabled(bool enabled);",
        "void set_legacy_korean_font_enabled(bool enabled);\nbool legacy_korean_font_available();")
replace("shapes/font.cc", "static void probe_korean_font() {",
'''bool legacy_korean_font_available() {
    return korean_font.is_pair("\\xb0\\xa1", 2);
}
static void probe_korean_font() {''')
replace("shapes/font_map.h", "void set_font_map_use_special_chars(bool value);",
        "void set_font_map_use_special_chars(bool value);\nvoid set_font_map_legacy_korean(bool value);")
replace("game.cc", '\tset_legacy_korean_font_enabled(korean_font == "yes" || korean_font == "true");',
        '\tset_legacy_korean_font_enabled(korean_font == "yes" || korean_font == "true");\n'
        '\tset_font_map_legacy_korean(legacy_korean_font_available());')
replace("shapes/font_map.cc", "void translate_utf8_to_font_hex(std::string& text, bool use_special_chars) {",
r'''static bool font_map_legacy_korean = false;

void set_font_map_legacy_korean(bool value) {
    font_map_legacy_korean = value;
}

// This is an explicit legacy-Korean game mode, not an encoding guess.
// A complete Hangul byte stream must reach the bitmap renderer unchanged.
static bool is_legacy_korean_text(std::string_view text) {
    bool hangul = false;
    for (size_t i = 0; i < text.size();) {
        const auto lead = static_cast<unsigned char>(text[i]);
        if (lead < 0x80) { ++i; continue; }
        if (i + 1 >= text.size()) return false;
        const auto trail = static_cast<unsigned char>(text[i + 1]);
        if (lead < 0xb0 || lead > 0xc8 || trail < 0xa1 || trail > 0xfe) return false;
        hangul = true;
        i += 2;
    }
    return hangul;
}

void translate_utf8_to_font_hex(std::string& text, bool use_special_chars) {
    if (font_map_legacy_korean && is_legacy_korean_text(text)) return;''')

# Approved B: one-pixel outline plus an extra down/right shadow; reserve
# one transparent advance column so punctuation cannot overpaint the shadow.
p = Path("upstream/shapes/font.cc")
text = p.read_text()
text = text.replace('int width() const { return glyph_width + 2; }',
                    'int width() const { return glyph_width + 4; }')
text = text.replace('int height() const { return glyph_height + 2; }',
                    'int height() const { return glyph_height + 4; }')
text = text.replace('korean_font.height() - 1', 'korean_font.height() - 3')
needle = '        for (int row = 0; row < glyph_height; ++row)\n            for (int col = 0; col < glyph_width; ++col)\n                if (glyph[row'
assert text.count(needle) == 1
shadow = '''        if (outline_colour != ink_colour) {
            const auto border = pixels;
            for (int row = 0; row + 1 < h; ++row)
                for (int col = 0; col + 1 < w; ++col)
                    if (border[row * w + col] != 255)
                        pixels[(row + 1) * w + col + 1] = outline_colour;
        }
'''
text = text.replace(needle, shadow + needle)

# Both fixed-width drawing overloads must consume a whole Hangul pair.
a = text.index('int Font::paint_text_fixedwidth(')
b = text.index('int Font::get_text_width(', a)
section = text[a:b]
needle = '\twhile ((chr = *text++) != 0) {'
assert section.count(needle) == 1
section = section.replace(needle, '''\twhile ((chr = *text) != 0) {
        if (korean_font.is_pair(text, 2)) {
            const int advance = std::max(2 * width, korean_font.width());
            korean_font.paint(win, x + (advance - korean_font.width()) / 2,
                yoff - get_text_baseline(), text, trans,
                korean_ink_colour(font_shapes.get()), korean_ink_colour(font_shapes.get(), true));
            x += advance;
            text += 2;
            continue;
        }
        ++text;''')
needle = '\twhile (textlen--) {'
assert section.count(needle) == 1
section = section.replace(needle, '''\twhile (textlen > 0) {
        if (korean_font.is_pair(text, textlen)) {
            const int advance = std::max(2 * width, korean_font.width());
            korean_font.paint(win, x + (advance - korean_font.width()) / 2,
                yoff - get_text_baseline(), text, trans,
                korean_ink_colour(font_shapes.get()), korean_ink_colour(font_shapes.get(), true));
            x += advance;
            text += 2;
            textlen -= 2;
            continue;
        }
        --textlen;''')
text = text[:a] + section + text[b:]

a = text.index('void Font::get_text_box_dims(')
b = text.index('int Font::get_text_height(', a)
section = text[a:b]
needle = '\t\twhile ((chr = *text++) != 0) {'
assert section.count(needle) == 1
section = section.replace(needle, '''\t\twhile ((chr = *text) != 0) {
            if (korean_font.is_pair(text, 2)) {
                cur_width += korean_font.width() + hor_lead;
                text += 2;
                continue;
            }
            ++text;''')
text = text[:a] + section + text[b:]

a = text.index('int Font::find_xcursor(')
b = text.index('Font::Font()', a)
section = text[a:b]
needle = '\twhile (textlen--) {'
assert section.count(needle) == 1
section = section.replace(needle, '''\twhile (textlen > 0) {
        if (korean_font.is_pair(text, textlen)) {
            const int w = korean_font.width() + hor_lead;
            if (cx >= curx && cx < curx + w) return static_cast<int>(text - start);
            curx += w;
            text += 2;
            textlen -= 2;
            continue;
        }
        --textlen;''')
text = text[:a] + section + text[b:]

# The '^' marker uppercases Latin only; never measure half a Hangul pair.
text = text.replace("const bool ucase_next = *text == '^';", "bool ucase_next = *text == '^';")
needle = "\t\tif (ucase_next) {    // Skip it.\n\t\t\ttext++;\n\t\t}"
assert text.count(needle) == 3
text = text.replace(needle, needle + "\n\t\tucase_next = ucase_next && !korean_font.is_pair(text, 2);")

helper = '''
static int korean_fixed_text_width(const char* text, int length, int cell) {
    int result = 0;
    while (length > 0) {
        if (korean_font.is_pair(text, length)) {
            result += std::max(2 * cell, korean_font.width());
            text += 2; length -= 2;
        } else {
            result += cell;
            ++text; --length;
        }
    }
    return result;
}
'''
needle = '//\tWant a more restrictive test for space.'
text = text.replace(needle, helper + '\n' + needle)
needle = 'static_cast<int>(ewrd - text) * char_width'
assert text.count(needle) == 1
text = text.replace(needle, 'korean_fixed_text_width(text, static_cast<int>(ewrd - text), char_width)')
p.write_text(text)

# Keep legacy menu metrics unchanged. Expanded metrics are text-specific.
p = Path("upstream/shapes/font.cc")
text = p.read_text()
def rewrite_function(text, signature, replacement):
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for end in range(brace, len(text)):
        if text[end] == "{": depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0: return text[:start] + replacement + text[end+1:]
    raise ValueError(signature)
text = rewrite_function(text, "int Font::get_text_height()", "int Font::get_text_height() { return highest + lowest + 1; }")
text = rewrite_function(text, "int Font::get_text_baseline()", "int Font::get_text_baseline() { return highest; }")
extra = r'''
int Font::get_text_baseline(const char* text, int length) {
    if (!text) return get_text_baseline();
    if (length < 0) length = static_cast<int>(std::strlen(text));
    while (length > 0) {
        if (korean_font.is_pair(text, length))
            return std::max(get_text_baseline(), korean_font.height() - 3);
        ++text; --length;
    }
    return get_text_baseline();
}
int Font::get_text_height(const char* text, int length) {
    return get_text_height() + get_text_baseline(text, length) - get_text_baseline();
}
'''
needle = "int Font::find_cursor("
text = text.replace(needle, extra + "\n" + needle, 1)
import re
# Scope both null-terminated and explicitly bounded draw methods.
for name in ("paint_text", "paint_text_fixedwidth"):
    signatures = list(re.finditer(r"int Font::" + name + r"\(", text))
    for match in reversed(signatures):
        start=match.start(); brace=text.index("{",start); depth=0
        for end in range(brace,len(text)):
            if text[end]=="{":depth+=1
            elif text[end]=="}":
                depth-=1
                if depth==0:break
        section=text[start:end+1]
        parameters=text[start:brace]
        bounded=bool(re.search(r"\btextlen\b",parameters))
        baseline="get_text_baseline(text, textlen)" if bounded else "get_text_baseline(text)"
        section=section.replace("yoff += get_text_baseline();", "const int baseline = " + baseline + ";\n\tyoff += baseline;")
        section=section.replace("yoff - get_text_baseline()", "yoff - baseline")
        text=text[:start]+section+text[end+1:]
text = text.replace("get_text_height() + vert_lead + ver_lead", "get_text_height(text) + vert_lead + ver_lead")
# get_text_box_dims advances its pointer; retain the original text for height.
text = text.replace("void Font::get_text_box_dims(const char* text, int& width, int& height, int vert_lead) {",
                    "void Font::get_text_box_dims(const char* text, int& width, int& height, int vert_lead) {\n    const char* layout_text = text;")
text = text.replace("height = num_lines * (get_text_height(text)", "height = num_lines * (get_text_height(layout_text)")
p.write_text(text)
replace("shapes/font.h", "\tint get_text_height();",
        "\tint get_text_height();\n\tint get_text_height(const char* text, int length = -1);")
replace("shapes/font.h", "\tint get_text_baseline();",
        "\tint get_text_baseline();\n\tint get_text_baseline(const char* text, int length = -1);")
replace("shapes/fontvga.h", "\tint get_text_height(int fontnum) {",
        "\tint get_text_height(int fontnum, const char* text) { return fonts[fontnum]->get_text_height(text); }\n\tint get_text_height(int fontnum) {")
replace("shapeid.h", "\tint get_text_height(int fontnum);",
        "\tint get_text_height(int fontnum);\n\tint get_text_height(int fontnum, const char* text);")
replace("shapeid.cc", "int Shape_manager::get_text_height(int fontnum) {",
        "int Shape_manager::get_text_height(int fontnum, const char* text) { return fonts->get_text_height(fontnum, text); }\n\nint Shape_manager::get_text_height(int fontnum) {")
replace("effects.cc", "\theight = 8 + sman->get_text_height(0);",
        "\theight = 8 + sman->get_text_height(0, msg.c_str());")

# iOS lifecycle events must be watched, not just polled in gameplay.
replace("exult.cc", '#\tinclude "ios_utils.h"', '#\tinclude "ios_utils.h"\n#include <atomic>')
replace("exult.cc", 'static void Init() {', "#ifdef SDL_PLATFORM_IOS\nstatic std::atomic<bool> exult_ios_background{false};\nstatic bool exult_ios_lifecycle_paused = false;\nstatic bool exult_ios_restore_focus = false;\nstatic bool exult_ios_restore_audio = false;\n\nstatic void exult_ios_apply_lifecycle() {\n    // Event watches can run on other threads. Engine state stays on main.\n    if (!SDL_IsMainThread()) return;\n    const bool background = exult_ios_background.load();\n    if (background && !exult_ios_lifecycle_paused) {\n        exult_ios_lifecycle_paused = true;\n        exult_ios_restore_audio = Audio::get_ptr() && (!gwin || gwin->have_focus());\n        exult_ios_restore_focus = gwin && gwin->get_main_actor() && gwin->have_focus();\n        if (exult_ios_restore_focus) gwin->lose_focus();\n        if (Audio::get_ptr()) Audio::get_ptr()->pause_audio();\n        std::cerr << \"iOS lifecycle: paused for background\" << std::endl;\n    } else if (!background && exult_ios_lifecycle_paused) {\n        exult_ios_lifecycle_paused = false;\n        if (exult_ios_restore_focus) {\n            if (gwin && !gwin->have_focus()) gwin->get_focus();\n        }\n        if (exult_ios_restore_audio && Audio::get_ptr()) Audio::get_ptr()->resume_audio();\n        exult_ios_restore_audio = false;\n        exult_ios_restore_focus = false;\n        std::cerr << \"iOS lifecycle: foreground restored\" << std::endl;\n    }\n}\n\nstatic bool SDLCALL exult_ios_lifecycle_watch(void*, SDL_Event* event) {\n    switch (event->type) {\n    case SDL_EVENT_WILL_ENTER_BACKGROUND:\n    case SDL_EVENT_DID_ENTER_BACKGROUND:\n        exult_ios_background.store(true);\n        break;\n    case SDL_EVENT_DID_ENTER_FOREGROUND:\n        exult_ios_background.store(false);\n        break;\n    default:\n        return true;\n    }\n    exult_ios_apply_lifecycle();\n    return true;\n}\n\nvoid exult_ios_lifecycle_poll() {\n    exult_ios_apply_lifecycle();\n    // Do not return to animation or menu loops until iOS is interactive.\n    while (exult_ios_background.load()) {\n        SDL_PumpEvents();\n        SDL_Delay(20);\n    }\n    exult_ios_apply_lifecycle();\n}\n#endif\n" + '\nstatic void Init() {')
replace("exult.cc", '\tSDL_AddEventWatch(Handle_device_connection_event, nullptr);',
'''\tSDL_AddEventWatch(Handle_device_connection_event, nullptr);
#ifdef SDL_PLATFORM_IOS
    SDL_AddEventWatch(exult_ios_lifecycle_watch, nullptr);
#endif''')
replace("gumps/gump_utils.h", 'inline void Delay() {',
'''#ifdef SDL_PLATFORM_IOS
void exult_ios_lifecycle_poll();
#endif
inline void Delay() {''')
replace("gumps/gump_utils.h", '\t\tSDL_PumpEvents();',
'''\t\tSDL_PumpEvents();
#ifdef SDL_PLATFORM_IOS
        exult_ios_lifecycle_poll();
#endif''')
replace("gamewin.cc", 'void Game_window::get_focus() {',
        'void Game_window::get_focus() {\n\tif (focus) return; // Duplicate foreground/focus events must not resume twice.')

p=Path("upstream/exult.cc")
text=p.read_text()
needle="case SDL_EVENT_WINDOW_FOCUS_GAINED:\n"
assert text.count(needle)==2
text=text.replace(needle, needle + "#ifdef SDL_PLATFORM_IOS\n    if (exult_ios_background.load()) break;\n#endif\n")
p.write_text(text)

# Approved C: scale ASCII ink in Korean text by 11/9, then rebuild the same
# outline/drop shadow. English-only menus retain their original font shapes.
replace("shapes/font.h", "public:\n\tFont();",
        "    bool legacy_korean_layout_override = false;\npublic:\n\tFont();")
p=Path("upstream/shapes/font.cc")
text=p.read_text()
text=text.replace('#include "palette.h"', '#include "palette.h"\n#include <cmath>')
needle="static int korean_fixed_text_width"
assert text.count(needle)==1
text=text.replace(needle, "\nstruct Korean_ascii_glyph {\n    std::vector<unsigned char> pixels;\n    int w = 0, h = 0, xleft = 0, yabove = 0, step = 0;\n    Korean_ascii_glyph(Shape_frame* source, int hlead, unsigned char shadow) {\n        const int sw = source->get_width(), sh = source->get_height();\n        Image_buffer8 sample(sw, sh);\n        sample.fill8(255);\n        source->paint_rle(&sample, source->get_xleft(), source->get_yabove());\n        int xmin = sw, ymin = sh, xmax = -1, ymax = -1;\n        bool monochrome = false;\n        auto bounds = [&](bool include_shadow) {\n            for (int y = 0; y < sh; ++y) for (int x = 0; x < sw; ++x) {\n                const auto c = sample.get_pixel8(x, y);\n                if (c == 255 || (!include_shadow && c == shadow)) continue;\n                xmin = std::min(xmin, x); ymin = std::min(ymin, y);\n                xmax = std::max(xmax, x); ymax = std::max(ymax, y);\n            }\n        };\n        bounds(false);\n        if (xmax < 0) { monochrome = true; bounds(true); }\n        const double scale = 11.0 / 9.0;\n        if (xmax < 0) {\n            step = std::max(0, static_cast<int>(std::lround((sw + hlead) * scale)));\n            return;\n        }\n        const int oldw = xmax - xmin + 1, oldh = ymax - ymin + 1;\n        const int iw = std::max(1, static_cast<int>(std::lround(oldw * scale)));\n        const int ih = std::max(1, static_cast<int>(std::lround(oldh * scale)));\n        const int left = static_cast<int>(std::lround((xmin - source->get_xleft()) * scale));\n        const int top = static_cast<int>(std::lround((ymin - source->get_yabove()) * scale));\n        w = iw + 3; h = ih + 3; xleft = 1 - left; yabove = 1 - top;\n        pixels.assign(w * h, 255);\n        std::vector<unsigned char> ink(w * h, 255);\n        for (int y = 0; y < ih; ++y) for (int x = 0; x < iw; ++x) {\n            const int sx = xmin + std::min(oldw - 1, static_cast<int>(x / scale));\n            const int sy = ymin + std::min(oldh - 1, static_cast<int>(y / scale));\n            const auto c = sample.get_pixel8(sx, sy);\n            if (c == 255 || (!monochrome && c == shadow)) continue;\n            ink[(y + 1) * w + x + 1] = c;\n            if (!monochrome)\n                for (int dy = 0; dy < 3; ++dy) for (int dx = 0; dx < 3; ++dx)\n                    pixels[(y + dy) * w + x + dx] = shadow;\n        }\n        if (!monochrome) {\n            const auto border = pixels;\n            for (int y = 0; y + 1 < h; ++y) for (int x = 0; x + 1 < w; ++x)\n                if (border[y * w + x] != 255) pixels[(y + 1) * w + x + 1] = shadow;\n        }\n        int right = -1;\n        for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x) {\n            if (ink[y * w + x] != 255) pixels[y * w + x] = ink[y * w + x];\n            if (pixels[y * w + x] != 255) right = std::max(right, x - xleft);\n        }\n        step = right + 1;\n    }\n    int advance() const { return step; }\n    void paint(int x, int y, unsigned char* trans) {\n        if (pixels.empty()) return;\n        Shape_frame frame(pixels.data(), w, h, xleft, yabove, true);\n        if (trans) frame.paint_rle_remapped(x, y, trans); else frame.paint_rle(x, y);\n    }\n};\n\nstatic bool contains_legacy_korean(const char* text, int length) {\n    if (!text) return false;\n    if (length < 0) length = static_cast<int>(std::strlen(text));\n    for (int i = 0; i < length; ++i)\n        if (korean_font.is_pair(text + i, length - i)) return true;\n    return false;\n}\nstruct Korean_layout_scope {\n    bool& slot;\n    const bool saved;\n    Korean_layout_scope(bool& value, bool korean) : slot(value), saved(value) { slot = slot || korean; }\n    ~Korean_layout_scope() { slot = saved; }\n};\n" + "\n" + needle)
# Guard complete paragraphs so measurements of Latin-only words/spaces agree
# with their rendering in a mixed Korean paragraph.
for name in ("paint_text_box", "paint_text_box_fixedwidth", "find_cursor"):
    start=text.index("int Font::"+name+"(")
    brace=text.index("{",start)
    text=text[:brace+1] + "\n    Korean_layout_scope layout(legacy_korean_layout_override, contains_legacy_korean(text, -1));" + text[brace+1:]
# Determine style once before pointers are advanced.
for name in ("paint_text", "paint_text_fixedwidth", "get_text_width", "find_xcursor", "get_text_box_dims"):
    pattern=r"(?:int|void) Font::"+name+r"\("
    for match in reversed(list(re.finditer(pattern,text))):
        brace=text.index("{",match.start())
        bounded=bool(re.search(r"\btextlen\b",text[match.start():brace]))
        length="textlen" if bounded else "-1"
        text=text[:brace+1]+"\n    const bool korean_layout = legacy_korean_layout_override || contains_legacy_korean(text, "+length+");"+text[brace+1:]
# Latin text inside a mixed paragraph uses its parent's baseline as well.
text=text.replace("if (!text) return get_text_baseline();",
                  "if (legacy_korean_layout_override) return std::max(get_text_baseline(), korean_font.height() - 3);\n    if (!text) return get_text_baseline();")
# Drawing overloads.
for name in ("paint_text", "paint_text_fixedwidth"):
    for match in reversed(list(re.finditer(r"int Font::"+name+r"\(",text))):
        start=match.start();brace=text.index("{",start);depth=0
        for end in range(brace,len(text)):
            if text[end]=="{":depth+=1
            elif text[end]=="}":
                depth-=1
                if depth==0:break
        section=text[start:end+1]
        needle="\t\t\tif (trans) {" if name=="paint_text" else "\t\tif (trans) {"
        assert section.count(needle)==1
        if name=="paint_text":
            addition='''            if (korean_layout) {
                Korean_ascii_glyph glyph(shape, hor_lead, korean_ink_colour(font_shapes.get(), true));
                glyph.paint(x, yoff, trans);
                x += glyph.advance();
                continue;
            }
'''
        else:
            addition='''        if (korean_layout) {
            Korean_ascii_glyph glyph(shape, hor_lead, korean_ink_colour(font_shapes.get(), true));
            // Undo the legacy centring step already applied above.
            x -= w;
            const int advance = std::max(width, glyph.advance());
            glyph.paint(x + (advance - glyph.advance()) / 2, yoff, trans);
            x += advance;
            continue;
        }
'''
        section=section.replace(needle,addition+needle)
        text=text[:start]+section+text[end+1:]
# Shared measurement/cursor formula for scaled ASCII.
text=text.replace("width += shape->get_width() + hor_lead;",
                  "width += korean_layout ? Korean_ascii_glyph(shape, hor_lead, korean_ink_colour(font_shapes.get(), true)).advance() : shape->get_width() + hor_lead;")
text=text.replace("cur_width += shape->get_width() + hor_lead;",
                  "cur_width += korean_layout ? Korean_ascii_glyph(shape, hor_lead, korean_ink_colour(font_shapes.get(), true)).advance() : shape->get_width() + hor_lead;")
text=text.replace("const int w = shape->get_width() + hor_lead;",
                  "const int w = korean_layout ? Korean_ascii_glyph(shape, hor_lead, korean_ink_colour(font_shapes.get(), true)).advance() : shape->get_width() + hor_lead;")
# Preserve Korean context when '^' uppercases the first Latin character.
needle="width        = get_text_width(&c, 1u) + get_text_width(text + 1, static_cast<uint32>(ewrd - text - 1));"
assert text.count(needle)==2
text=text.replace(needle, "std::string capitalized(text, ewrd - text);\n            if (!capitalized.empty()) capitalized[0] = c;\n            width = get_text_width(capitalized.c_str());")
# Fixed-width layout uses the same expanded ASCII advance as its draw path.
text=text.replace("korean_fixed_text_width(const char* text, int length, int cell)",
                  "korean_fixed_text_width(const char* text, int length, int cell, Shape_file* shapes = nullptr, bool style = false, int hlead = 0)")
text=text.replace("result += cell;\n            ++text; --length;",
'''            auto* shape = shapes ? shapes->get_frame(static_cast<unsigned char>(*text)) : nullptr;
            result += style && shape && shape->is_rle()
                ? std::max(cell, Korean_ascii_glyph(shape, hlead, korean_ink_colour(shapes, true)).advance()) : cell;
            ++text; --length;''')
text=text.replace("korean_fixed_text_width(text, static_cast<int>(ewrd - text), char_width)",
                  "korean_fixed_text_width(text, static_cast<int>(ewrd - text), char_width, font_shapes.get(), legacy_korean_layout_override, hor_lead)")
p.write_text(text)

# Detaching a gump must detach its compositor layers before callbacks can
# open another modal or enter a blocking conversation in a derived destructor.
replace("gumps/Gump_manager.cc", "bool Gump_manager::remove_gump(Gump* gump) {",
'''bool Gump_manager::remove_gump(Gump* gump) {
    gump->free_render_layer();''')

# Keep the notebook clear of rounded iPhone display corners. Move the gump
# itself so its layer and inverse input mapping share the same new origin.
replace("gumps/Notebook_gump.cc", "\tset_pos(5, -2);",
'''#if defined(SDL_PLATFORM_IOS)
    set_pos(32, 4);
#else
    set_pos(5, -2);
#endif''')

# Fit only the launcher/menu scenes; keep gameplay video settings untouched.
p = Path("upstream/exultmenu.cc")
text = p.read_text()
helper = """
static void fit_launcher_scene(Scene_view& scene, int w, int h) {
    auto* gwin = Game_window::get_instance();
    auto* win = gwin->get_win();
    const int dw = win->get_display_width(), dh = win->get_display_height();
    // Integer arithmetic preserves the scene ratio without cropping.
    int width = dw, height = static_cast<int>(static_cast<long long>(dw) * h / w);
    if (height > dh) {
        height = dh;
        width = static_cast<int>(static_cast<long long>(dh) * w / h);
    }
    gwin->layer_set_dest(scene.get_handle(), (dw - width) / 2, (dh - height) / 2, width, height);
}
"""
anchor = 'using std::'
position = text.find(anchor)
if position < 0: raise RuntimeError("Launcher helper anchor missing")
text = text[:position] + helper + "\n" + text[position:]
for anchor, call in [
    ("Scene_view mods_scene(dummy_topx, dummy_topy, centerx, centery, ibuf, true, scene_w, scene_h);",
     "fit_launcher_scene(mods_scene, scene_w, scene_h);"),
    ("Scene_view logo_scene(splash_topx, splash_topy, centerx, centery, ibuf, false, 320, 200);",
     "fit_launcher_scene(logo_scene, 320, 200);"),
    ("menu_scene.emplace(dummy_topx, dummy_topy, centerx, centery, ibuf, true, scene_w, scene_h);",
     "fit_launcher_scene(*menu_scene, scene_w, scene_h);")]:
    if text.count(anchor) != 1: raise RuntimeError("Launcher scene anchor missing")
    text = text.replace(anchor, anchor + "\n    " + call)
p.write_text(text)

# On touch devices accept the full checkmark rectangle, including transparent
# gaps between strokes. Both press and release use this same virtual method.
replace("gumps/misc_buttons.h", "\tCheckmark_button(Gump* par, int px, int py);",
'''\tCheckmark_button(Gump* par, int px, int py);
    bool on_widget(int mx, int my) const override;''')
replace("gumps/misc_buttons.cc", "bool Checkmark_button::activate(MouseButton button) {",
'''bool Checkmark_button::on_widget(int mx, int my) const {
#if defined(SDL_PLATFORM_IOS)
    TileRect hit = get_rect();
    hit.enlarge(3);
    return hit.has_point(mx, my);
#else
    return Gump_widget::on_widget(mx, my);
#endif
}

bool Checkmark_button::activate(MouseButton button) {''')

# Let a tap outside the notebook dismiss the native keyboard. Do not open it
# just for reading: tapping a page still starts text entry through on_button.
replace("gumps/Notebook_gump.cc",
'''            PLACEHOLDER''', '''PLACEHOLDER''') if False else None
p = Path("upstream/gumps/Notebook_gump.cc")
text = p.read_text()
start = text.index("Notebook_gump* Notebook_gump::create()")
end = text.index("Notebook_gump::~Notebook_gump()", start)
section = text[start:end]
anchor = """\t\t\tif (!SDL_TextInputActive(window)) {
\t\t\t\tTouchUI::startTextInput(window);
\t\t\t}"""
if section.count(anchor) != 1: raise RuntimeError("Notebook keyboard anchor missing")
section = section.replace(anchor, """#if !defined(SDL_PLATFORM_IOS)
""" + anchor + """
#else
            if (SDL_TextInputActive(window)) SDL_StopTextInput(window);
#endif""")
text = text[:start] + section + text[end:]
anchor = "\tGump_button* btn = Gump::on_button(mx, my);"
if text.count(anchor) != 1: raise RuntimeError("Notebook input anchor missing")
text = text.replace(anchor, """#if defined(SDL_PLATFORM_IOS)
    if (!get_rect().has_point(mx, my)) {
        SDL_Window* window = gwin->get_win()->get_screen_window();
        if (SDL_TextInputActive(window)) SDL_StopTextInput(window);
        return nullptr;
    }
#endif
""" + anchor)
p.write_text(text)
