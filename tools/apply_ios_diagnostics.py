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
    set_pos(64, 8);
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
    // Exult launcher artwork uses its native 16:10 source aspect ratio.
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
p = Path("upstream/gumps/Notebook_gump.cc")
text = p.read_text()
start = text.index("Notebook_gump* Notebook_gump::create()")
end = text.index("Notebook_gump::~Notebook_gump()", start)
section = text[start:end]
anchor = """\t\t\tif (!SDL_TextInputActive(window)) {
\t\t\t\tTouchUI::startTextInput(window);
\t\t\t}"""
if section.count(anchor) != 1: raise RuntimeError("Notebook keyboard anchor missing")
# Preserve upstream automatic text-input activation on every platform.
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

# Install a common native keyboard-dismiss control, independent of gump type.
replace("ios/ios_utils.mm", "void KoreanIOSDiagnostics() {", "static void InstallExultKeyboardDismissControl();\nvoid KoreanIOSDiagnostics() {\n    InstallExultKeyboardDismissControl();")
p = Path("upstream/ios/ios_utils.mm")
p.write_text(p.read_text() + r'''
#import <SDL3/SDL.h>

// One native dismissal control for every SDL text-input screen.
static UIView* ExultFindKeyboardResponder(UIView* view) {
    if (view.isFirstResponder) return view;
    for (UIView* child in view.subviews) {
        UIView* responder = ExultFindKeyboardResponder(child);
        if (responder) return responder;
    }
    return nil;
}

@interface ExultKeyboardDismissControl : NSObject
@property(nonatomic, strong) UIToolbar* toolbar;
- (void)keyboardFrame:(NSNotification*)notification;
- (void)keyboardHidden:(NSNotification*)notification;
- (void)dismissKeyboard;
@end

@implementation ExultKeyboardDismissControl
- (void)keyboardFrame:(NSNotification*)notification {
    (void)notification;
    SDL_Window* sdlWindow = SDL_GetKeyboardFocus();
    if (!sdlWindow) return;
    UIWindow* window = (__bridge UIWindow*)SDL_GetPointerProperty(
        SDL_GetWindowProperties(sdlWindow), SDL_PROP_WINDOW_UIKIT_WINDOW_POINTER, nullptr);
    if (!window) return;
    UIView* responder = ExultFindKeyboardResponder(window);
    if (!responder) return;
    if (!self.toolbar) {
        self.toolbar = [[UIToolbar alloc] initWithFrame:CGRectMake(0, 0, window.bounds.size.width, 44)];
        self.toolbar.autoresizingMask = UIViewAutoresizingFlexibleWidth;
        UIBarButtonItem* space = [[UIBarButtonItem alloc]
            initWithBarButtonSystemItem:UIBarButtonSystemItemFlexibleSpace target:nil action:nil];
        UIBarButtonItem* done = [[UIBarButtonItem alloc]
            initWithBarButtonSystemItem:UIBarButtonSystemItemDone target:self action:@selector(dismissKeyboard)];
        self.toolbar.items = @[space, done];
    }
    // SDL's iOS text input uses a UITextField. Use the native accessory slot,
    // so UIKit handles keyboard animation, orientation and safe-area layout.
    if ([responder isKindOfClass:UITextField.class]) {
        UITextField* field = (UITextField*)responder;
        if (field.inputAccessoryView != self.toolbar) {
            field.inputAccessoryView = self.toolbar;
            [field reloadInputViews];
        }
    } else if ([responder isKindOfClass:UITextView.class]) {
        UITextView* field = (UITextView*)responder;
        if (field.inputAccessoryView != self.toolbar) {
            field.inputAccessoryView = self.toolbar;
            [field reloadInputViews];
        }
    }
}
- (void)keyboardHidden:(NSNotification*)notification {
    (void)notification; // UIKit owns accessory visibility.
}
- (void)dismissKeyboard {
    SDL_RunOnMainThread([](void*) {
        SDL_Window* window = SDL_GetKeyboardFocus();
        if (window && SDL_TextInputActive(window)) SDL_StopTextInput(window);
    }, nullptr, false);
}
@end

static void InstallExultKeyboardDismissControl() {
    static ExultKeyboardDismissControl* control = nil;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        control = [[ExultKeyboardDismissControl alloc] init];
        NSNotificationCenter* center = NSNotificationCenter.defaultCenter;
        [center addObserver:control selector:@selector(keyboardFrame:)
                       name:UIKeyboardWillChangeFrameNotification object:nil];
        [center addObserver:control selector:@selector(keyboardHidden:)
                       name:UIKeyboardWillHideNotification object:nil];
    });
}
''')

# Every iOS takeover scene (BG/SI logos, intro, title, character creation,
# credits and loading scenes) use the original DOS 4:3 display ratio.
# Layer inverse transforms already use this destination for touch mapping.
replace("scene_layer.h",
'''\t\t\tgwin->layer_set_opaque(handle, true);''',
'''\t\t\tgwin->layer_set_opaque(handle, true);
#ifdef SDL_PLATFORM_IOS
            const int dw = iwin->get_display_width(), dh = iwin->get_display_height();
            int width = dw;
            int height = static_cast<int>(static_cast<long long>(dw) * 3 / 4);
            if (height > dh) {
                height = dh;
                width = static_cast<int>(static_cast<long long>(dh) * 4 / 3);
            }
            gwin->layer_set_dest(handle, (dw - width) / 2, (dh - height) / 2, width, height);
#endif''')

# Button centering must measure the actual Korean label, not Latin-only metrics.
replace("gumps/Text_button.cc",
        "const int text_height = font->get_text_height();",
        "const int text_height = font->get_text_height(text.c_str());")

# Engine-owned touch actions, authored here; game-provided object/NPC/place
# names remain obj->get_name() so the installed Korean translation is canonical.
replace("gumps/ItemMenu_gump.cc", '#include "items.h"',
        '#include "items.h"\n#include "font.h"')
p = Path("upstream/gumps/ItemMenu_gump.cc")
text = p.read_text()
for message, korean in [
    (0x650, "소지품 보기"), (0x651, "대화하기"),
    (0x652, "내용물 보기"), (0x653, "사용하기"),
    (0x654, "집기"), (0x655, "옮기기"), (0x656, "아무것도 안 하기")]:
    original = "return get_text_msg(0x%x - msg_file_start);" % message
    literal = "".join("\\x%02x" % byte for byte in korean.encode("euc_kr"))
    if text.count(original) != 1: raise RuntimeError("Touch action anchor missing")
    text = text.replace(original,
        'if (legacy_korean_font_available()) return "' + literal + '";\n\t\t' + original)
cancel = "".join("\\x%02x" % byte for byte in "취소".encode("euc_kr"))
anchor = "class Strings : public GumpStrings {\npublic:"
if text.count(anchor) != 1: raise RuntimeError("Touch strings anchor missing")
text = text.replace(anchor, anchor + '\n    static const char* Cancel() {\n'
    '        if (legacy_korean_font_available()) return "' + cancel + '";\n'
    '        return GumpStrings::Cancel();\n    }')
p.write_text(text)

# Clamp the real union of translated button rectangles, rather than assuming
# every menu is 100 pixels wide and each button has the nominal height.
p = Path("upstream/gumps/ItemMenu_gump.cc")
text = p.read_text()
start = text.index("void Itemmenu_gump::fix_position(int num_elements) {")
end = text.index("\nItemmenu_gump::Itemmenu_gump(", start)
text = text[:start] + """void Itemmenu_gump::fix_position(int num_elements) {
    (void)num_elements;
    const int w = Game_window::get_instance()->get_width();
    const int h = Game_window::get_instance()->get_height();
    const TileRect bounds = get_rect();
    const int max_x = w > bounds.w ? w - bounds.w : 0;
    const int max_y = h > bounds.h ? h - bounds.h : 0;
    x += clamp(bounds.x, 0, max_x) - bounds.x;
    y += clamp(bounds.y, 0, max_y) - bounds.y;
}
""" + text[end:]
p.write_text(text)

# Approved B: one extra horizontal ink pixel for Korean Text_button labels.
# The existing four-pixel glyph padding contains the dilation, preserving
# advances and leaving room before the next character. Other text is unchanged.
replace("shapes/font.h", "bool legacy_korean_font_available();",
        "bool legacy_korean_font_available();\nbool set_legacy_korean_button_bold(bool enabled);")
replace("shapes/font.cc", "static bool legacy_korean_font_enabled = true;",
'''static bool legacy_korean_font_enabled = true;
static bool legacy_korean_button_bold = false;
bool set_legacy_korean_button_bold(bool enabled) {
    const bool previous = legacy_korean_button_bold;
    legacy_korean_button_bold = enabled;
    return previous;
}''')
replace("shapes/font.cc",
'''                    pixels[(row + 1) * w + col + 1] = ink_colour;''',
'''                {
                    pixels[(row + 1) * w + col + 1] = ink_colour;
                    if (legacy_korean_button_bold)
                        pixels[(row + 1) * w + col + 2] = ink_colour;
                }''')
replace("gumps/Text_button.cc", "void Text_button::paint() {",
'''namespace {
struct Korean_button_weight_scope {
    const bool previous = set_legacy_korean_button_bold(true);
    ~Korean_button_weight_scope() { set_legacy_korean_button_bold(previous); }
};
}
void Text_button::paint() {
    Korean_button_weight_scope korean_weight;''')

# Resolve legacy NPC display labels from the installed translation, without
# bundling any translation text or modifying savegame names.
replace("gumps/ItemMenu_gump.cc", '#include "font.h"',
        '#include "font.h"\n#include "fnames.h"\n#include "U7file.h"\n#include <map>')
replace("gumps/ItemMenu_gump.cc", "using Itemmenu_button =", "\nstatic std::string korean_touch_object_name(Game_object* object) {\n    const std::string original = object->get_name();\n    Actor* actor = object->as_actor();\n    // Never reveal an unmet actor, replace the Avatar's chosen name, or\n    // override a name that is already localized.\n    if (!legacy_korean_font_available() || !actor || actor->get_npc_num() <= 0\n        || !actor->get_flag(Obj_flags::met)) return original;\n    for (unsigned char c : original) if (c >= 0x80) return original;\n    const char* source = is_system_path_defined(\"<PATCH>\") && U7exists(PATCH_USECODE)\n        ? PATCH_USECODE : USECODE;\n    const std::string path = get_system_path(source);\n    static std::string cached_path;\n    static std::map<int, std::string> translated;\n    if (path != cached_path) {\n        cached_path = path;\n        translated.clear();\n        IFileDataSource input(source, true);\n        if (input.good() && input.getSize() == 1446254) {\n            std::vector<unsigned char> bytes(input.getSize());\n            input.read(bytes.data(), bytes.size());\n            unsigned long long hash = 14695981039346656037ULL;\n            for (auto c : bytes) hash = (hash ^ c) * 1099511628211ULL;\n            // Only offsets and a checksum are shipped; all actual names are\n            // read from the user's installed Korean translation at runtime.\n            if (hash == 7035595989666174218ULL) {\n                struct Entry { int npc; unsigned offset; unsigned length; };\n                static const Entry entries[] = {\n                    {1,157882,6},\n                    {2,165885,6},\n                    {3,174029,6},\n                    {4,178842,6},\n                    {5,185247,4},\n                    {6,189151,6},\n                    {7,193248,6},\n                    {8,197611,6},\n                    {9,202389,8},\n                    {10,207401,8},\n                    {11,218429,6},\n                    {12,222036,6},\n                    {13,228452,8},\n                    {14,231325,4},\n                    {15,233060,6},\n                    {16,235357,4},\n                    {17,238778,4},\n                    {18,240153,2},\n                    {19,242350,10},\n                    {20,244695,6},\n                    {21,245678,6},\n                    {22,249228,8},\n                    {23,251284,13},\n                    {24,264720,6},\n                    {25,266535,4},\n                    {26,269173,6},\n                    {27,281464,8},\n                    {28,285577,4},\n                    {29,287819,8},\n                    {30,289922,4},\n                    {31,292278,8},\n                    {32,293653,4},\n                    {33,295096,8},\n                    {34,296491,4},\n                    {35,299986,2},\n                    {36,303398,4},\n                    {37,305667,4},\n                    {38,308287,4},\n                    {39,312329,4},\n                    {40,314146,6},\n                    {41,316541,6},\n                    {42,320534,6},\n                    {43,324514,6},\n                    {44,330770,8},\n                    {45,336303,4},\n                    {46,341192,6},\n                    {47,345716,4},\n                    {48,348017,6},\n                    {49,351571,4},\n                    {50,353156,6},\n                    {51,355079,4},\n                    {52,357896,4},\n                    {53,363469,4},\n                    {54,366266,2},\n                    {55,369885,8},\n                    {56,372453,6},\n                    {57,374950,6},\n                    {58,377953,4},\n                    {59,381130,2},\n                    {60,384821,8},\n                    {61,388085,2},\n                    {62,393744,6},\n                    {63,399802,4},\n                    {64,402754,6},\n                    {65,404716,6},\n                    {66,406319,4},\n                    {67,408676,4},\n                    {68,410691,4},\n                    {69,412485,6},\n                    {70,417533,6},\n                    {71,421036,12},\n                    {72,423242,2},\n                    {73,425561,4},\n                    {74,428429,6},\n                    {75,431733,8},\n                    {76,436940,8},\n                    {77,438612,7},\n                    {78,441727,6},\n                    {79,443162,8},\n                    {80,444790,9},\n                    {81,446097,6},\n                    {82,455247,6},\n                    {83,458415,8},\n                    {84,460315,4},\n                    {85,461881,10},\n                    {86,466467,6},\n                    {87,469643,4},\n                    {88,473505,4},\n                    {89,477381,2},\n                    {90,481195,4},\n                    {91,490813,8},\n                    {92,496203,8},\n                    {93,500331,6},\n                    {94,503040,6},\n                    {95,506183,4},\n                    {96,510289,4},\n                    {97,513218,8},\n                    {98,515310,6},\n                    {99,517883,6},\n                    {100,519087,6},\n                    {101,521104,6},\n                    {102,524184,10},\n                    {103,530056,4},\n                    {104,532145,8},\n                    {105,534550,7},\n                    {106,536101,6},\n                    {107,538542,8},\n                    {108,544150,6},\n                    {109,548666,4},\n                    {110,551666,4},\n                    {111,555992,4},\n                    {112,557299,4},\n                    {113,559779,6},\n                    {114,563244,6},\n                    {115,566037,4},\n                    {116,568686,2},\n                    {117,571452,4},\n                    {118,574069,4},\n                    {119,576412,7},\n                    {120,580848,4},\n                    {121,586257,6},\n                    {122,591160,8},\n                    {123,597918,6},\n                    {124,601898,8},\n                    {125,609699,6},\n                    {126,613795,6},\n                    {127,616976,6},\n                    {128,619739,8},\n                    {129,621260,4},\n                    {130,625363,6},\n                    {131,630759,6},\n                    {132,634920,4},\n                    {133,638193,8},\n                    {134,642705,4},\n                    {135,648738,6},\n                    {136,651545,4},\n                    {137,656055,2},\n                    {138,661293,4},\n                    {140,668350,4},\n                    {141,674863,6},\n                    {142,679125,6},\n                    {143,685142,6},\n                    {144,691706,6},\n                    {145,693727,8},\n                    {146,698440,6},\n                    {147,706771,8},\n                    {149,714345,4},\n                    {150,718348,8},\n                    {151,724385,6},\n                    {152,728498,4},\n                    {153,733752,8},\n                    {154,737301,6},\n                    {155,741089,6},\n                    {156,744344,8},\n                    {157,749308,6},\n                    {158,752360,4},\n                    {159,754128,6},\n                    {160,755443,6},\n                    {161,758637,4},\n                    {162,760697,6},\n                    {163,764505,6},\n                    {164,769552,4},\n                    {165,772589,6},\n                    {166,775635,6},\n                    {167,779785,8},\n                    {168,787220,6},\n                    {169,791364,6},\n                    {170,794102,4},\n                    {171,796840,4},\n                    {172,802620,4},\n                    {173,809711,8},\n                    {174,814847,6},\n                    {175,817800,2},\n                    {176,821571,6},\n                    {177,825451,4},\n                    {178,829002,8},\n                    {179,833764,4},\n                    {180,835899,10},\n                    {181,840375,6},\n                    {182,841978,8},\n                    {183,844028,8},\n                    {184,849015,6},\n                    {185,850159,2},\n                    {186,854088,6},\n                    {187,856793,6},\n                    {188,858237,6},\n                    {189,860269,6},\n                    {190,863842,6},\n                    {191,866506,6},\n                    {192,872122,6},\n                    {193,874223,9},\n                    {194,876810,2},\n                    {195,881210,7},\n                    {196,886379,6},\n                    {197,891063,6},\n                    {198,892947,4},\n                    {199,895842,7},\n                    {200,901386,4},\n                    {201,906195,4},\n                    {202,908754,4},\n                    {203,911815,6},\n                    {204,914385,4},\n                    {205,916492,4},\n                    {206,919245,8},\n                    {207,921695,4},\n                    {208,924962,6},\n                    {209,927048,6},\n                    {210,930705,6},\n                    {211,933652,5},\n                    {212,935967,6},\n                    {213,940210,6},\n                    {214,941401,5},\n                    {215,943402,10},\n                    {216,946168,9},\n                    {219,950344,12},\n                    {220,952228,6},\n                    {221,957174,4},\n                    {222,960067,6},\n                    {223,964494,4},\n                    {224,968031,8},\n                    {225,970928,4},\n                    {226,973917,8},\n                    {227,977404,6},\n                    {228,981485,6},\n                    {229,983468,4},\n                    {230,987691,4},\n                    {231,991508,4},\n                    {232,997740,6},\n                    {233,999644,2},\n                    {236,1001899,4},\n                    {237,1003210,6},\n                    {238,1007549,4},\n                    {239,1009690,6},\n                    {240,1017104,4},\n                    {241,1020664,6},\n                    {242,1024334,6},\n                    {243,1028588,6},\n                    {244,1034576,6},\n                    {245,1036932,4},\n                    {246,1039874,8},\n                    {247,1044741,4},\n                    {248,1051827,8},\n                    {249,1057962,4},\n                    {250,1063558,4},\n                    {251,1069877,6},\n                    {252,1076002,10},\n                    {253,1078070,6},\n                    {254,1080531,4},\n                    {255,1088489,4},\n                };\n                for (const auto& entry : entries) {\n                    if (entry.offset + entry.length <= bytes.size())\n                        translated.emplace(entry.npc, std::string(\n                            reinterpret_cast<const char*>(bytes.data() + entry.offset), entry.length));\n                }\n            }\n        }\n    }\n    const auto found = translated.find(actor->get_npc_num());\n    return found == translated.end() ? original : found->second;\n}\n\nusing Itemmenu_button =")
replace("gumps/ItemMenu_gump.cc", "std::string  name = o->get_name();",
        "std::string  name = korean_touch_object_name(o);")

# Signs receive translated place names through usecode. Measure the actual
# tallest line, keeping existing rune conversion and text unchanged.
replace("gumps/Sign_gump.cc",
        "const int lheight = sman->get_text_height(font);",
'''int lheight = sman->get_text_height(font);
    for (int i = 0; i < num_lines; ++i) {
        const int height = sman->get_text_height(font, lines[i].c_str());
        if (height > lheight) lheight = height;
    }''')


# Audit fix: measure painted pixels, including negative bearings and shadows.
replace("shapes/font.h", "\tint get_text_height();",
        "\tvoid get_text_ink_bounds(const char* text, int& left, int& top, int& width, int& height);\n\tint get_text_height();")
replace("shapes/font.cc", "int height() const { return glyph_height + 4; }",
r'''int height() const { return glyph_height + 4; }
    void ink_bounds(const char* text, bool outline, int& l, int& t, int& r, int& b) {
        const auto index = (static_cast<unsigned char>(text[0]) - 0xb0) * 94
                         + static_cast<unsigned char>(text[1]) - 0xa1;
        const auto* glyph = glyphs.data() + index * bytes_per_glyph;
        l = width(); t = height(); r = b = -1;
        for (int y = 0; y < glyph_height; ++y)
            for (int x = 0; x < glyph_width; ++x)
                if (glyph[y * bytes_per_row + x / 8] & (0x80 >> (x % 8))) {
                    l = std::min(l, x + 1); t = std::min(t, y + 1);
                    r = std::max(r, x + 1); b = std::max(b, y + 1);
                }
        if (r < 0) return;
        if (outline) { --l; --t; r += 2; b += 2; }
        else if (legacy_korean_button_bold) ++r;
    }''')
# Small monochrome button digits must share the Korean ink's vertical centre.
replace("shapes/font.cc",
        "w = iw + 3; h = ih + 3; xleft = 1 - left; yabove = 1 - top;",
'''w = iw + 3; h = ih + 3; xleft = 1 - left; yabove = 1 - top;
        if (legacy_korean_button_bold && monochrome)
            yabove = korean_font.height() - 3 - (korean_font.height() - 4 - ih) / 2;''')
p = Path("upstream/shapes/font.cc")
p.write_text(p.read_text() + r'''

void Font::get_text_ink_bounds(const char* text, int& left, int& top, int& width, int& height) {
    left = top = width = height = 0;
    if (!text || !font_shapes) return;
    const bool style = legacy_korean_layout_override || contains_legacy_korean(text, -1);
    const int baseline = get_text_baseline(text);
    const auto ink = korean_ink_colour(font_shapes.get());
    const auto shadow = korean_ink_colour(font_shapes.get(), true);
    int pen = 0, right = 0, bottom = 0;
    bool found = false;
    auto include = [&](int l, int t, int r, int b) {
        if (r < l || b < t) return;
        if (!found) { left = l; top = t; right = r; bottom = b; found = true; }
        else { left = std::min(left, l); top = std::min(top, t);
               right = std::max(right, r); bottom = std::max(bottom, b); }
    };
    for (int i = 0; text[i];) {
        if (korean_font.is_pair(text + i, 2)) {
            int l, t, r, b;
            korean_font.ink_bounds(text + i, ink != shadow, l, t, r, b);
            include(pen + l, t, pen + r, b);
            pen += korean_font.width() + hor_lead; i += 2;
            continue;
        }
        auto* shape = font_shapes->get_frame(static_cast<unsigned char>(text[i++]));
        if (!shape || !shape->is_rle()) continue;
        if (style) {
            Korean_ascii_glyph glyph(shape, hor_lead, shadow);
            for (int y = 0; y < glyph.h; ++y)
                for (int x = 0; x < glyph.w; ++x)
                    if (glyph.pixels[y * glyph.w + x] != 255)
                        include(pen + x - glyph.xleft, baseline + y - glyph.yabove,
                                pen + x - glyph.xleft, baseline + y - glyph.yabove);
            pen += glyph.advance();
        } else {
            const int sw = shape->get_width(), sh = shape->get_height();
            Image_buffer8 sample(sw, sh);
            sample.fill8(255);
            shape->paint_rle(&sample, shape->get_xleft(), shape->get_yabove());
            for (int y = 0; y < sh; ++y)
                for (int x = 0; x < sw; ++x)
                    if (sample.get_pixel8(x, y) != 255)
                        include(pen + x - shape->get_xleft(), baseline + y - shape->get_yabove(),
                                pen + x - shape->get_xleft(), baseline + y - shape->get_yabove());
            pen += sw + hor_lead;
        }
    }
    if (found) { width = right - left + 1; height = bottom - top + 1; }
}
''')

# Measure and paint buttons under the same weight/ASCII-layout scope.
p = Path("upstream/gumps/Text_button.cc")
text = p.read_text()
a = text.index("namespace {\nstruct Korean_button_weight_scope")
b = text.index("void Text_button::paint()", a)
scope = text[a:b]
text = text[:a] + text[b:]
a = text.index("void Text_button::init()")
text = text[:a] + scope + text[a:]
text = text.replace("void Text_button::init() {", """void Text_button::init() {
    Korean_button_weight_scope korean_weight;
    int ink_left, ink_top, ink_width, ink_height;
    font->get_text_ink_bounds(text.c_str(), ink_left, ink_top, ink_width, ink_height);""", 1)
text = text.replace("const int text_height = font->get_text_height(text.c_str());",
                    "const int text_height = ink_height;")
text = text.replace("const int text_width = font->get_text_width(text.c_str());",
                    "const int text_width = ink_width;")
text = text.replace("text_y = (draw_area.h - text_height) / 2;",
                    "text_y = (draw_area.h - text_height) / 2 - ink_top;")
text = text.replace("text_x = (draw_area.w - text_width) >> 1;",
                    "text_x = ((draw_area.w - text_width) >> 1) - ink_left;")
p.write_text(text)

# One sign path covers wood, gold, tombstones and runic scroll signs.
# Fit a complete ink rectangle rather than clipping an over-wide inscription.
replace("gumps/Sign_gump.cc", '#include "gamewin.h"',
        '#include "gamewin.h"\n#include "font.h"\n#include "iwin8.h"\n#include <algorithm>')
p = Path("upstream/gumps/Sign_gump.cc")
text = p.read_text()
old = """\t\tsman->paint_text(
\t\t\t\tfont, lines[i].c_str(), x + object_area.x + (object_area.w - sman->get_text_width(font, lines[i].c_str())) / 2,
\t\t\t\typos);"""
new = """        auto face = sman->get_font(font);
        int il, it, iw, ih;
        face->get_text_ink_bounds(lines[i].c_str(), il, it, iw, ih);
        if (iw > 0 && ih > 0) {
            Image_buffer8 sample(iw, ih);
            sample.fill8(255);
            auto* target = gwin->push_render_target(&sample);
            face->paint_text(&sample, lines[i].c_str(), -il, -it);
            gwin->pop_render_target(target);
            const int available = std::max(1, object_area.w - 8);
            const int dw = std::min(iw, available);
            const int dh = std::max(1, ih * dw / iw);
            const int dx = x + object_area.x + (object_area.w - dw) / 2;
            auto* output = gwin->get_win()->get_ib8();
            for (int yy = 0; yy < dh; ++yy)
                for (int xx = 0; xx < dw; ++xx) {
                    const auto c = sample.get_pixel8(xx * iw / dw, yy * ih / dh);
                    if (c != 255) output->put_pixel8(c, dx + xx, ypos + yy);
                }
        }"""
if text.count(old) != 1: raise RuntimeError("Sign ink-fit anchor missing")
text = text.replace(old, new)
p.write_text(text)

# Reserve paragraph edge space for glyph bearings/shadows. Preserve the outer
# clip, so ink may use the reserved margin without disappearing at the edge.
p = Path("upstream/shapes/font.cc")
text = p.read_text()
for signature in ("int Font::paint_text_box(", "int Font::paint_text_box_fixedwidth("):
    a = text.index(signature)
    brace = text.index("{", a)
    depth = 0
    for b in range(brace, len(text)):
        if text[b] == "{": depth += 1
        elif text[b] == "}":
            depth -= 1
            if depth == 0: break
    section = text[a:b+1]
    anchor = "\tconst int   endx"
    addition = """    // Two pixels contain Korean outline/drop-shadow overhangs.
    const int edge = std::min(2, std::max(0, (w - 1) / 2));
    x += edge; w -= 2 * edge;
"""
    if section.count(anchor) != 1: raise RuntimeError("Text box edge anchor missing")
    section = section.replace(anchor, addition + anchor, 1)
    # A long Korean token must wrap at a full two-byte glyph, never disappear
    # beyond the right edge. Keep the existing pagination return convention.
    if signature == "int Font::paint_text_box(":
        anchor = "\t\tif (curx + width - hor_lead > endx) {"
        addition = """        if (korean_layout_override_unused) {}
"""
        addition = """        if (legacy_korean_layout_override && width - hor_lead > w) {
            const char* split = text;
            const char* next = text;
            while (next < ewrd) {
                next += korean_font.is_pair(next, static_cast<int>(ewrd - next)) ? 2 : 1;
                if (get_text_width(text, static_cast<int>(next - text)) - hor_lead > w) break;
                split = next;
            }
            if (split == text && text < ewrd)
                split = text + (korean_font.is_pair(text, static_cast<int>(ewrd - text)) ? 2 : 1);
            ewrd = split;
            width = get_text_width(text, static_cast<int>(ewrd - text));
        }
"""
        section = section.replace("const char* ewrd = Pass_word(text);", "const char* ewrd = Pass_word(text);")
        section = section.replace(anchor, addition + anchor, 1)
    text = text[:a] + section + text[b+1:]
p.write_text(text)

# Book and scroll pagination must use the same Korean height as the painter.
replace("gumps/Text_gump.cc", "sman->get_text_height(font) + vlead;",
        "sman->get_text_height(font, text + start) + vlead;")


# A Korean line needs the full padded bitmap height even in a Latin font with
# no descender. Do not enlarge English-only menus.
p = Path("upstream/shapes/font.cc")
text = p.read_text()
text = rewrite_function(text, "int Font::get_text_height(const char* text, int length)", r'''int Font::get_text_height(const char* text, int length) {
    const int height = get_text_height() + get_text_baseline(text, length) - get_text_baseline();
    return (legacy_korean_layout_override || contains_legacy_korean(text, length))
        ? std::max(height, korean_font.height()) : height;
}''')
p.write_text(text)

# BG stock backing plates: align the complete 21px check frame vertically.
# Apply only to the known default coordinates; custom patch coordinates win.
p = Path("upstream/data/bg/gump_info.txt")
text = p.read_text()
for shape, x, old_y, new_y in [
    (0,24,44,36), (1,24,52,49), (9,24,54,50), (10,24,50,46),
    (11,24,44,38), (22,24,34,31), (27,24,34,32), (53,24,58,56),
]:
    before = ":%d/%d/%d/2" % (shape,x,old_y)
    after = ":%d/%d/%d/2" % (shape,x,new_y)
    if text.count(before) != 1: raise RuntimeError("Checkmark coordinate anchor missing")
    text = text.replace(before,after)
p.write_text(text)
# Fallback coordinates are used when gump_info is unavailable.
p = Path("upstream/gumps/Gump.cc")
text = p.read_text()
for name, old, new in [
    ("box",44,36), ("crate",52,49), ("bag",54,50), ("backpack",50,46),
    ("basket",44,38), ("chest",34,31), ("drawer",34,32), ("body",58,56),
]:
    a = text.index('game->get_shape("gumps/' + name + '")', text.index("void Container_gump::initialize"))
    b = text.index(";", a)
    section = text[a:b+1]
    # BG and SI share some defaults; keep SI positions unchanged.
    section = section.replace(", 24, %d)" % old,
        ", 24, Game::get_game_type() == BLACK_GATE ? %d : %d)" % (new,old))
    text = text[:a] + section + text[b+1:]
# Dirty regions must include buttons outside the container background.
text = text.replace("TileRect Gump::get_dirty() {\n\tTileRect rect = get_rect();",
"""TileRect Gump::get_dirty() {
    TileRect rect = get_rect();
    for (auto* elem : elems) if (elem) rect = rect.add(elem->get_rect());""",1)
p.write_text(text)


# The margin is font-dependent: some runes have a negative left bearing.
replace("shapes/font.h", "\tvoid get_text_ink_bounds(",
        "\tint get_text_edge_padding(const char* text);\n\tvoid get_text_ink_bounds(")
p = Path("upstream/shapes/font.cc")
text = p.read_text()
text += r'''
int Font::get_text_edge_padding(const char* text) {
    int padding = 0;
    if (!text) return padding;
    Korean_layout_scope scope(legacy_korean_layout_override, contains_legacy_korean(text, -1));
    for (int i = 0; text[i];) {
        const int bytes = korean_font.is_pair(text + i, 2) ? 2 : 1;
        char token[3] = {text[i], bytes == 2 ? text[i + 1] : '\0', '\0'};
        int l, t, w, h;
        get_text_ink_bounds(token, l, t, w, h);
        if (w > 0) {
            padding = std::max(padding, -l);
            padding = std::max(padding, l + w - get_text_width(token));
        }
        i += bytes;
    }
    return padding;
}
'''
text = text.replace("std::min(2, std::max(0, (w - 1) / 2))",
                    "std::min(get_text_edge_padding(text), std::max(0, (w - 1) / 2))")
# Cursor hit-testing must use the same inset and long-token split as painting.
a = text.index("int Font::find_cursor(")
brace = text.index("{", a)
insert = """
    const int edge = std::min(get_text_edge_padding(text), std::max(0, (w - 1) / 2));
    x += edge; w -= 2 * edge;
"""
text = text[:brace+1] + insert + text[brace+1:]
# Share the exact bounded-prefix decision with the ordinary text-box painter.
a = text.index("int Font::paint_text_box(")
start = text.index("        if (legacy_korean_layout_override && width - hor_lead > w)", a)
end = text.index("\n\t\tif (curx + width - hor_lead > endx)", start)
split = text[start:end]
a = text.index("int Font::find_cursor(")
b = text.index("\t\tif (curx + width - hor_lead > endx)", a)
text = text[:b] + split + "\n" + text[b:]
a = text.index("int Font::paint_text_box_fixedwidth(")
b = text.index("\t\tif (curx + width - hor_lead > endx)", a)
fixed = split.replace("get_text_width(text, static_cast<int>(next - text))",
    "korean_fixed_text_width(text, static_cast<int>(next - text), char_width, font_shapes.get(), legacy_korean_layout_override, hor_lead)")
fixed = fixed.replace("get_text_width(text, static_cast<int>(ewrd - text))",
    "korean_fixed_text_width(text, static_cast<int>(ewrd - text), char_width, font_shapes.get(), legacy_korean_layout_override, hor_lead)")
# Fixed-width width must be mutable when a token is split.
part = text[a:b].replace("const int   width = korean_fixed_text_width", "int         width = korean_fixed_text_width")
text = text[:a] + part + fixed + "\n" + text[b:]
p.write_text(text)

# Fit the complete inscription vertically as well as horizontally.
p = Path("upstream/gumps/Sign_gump.cc")
text = p.read_text()
anchor = "\t// Get space between lines."
text = text.replace(anchor, """    const int slot = std::max(1, (object_area.h - 8) / std::max(1, num_lines));
    lheight = std::min(lheight, slot);
""" + anchor,1)
text = text.replace("const int dw = std::min(iw, available);",
    "const int dw = std::max(1, std::min(std::min(iw, available), iw * slot / ih));")
p.write_text(text)
