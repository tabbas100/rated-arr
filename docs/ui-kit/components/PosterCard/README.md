A film or show as a 2:3 poster with its title and a meta line.

**Use** in every sideways row: suggestions, genres, search results, the library.

**Provide** the poster image (TMDB `w342`), the title, and a meta line: year and rating ("1996 · ★ 5.4"), or size and quality in the library ("37.4 GB · Bluray-1080p"). Without an image, show the title's initials in `ink-faint` on the `surface` gradient.

**Badge.** A title in the library shows "In library"; a downloaded one "Ready". The badge sits `space-2` from the bottom-left corner, `ready` fill, `on-ready` text and tick, `radius-s`.

**States.** Focused: scale `focus-scale`, a `focus-ring` ring in `focus`, `lift`. The row scrolls so the focused card stays inside the `gutter`.

**Sizes.** `poster-w` × `poster-h`, `radius-m`, `card-gap` apart. Title in `card-title`, one line, ellipsised; meta in `card-meta`, `ink-faint`.

**In the app:** `@layout/card_poster`, `Cards.poster`, `drawable/focus_ring`, `drawable/badge_library`.
