import os
from spec import BUYER

OUT = "/home/claude/aerchain/dataset/vendors/E_annapurna"
os.makedirs(OUT, exist_ok=True)

e1 = f"""From: Suresh Kamath <suresh@annapurnapackers.com>
To: {BUYER['buyer_name']} <{BUYER['buyer_email']}>
Date: Wed, 30 Sep 2026 21:17:52 +0530
Subject: Re: {BUYER['rfq_no']} - Corrugated packaging annual contract

Hi Priya,

₹42/kg for the 5-ply, 38 for the 3-ply, rest same as last year, freight extra.

Suresh

On Mon, 21 Sep 2026 at 10:02, Priya Raman <{BUYER['buyer_email']}> wrote:
> Dear Partner,
> Please find attached our RFQ {BUYER['rfq_no']} for corrugated packaging (30 line items),
> the price bid template and the technical questionnaire. Kindly respond by 1 Oct 2026, 18:00 IST.
> Regards, Priya Raman, Category Manager - Packaging, {BUYER['name']}
"""

e2 = f"""From: Suresh Kamath <suresh@annapurnapackers.com>
To: {BUYER['buyer_name']} <{BUYER['buyer_email']}>
Date: Thu, 01 Oct 2026 09:02:10 +0530
Subject: Re: Re: {BUYER['rfq_no']} - Corrugated packaging annual contract

Priya, small correction - 42 was the old rate, 5-ply is ₹44/kg now (kraft has gone up). 3-ply stays 38.
Freight ₹4,500 per trip from our Hoskote unit as usual.
Questionnaire same as last year, you have all our documents already.

Regards,
Suresh Kamath
Annapurna Packers | Hoskote | 98860 40517
"""
open(f"{OUT}/email_1_2026-09-30.eml", "w").write(e1)
open(f"{OUT}/email_2_2026-10-01_revision.eml", "w").write(e2)
print("E done")
