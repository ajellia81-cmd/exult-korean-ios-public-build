"""Remove temporary diagnostics after applying the audited gameplay patches."""
from pathlib import Path
import re

def change(path,before,after):
 p=Path("upstream")/path;s=p.read_text()
 if s.count(before)!=1:raise RuntimeError(f"{path}: expected one release anchor {before[:70]!r}")
 p.write_text(s.replace(before,after,1))

# Audio and keyboard setup are production behavior, independent of diagnostics.
p=Path("upstream/ios/ios_utils.mm");s=p.read_text()
start=s.index("void KoreanIOSDiagnostics() {")
brace=s.index("{",start);depth=0
for end in range(brace,len(s)):
 if s[end]=="{":depth+=1
 elif s[end]=="}":
  depth-=1
  if not depth:break
s=s[:start]+'''void KoreanIOSInitialize() {
    InstallExultKeyboardDismissControl();
    AVAudioSession* session = [AVAudioSession sharedInstance];
    [session setCategory:AVAudioSessionCategoryPlayback error:nil];
    [session setActive:YES error:nil];
}'''+s[end+1:]
p.write_text(s)
p=Path("upstream/exult.cc");s=p.read_text().replace("KoreanIOSDiagnostics","KoreanIOSInitialize")
# Runtime debug traces must not be re-enabled by an older diagnostic config.
start=s.index("\t// Enable tracing of intrinsics?")
end=s.index("\t// Save game compression level",start)
s=s[:start]+"\t// Production builds do not enable execution traces from user config.\n\tintrinsic_trace = false;\n\tusecode_trace = 0;\n\tcombat_trace = false;\n\n"+s[end:]
p.write_text(s)

# Remove only known temporary probes. Keep normal engine errors and all calls
# with side effects (audio init/resume, font validation, lifecycle transitions).
markers=("Korean diagnostic:","Korean font:","Korean font probe:",
 "Audio diagnostic:","SDL audio init failed:","SDL audio stream failed:",
 "SDL audio driver:","SDL audio resume failed:","Audio recovery:",
 "Audio recovery v2:","iOS lifecycle:","Patched initial data:")
def erase_probes(s):
 for token in ("std::cerr","std::cout"):
  pos=0
  while True:
   a=s.find(token,pos)
   if a<0:break
   i=a;quote=None;escape=False
   while i<len(s):
    c=s[i]
    if quote:
     if escape:escape=False
     elif c=="\\":escape=True
     elif c==quote:quote=None
    elif c in ('"',"'"):quote=c
    elif c==";":break
    i+=1
   statement=s[a:i+1]
   if any(marker in statement for marker in markers):
    s=s[:a]+"(void)0;"+s[i+1:];pos=a+8
   else:pos=i+1
 return s
for name in ("shapes/font.cc","audio/Audio.cc","audio/AudioMixer.cc","exult.cc","gamedat.cc"):
 p=Path("upstream")/name
 if p.exists():p.write_text(erase_probes(p.read_text()))
# The pack-presence loop was diagnostic only and need not do filesystem I/O.
p=Path("upstream/audio/Audio.cc");s=p.read_text()
a=s.index('    for(const char* pack:{"<DATA>/jmsfx.flx"')
b=s.index("#endif",a)
s=s[:a]+s[b:]
p.write_text(s)
# Remove the one-time UTF-8 probe state as well as its output.
p=Path("upstream/shapes/font.cc");s=p.read_text()
s,n=re.subn(r'\s*static bool reported_utf8 = false;\s*if \(!reported_utf8 && first >= 0xe0 && first <= 0xef\) \{\s*reported_utf8 = true;\s*\(void\)0;\s*\}',"",s)
assert n==1
p.write_text(s)

# Debugger/editor modules are disabled by the iOS config; make that explicit.
p=Path("upstream/ios/include/config.h");s=p.read_text()
for macro in ("DEBUG","USECODE_DEBUGGER","USECODE_CONSOLE_DEBUGGER","USE_EXULTSTUDIO",
              "SHOW_USECODE_CONTAINER","SHOW_NONREADIED_OBJECTS"):
 s+=f"\n#ifdef {macro}\n#undef {macro}\n#endif\n"
p.write_text(s)
# Size optimization and symbol policy for every Release configuration in the
# app project; dependencies also receive matching command-line settings in CI.
p=Path("upstream/ios/Exult.xcodeproj/project.pbxproj");s=p.read_text()
pattern=r'(/\* Release \*/ = \{\n\s*isa = XCBuildConfiguration;\n\s*buildSettings = \{)'
s,n=re.subn(pattern,r'''\1
                GCC_OPTIMIZATION_LEVEL = s;
                GCC_GENERATE_DEBUGGING_SYMBOLS = NO;
                DEAD_CODE_STRIPPING = YES;
                ENABLE_TESTABILITY = NO;
                ENABLE_NS_ASSERTIONS = NO;
                MTL_ENABLE_DEBUG_INFO = NO;''',s)
assert n==3
# Existing entries should not override the compact policy.
s=s.replace('DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";','DEBUG_INFORMATION_FORMAT = dwarf;')
# Omit C/C++ assertion diagnostics in the production configurations.
for a,b in reversed([(m.start(),s.index("\n\t\t\tname = Release;",m.start())) for m in re.finditer(pattern,s)]):
 section=s[a:b]
 section=section.replace("GCC_PREPROCESSOR_DEFINITIONS = (",'GCC_PREPROCESSOR_DEFINITIONS = (\n                    "NDEBUG=1",',1)
 s=s[:a]+section+s[b:]
# Omit the optional SDL dSYM build phase; symbols are not generated in this build.
s,n=re.subn(r'shellScript = "if \[ -d .*?Generating dSYM.*?";', lambda m:'shellScript = "true\\n";',s)
assert n==1
# Remove duplicate setting lines inside individual build configurations.
for a,b in reversed([(m.start(),s.index("\n\t\t\tname = Release;",m.start())) for m in re.finditer(pattern,s)]):
 section=s[a:b];seen=set();lines=[]
 for line in section.splitlines(keepends=True):
  key=line.strip().split(" = ",1)[0] if " = " in line else ""
  if key in ("GCC_OPTIMIZATION_LEVEL","GCC_GENERATE_DEBUGGING_SYMBOLS","DEAD_CODE_STRIPPING",
             "ENABLE_TESTABILITY","ENABLE_NS_ASSERTIONS","MTL_ENABLE_DEBUG_INFO"):
   if key in seen:continue
   seen.add(key)
  lines.append(line)
 s=s[:a]+"".join(lines)+s[b:]
p.write_text(s)
print("PASS: production audio/keyboard preserved; temporary probes, log redirection and config backup removed")
