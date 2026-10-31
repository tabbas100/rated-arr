A thin bar for download progress, and a thicker one for disk space.

**Use** inside download cards and on title pages (6px), and as the disk meter on the Library tab (8px, `f-progress--thick`).

**Provide** a fraction from 0 to 1 and a status line under it.

**Colour.** Progress fills with `accent` on a `glass-selected` track. The disk meter turns `warning`, line included, when less than a tenth of the plan is free.

**In the app:** `drawable/progress_bar`, `@layout/storage_header`.
