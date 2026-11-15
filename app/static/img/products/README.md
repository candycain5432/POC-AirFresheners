# Product photos

Put one photo per product in this folder, named after the product's **slug**
(the last part of its shop URL), as a `.jpg`:

    /shop/product/burnt-clutch   ->   burnt-clutch.jpg

- Square works best (about 800 x 800). Keep each under ~150 KB.
- The files here now are drawn PLACEHOLDERS (`tools/make_placeholder_art.py`).
  Overwrite them with real photos using the same names.
- A product with no photo here falls back to a drawn SVG placeholder automatically.
