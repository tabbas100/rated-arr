A pill-shaped action: glass at rest, solid `focus` with `on-focus` text when focused.

**Use** for actions on a title page and in dialogs: Add film, Download all, Choose episodes…, Done, Cancel.

**Provide** a short label in `label` type, one or two words plus an ellipsis when it opens a picker.

**Sizes.** Primary actions are `control-l` high with `space-5` padding. Quiet actions (the quality chip) and destructive ones are `control-s` with `space-4`.

**Destructive.** Delete file, Remove film, Delete episodes… and Remove show use `danger` text and sit on their own row under the primary buttons, `space-3` apart. Focused, they take the `focus` fill with `danger-on-focus` text. Each one opens a ConfirmDialog first.

**States.** Focused: `focus` fill, scale `focus-scale-wide`, `lift`. Disabled: 45% opacity, label says what is happening ("Adding…").

**In the app:** `@style/Button`, `@layout/button`, `@layout/button_danger`, `drawable/button_bg`.
