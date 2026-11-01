"""Assemble a minimal unsigned IPA; retain every runtime engine resource."""
from pathlib import Path
import hashlib,io,json,plistlib,shutil,subprocess,sys,zipfile
from audit_release_package import ipa_bytes,inventory

source=Path(sys.argv[1]);out=Path(sys.argv[2]);baseline=Path(sys.argv[3])
assert source.is_dir() and source.name=="Exult.app"
payload=Path("ipa/Payload");app=payload/"Exult.app"
if payload.parent.exists():shutil.rmtree(payload.parent)
payload.mkdir(parents=True);shutil.copytree(source,app,symlinks=True)
info=app/"Info.plist"
pl=plistlib.loads(info.read_bytes());pl["CFBundleDisplayName"]="Ultima VII";pl["CFBundleName"]="Ultima VII"
info.write_bytes(plistlib.dumps(pl,fmt=plistlib.FMT_BINARY))
removed=[]
# Development-only framework metadata identified in the prior IPA.
dirs={".git",".github","__MACOSX","__pycache__","Headers","PrivateHeaders","Modules","CMake"}
suffixes={".dsym",".bcsymbolmap",".o",".a",".h",".hpp",".c",".cc",".cpp",".m",".mm",
          ".swift",".swiftdoc",".swiftmodule",".swiftsourceinfo",".modulemap",".pyc"}
def forbidden(p):
 rel=p.relative_to(app);parts=rel.parts
 return (any(part in dirs or part.lower().endswith(".dsym") for part in parts)
         or p.suffix.lower() in suffixes
         or p.name in (".DS_Store","dummy")
         or p.name.startswith("._") or p.name.endswith(".debug.dylib")
         or (rel.as_posix().startswith("Frameworks/") and p.name in ("README.md","INSTALL.md")))
for p in sorted(app.rglob("*"),key=lambda p:len(p.parts),reverse=True):
 if p.is_file() and forbidden(p):
  removed.append({"path":p.relative_to(app).as_posix(),"bytes":p.stat().st_size});p.unlink()
for p in sorted(app.rglob("*"),key=lambda p:len(p.parts),reverse=True):
 if p.is_dir() and not any(p.iterdir()):p.rmdir()
# Runtime resources must remain byte-identical to the successfully built app.
runtime=[p for p in source.rglob("*") if p.is_file()
         and p.suffix.lower() in (".flx",".png",".car",".nib",".metallib")]
for p in runtime:
 assert (app/p.relative_to(source)).read_bytes()==p.read_bytes(),str(p)
for name in ("exult.flx","exult_bg.flx","exult_si.flx","midisfx.flx"):
 assert (app/"data"/name).is_file(),name
assert (app/"Frameworks/SDL3.framework/default.metallib").is_file()
assert (app/"Frameworks/SDL3.framework/LICENSE.txt").is_file()
macho=[]
magic={b"\xcf\xfa\xed\xfe",b"\xfe\xed\xfa\xcf",b"\xca\xfe\xba\xbe",b"\xbe\xba\xfe\xca"}
for p in app.rglob("*"):
 if not p.is_file() or p.is_symlink():continue
 with p.open("rb") as f:header=f.read(4)
 if header not in magic:continue
 before=p.stat().st_size
 subprocess.run(["xcrun","strip","-S","-x",str(p)],check=True)
 arch=subprocess.check_output(["xcrun","lipo","-archs",str(p)],text=True).strip()
 assert arch=="arm64",(str(p),arch)
 commands=subprocess.check_output(["xcrun","otool","-l",str(p)],text=True)
 assert "__DWARF" not in commands,str(p)
 macho.append({"path":p.relative_to(app).as_posix(),"before":before,"after":p.stat().st_size,"arch":arch})
assert {x["path"] for x in macho}=={"Exult","Frameworks/SDL3.framework/SDL3"}
binary=(app/"Exult").read_bytes()
for token in (b"KoreanIOSDiagnostics",b"exult-ios-stdout.txt",b"exult-ios-stderr.txt",
              b"exult-before-audio-repair.cfg",b"Korean font probe:",b"Audio diagnostic:",b"iOS lifecycle:"):
 assert token not in binary,token
for p in app.rglob("*"):
 if p.is_file():assert not forbidden(p),str(p)
# Check that the only missing previous files are the reviewed development debris.
previous=inventory(ipa_bytes(baseline))
removed_names={"Payload/Exult.app/"+x["path"] for x in removed}
current={"Payload/Exult.app/"+p.relative_to(app).as_posix() for p in app.rglob("*") if p.is_file()}
missing={i["path"] for i in previous["files"]}-current
assert missing<=removed_names,missing-removed_names
with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(payload.rglob("*")):
  if p.is_file():z.write(p,p.relative_to(payload.parent).as_posix())
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 assert all(n.startswith("Payload/Exult.app/") for n in z.namelist())
 assert not any("__MACOSX" in n for n in z.namelist())
report={"previous_ipa_bytes":previous["ipa_bytes"],"ipa_bytes":out.stat().st_size,
        "saved_bytes":previous["ipa_bytes"]-out.stat().st_size,
        "previous_uncompressed_bytes":previous["uncompressed_bytes"],
        "uncompressed_bytes":sum(p.stat().st_size for p in app.rglob("*") if p.is_file()),
        "removed":removed,"mach_o":macho,"runtime_resources_verified":len(runtime),
        "sha256":hashlib.sha256(out.read_bytes()).hexdigest()}
Path("release-package-audit.json").write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
