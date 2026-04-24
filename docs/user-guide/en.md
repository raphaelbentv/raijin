# User Guide — Raijin

Raijin automates supplier invoice entry. Upload a PDF or image, the OCR engine extracts the data, you review (or correct) in a few seconds, and export everything to Excel for your accounting.

## 1. Sign in

1. Open `https://app.<your-domain>.com`
2. First time? Click **Sign up**
   - Organisation: your company name
   - Full name: your name
   - Email + password (min. 8 chars)
3. Otherwise use **Sign in**

Sessions last 30 minutes and auto-refresh while active.

## 2. Upload invoices

### From the Upload page

- Drag-and-drop one or more invoices in the dashed zone, or click to browse
- Accepted formats: **PDF, JPG, PNG**
- Max size: **20 MB** per file
- Click **Upload** to start processing

### What happens next

1. File stored securely (EU region, encrypted)
2. Azure Document Intelligence extracts fields (vendor, amounts, dates, lines)
3. Values are normalised (EU formats, Greek VAT auto-prefixed `EL`)
4. Invoice appears on the dashboard with status **Ready for review**

Typical processing time: 10–30 seconds.

## 3. Review an invoice

From the dashboard, click an invoice in **Ready for review**.

### Review screen

- **Left**: original PDF preview
- **Right**: editable form with extracted fields

### Fields to check

- **Invoice number** — must be unique per supplier
- **Issue date** and **Due date**
- **Subtotal + VAT = Total** — UI flags a mismatch above 0.02 € tolerance
- **Line items** — you can add, edit or remove lines

### Validation indicators

At the top of the form, a panel summarises alerts:

- 🟢 **Green**: all checks pass, safe to confirm
- 🟡 **Yellow** (warning): non-blocking (missing number, medium confidence, possible duplicate)
- 🔴 **Red** (error): blocking — the Confirm button will be refused

### Actions

- **Save** — persists edits without changing status
- **Confirm** — status becomes *Confirmed*, exportable
- **Reject** — marks as rejected (reason required)
- **Skip** — comes back later (stays in *Ready for review*)
- **Reopen** — available on *Confirmed* / *Rejected* invoices to edit again

Every correction is tracked (who, when, what) for audit.

## 4. Dashboard

- KPI widgets at the top: count per status
- Quick filters: All / Review / Confirmed / Rejected / etc.
- Pagination at the bottom
- Click any row to open the review

## 5. Export to Excel

**Export Excel** button at the top right.

The generated file contains:
- An **Invoices** sheet with all invoices (filters applied)
- An **Export** sheet with metadata (export date, invoice count)
- Frozen headers, formatted columns (dates, currencies, %)
- A totals row at the bottom (SUM subtotal, VAT, total)

## 6. Status glossary

| Status | Meaning |
|--------|---------|
| **Uploaded** | File uploaded, OCR not started |
| **Processing** | OCR in progress at Azure |
| **Ready for review** | OCR complete, awaiting human review |
| **Confirmed** | Approved, exportable |
| **Rejected** | Invalid (duplicate, error…) |
| **Failed** | OCR failed permanently — see reason |

## 7. Help & contact

- Technical issues: contact@venio.paris
- API docs: `https://api.<your-domain>.com/docs`

## Tips

- Upload native PDFs rather than scans when possible — OCR accuracy is higher
- For scans, use 300 dpi minimum
- Thorough review builds a corrections dataset that can feed future improvements
