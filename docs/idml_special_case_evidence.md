# IDML special-case evidence

Inspected locally on 2026-08-20. The IDML packages were read as ZIP/XML; no
source document was modified.

## Confirmed same-page thread

Source:
`raw_data/JSON and IDML Files/Project_with_2_text_boxes_and_overflow.idml`

`Spreads/Spread_uce.xml` contains this chain:

```text
TextFrame uff
  ParentStory=ued
  PreviousTextFrame=n
  NextTextFrame=u116

TextFrame u116
  ParentStory=ued
  PreviousTextFrame=uff
  NextTextFrame=n
```

`Stories/Story_ued.xml` contains one 1,174-character story. This establishes
that the two frames are one InDesign story rather than manually split copy.
The corresponding relationship-aware record is
`same_page_text_thread_001` in the special-case library.

## Other available IDML

`Feb_10_project.idml` also contains two confirmed same-spread frame chains:

- `uff -> u16b`, `ParentStory=ued`
- `u146 -> u186`, `ParentStory=u134`

No available IDML contains a confirmed text chain crossing from one spread to
another. Cross-page threading therefore remains instruction- and
validation-supported, but has no RAG reference yet.

## Confirmed spread with overlays

Pages 26 and 27 in `layout_prompt_library_updated.json` describe a 17.02-inch
events image originating on page 26. Page 26 contains text overlays; page 27
contains additional overlay text and a different image, without duplicating
the spanning image. The relationship-aware normalized record is
`image_spread_with_overlays_001`.

## Missing evidence

No rendered PDFs were found in the workspace. Converter ownership and the
accepted wire type for `expand` are also not documented in the repository.
