package com.androidtv.fetch.screens;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.KeyEvent;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.androidtv.fetch.R;
import com.androidtv.fetch.gateway.FetchException;
import com.androidtv.fetch.gateway.Session;
import com.androidtv.fetch.model.DownloadGroup;
import com.androidtv.fetch.model.Genre;
import com.androidtv.fetch.model.Genres;
import com.androidtv.fetch.model.Item;
import com.androidtv.fetch.model.Library;
import com.androidtv.fetch.model.LibraryEntry;
import com.androidtv.fetch.model.PersonCredits;
import com.androidtv.fetch.model.SearchResults;
import com.androidtv.fetch.model.Shelf;
import com.androidtv.fetch.model.Storage;
import com.androidtv.fetch.ui.Background;
import com.androidtv.fetch.ui.Cards;
import com.androidtv.fetch.ui.Errors;
import com.androidtv.fetch.ui.Labels;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Search, results and home. Typing searches after a short pause; the keyboard's Search key also
 * moves to the first result. With no search, home shows the downloads (one card per title), then
 * suggestions and recent additions for the chosen tab, Films or Shows. Moving across the tabs
 * switches them at once from the loaded data. Under Downloading, genre chips swap the suggestions for
 * a genre's rows, fetched once per genre. Only the Downloading row refreshes while home is open, in
 * place, so focus and scrolling never jump. The Library tab shows the plan's disk space
 * and what is downloaded, largest first; it loads each time it is chosen, and again after a title
 * was deleted.
 */
public class MainActivity extends Activity {

    /** A name to search for when this screen is opened, such as an actor clicked on a title page. */
    static final String EXTRA_SEARCH = "search";
    private static final long TYPING_PAUSE_MS = 600;
    private static final long HOME_REFRESH_MS = 15_000;
    private static final int MIN_QUERY = 2;
    private static final int REQUEST_DETAIL = 1;
    private static final String PREF_TAB = "home_tab";
    private static final double STORAGE_WARNING = 0.9;

    private enum Tab {
        FILM, SHOW, LIBRARY;

        Item.Kind kind() {
            return this == SHOW ? Item.Kind.SHOW : Item.Kind.FILM;
        }
    }

    /** What the home screen shows when nothing is searched. */
    private static final class Home {
        final List<DownloadGroup> downloads;
        final List<Shelf> shelves;
        final List<Item> recent;
        final Genres genres;

        Home(List<DownloadGroup> downloads, List<Shelf> shelves, List<Item> recent, Genres genres) {
            this.downloads = downloads;
            this.shelves = shelves;
            this.recent = recent;
            this.genres = genres;
        }
    }

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, View> cards = new HashMap<>();
    private final Runnable searchAfterTyping = () -> search(false);
    private final Runnable refreshDownloads = new Runnable() {
        @Override
        public void run() {
            if (homeShown) updateDownloads();
            handler.postDelayed(this, HOME_REFRESH_MS);
        }
    };

    private Session session;
    private EditText searchBox;
    private LinearLayout sections;
    private TextView message;
    private ProgressBar spinner;
    /** Bumped by every search so a slow reply never replaces newer results. */
    private int generation;
    private boolean homeShown;
    private boolean libraryShown;
    /** Set when a details screen deleted something, so home and the library load again. */
    private boolean libraryChanged;
    private Home home;
    private Tab tab = Tab.FILM;
    private TextView tabFilms, tabShows, tabLibrary;
    private View tabs;
    /** The genre chosen on each tab ("" is For you), and the rows of genres already fetched, by kind and genre. */
    private final Map<Item.Kind, String> genreChoice = new HashMap<>();
    private final Map<String, List<Shelf>> genreRows = new HashMap<>();
    /** The rows under the genre chips, replaced when another chip is chosen. */
    private LinearLayout homeContent;
    /** The title whose details were opened last, to focus its card again when the rows are rebuilt. */
    private String openedKey = "";
    /** The Downloading section and the groups its cards show, for refreshing in place. */
    private View downloadsSection;
    private List<DownloadGroup> shownGroups = new java.util.ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        session = Session.get(this);
        searchBox = findViewById(R.id.search);
        sections = findViewById(R.id.sections);
        message = findViewById(R.id.message);
        spinner = findViewById(R.id.spinner);
        tabs = findViewById(R.id.tabs);
        tabFilms = findViewById(R.id.tabFilms);
        tabShows = findViewById(R.id.tabShows);
        tabLibrary = findViewById(R.id.tabLibrary);
        if (getString(R.string.gateway_url).isEmpty()) {
            showMessage(getString(R.string.not_configured));
            return;
        }
        if (!session.isPaired()) {
            openPairing();
            return;
        }
        setUpSearchBox();
        setUpTabs();
        searchFrom(getIntent());
    }

    // Purpose: an actor clicked on a title page comes back here as a search for their name.
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (session.isPaired()) searchFrom(intent);
    }

    private void searchFrom(Intent intent) {
        String name = intent.getStringExtra(EXTRA_SEARCH);
        if (name == null || name.isEmpty()) return;
        searchBox.setText(name);
        searchBox.setSelection(name.length());
        handler.removeCallbacks(searchAfterTyping);
        search(true);
    }

    // Purpose: the tabs switch on focus. Films and Shows render from the home already loaded and are
    // remembered; Library loads fresh and is not remembered, so the app always opens on suggestions.
    private void setUpTabs() {
        tab = "SHOW".equals(session.prefs.getString(PREF_TAB, "FILM")) ? Tab.SHOW : Tab.FILM;
        chooseOnFocus(tabFilms, Tab.FILM);
        chooseOnFocus(tabShows, Tab.SHOW);
        chooseOnFocus(tabLibrary, Tab.LIBRARY);
        showTabState();
    }

    private void chooseOnFocus(View tabView, Tab chosen) {
        tabView.setOnFocusChangeListener((v, focused) -> {
            if (focused) chooseTab(chosen);
        });
    }

    private void chooseTab(Tab chosen) {
        if (chosen == tab) return;
        tab = chosen;
        if (chosen != Tab.LIBRARY) session.prefs.edit().putString(PREF_TAB, chosen.name()).apply();
        showTabState();
        if (!query().isEmpty()) return;
        if (chosen == Tab.LIBRARY) loadLibrary(false);
        else if (home != null) renderHome(false);
    }

    private void showTabState() {
        tabFilms.setSelected(tab == Tab.FILM);
        tabShows.setSelected(tab == Tab.SHOW);
        tabLibrary.setSelected(tab == Tab.LIBRARY);
        searchBox.setNextFocusDownId(tab == Tab.FILM ? R.id.tabFilms : tab == Tab.SHOW ? R.id.tabShows : R.id.tabLibrary);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!session.isPaired() || getString(R.string.gateway_url).isEmpty()) return;
        if (query().isEmpty() && libraryChanged) loadHome(false);
        else if (query().isEmpty() && !homeShown && !libraryShown) loadHome(true);
        handler.postDelayed(refreshDownloads, homeShown ? 0 : HOME_REFRESH_MS);
    }

    @Override
    protected void onPause() {
        super.onPause();
        handler.removeCallbacks(refreshDownloads);
        handler.removeCallbacks(searchAfterTyping);
    }

    // Purpose: Back from results returns to home and the search box; Back from home leaves the app.
    @Override
    public void onBackPressed() {
        if (!query().isEmpty()) {
            searchBox.setText("");
            searchBox.requestFocus();
            return;
        }
        super.onBackPressed();
    }

    // Purpose: a title added or removed on the details screen gets its badge here without a new search;
    // after a delete, home and the library load again when this screen returns.
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_DETAIL || resultCode != RESULT_OK || data == null) return;
        libraryChanged |= data.getBooleanExtra(DetailActivity.EXTRA_LIBRARY_CHANGED, false);
        View card = cards.get(data.getStringExtra(DetailActivity.EXTRA_KEY));
        if (card == null || libraryShown) return;
        Cards.markInLibrary(card, data.getBooleanExtra(DetailActivity.EXTRA_IN_LIBRARY, true),
                data.getBooleanExtra(DetailActivity.EXTRA_DOWNLOADED, false));
    }

    private void setUpSearchBox() {
        searchBox.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {
            }

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
            }

            @Override
            public void afterTextChanged(Editable s) {
                handler.removeCallbacks(searchAfterTyping);
                if (query().isEmpty()) loadHome(true);
                else if (query().length() >= MIN_QUERY) handler.postDelayed(searchAfterTyping, TYPING_PAUSE_MS);
            }
        });
        searchBox.setOnEditorActionListener((view, actionId, event) -> {
            boolean enter = event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                    && event.getAction() == KeyEvent.ACTION_DOWN;
            if (actionId != EditorInfo.IME_ACTION_SEARCH && !enter) return false;
            handler.removeCallbacks(searchAfterTyping);
            hideKeyboard();
            search(true);
            return true;
        });
    }

    private String query() {
        return searchBox.getText().toString().trim();
    }

    private void search(boolean focusResults) {
        String query = query();
        if (query.isEmpty()) return;
        int ticket = ++generation;
        tabs.setVisibility(View.GONE);
        showLoading(getString(R.string.searching));
        Background.run(this, () -> session.client.search(query), results -> {
            if (ticket == generation) showResults(query, results, focusResults);
        }, error -> {
            if (ticket == generation) showError(error);
        });
    }

    private void showResults(String query, SearchResults results, boolean focusResults) {
        clearSections();
        tabs.setVisibility(View.GONE);
        if (results.isEmpty()) {
            showMessage(getString(R.string.nothing_found, query));
            return;
        }
        LayoutInflater inflater = getLayoutInflater();
        if (!results.suggestion.isEmpty()) addSuggestion(inflater, results.suggestion);
        for (PersonCredits person : results.people) {
            if (person.named) addPersonRows(inflater, person);
        }
        addItemRow(inflater, getString(R.string.section_films), results.films,
                results.unavailable.contains(Item.Kind.FILM) ? getString(R.string.unavailable_films) : "");
        addItemRow(inflater, getString(R.string.section_shows), results.shows,
                results.unavailable.contains(Item.Kind.SHOW) ? getString(R.string.unavailable_shows) : "");
        for (PersonCredits person : results.people) {
            if (!person.named) addPersonRows(inflater, person);
        }
        if (!results.people.isEmpty()) addCredit(inflater);
        if (focusResults) focusFirstCard();
    }

    private void addSuggestion(LayoutInflater inflater, String suggestion) {
        TextView note = (TextView) inflater.inflate(R.layout.search_note, sections, false);
        note.setText(getString(R.string.search_suggestion, suggestion));
        sections.addView(note);
    }

    // Purpose: a search that names an actor or director also lists their films and regular shows; when the
    // search is their name or surname, these rows come first.
    private void addPersonRows(LayoutInflater inflater, PersonCredits person) {
        int films = person.directing ? R.string.section_person_directed : R.string.section_person_films;
        addItemRow(inflater, getString(films, person.name), person.films, "");
        addItemRow(inflater, getString(R.string.section_person_shows, person.name), person.shows, "");
    }

    private void loadHome(boolean showSpinner) {
        int ticket = ++generation;
        if (showSpinner) showLoading("");
        Background.run(this, () -> new Home(DownloadGroup.of(session.client.downloads()), discoverOrNothing(),
                session.client.recent(), genresOrNone()), home -> {
            if (ticket == generation && query().isEmpty()) showHome(home);
        }, error -> {
            if (ticket == generation && query().isEmpty()) showError(error);
        });
    }

    // Purpose: Discover rows are extras; if Radarr cannot give them, home shows the rest.
    private List<Shelf> discoverOrNothing() {
        try {
            return session.client.discover();
        } catch (FetchException e) {
            return new java.util.ArrayList<>();
        }
    }

    // Purpose: genres are extras too; without them home has no chips.
    private Genres genresOrNone() {
        try {
            return session.client.genres();
        } catch (FetchException e) {
            return Genres.none();
        }
    }

    private void showHome(Home loaded) {
        home = loaded;
        libraryChanged = false;
        View focused = getCurrentFocus();
        boolean focusSearch = focused == null || focused == searchBox;
        if (tab == Tab.LIBRARY) loadLibrary(focusSearch);
        else keepFocusAcross(() -> renderHome(focusSearch));
    }

    // Purpose: Downloading for everything, then the genre chips, then the chosen genre's rows or, for For you,
    // the tab's suggestion rows and recent additions.
    private void renderHome(boolean focusSearch) {
        clearSections();
        homeShown = true;
        tabs.setVisibility(View.VISIBLE);
        LayoutInflater inflater = getLayoutInflater();
        showDownloads(home.downloads);
        addGenreChips(inflater);
        homeContent = new LinearLayout(this);
        homeContent.setOrientation(LinearLayout.VERTICAL);
        homeContent.setClipChildren(false);
        sections.addView(homeContent);
        fillHomeContent();
        if (focusSearch) searchBox.requestFocus();
    }

    private void fillHomeContent() {
        homeContent.removeAllViews();
        String genre = genreChoice.getOrDefault(tab.kind(), "");
        if (genre.isEmpty()) addSuggestionRows();
        else addGenreRows(genre);
    }

    private void addSuggestionRows() {
        LayoutInflater inflater = getLayoutInflater();
        boolean creditTmdb = false;
        for (Shelf shelf : home.shelves) {
            String title = shelfTitle(shelf);
            if (title.isEmpty() || shelf.items.get(0).kind != tab.kind()) continue;
            addItemRow(inflater, homeContent, title, shelf.items, "");
            creditTmdb |= shelf.fromTmdb();
        }
        addItemRow(inflater, homeContent, getString(R.string.section_recent), ofKind(home.recent, tab.kind()), "");
        if (creditTmdb) addCredit(inflater, homeContent);
        if (home.downloads.isEmpty() && homeContent.getChildCount() == 0) showMessage(getString(R.string.home_empty));
    }

    // Purpose: a genre's rows from the cache, or fetched now; a reply is shown only if that genre is still chosen.
    private void addGenreRows(String genre) {
        Item.Kind kind = tab.kind();
        String key = kind + ":" + genre;
        List<Shelf> rows = genreRows.get(key);
        if (rows == null) {
            homeContent.addView(getLayoutInflater().inflate(R.layout.row_loading, homeContent, false));
            Background.run(this, () -> session.client.browse(kind, genre), loaded -> {
                genreRows.put(key, loaded);
                if (isShowing(kind, genre)) fillHomeContent();
            }, error -> {
                if (isShowing(kind, genre)) showGenreError(error);
            });
            return;
        }
        LayoutInflater inflater = getLayoutInflater();
        for (Shelf shelf : rows) addItemRow(inflater, homeContent, browseTitle(shelf), shelf.items, "");
        if (!rows.isEmpty()) addCredit(inflater, homeContent);
    }

    private boolean isShowing(Item.Kind kind, String genre) {
        return homeShown && tab.kind() == kind && genre.equals(genreChoice.getOrDefault(kind, ""));
    }

    private void showGenreError(FetchException error) {
        homeContent.removeAllViews();
        TextView note = (TextView) getLayoutInflater().inflate(R.layout.search_note, homeContent, false);
        note.setText(Errors.message(this, error));
        homeContent.addView(note);
    }

    private void addGenreChips(LayoutInflater inflater) {
        List<Genre> genres = home.genres.of(tab.kind());
        if (genres.isEmpty()) return;
        View strip = inflater.inflate(R.layout.genre_chips, sections, false);
        ViewGroup row = strip.findViewById(R.id.chipRow);
        addChip(inflater, row, "", getString(R.string.genre_for_you));
        for (Genre genre : genres) addChip(inflater, row, genre.id, genre.name);
        sections.addView(strip);
    }

    private void addChip(LayoutInflater inflater, ViewGroup row, String genreId, String name) {
        TextView chip = (TextView) inflater.inflate(R.layout.chip, row, false);
        chip.setText(name);
        chip.setSelected(genreId.equals(genreChoice.getOrDefault(tab.kind(), "")));
        chip.setOnClickListener(v -> chooseGenre(row, chip, genreId));
        Cards.zoomOnFocus(chip, Cards.WIDE_FOCUSED_SCALE);
        row.addView(chip);
    }

    private void chooseGenre(ViewGroup row, View chosen, String genreId) {
        genreChoice.put(tab.kind(), genreId);
        for (int i = 0; i < row.getChildCount(); i++) row.getChildAt(i).setSelected(row.getChildAt(i) == chosen);
        message.setVisibility(View.GONE);
        fillHomeContent();
    }

    private String browseTitle(Shelf shelf) {
        switch (shelf.id) {
            case "soBad": return getString(R.string.browse_so_bad);
            case "bMovies": return getString(R.string.browse_b_movies);
            case "flops": return getString(R.string.browse_flops);
            case "topRated": return getString(R.string.browse_top_rated);
            default: return getString(R.string.browse_popular);
        }
    }

    private void loadLibrary(boolean focusSearch) {
        int ticket = ++generation;
        if (!libraryShown) showLoading("");
        Background.run(this, session.client::library, library -> {
            if (ticket == generation && query().isEmpty() && tab == Tab.LIBRARY) {
                keepFocusAcross(() -> renderLibrary(library, focusSearch));
            }
        }, error -> {
            if (ticket == generation && query().isEmpty() && tab == Tab.LIBRARY) showError(error);
        });
    }

    // Purpose: the disk space, then what Plex cannot play, then films and shows by the space they take.
    private void renderLibrary(Library library, boolean focusSearch) {
        clearSections();
        libraryShown = true;
        tabs.setVisibility(View.VISIBLE);
        LayoutInflater inflater = getLayoutInflater();
        if (library.storage.limit > 0) addStorage(inflater, library.storage);
        addLibraryRow(inflater, getString(R.string.library_problems), library.problems(),
                getString(R.string.library_problems_note));
        addLibraryRow(inflater, getString(R.string.library_films), Library.largestFirst(library.films), "");
        addLibraryRow(inflater, getString(R.string.library_shows), Library.largestFirst(library.shows), "");
        if (library.films.isEmpty() && library.shows.isEmpty()) showMessage(getString(R.string.library_empty));
        if (focusSearch) searchBox.requestFocus();
    }

    // Purpose: the bar and line turn amber when less than a tenth of the plan is free.
    private void addStorage(LayoutInflater inflater, Storage storage) {
        View header = inflater.inflate(R.layout.storage_header, sections, false);
        double used = (double) storage.used / storage.limit;
        ProgressBar bar = header.findViewById(R.id.storageBar);
        bar.setProgress((int) Math.round(Math.min(1, used) * 1000));
        TextView line = header.findViewById(R.id.storageLine);
        line.setText(Labels.storage(storage));
        if (used >= STORAGE_WARNING) {
            line.setTextColor(getColor(R.color.warning));
            bar.setProgressTintList(android.content.res.ColorStateList.valueOf(getColor(R.color.warning)));
        }
        sections.addView(header);
    }

    private void addLibraryRow(LayoutInflater inflater, String title, List<LibraryEntry> entries, String note) {
        if (entries.isEmpty()) return;
        ViewGroup row = Cards.section(inflater, sections, title, note);
        for (LibraryEntry entry : entries) {
            cards.put(entry.item.key(), Cards.libraryPoster(inflater, row, entry, v -> openDetail(entry.item, entry.size)));
        }
    }

    // Purpose: rebuilding the rows removes the focused card; focus the same title again, or the first card.
    private void keepFocusAcross(Runnable render) {
        boolean focusInRows = sections.hasFocus();
        render.run();
        if (!focusInRows) return;
        View card = cards.get(openedKey);
        if (card != null) card.requestFocus();
        else focusFirstCard();
    }

    private static List<Item> ofKind(List<Item> items, Item.Kind kind) {
        List<Item> out = new java.util.ArrayList<>();
        for (Item item : items) {
            if (item.kind == kind) out.add(item);
        }
        return out;
    }

    // Purpose: the row's heading, or "" for a row this version does not know (it is then skipped).
    private String shelfTitle(Shelf shelf) {
        switch (shelf.id) {
            case "recommended": return getString(R.string.section_recommended);
            case "trending": return getString(R.string.section_trending);
            case "popular": return getString(R.string.section_popular);
            case "becauseYouHave": return shelf.subject.isEmpty() ? "" : getString(R.string.section_because, shelf.subject);
            case "trendingShows": return getString(R.string.section_trending_shows);
            case "topRatedShows": return getString(R.string.section_top_rated_shows);
            default: return "";
        }
    }

    // Purpose: TMDB's terms ask for this line wherever its data is shown.
    private void addCredit(LayoutInflater inflater) {
        addCredit(inflater, sections);
    }

    private void addCredit(LayoutInflater inflater, ViewGroup parent) {
        TextView credit = (TextView) inflater.inflate(R.layout.credit, parent, false);
        parent.addView(credit);
    }

    private void updateDownloads() {
        int ticket = generation;
        Background.run(this, session.client::downloads, queue -> {
            if (ticket == generation && homeShown) showDownloads(DownloadGroup.of(queue));
        }, error -> {
        });
    }

    // Purpose: the Downloading row at the top of home; the same cards are updated while the titles stay the same.
    private void showDownloads(List<DownloadGroup> groups) {
        if (downloadsSection != null && sameTitles(groups, shownGroups)) {
            ViewGroup row = downloadsSection.findViewById(R.id.sectionRow);
            for (int i = 0; i < groups.size(); i++) Cards.bindDownloadGroup(row.getChildAt(i), groups.get(i));
            shownGroups = groups;
            return;
        }
        boolean hadFocus = downloadsSection != null && downloadsSection.hasFocus();
        if (downloadsSection != null) sections.removeView(downloadsSection);
        downloadsSection = null;
        shownGroups = groups;
        if (groups.isEmpty()) {
            if (hadFocus) searchBox.requestFocus();
            return;
        }
        LayoutInflater inflater = getLayoutInflater();
        ViewGroup row = Cards.section(inflater, sections, getString(R.string.section_downloading), "");
        downloadsSection = (View) row.getParent().getParent();
        sections.removeView(downloadsSection);
        sections.addView(downloadsSection, sections.indexOfChild(spinner) + 1);
        for (DownloadGroup group : groups) Cards.downloadGroup(inflater, row, group, v -> openDownloads(group));
        if (hadFocus) row.getChildAt(0).requestFocus();
    }

    private static boolean sameTitles(List<DownloadGroup> a, List<DownloadGroup> b) {
        if (a.size() != b.size()) return false;
        for (int i = 0; i < a.size(); i++) {
            if (!a.get(i).key.equals(b.get(i).key)) return false;
        }
        return true;
    }

    private void openDownloads(DownloadGroup group) {
        startActivity(new Intent(this, DownloadsActivity.class)
                .putExtra(DownloadsActivity.EXTRA_KEY, group.key)
                .putExtra(DownloadsActivity.EXTRA_TITLE, group.title)
                .putExtra(DownloadsActivity.EXTRA_POSTER, group.poster));
    }

    private void addItemRow(LayoutInflater inflater, String title, List<Item> items, String note) {
        addItemRow(inflater, sections, title, items, note);
    }

    private void addItemRow(LayoutInflater inflater, ViewGroup parent, String title, List<Item> items, String note) {
        if (items.isEmpty() && note.isEmpty()) return;
        ViewGroup row = Cards.section(inflater, parent, title, note);
        for (Item item : items) cards.put(item.key(), Cards.poster(inflater, row, item, v -> openDetail(item)));
    }

    private void showError(FetchException error) {
        if (error.reason == FetchException.Reason.NOT_PAIRED) {
            session.forget();
            openPairing();
            return;
        }
        clearSections();
        showMessage(Errors.message(this, error));
    }

    private void showLoading(String text) {
        clearSections();
        if (!text.isEmpty()) showMessage(text);
        spinner.setVisibility(View.VISIBLE);
    }

    private void showMessage(String text) {
        message.setText(text);
        message.setVisibility(View.VISIBLE);
    }

    // Purpose: remove the rows and hide the message and spinner, keeping those two views for reuse.
    private void clearSections() {
        cards.clear();
        homeShown = false;
        libraryShown = false;
        downloadsSection = null;
        shownGroups = new java.util.ArrayList<>();
        for (int i = sections.getChildCount() - 1; i >= 0; i--) {
            View child = sections.getChildAt(i);
            if (child != message && child != spinner) sections.removeViewAt(i);
        }
        message.setVisibility(View.GONE);
        spinner.setVisibility(View.GONE);
    }

    // Purpose: focus the first card of the first row that has one.
    private void focusFirstCard() {
        sections.post(() -> {
            for (int i = 0; i < sections.getChildCount(); i++) {
                ViewGroup row = sections.getChildAt(i).findViewById(R.id.sectionRow);
                if (row != null && row.getChildCount() > 0) {
                    row.getChildAt(0).requestFocus();
                    return;
                }
            }
        });
    }

    private void hideKeyboard() {
        InputMethodManager keyboard = getSystemService(InputMethodManager.class);
        if (keyboard != null) keyboard.hideSoftInputFromWindow(searchBox.getWindowToken(), 0);
    }

    private void openDetail(Item item) {
        openDetail(item, 0);
    }

    /** @param size the bytes the title takes on disk, 0 when unknown; the delete questions say what is freed */
    private void openDetail(Item item, long size) {
        openedKey = item.key();
        startActivityForResult(new Intent(this, DetailActivity.class)
                .putExtra(DetailActivity.EXTRA_ITEM, item.json)
                .putExtra(DetailActivity.EXTRA_SIZE, size), REQUEST_DETAIL);
    }

    private void openPairing() {
        startActivity(new Intent(this, PairActivity.class));
        finish();
    }
}
