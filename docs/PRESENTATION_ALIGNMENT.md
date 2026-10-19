# Research and presentation alignment

Revision: 19 October 2026. The presentation has exactly fifteen slides and is a self-contained HTML file served by the existing presentation tab. The audit implementation and Excel templates are outside this change.

## Evidence used

- The researcher's seventh thesis revision and the implementation of document extraction, supported contract parsing, Decimal arithmetic, matching and review.
- The 17 October test report: 7,249 text-layer receipts agreeing with the compared report fields; ten known errors in the 730 regression set; 57 correct automatic acceptances out of 61 synthetic-scan receipts; four referrals. The VLM re-test reused saved readings.
- The researcher's correction on 19 October: the earlier failed additional-template run does not represent the current system. The latest local trial took less than two minutes and produced observations the researcher checked against the documents and confirmed were actual errors preventing payment of the affected receipts until correction. This is an operational observation, not a computed precision or recall rate.
- The researcher confirmed that the 49-page additional-template dataset is entirely synthetic with fictitious data. Its name is not evidence that it contains real supplier records.

## Interpretation

Automatic acceptance, accuracy of extracted fields, detection of an actual accounting error, referral caused by weak reading, and human approval are different measurements. A valid referral is not necessarily an extraction failure. No observed error in a finite sample proves neither universal accuracy nor zero residual risk.

The Tesseract summary uses an earlier 210-page baseline; the VLM prompt comparison uses 90 pages. These are development results, not a paired benchmark on the same sample. Tender-level weight-training separation does not make later diagnostic use of held-out bundles a blind final test.

The historical 56-minute manual observation and the latest under-two-minute machine run cover different activities. The assisted end-to-end review time has not been measured under a controlled comparison. The workload slider is an explicitly labelled scenario calculation.

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

The presentation frame uses almost the full viewport width and an increased height. The deck includes a full-screen button and redesigned previous/next controls. Upload guidance uses the synthetic receipt STO0000005253 from competition MED-2026-339, bundle 01-001, page 16.
