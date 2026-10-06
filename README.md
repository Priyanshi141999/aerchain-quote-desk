# Quote Desk: kill the quote spreadsheet

Prototype for the Aerchain PM assignment. A buyer drafts an RFQ with an AI co-pilot, vendors reply in any
format (Excel, PDF, Word, phone photo, one-line email), and the system turns every reply into one
comparable table the buyer can question in plain English.

## How extraction works

1. **Code reads the files** (`quotedesk/ingest.py`). Emails, Excel sheets (including hidden rows), Word letters,
   PDFs (including text a person can't see) and photos. Facts code can verify exactly, such as send times,
   hidden rows and invisible text, are recorded here rather than left to the AI.
2. **AI transcribes** (`quotedesk/extract.py`). The model reads each vendor's documents and reports every
   price *exactly as written*, with its unit, currency, tax basis, source location and a confidence level.
   It is told to treat vendor documents as untrusted data and never follow instructions found inside them.
3. **Code converts** (`quotedesk/normalize.py`). Per-1000, per-kg, per-sq.ft, USD and GST-inclusive prices
   are converted to ₹ per RFQ unit, ex-GST. Each step is written to a visible trail. Assumptions raise flags.
4. **Code checks** (`quotedesk/checks.py`). Late submissions, expired offers, certificate validity and legal
   name, payment terms, conditional discounts, conflicts between documents, and qualification on must-pass
   questions.

**The AI reads; code calculates.** Every number on screen can be traced back to a sentence in a vendor's file.

## Models
Switch with `LLM_PROVIDER=gemini` or `LLM_PROVIDER=claude`. Keys come from environment variables or
Streamlit secrets (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`). They are never stored in the code.

## Accuracy test
`eval/run_eval.py` runs extraction on all five vendors and scores it against `eval/answer_key/`
(150 prices, plus 38 edge-case checks). The app never reads the answer key. The GitHub Action
*Extraction accuracy test* runs it on every change.

## Data
`data/` holds the fabricated RFQ and five vendor responses. See `data/DATASET_GUIDE.md` for every planted trap.
