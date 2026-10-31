package com.androidtv.fetch.screens;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.androidtv.fetch.R;
import com.androidtv.fetch.gateway.FetchException;
import com.androidtv.fetch.gateway.GatewayJson;
import com.androidtv.fetch.gateway.Session;
import com.androidtv.fetch.model.CastMember;
import com.androidtv.fetch.model.Download;
import com.androidtv.fetch.model.Episode;
import com.androidtv.fetch.model.Item;
import com.androidtv.fetch.model.Profile;
import com.androidtv.fetch.model.Profiles;
import com.androidtv.fetch.model.Season;
import com.androidtv.fetch.model.TitleDetails;
import com.androidtv.fetch.ui.Background;
import com.androidtv.fetch.ui.Cards;
import com.androidtv.fetch.ui.Confirm;
import com.androidtv.fetch.ui.Errors;
import com.androidtv.fetch.ui.Labels;
import com.androidtv.fetch.ui.Posters;
import com.androidtv.fetch.ui.PrintFilter;

import java.util.ArrayList;
import java.util.List;

/**
 * One film or show: its details and the buttons that add it. A film has one button; a show has
 * Download all and Choose episodes, which opens the episode picker. The quality chip cycles through
 * the server's profiles and is remembered.
 * Once the title is in the library, its download progress is shown and refreshed, and a second row
 * of red buttons deletes: a film's file, a show's episodes, or the whole title. Each asks first.
 * TMDB's tagline, director or creators, rating and cast arrive after the page opens; clicking an actor
 * searches for them.
 */
public class DetailActivity extends Activity {

    static final String EXTRA_ITEM = "item";
    static final String EXTRA_KEY = "key";
    static final String EXTRA_DOWNLOADED = "downloaded";
    static final String EXTRA_IN_LIBRARY = "inLibrary";
    static final String EXTRA_LIBRARY_CHANGED = "libraryChanged";
    /** Bytes the title takes on disk, when the opening screen knows; the delete questions say what is freed. */
    static final String EXTRA_SIZE = "size";
    // Renamed from "profile_" when "Up to 1080p" became the default, so choices saved before it are dropped once.
    private static final String PREF_PROFILE = "quality_";
    private static final float FANART_ALPHA = 0.55f;
    private static final long PROGRESS_REFRESH_MS = 10_000;
    private static final int REQUEST_EPISODES = 2;

    private Session session;
    private Item item;
    private LinearLayout actions, danger, castRow;
    private TextView tagline, credits;
    private View castTitle, castScroll;
    private long size;
    /** True once something of this title was deleted, for the screen that opened this one. */
    private boolean libraryChanged;
    private TextView quality, feedback, status;
    private final List<TextView> buttons = new ArrayList<>();
    private final java.util.Map<TextView, Integer> labels = new java.util.HashMap<>();
    private Profiles profiles;
    private Profile profile;
    private View progressRow;
    private ProgressBar progressBar;
    private TextView progressText;
    private boolean followingDownloads;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable refreshProgress = new Runnable() {
        @Override
        public void run() {
            Background.run(DetailActivity.this, session.client::downloads, DetailActivity.this::showProgress, error -> {
            });
            handler.postDelayed(this, PROGRESS_REFRESH_MS);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        session = Session.get(this);
        String json = getIntent().getStringExtra(EXTRA_ITEM);
        try {
            if (json == null) throw new FetchException(FetchException.Reason.NOT_FOUND, "no item");
            item = GatewayJson.item(json);
        } catch (FetchException e) {
            finish();
            return;
        }
        setContentView(R.layout.activity_detail);
        actions = findViewById(R.id.actions);
        danger = findViewById(R.id.danger);
        tagline = findViewById(R.id.tagline);
        credits = findViewById(R.id.credits);
        castTitle = findViewById(R.id.castTitle);
        castScroll = findViewById(R.id.castScroll);
        castRow = findViewById(R.id.castRow);
        size = getIntent().getLongExtra(EXTRA_SIZE, 0);
        quality = findViewById(R.id.quality);
        feedback = findViewById(R.id.feedback);
        status = findViewById(R.id.status);
        progressRow = findViewById(R.id.progressRow);
        progressBar = findViewById(R.id.progressBar);
        progressText = findViewById(R.id.progressText);
        bindDetails();
        loadDetails();
        if (item.inLibrary) showInLibrary(item, "");
        else showAddButtons();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (followingDownloads) followDownloads();
    }

    @Override
    protected void onPause() {
        super.onPause();
        handler.removeCallbacks(refreshProgress);
    }

    private void bindDetails() {
        ((TextView) findViewById(R.id.title)).setText(item.title);
        ((TextView) findViewById(R.id.details)).setText(Labels.details(item));
        ((TextView) findViewById(R.id.overview)).setText(item.overview);
        Cards.bindPoster(findViewById(android.R.id.content), item.title, item.poster);
        ImageView fanart = findViewById(R.id.fanart);
        fanart.setColorFilter(PrintFilter.agedPrint());
        Posters.load(fanart, item.fanart, getResources().getDisplayMetrics().widthPixels,
                () -> fanart.animate().alpha(FANART_ALPHA).setDuration(400).start());
    }

    // Purpose: TMDB's extras arrive after the page opens; without them the page is as before.
    private void loadDetails() {
        Background.run(this, () -> session.client.details(item.kind, item.id), this::showDetails, error -> {
        });
    }

    private void showDetails(TitleDetails details) {
        showIfAny(tagline, details.tagline);
        if (item.overview.isEmpty()) ((TextView) findViewById(R.id.overview)).setText(details.overview);
        showIfAny(credits, Labels.credits(details));
        if (details.cast.isEmpty()) return;
        LayoutInflater inflater = getLayoutInflater();
        for (CastMember member : details.cast) addCastCard(inflater, member);
        castTitle.setVisibility(View.VISIBLE);
        castScroll.setVisibility(View.VISIBLE);
    }

    private static void showIfAny(TextView view, String text) {
        view.setText(text);
        view.setVisibility(text.isEmpty() ? View.GONE : View.VISIBLE);
    }

    private void addCastCard(LayoutInflater inflater, CastMember member) {
        View card = inflater.inflate(R.layout.card_person, castRow, false);
        ((TextView) card.findViewById(R.id.name)).setText(member.name);
        ((TextView) card.findViewById(R.id.character)).setText(member.character);
        Cards.bindPoster(card, member.name, member.photo);
        card.setContentDescription(member.name);
        card.setOnClickListener(v -> startActivity(new Intent(this, MainActivity.class)
                .putExtra(MainActivity.EXTRA_SEARCH, member.name)));
        Cards.zoomOnFocus(card);
        castRow.addView(card);
    }

    // Purpose: the result of the episode picker: the show is in the library with the chosen episodes, or
    // the picked episodes were deleted.
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_EPISODES || resultCode != RESULT_OK || data == null) return;
        if (data.getBooleanExtra(EpisodesActivity.EXTRA_DELETED, false)) noteDeleted();
        try {
            item = GatewayJson.item(data.getStringExtra(EpisodesActivity.EXTRA_ITEM));
        } catch (FetchException | RuntimeException e) {
            return;
        }
        showInLibrary(item, data.getStringExtra(EpisodesActivity.EXTRA_MESSAGE));
    }

    private void showAddButtons() {
        if (item.kind == Item.Kind.FILM) {
            addButton(R.string.add_film, this::add);
        } else {
            addButton(R.string.download_all, this::add);
            addButton(R.string.choose_episodes, pressed -> openPicker(false));
        }
        buttons.get(0).requestFocus();
        quality.setOnClickListener(v -> nextProfile());
        Cards.zoomOnFocus(quality);
        loadProfiles();
    }

    private interface Press {
        void on(TextView button);
    }

    private TextView addButton(int label, Press press) {
        return addButton(actions, R.layout.button, label, press);
    }

    private TextView addDangerButton(int label, Press press) {
        return addButton(danger, R.layout.button_danger, label, press);
    }

    private TextView addButton(ViewGroup row, int layout, int label, Press press) {
        TextView button = (TextView) LayoutInflater.from(this).inflate(layout, row, false);
        button.setText(label);
        button.setOnClickListener(v -> press.on(button));
        Cards.zoomOnFocus(button);
        row.addView(button);
        buttons.add(button);
        labels.put(button, label);
        return button;
    }

    /** @param deleting pick downloaded episodes to delete, instead of episodes to download */
    private void openPicker(boolean deleting) {
        Intent intent = new Intent(this, EpisodesActivity.class)
                .putExtra(EpisodesActivity.EXTRA_ITEM, item.json)
                .putExtra(EpisodesActivity.EXTRA_PROFILE, profile != null ? profile.id : 0)
                .putExtra(EpisodesActivity.EXTRA_DELETING, deleting);
        startActivityForResult(intent, REQUEST_EPISODES);
    }

    private void loadProfiles() {
        Background.run(this, () -> GatewayJson.profiles(session.client.profiles(), item.kind), loaded -> {
            if (loaded.isEmpty()) {
                quality.setVisibility(View.GONE);
                return;
            }
            profiles = loaded;
            profile = loaded.pick(session.prefs.getInt(PREF_PROFILE + item.kind, 0));
            showProfile();
        }, error -> quality.setVisibility(View.GONE));
    }

    private void nextProfile() {
        if (profiles == null) return;
        profile = profiles.next(profile);
        session.prefs.edit().putInt(PREF_PROFILE + item.kind, profile.id).apply();
        showProfile();
    }

    private void showProfile() {
        quality.setText(getString(R.string.quality, profile.name));
    }

    // Purpose: add the film, or the whole show with every season.
    private void add(TextView pressed) {
        setButtonsEnabled(false);
        pressed.setText(R.string.adding);
        feedback.setVisibility(View.GONE);
        int profileId = profile != null ? profile.id : 0;
        Background.run(this, () -> item.kind == Item.Kind.FILM
                        ? session.client.addFilm(item.id, profileId)
                        : session.client.addShow(item.id, "all", profileId),
                added -> showInLibrary(added, getString(item.kind == Item.Kind.FILM ? R.string.added_film : R.string.added_show)),
                error -> showAddError(error));
    }

    private void showAddError(FetchException error) {
        if (error.reason == FetchException.Reason.ALREADY_ADDED) {
            showInLibrary(error.item != null ? error.item : item, getString(R.string.already_added));
            return;
        }
        if (error.reason == FetchException.Reason.NOT_PAIRED) {
            repair();
            return;
        }
        restoreButtonLabels();
        setButtonsEnabled(true);
        showFeedback(Errors.message(this, error), R.color.danger);
        buttons.get(0).requestFocus();
    }

    // Purpose: the title is in the library: say so (message "" for none), offer Done (and Choose episodes for
    // a show) and the delete buttons, and tell the results screen.
    private void showInLibrary(Item added, String message) {
        item = added;
        status.setText(Labels.libraryStatus(added));
        if (added.kind == Item.Kind.SHOW) loadEpisodeCounts();
        status.setVisibility(View.VISIBLE);
        removeButtons();
        quality.setVisibility(View.GONE);
        TextView done = addButton(R.string.done, pressed -> finish());
        if (item.kind == Item.Kind.SHOW) addButton(R.string.choose_episodes, pressed -> openPicker(false));
        addDangerButtons();
        done.requestFocus();
        if (message != null && !message.isEmpty()) showFeedback(message, R.color.text);
        followDownloads();
        reportResult();
    }

    private void addDangerButtons() {
        if (item.kind == Item.Kind.FILM) {
            if (item.downloaded) addDangerButton(R.string.delete_file, pressed -> confirmDeleteFile());
            addDangerButton(R.string.remove_film, pressed -> confirmRemove());
        } else {
            addDangerButton(R.string.delete_episodes, pressed -> openPicker(true));
            addDangerButton(R.string.remove_show, pressed -> confirmRemove());
        }
    }

    // Purpose: the title left the library: offer to add it again, as for any title not in the library.
    private void showRemoved(String message) {
        item = item.removed();
        followingDownloads = false;
        handler.removeCallbacks(refreshProgress);
        status.setVisibility(View.GONE);
        progressRow.setVisibility(View.GONE);
        removeButtons();
        quality.setVisibility(View.VISIBLE);
        showAddButtons();
        showFeedback(message, R.color.text);
        reportResult();
    }

    private void removeButtons() {
        actions.removeAllViews();
        danger.removeAllViews();
        buttons.clear();
        labels.clear();
    }

    private void reportResult() {
        setResult(RESULT_OK, new Intent()
                .putExtra(EXTRA_KEY, item.key())
                .putExtra(EXTRA_IN_LIBRARY, item.inLibrary)
                .putExtra(EXTRA_DOWNLOADED, item.downloaded)
                .putExtra(EXTRA_LIBRARY_CHANGED, libraryChanged));
    }

    private void confirmDeleteFile() {
        Confirm.ask(this, getString(R.string.confirm_delete_file, item.title),
                getString(R.string.confirm_delete_file_body, freedNote()), R.string.delete, () -> delete(true));
    }

    private void confirmRemove() {
        Confirm.ask(this, getString(R.string.confirm_remove, item.title),
                getString(R.string.confirm_remove_body, freedNote()), R.string.remove, () -> delete(false));
    }

    // Purpose: "This frees 37.4 GB. " when the size is known (opened from the Library tab), else nothing.
    private String freedNote() {
        return size > 0 ? getString(R.string.confirm_frees, Labels.size(size)) : "";
    }

    /** @param fileOnly delete only a film's file and keep the film; otherwise remove the title and its files */
    private void delete(boolean fileOnly) {
        setButtonsEnabled(false);
        feedback.setVisibility(View.GONE);
        Background.run(this, () -> session.client.deleteTitle(item.kind, item.id, fileOnly), freed -> {
            noteDeleted();
            if (fileOnly) showInLibrary(item.withoutFile(), getString(R.string.deleted_file, Labels.size(freed)));
            else showRemoved(getString(R.string.removed, Labels.size(freed)));
        }, this::showDeleteError);
    }

    private void noteDeleted() {
        libraryChanged = true;
        size = 0;
    }

    private void showDeleteError(FetchException error) {
        if (error.reason == FetchException.Reason.NOT_PAIRED) {
            repair();
            return;
        }
        setButtonsEnabled(true);
        showFeedback(Errors.message(this, error), R.color.danger);
    }

    private void repair() {
        session.forget();
        startActivity(new Intent(this, PairActivity.class));
        finishAffinity();
    }

    private void loadEpisodeCounts() {
        Background.run(this, () -> session.client.episodes(item.id), list -> {
            List<Episode> all = new ArrayList<>();
            for (Season season : list.seasons) all.addAll(season.episodes);
            status.setText(Labels.episodesStatus(all));
        }, error -> {
        });
    }

    private void followDownloads() {
        followingDownloads = true;
        handler.removeCallbacks(refreshProgress);
        handler.post(refreshProgress);
    }

    // Purpose: this title's part of the download queue, as a bar and one line (amber when a download needs
    // attention); hidden when nothing is queued.
    private void showProgress(List<Download> queue) {
        List<Download> mine = new ArrayList<>();
        for (Download download : queue) {
            if (download.key().equals(item.key())) mine.add(download);
        }
        progressRow.setVisibility(mine.isEmpty() ? View.GONE : View.VISIBLE);
        if (mine.isEmpty()) return;
        progressBar.setProgress((int) Math.round(Labels.averageProgress(mine) * 1000));
        progressText.setText(Labels.progressSummary(mine));
        progressText.setTextColor(getColor(Download.anyProblem(mine) ? R.color.warning : R.color.accent));
    }

    private void showFeedback(String text, int color) {
        feedback.setText(text);
        feedback.setTextColor(getColor(color));
        feedback.setVisibility(View.VISIBLE);
    }

    private void setButtonsEnabled(boolean enabled) {
        for (TextView button : buttons) button.setEnabled(enabled);
        quality.setEnabled(enabled);
    }

    private void restoreButtonLabels() {
        for (TextView button : buttons) button.setText(labels.get(button));
    }
}
