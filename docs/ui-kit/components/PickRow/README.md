One row of the episode picker: All episodes, a season, or one episode.

**Use** in the two-column picker. Seasons on the left, the focused season's episodes on the right.

**Provide** the pick mark, the label ("Season 1", "3 · Chitty Chitty Death Bang"), the have mark and a note: downloaded of aired ("7/7"), plus size when deleting.

**States.** Focused: `glass-selected` with a 2px `focus` outline. Not pickable (when deleting, nothing downloaded): 45% opacity and no pick mark. Height 60px, `radius-m`.

**In the app:** `@layout/row_pick`, `EpisodesActivity`.
