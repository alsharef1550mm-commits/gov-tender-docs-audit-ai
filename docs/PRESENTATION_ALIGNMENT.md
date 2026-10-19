# Research and presentation alignment

Revision: 19 October 2026. The presentation has exactly fifteen slides and is a self-contained HTML file served by the existing presentation tab. The audit implementation and Excel templates are outside this change.

## Evidence used

- The researcher's seventh thesis revision and the implementation of document extraction, supported contract parsing, Decimal arithmetic, matching and review.
- The 17 October test report: 7,249 text-layer receipts agreeing with the compared report fields; ten known errors in the 730 regression set; 57 correct automatic acceptances out of 61 synthetic-scan receipts; four referrals. The VLM re-test reused saved readings.
- Official runtime benchmark, 19 October: batch MED-2026-144-02-012, 18 receipts, 12 seconds; complete tender MED-2026-231, 1,653 receipts, 424 seconds. Researcher-directed, automation-assisted local runs on known synthetic text PDFs. Previous ad hoc times are superseded for the official comparison. See OFFICIAL_PERFORMANCE_TEST_20261019.md.
- The researcher confirmed that the 49-page additional-template dataset is entirely synthetic with fictitious data. Its name is not evidence that it contains real supplier records.

## Interpretation

Automatic acceptance, accuracy of extracted fields, detection of an actual accounting error, referral caused by weak reading, and human approval are different measurements. A valid referral is not necessarily an extraction failure. No observed error in a finite sample proves neither universal accuracy nor zero residual risk.

The Tesseract summary uses an earlier 210-page baseline; the VLM prompt comparison uses 90 pages. These are development results, not a paired benchmark on the same sample. Tender-level weight-training separation does not make later diagnostic use of held-out bundles a blind final test.

The researcher reports 180–204 seconds per receipt for full manual checking. The interactive slider extrapolates estimated manual effort: 54–61.2 minutes for 18 receipts and 82.65–93.67 working hours for 1,653 receipts. These are not timed manual trials on the complete files. System timing excludes upload, ZIP preparation / pre-job expansion, subsequent verification and human review. End-to-end savings have not been measured.

## Presentation behavior

Slide 6 offers clear text, clear scan and confirmed-discrepancy scenarios with play, pause, reset and speed controls. The document moves through routing, reading, verification and matching, then follows the report or review branch. This is an explanatory simulation and never starts an actual audit or calls a paid model.

The four research diagrams were redrawn with legible Arabic and shared terminology. Editable SVG originals accompany the project. Source-document examples and QR destinations are retained.

## Primary sources checked

- https://www.uqn.gov.sa/decisions-and-regulations/4001760
- https://socpa.org.sa/SOCPA/files/a9/a963c9e3-3665-4643-9be3-cc7ff79bc4ec.pdf
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6095166
- https://eaa-online.org/app/uploads/sites/80/2026/05/scientific_programme-open.pdf
- https://arxiv.org/abs/2605.05252
- https://huggingface.co/Qwen/Qwen3.5-9B

The thesis remains a local academic document. Synchronization publishes only the presentation and its project documentation and diagrams.

The presentation frame stays within the same responsive content container as the rest of the app, with a flexible height and a single full-screen button inside the deck. The duplicate landing-page entry button was removed. Previous/next controls and all fifteen slides are preserved. Upload guidance uses the synthetic receipt STO0000005253 from competition MED-2026-339, bundle 01-001, page 16.
