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
