# Pre-upgrade layout behavior

Captured on 2026-08-20 from branch `main` before generation changes. All 27
existing unit tests passed.

## Regression baselines

- `baseline_outputs/normal_magazine_article.json`
- `baseline_outputs/normal_cover.json`
- `baseline_outputs/normal_editorial.json`
- `baseline_outputs/normal_advertisement.json`

These were generated through the existing Vertex retrieval, reranking, Gemini,
schema-validation, and geometry-validation path.

## Converter-facing schema

The root is a `LayoutProject` with `pageIndex: 0`, document settings, project
information, and sequential pages starting at 1. Assets are strict `Article`,
`Image`, or `Ad` objects. Article typography and frame settings are siblings of
`content`; image content accepts only HTTPS URLs or URL placeholders.

Before this upgrade, Article content allowed only `textBody`; neither
`articleDocumentLink` nor `expand` was representable.

## Validation

Pydantic rejects unknown fields and invalid asset shapes. Quality validation
then enforces approved fonts, a 0.25-inch Article safe margin, 0.125-inch image
bleed, 0.5-inch ad tolerance, and non-overlapping Article frames. It had no
relationship validation and treated an intentional cross-page image like an
invalid oversized bleed.

## Retrieval

The normal library contains one page per example. Vertex embeddings query the
checked-in local vector store; BM25 supplies lexical candidates; weighted
results are reranked and sanitized before the top examples are sent to Gemini.
Only example JSON was sent to Gemini, so relationship intent was not preserved.

## Confirmed source evidence

`raw_data/New_doc_with_image_bleed_data.json` contains a page-2 image extending
14 inches into an existing empty page 3. The overflow raw sample contains
manually split text and no thread metadata, so it was not promoted as a
confirmed threaded-text reference.
