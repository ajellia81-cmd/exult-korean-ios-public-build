"""Read a previous Actions ZIP/IPA without extracting its contents."""
import io,json,sys,zipfile
from pathlib import Path
def ipa_bytes(path):
 raw=Path(path).read_bytes()
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  names=z.namelist()
  nested=[n for n in names if n.endswith(".ipa")]
  if nested:return z.read(nested[0])
 return raw
def inventory(raw):
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  rows=[{"path":i.filename,"bytes":i.file_size} for i in z.infolist() if not i.is_dir()]
 return {"ipa_bytes":len(raw),"uncompressed_bytes":sum(i["bytes"] for i in rows),
         "files":rows}
if __name__=="__main__":
 report=inventory(ipa_bytes(sys.argv[1]))
 Path(sys.argv[2]).write_text(json.dumps(report,indent=2))
 print(json.dumps(report,indent=2))
