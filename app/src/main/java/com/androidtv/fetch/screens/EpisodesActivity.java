package com.androidtv.fetch.screens;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.androidtv.fetch.R;
import com.androidtv.fetch.gateway.FetchException;
import com.androidtv.fetch.gateway.GatewayJson;
import com.androidtv.fetch.gateway.Session;
import com.androidtv.fetch.model.Episode;
import com.androidtv.fetch.model.EpisodeList;
import com.androidtv.fetch.model.Have;
import com.androidtv.fetch.model.Item;
import com.androidtv.fetch.model.Season;
import com.androidtv.fetch.ui.Background;
import com.androidtv.fetch.ui.Cards;
import com.androidtv.fetch.ui.Confirm;
import com.androidtv.fetch.ui.EpisodeSelection;
import com.androidtv.fetch.ui.Errors;
import com.androidtv.fetch.ui.Labels;

import java.util.HashMap;
import java.util.Map;

/**
 * Picks what of a show to download: everything, whole seasons or single episodes. Seasons are on
 * the left; focusing one lists its episodes on the right. OK toggles the focused row. The bottom bar
 * counts the picks, and Download makes exactly those episodes wanted in Sonarr. Focus moves by rule,
 * not by geometry: Right from a season goes to its first episode, Left from an episode back to its
 * season, and Down from the last row of either column to Download.
 * In delete mode only downloaded episodes can be picked, nothing starts picked, and the button
 * deletes the picked episodes' files after asking.
 */
public class EpisodesActivity extends Activity {

    static final String EXTRA_ITEM = "item";
    static final String EXTRA_PROFILE = "profile";
    static final String EXTRA_MESSAGE = "message";
    static final String EXTRA_DELETING = "deleting";
    /** In the result: true when episode files were deleted. */
    static final String EXTRA_DELETED = "deleted";
    private static final float NOT_PICKABLE_ALPHA = 0.45f;

    private Session session;
    private Item item;
    private int profileId;
    private boolean deleting;
    private EpisodeList list;
    private EpisodeSelection selection;
    private LinearLayout seasonsColumn, episodesColumn;
    private TextView summary, download;
    private View loading;
    private View allRow;
    private Season shown;
    private final Map<Season, View> seasonRows = new HashMap<>();
    private final Map<View, Episode> episodeRows = new HashMap<>();

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
        profileId = getIntent().getIntExtra(EXTRA_PROFILE, 0);
        deleting = getIntent().getBooleanExtra(EXTRA_DELETING, false);
        setContentView(R.layout.activity_episodes);
        ((TextView) findViewById(R.id.title)).setText(deleting ? getString(R.string.pick_delete_title, item.title) : item.title);
        if (deleting) ((TextView) findViewById(R.id.subtitle)).setText(R.string.pick_delete_subtitle);
        seasonsColumn = findViewById(R.id.seasons);
        episodesColumn = findViewById(R.id.episodes);
        summary = findViewById(R.id.summary);
        download = findViewById(R.id.download);
        loading = findViewById(R.id.loading);
        if (deleting) {
            download.setOnClickListener(v -> confirmDelete());
            download.setTextColor(getColorStateList(R.color.danger_text));
        } else {
            download.setOnClickListener(v -> download());
        }
        Cards.zoomOnFocus(download);
        load();
    }

    private void load() {
        loading.setVisibility(View.VISIBLE);
        Background.run(this, () -> session.client.episodes(item.id), this::show, this::showLoadError);
    }

    private void show(EpisodeList loaded) {
        loading.setVisibility(View.GONE);
        if (loaded.seasons.isEmpty()) {
            summary.setText(R.string.pick_no_episodes);
            return;
        }
        list = loaded;
        selection = new EpisodeSelection(loaded.seasons, deleting);
        LayoutInflater inflater = getLayoutInflater();
        allRow = row(inflater, seasonsColumn, getString(R.string.pick_all), seasonNote(allEpisodes(loaded)));
        showHave(allRow, Have.of(allEpisodes(loaded)));
        allRow.setOnClickListener(v -> {
            selection.toggleAll();
            refreshMarks();
        });
        for (Season season : loaded.seasons) addSeasonRow(inflater, season);
        seasonRows.get(loaded.seasons.get(loaded.seasons.size() - 1)).setNextFocusDownId(download.getId());
        showSeason(loaded.seasons.get(0));
        refreshMarks();
        seasonRows.get(loaded.seasons.get(0)).requestFocus();
    }

    private void addSeasonRow(LayoutInflater inflater, Season season) {
        String label = season.number == 0 ? getString(R.string.pick_specials) : getString(R.string.pick_season, season.number);
        View row = row(inflater, seasonsColumn, label, seasonNote(season.episodes));
        showHave(row, Have.of(season.episodes));
        row.setId(View.generateViewId());
        row.setOnClickListener(v -> {
            selection.toggle(season);
            refreshMarks();
        });
        row.setOnFocusChangeListener((v, focused) -> {
            zoom(v, focused);
            if (focused) showSeason(season);
        });
        seasonRows.put(season, row);
    }

    // Purpose: list one season's episodes on the right, once per change of season.
    private void showSeason(Season season) {
        if (season == shown) return;
        shown = season;
        episodesColumn.removeAllViews();
        episodeRows.clear();
        LayoutInflater inflater = getLayoutInflater();
        View seasonRow = seasonRows.get(season);
        View last = null;
        for (Episode episode : season.episodes) {
            View row = row(inflater, episodesColumn, episodeLabel(episode), episodeNote(episode));
            showHave(row, episodeHave(episode));
            row.setId(View.generateViewId());
            row.setNextFocusLeftId(seasonRow.getId());
            row.setOnClickListener(v -> {
                selection.toggle(episode);
                refreshMarks();
            });
            episodeRows.put(row, episode);
            last = row;
        }
        if (last != null) last.setNextFocusDownId(download.getId());
        routeSeasonsTo(episodesColumn.getChildAt(0));
        refreshMarks();
    }

    // Purpose: Right from any season row (and All episodes) goes to the first episode on show.
    private void routeSeasonsTo(View firstEpisode) {
        if (firstEpisode == null) return;
        allRow.setNextFocusRightId(firstEpisode.getId());
        for (View row : seasonRows.values()) row.setNextFocusRightId(firstEpisode.getId());
    }

    private View row(LayoutInflater inflater, ViewGroup parent, String label, String note) {
        View row = inflater.inflate(R.layout.row_pick, parent, false);
        ((TextView) row.findViewById(R.id.label)).setText(label);
        ((TextView) row.findViewById(R.id.note)).setText(note);
        row.setOnFocusChangeListener((v, focused) -> zoom(v, focused));
        parent.addView(row);
        return row;
    }

    private static void zoom(View view, boolean focused) {
        float scale = focused ? Cards.WIDE_FOCUSED_SCALE : 1f;
        view.animate().scaleX(scale).scaleY(scale).setDuration(120).start();
    }

    private String episodeLabel(Episode episode) {
        String title = episode.title.isEmpty() ? getString(R.string.pick_episode_untitled, episode.number) : episode.title;
        return getString(R.string.pick_episode, episode.number, title);
    }

    private String episodeNote(Episode episode) {
        if (episode.downloaded) return deleting ? Labels.size(episode.size) : "";
        if (!episode.aired && episode.airDate.isEmpty()) return getString(R.string.pick_not_aired);
        return episode.airDate;
    }

    // Purpose: a season's note: downloaded of aired ("8/9") for a show in the library, else its size; when
    // deleting, also the space its files take.
    private String seasonNote(java.util.List<Episode> episodes) {
        long size = sizeOf(episodes);
        if (deleting && size > 0) return getString(R.string.pick_season_files, Have.count(episodes), Labels.size(size));
        return list.inLibrary ? Have.count(episodes) : String.valueOf(episodes.size());
    }

    private static long sizeOf(java.util.List<Episode> episodes) {
        long total = 0;
        for (Episode episode : episodes) total += episode.size;
        return total;
    }

    // Purpose: green when downloaded, red when aired and missing; nothing for unaired episodes or new shows.
    private Have episodeHave(Episode episode) {
        if (episode.downloaded) return Have.ALL;
        return episode.aired ? Have.NONE : Have.NOTHING_AIRED;
    }

    private void showHave(View row, Have have) {
        ImageView icon = row.findViewById(R.id.have);
        if (!list.inLibrary || have == Have.NOTHING_AIRED) {
            icon.setVisibility(View.GONE);
            return;
        }
        icon.setImageResource(have == Have.ALL ? R.drawable.ic_have_all
                : have == Have.SOME ? R.drawable.ic_have_some : R.drawable.ic_have_none);
        icon.setVisibility(View.VISIBLE);
    }

    private static java.util.List<Episode> allEpisodes(EpisodeList loaded) {
        java.util.List<Episode> all = new java.util.ArrayList<>();
        for (Season season : loaded.seasons) all.addAll(season.episodes);
        return all;
    }

    // Purpose: every check mark, the count and the button follow the selection. Rows that cannot be
    // picked (not downloaded, when deleting) are faded and have no check box.
    private void refreshMarks() {
        if (selection == null) return;
        setMark(allRow, selection.markAll());
        for (Map.Entry<Season, View> entry : seasonRows.entrySet()) {
            setMark(entry.getValue(), selection.mark(entry.getKey()));
            showPickable(entry.getValue(), selection.isPickable(entry.getKey()));
        }
        for (Map.Entry<View, Episode> entry : episodeRows.entrySet()) {
            setMark(entry.getKey(), selection.isPicked(entry.getValue()) ? EpisodeSelection.Mark.ALL : EpisodeSelection.Mark.NONE);
            showPickable(entry.getKey(), selection.isPickable(entry.getValue()));
        }
        if (deleting) showDeleteSummary();
        else showDownloadSummary();
    }

    private void showDownloadSummary() {
        int picked = selection.pickedCount();
        int total = selection.totalCount();
        summary.setText(getResources().getQuantityString(R.plurals.pick_summary, total, picked, total));
        download.setText(downloadLabel(picked));
        // A show in the library is only saved when something changed, so Save never rewrites it by accident.
        download.setEnabled(list.inLibrary ? selection.isChanged() : picked > 0);
    }

    private void showDeleteSummary() {
        int picked = selection.pickedCount();
        summary.setText(getResources().getQuantityString(R.plurals.pick_delete_summary, picked, picked,
                Labels.size(selection.pickedSize())));
        download.setText(picked == 0 ? getString(R.string.pick_delete_none)
                : getResources().getQuantityString(R.plurals.pick_delete, picked, picked));
        download.setEnabled(picked > 0);
    }

    private static void showPickable(View row, boolean pickable) {
        row.setAlpha(pickable ? 1f : NOT_PICKABLE_ALPHA);
        row.findViewById(R.id.check).setVisibility(pickable ? View.VISIBLE : View.INVISIBLE);
    }

    private String downloadLabel(int picked) {
        if (list.inLibrary && !selection.isChanged()) return getString(R.string.pick_no_changes);
        if (list.inLibrary) return getResources().getQuantityString(R.plurals.pick_save, picked, picked);
        if (picked == 0) return getString(R.string.pick_download_none);
        return getResources().getQuantityString(R.plurals.pick_download, picked, picked);
    }

    private static void setMark(View row, EpisodeSelection.Mark mark) {
        ImageView check = row.findViewById(R.id.check);
        check.setImageResource(mark == EpisodeSelection.Mark.ALL ? R.drawable.ic_pick_all
                : mark == EpisodeSelection.Mark.SOME ? R.drawable.ic_pick_some : R.drawable.ic_pick_none);
    }

    private void download() {
        download.setEnabled(false);
        download.setText(R.string.adding);
        Background.run(this, () -> session.client.chooseEpisodes(item.id, selection.picks(), profileId), choice -> {
            setResult(RESULT_OK, new Intent()
                    .putExtra(EXTRA_ITEM, choice.item.json)
                    .putExtra(EXTRA_MESSAGE, Labels.choiceMessage(choice)));
            finish();
        }, this::showSaveError);
    }

    private void confirmDelete() {
        int picked = selection.pickedCount();
        String episodes = getResources().getQuantityString(R.plurals.episodes_count, picked, picked);
        Confirm.ask(this, getString(R.string.confirm_delete_episodes, episodes),
                getString(R.string.confirm_delete_episodes_body, Labels.size(selection.pickedSize())), R.string.delete,
                this::deletePicked);
    }

    private void deletePicked() {
        download.setEnabled(false);
        download.setText(R.string.deleting);
        Background.run(this, () -> session.client.deleteEpisodes(item.id, selection.picks()), freed -> {
            setResult(RESULT_OK, new Intent()
                    .putExtra(EXTRA_ITEM, item.json)
                    .putExtra(EXTRA_DELETED, true)
                    .putExtra(EXTRA_MESSAGE, getString(R.string.deleted_episodes, Labels.size(freed))));
            finish();
        }, this::showSaveError);
    }

    private void showLoadError(FetchException error) {
        loading.setVisibility(View.GONE);
        if (error.reason == FetchException.Reason.NOT_PAIRED) {
            repair();
            return;
        }
        summary.setText(Errors.message(this, error));
        summary.setTextColor(getColor(R.color.danger));
    }

    private void showSaveError(FetchException error) {
        if (error.reason == FetchException.Reason.NOT_PAIRED) {
            repair();
            return;
        }
        summary.setText(Errors.message(this, error));
        summary.setTextColor(getColor(R.color.danger));
        refreshMarks();
        download.requestFocus();
    }

    private void repair() {
        session.forget();
        startActivity(new Intent(this, PairActivity.class));
        finishAffinity();
    }
}
