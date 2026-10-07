"""Documents a vendor might upload in the portal, to demo qualification fixes (good and bad)."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from gen_certs import cert
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = os.path.join(os.path.dirname(__file__), "../../data/portal_samples")
os.makedirs(OUT, exist_ok=True)
cert(f"{OUT}/Deccan_ISO9001_renewed_2026.pdf", "Deccan Packaging Industries",
     "No. 118, 3rd Phase, Peenya Industrial Area, Bengaluru 560058", "QMS/IN/22907-R1", "01-Apr-2026", "31-Mar-2029",
     "Manufacture of corrugated sheets, boxes and partitions")
cert(f"{OUT}/SriMurugan_ISO9001_reissued.pdf", "Sri Murugan Corrugated Boxes",
     "SF No. 211, Hosur Road, Kaveripattinam, Krishnagiri 635112", "QMS/IN/39150-A", "10-Aug-2022", "09-Aug-2028",
     "Manufacture of corrugated boxes")
cert(f"{OUT}/Annapurna_ISO9001.pdf", "Annapurna Packers",
     "Plot 7, KIADB Industrial Area, Hoskote 562114", "QMS/IN/31044", "12-Jan-2024", "11-Jan-2027",
     "Manufacture of corrugated boxes and pads")
# a document that should be REJECTED: not a certificate
c = canvas.Canvas(f"{OUT}/Vijay_audit_schedule_letter.pdf", pagesize=A4)
W, H = A4
c.setFont("Helvetica-Bold", 14); c.drawString(60, H - 80, "QualiCert Assessments Pvt Ltd")
c.setFont("Helvetica", 11)
for i, t in enumerate(["Date: 18 September 2026", "", "To: Vijay Box Works, Mookandapalli, Hosur",
                       "", "Sub: ISO 9001:2015 Stage 1 audit - schedule confirmation", "",
                       "We confirm that the Stage 1 certification audit of your unit is scheduled for",
                       "12-13 November 2026. Certification will be decided after the Stage 2 audit.",
                       "This letter is not a certificate of conformity.", "", "For QualiCert Assessments", "Audit Planning Desk"]):
    c.drawString(60, H - 120 - 18 * i, t)
c.showPage(); c.save()
print(sorted(os.listdir(OUT)))
