# Rated Arr UI kit

Rated Arr (code name Fetch) is an Android TV app for finding films and shows and adding them to a seedbox. Everything here is read from a sofa three metres away and driven with a remote's arrows and OK. Design for that first: few, large things; one obvious focus; nothing that needs a pointer.

**Grindhouse** is the app's look: a 70s exploitation poster for so-bad-it's-good nights. **Classic** is how the app looked before it. **Rewind** and **Teletext** are further concepts over the same parts.

Open `index.html` in a browser to see every part under each theme. `tokens.json` holds the tokens; after changing it, run `python3 build.py` to write `tokens.css` and `index.html` again. Outfit is in `fonts/`; the theme faces (Anton, Courier Prime, Bowlby One, VT323) load from Google Fonts, so the concepts need a connection.

## Voice and copy

- Write plain, short sentences in sentence case. Say what happened and what to do: "The download is stalled with no connections", "Nothing matched exactly. Showing “The Glimmer Man”."
- Name actions by what they do: "Add film", "Download all", "Choose episodes…", "Delete file", "Remove show". An ellipsis (…) means the action opens another screen.
- Status words are one or two words: "Ready", "In library", "Adding…", "Deleting…".
- Separate facts with a middle dot and spaces: "1996 · 1h 32m · Action, Comedy · ★ 5.4", "In your library · Ready to watch".
- Use typographic quotes and apostrophes (“ ” ’), "★" before a rating, decimal units for sizes ("37.4 GB", "1.74 TB of 3.9 TB used · 2.16 TB free").
- Every delete asks first and says what it frees and that it can't be undone: "This frees 96.5 GB. Radarr won’t download it again. This can’t be undone."
- No emoji, no exclamation marks, no jargon from Radarr or Sonarr where a plain word works ("downloaded", not "has file").

## Visual foundations

**Screen.** Design at 960 × 540 dp. Paint the screen with a vertical gradient from `screen-top` to `screen`, with `glow` as a soft light in the top-left corner. Keep `gutter` free on both sides: rows scroll sideways inside it, so the focused card never touches the TV's edge.

**Colour.** Set text in `ink`; secondary text in `ink-dim`; metadata in `ink-faint`. Fill controls with `glass` and chosen ones with `glass-selected`; outline them with `line`. Use `accent` only for progress and picked episodes, `ready` only for things that are downloaded, `warning` for anything that needs attention, and `danger` only for destructive actions and missing episodes. Darken backdrops behind text with `scrim`.

**Focus.** There is one focus colour, `focus`, and exactly one focused thing on screen. A focused pill control (button, tab, chip) fills with `focus` and its text turns `on-focus`. A focused card grows to `focus-scale` (wide cards and buttons to `focus-scale-wide`), gets a `focus-ring` ring in `focus` and lifts with `lift`. Moving up from a row returns to the chosen tab.

**Type.** The styles in the App group: `display` for a title page's title, `title` for screen and dialog titles, `heading` in capitals for row titles, `body` for plots and messages, `label` for controls, `card-title` and `card-meta` under cards, `badge` in badges and the status pill. Classic sets them all in Outfit. Grindhouse, as the app does, sets the wordmark, titles, row headings, tabs, chips, buttons, card titles and badges in Anton capitals, and plots, taglines, card details and messages in Courier Prime. Nothing is smaller than 12px.

**Spacing and shape.** Use the 4px steps `space-1` to `space-7`. Cards sit `card-gap` apart and rows `row-gap` apart. Posters are 2:3 (`poster-w` × `poster-h`) with `radius-m`; download cards and dialogs use `radius-l`; badges `radius-s`; every control is a pill (`radius-pill`) at `control-s` or `control-l`, the search field at `control-xl`.

**Imagery.** Posters come from TMDB at w342, backdrops at w1280, cast photos at w185. Without an image, show the title's initials on the `surface` gradient. A title page's backdrop sits at 55% opacity under `scrim`, strongest on the left where the text is. Grindhouse gives pictures an aged-print filter, `sepia(.35) contrast(1.15)`; the app applies it to the title page's backdrop.

**Motion.** Only focus moves: a 160 ms decelerating zoom. Nothing else animates; screens and rows never jump while you use them, and the Downloading row refreshes in place.

**States.** Disabled controls drop to 45% opacity and say what is happening. A row of red buttons (Delete file, Remove film) always sits below the normal buttons, never among them.

## Iconography

The app's icons are Android vector drawables on a 24-unit grid: round caps, round joins, 2–3 unit strokes, simple discs and rings. They are copied here as SVG under Icons with the app's current colours; in the UI the marks take `ready`, `warning`, `danger`, `accent` and `ink-dim`. Every status mark differs in shape as well as colour (tick, half, cross, dash, ring). No emoji, no icon font.

The logo is a film rating box: "RATED" reversed out of an ink bar over a red "ARR", in Anton on newsprint (`assets/Logos`: the TV launcher banner, and the launcher icon, the box alone). `tools/make_art.py` draws both. Inside the app the wordmark is plain text in the `wordmark` style.

## Themes

- **Grindhouse** (default, the app's look). A 70s exploitation poster on aged newsprint, for so-bad-it's-good nights. Titles and headings in a condensed poster face in capitals, plots in a typewriter face, red `focus`, square corners, thick ink outlines, a halftone dot screen, and focused posters that tilt like a poster slapped on a wall.
- **Rewind.** A 90s video rental shelf. Titles like VHS box spines, labels and badges in a VCR on-screen display face, posters in black clamshell frames, round orange stickers for Ready, yellow price-tag `focus`, faint scanlines, and a "▶ PLAY SP" readout.
- **Teletext.** An eight-colour TV text page. One blocky face for everything, square corners, Films / Shows / Library as red, green and yellow Fastext keys, headings on blue bars, and a page header line ("P100 RATED ARR").
