from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

def cert(path, company, address, cert_no, issued, valid_to, scope, body="QualiCert Assessments Pvt Ltd"):
    c = canvas.Canvas(path, pagesize=A4)
    W, H = A4
    c.setStrokeColor(colors.HexColor("#1F4E78")); c.setLineWidth(6); c.rect(25, 25, W - 50, H - 50)
    c.setLineWidth(1.5); c.rect(36, 36, W - 72, H - 72)
    c.setFont("Helvetica-Bold", 13); c.setFillColor(colors.HexColor("#1F4E78"))
    c.drawCentredString(W / 2, H - 90, body.upper())
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawCentredString(W / 2, H - 105, "Accredited Certification Body | Mumbai, India")
    c.setFont("Times-Bold", 30); c.drawCentredString(W / 2, H - 175, "CERTIFICATE")
    c.setFont("Times-Roman", 13); c.drawCentredString(W / 2, H - 205, "This is to certify that the Quality Management System of")
    c.setFont("Times-Bold", 20); c.drawCentredString(W / 2, H - 245, company)
    c.setFont("Times-Roman", 11); c.drawCentredString(W / 2, H - 265, address)
    c.setFont("Times-Roman", 13); c.drawCentredString(W / 2, H - 305, "has been assessed and found to conform to the requirements of")
    c.setFont("Times-Bold", 24); c.drawCentredString(W / 2, H - 345, "ISO 9001:2015")
    c.setFont("Times-Roman", 12); c.drawCentredString(W / 2, H - 385, "for the following scope:")
    c.setFont("Times-Italic", 12); c.drawCentredString(W / 2, H - 405, scope)
    y = H - 480
    c.setFont("Helvetica", 11)
    for k, v in [("Certificate No.", cert_no), ("Date of initial issue", issued), ("Valid until", valid_to)]:
        c.drawString(140, y, k + ":"); c.setFont("Helvetica-Bold", 11); c.drawString(300, y, v); c.setFont("Helvetica", 11); y -= 24
    c.setFont("Helvetica", 9)
    c.drawString(140, y - 30, "Validity of this certificate is subject to successful annual surveillance audits.")
    c.line(W - 230, 130, W - 80, 130); c.drawString(W - 220, 115, "Director - Certification")
    c.setFillColor(colors.HexColor("#C9A227")); c.circle(120, 130, 38, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 10); c.drawCentredString(120, 133, "QUALICERT"); c.drawCentredString(120, 120, "SEAL")
    c.showPage(); c.save()

base = "/home/claude/aerchain/dataset/vendors"
cert(f"{base}/A_siam_pacific/SPPI_ISO9001_Certificate.pdf", "Siam Pacific Packaging (India) Pvt Ltd",
     "Plot B-7, SIPCOT Industrial Park, Sriperumbudur 602105, Tamil Nadu", "QMS/IN/48812", "15-Feb-2019", "14-Feb-2028",
     "Design and manufacture of corrugated boxes and printed packaging")
cert(f"{base}/B_deccan/Deccan_ISO_Certificate.pdf", "Deccan Packaging Industries",
     "No. 118, 3rd Phase, Peenya Industrial Area, Bengaluru 560058", "QMS/IN/22907", "01-Apr-2020", "31-Mar-2026",
     "Manufacture of corrugated sheets, boxes and partitions")
cert(f"{base}/D_sri_murugan/ISO_certificate.pdf", "Murugan Packaging Industries",
     "SF No. 211, Hosur Road, Kaveripattinam, Krishnagiri 635112", "QMS/IN/39150", "10-Aug-2022", "09-Aug-2028",
     "Manufacture of corrugated boxes")
print("certs done")
