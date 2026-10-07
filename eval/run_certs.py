"""Run the portal's certificate check (AI read + code validation) on every sample upload, as the live app would."""
import sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quotedesk import llm  # noqa: E402
from quotedesk.updates import read_certificate, validate_certificate  # noqa: E402

CASES = [
    ("data/portal_samples/Deccan_ISO9001_renewed_2026.pdf", "Deccan Packaging Industries", True),
    ("data/portal_samples/SriMurugan_ISO9001_reissued.pdf", "Sri Murugan Corrugated Boxes", True),
    ("data/portal_samples/Annapurna_ISO9001.pdf", "Annapurna Packers", True),
    ("data/portal_samples/Vijay_audit_schedule_letter.pdf", "Vijay Box Works", False),
    ("data/vendors/B_deccan/Deccan_ISO_Certificate.pdf", "Deccan Packaging Industries", False),      # expired
    ("data/portal_samples/SriMurugan_ISO9001_reissued.pdf", "Deccan Packaging Industries", False),   # wrong company
    ("data/vendors/D_sri_murugan/ISO_certificate.pdf", "Sri Murugan Corrugated Boxes", False),       # sister company name
]
out = [f"# Certificate check — {llm.provider()}\n", "| File | Uploaded as | Read by | Holder read | Valid until | Expected | Result | Reason |", "|---|---|---|---|---|---|---|---|"]
ok_all = 0
for f, vendor, expect in CASES:
    t0 = time.time()
    try:
        c = read_certificate((ROOT / f).read_bytes(), "application/pdf")
        ok, why = validate_certificate(c, vendor)
        out.append(f"| {Path(f).name} | {vendor} | {c.get('read_by')} ({time.time()-t0:.0f}s) | {c.get('certificate_holder')} | {c.get('valid_until')} | "
                   f"{'accept' if expect else 'reject'} | {'✅' if ok == expect else '❌'} {'accepted' if ok else 'rejected'} | {why} |")
        ok_all += ok == expect
    except Exception as e:
        out.append(f"| {Path(f).name} | {vendor} | FAILED | | | | ❌ | {str(e)[:120]} |")
    time.sleep(5)
out.insert(1, f"**{ok_all}/{len(CASES)} behaved as expected**\n")
(ROOT / "eval/out").mkdir(parents=True, exist_ok=True)
(ROOT / f"eval/out/certs_{llm.provider()}.md").write_text("\n".join(out))
print("\n".join(out))
