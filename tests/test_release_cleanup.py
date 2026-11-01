"""Release-only diagnostics checks, run in addition to all gameplay regressions."""
from pathlib import Path
ios=Path("upstream/ios/ios_utils.mm").read_text()
exult=Path("upstream/exult.cc").read_text()
assert "KoreanIOSInitialize();" in exult
assert "KoreanIOSDiagnostics" not in exult+ios
for text in ("exult-ios-stdout.txt","exult-ios-stderr.txt","exult-before-audio-repair.cfg",
             "freopen","setvbuf","currentRoute.outputs","sampleRate"):
 assert text not in ios,text
assert "InstallExultKeyboardDismissControl();" in ios
assert "AVAudioSessionCategoryPlayback" in ios and "setActive:YES" in ios
assert "intrinsic_trace = false;" in exult and "usecode_trace = 0;" in exult
assert 'config->value("config/debug/trace/' not in exult
for name in ("shapes/font.cc","audio/Audio.cc","audio/AudioMixer.cc","exult.cc"):
 s=(Path("upstream")/name).read_text()
 for text in ("Korean diagnostic:","Korean font probe:","Korean font:",
              "Audio diagnostic:","Audio recovery:","Audio recovery v2:","iOS lifecycle:","SFX pack "):
  assert text not in s,(name,text)
audio=Path("upstream/audio/Audio.cc").read_text()
assert 'config->set("config/audio/midi/use_oggs","yes",false);' in audio
assert "SDL_ResumeAudioDevice(dev)" in Path("upstream/audio/AudioMixer.cc").read_text()
project=Path("upstream/ios/Exult.xcodeproj/project.pbxproj").read_text()
assert project.count("GCC_OPTIMIZATION_LEVEL = s;")==3
assert project.count("GCC_GENERATE_DEBUGGING_SYMBOLS = NO;")==3
assert project.count("ENABLE_TESTABILITY = NO;")==3
print("PASS: release diagnostics absent; audio, keyboard dismissal and lifecycle retained; size optimization enabled")
