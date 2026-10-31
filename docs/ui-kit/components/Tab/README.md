A top-level switch between Films, Shows and Library.

**Use** once per screen, under the search field. Tabs switch on focus, so moving across them changes the page at once.

**Provide** the tab names in `label` type.

**States.** Chosen: `glass-selected` fill with a `line` outline and `ink` text. Focused: `focus` fill, `on-focus` text. Others: `ink-dim` text and no fill.

**Rules.** Moving up from any row lands on the chosen tab, never the nearest one. Height `control-s`, `space-2` apart.

**In the app:** `@style/Tab`, `TabBar`, `drawable/tab_bg`, `color/tab_text`.
