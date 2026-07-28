# AAAI-27 Main Track rules snapshot

Verified on 2026-07-27. Recheck the official pages before a final verdict.

## Official sources

- Main track call: <https://aaai.org/conference/aaai/aaai-27/main-technical-track-call/>
- Submission instructions: <https://aaai.org/conference/aaai/aaai-27/submission-instructions/>
- Supplementary-material rules: <https://aaai.org/conference/aaai/aaai-27/supplementary-material/>
- Author Kit: <https://aaai.org/authorkit27/>

## Submission profile

- Main content: at most 7 pages. Total main PDF: at most 9 pages. Pages 8--9 are exclusively references.
- The main paper is anonymous. Remove names, affiliations, acknowledgments, identifying links, and PDF metadata that can reveal authors.
- Use AAAI two-column camera-ready style, US Letter, Type 1 or TrueType fonts, and a trouble-free high-resolution PDF.
- Submit the reproducibility checklist separately. It is available to reviewers.
- Supplementary document, media, and code/data packages are separate submissions. The main paper must remain self-contained.
- Do not point to web supplementary material, including anonymous repositories or anonymous datasets.
- Materials necessary to substantiate reproducibility must be provided at submission. A future-release promise is not reproducibility evidence.

## Author Kit constraints relevant to this skill

- Use `aaai2027.sty`, `aaai2027.bst`, PDFLaTeX, US Letter, embedded fonts, and PDF 1.5 or later.
- Do not use Type 3 fonts, hyperlinks/bookmarks, page numbers, headers/footers, package or command tricks that change spacing, margins, fonts, font size, or layout.
- Do not use `\\resizebox`, `\\tiny`, negative `\\vspace`/`\\vskip`, `\\trim`, `\\clip`, `hyperref`, or `pgfplots` in the paper source.
- Figure and table captions appear below the object. Captions are 10pt Roman. Table text is 10pt, or 9pt only when necessary. Figure-internal text is at least 9pt.
- Tables may not be resized wholesale. Shorten content, reduce precision, adjust `\\tabcolsep`, span columns, or split tables.
- The source must not contain EPS or PS figures. Pre-generate PDF, PNG, or JPG figures. Crop figures outside LaTeX.

## SuDIS stricter rules

- Sections must be numbered using `secnumdepth` 1 or 2.
- Page one must include a teaser that communicates the paper story without relying on the body.
- Every appendix section must be lettered and explicitly referenced from main text.
- Use vector output for diagrams, architecture figures, and plots. Raster examples may be used only when inherently photographic or frame-based and must be high resolution.
- Use no em dash or AI-tone/hype wording. Qualify all comparative claims with setting and evidence.

## Automated font interpretation

- A confirmed Type 3 font or `emb=no` row from `pdffonts` is an official format failure.
- `Identity-H` is not sufficient evidence by itself to locate prohibited content. Block G5 for manual confirmation instead of automatically failing it.
- Do not infer figure-internal point size from font metadata. Confirm suspected small text on the rendered page and record the exact figure or table.
