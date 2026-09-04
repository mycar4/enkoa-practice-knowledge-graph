import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

manifest = json.load(open('내작업폴더/data/resolution_manifests/promotion_dryrun_20260904_060936.json', encoding='utf-8'))

def normalize_corp_name(name: str) -> str:
    norm = str(name).strip().replace('(주)', '').replace('주식회사', '').replace('(유)', '').replace('유한회사', '').replace('㈜', '')
    return ''.join(norm.split())

all_exact = True
for p in manifest['proposed_holds_economic_stake']:
    cand_h = p['source_holding_company']['corp_name']
    ex_h = p['re_verification_details']['parsed_evidence']['extracted_holder']
    norm_c = normalize_corp_name(cand_h)
    norm_e = normalize_corp_name(ex_h)
    exact = (norm_c == norm_e)
    if not exact:
        all_exact = False
    print(f"Seq {p['sequence']:2d} | exact={exact:<5} | cand='{norm_c}' vs extracted='{norm_e}'")

print(f"\nAll 19 exact matches: {all_exact}")
