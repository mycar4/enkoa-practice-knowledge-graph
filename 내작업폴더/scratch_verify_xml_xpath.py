import json
import re
import hashlib
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = Path(r"c:\Users\Playdata\enkoa-practice-knowledge-graph\enkoa-practice-knowledge-graph\내작업폴더")
manifest_path = BASE_DIR / "data" / "resolution_manifests" / "promotion_dryrun_20260904_060936.json"
xml_dir = BASE_DIR / "data" / "raw_filings" / "batch_runs" / "batch_15000_20260904_001355" / "xml"

def clean_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

def compute_sha256(val: str) -> str:
    return hashlib.sha256(val.encode('utf-8')).hexdigest()

with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

print(f"Checking all {len(manifest['proposed_holds_economic_stake'])} candidates against raw XML files...")

results = []
for p in manifest['proposed_holds_economic_stake']:
    rcept_no = p['rcept_no']
    target_hash = p['evidence_bindings']['row_inner_hash']
    xml_file = xml_dir / f"{rcept_no}.xml"
    if not xml_file.exists():
        print(f"Missing XML file: {xml_file}")
        continue
    content = xml_file.read_text(encoding='utf-8', errors='ignore')
    table_pattern = re.compile(r'<TABLE[^>]*>(.*?)</TABLE>', re.DOTALL | re.IGNORECASE)
    tables = table_pattern.findall(content)
    
    target_table_idx = None
    target_table_html = None
    for idx, tbl in enumerate(tables):
        clean_tbl = clean_whitespace(re.sub(r'<[^>]+>', ' ', tbl))
        if "제142조" in clean_tbl and any(k in clean_tbl for k in ["제1호", "제2호", "보고자", "특별관계자"]):
            target_table_idx = idx
            target_table_html = tbl
            break
            
    tr_pattern = re.compile(r'<TR[^>]*>(.*?)</TR>', re.DOTALL | re.IGNORECASE)
    all_trs = tr_pattern.findall(target_table_html)
    header_trs = [tr for tr in all_trs if '<TH' in tr.upper()]
    data_trs = [tr for tr in all_trs if tr not in header_trs]
    
    found = False
    for r_idx, tr in enumerate(data_trs):
        clean_tr = clean_whitespace(tr)
        h = compute_sha256(clean_tr)
        if h == target_hash:
            all_idx = all_trs.index(tr)
            std_xpath = f"//TABLE[{target_table_idx + 1}]//TR[{all_idx + 1}]"
            results.append({
                "seq": p["sequence"],
                "cid": p["candidate_id"],
                "table_parser_index": target_table_idx,
                "all_tr_index": all_idx,
                "data_row_index": r_idx,
                "standard_xpath": std_xpath,
                "raw_parser_xpath": p['evidence_bindings'].get('row_raw_parser_xpath', ''),
                "hash_verified": True
            })
            found = True
            break
    if not found:
        print(f"Seq {p['sequence']} NOT FOUND by hash!")

print(f"\n✅ Verified {len(results)}/19 perfectly against raw XML files!")
print(f"{'Seq':<3} | {'Raw Parser XPath':<20} | {'Table (0-based / 1-based)':<25} | {'All TR (0-based / 1-based)':<25} | {'Data Row':<8} | {'True Standard XPath'}")
print("-" * 125)
for r in results:
    print(f"{r['seq']:2d}  | {r['raw_parser_xpath']:<20} | {r['table_parser_index']:2d} -> {r['table_parser_index']+1:2d}                     | {r['all_tr_index']:2d} -> {r['all_tr_index']+1:2d}                     | {r['data_row_index']:2d}       | {r['standard_xpath']}")
