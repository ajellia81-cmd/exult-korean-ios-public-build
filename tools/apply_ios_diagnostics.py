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
