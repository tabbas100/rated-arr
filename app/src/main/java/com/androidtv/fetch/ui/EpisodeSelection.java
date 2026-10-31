package com.androidtv.fetch.ui;

import com.androidtv.fetch.model.Episode;
import com.androidtv.fetch.model.Season;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Which episodes are picked, with the three ways to toggle them: everything, a whole season, or one
 * episode. For downloading it starts from what Sonarr already wants; for deleting only downloaded
 * episodes can be picked and nothing starts picked.
 */
public final class EpisodeSelection {

    public enum Mark { NONE, SOME, ALL }

    private final List<Season> seasons;
    private final boolean forDeleting;
    private final Set<Long> picked = new HashSet<>();
    /** What Sonarr wanted when the picker opened. */
    private final Set<Long> initial;

    public EpisodeSelection(List<Season> seasons) {
        this(seasons, false);
    }

    /** @param forDeleting only downloaded episodes can be picked, and none is picked at first */
    public EpisodeSelection(List<Season> seasons, boolean forDeleting) {
        this.seasons = seasons;
        this.forDeleting = forDeleting;
        for (Season season : seasons) {
            for (Episode episode : season.episodes) {
                if (!forDeleting && episode.wanted) picked.add(key(episode));
            }
        }
        initial = new HashSet<>(picked);
    }

    /** True when the episode can be toggled: any episode, or only downloaded ones when deleting. */
    public boolean isPickable(Episode episode) {
        return !forDeleting || episode.downloaded;
    }

    /** True when the season has an episode that can be toggled. */
    public boolean isPickable(Season season) {
        return !pickable(season.episodes).isEmpty();
    }

    /** The total size of the picked episodes' files. */
    public long pickedSize() {
        long total = 0;
        for (Episode episode : allEpisodes()) {
            if (isPicked(episode)) total += episode.size;
        }
        return total;
    }

    /** True once the picks differ from what Sonarr wanted when the picker opened. */
    public boolean isChanged() {
        return !picked.equals(initial);
    }

    public boolean isPicked(Episode episode) {
        return picked.contains(key(episode));
    }

    public void toggle(Episode episode) {
        if (!isPickable(episode)) return;
        if (!picked.remove(key(episode))) picked.add(key(episode));
    }

    public Mark mark(Season season) {
        return mark(pickable(season.episodes));
    }

    /** A season that is all picked becomes empty; otherwise all of it is picked. */
    public void toggle(Season season) {
        setPicked(pickable(season.episodes), mark(season) != Mark.ALL);
    }

    public Mark markAll() {
        return mark(pickable(allEpisodes()));
    }

    public void toggleAll() {
        setPicked(pickable(allEpisodes()), markAll() != Mark.ALL);
    }

    public int pickedCount() {
        return picked.size();
    }

    public int totalCount() {
        return pickable(allEpisodes()).size();
    }

    /** The picks as [season, episode] pairs, in order. */
    public List<int[]> picks() {
        List<int[]> out = new ArrayList<>();
        for (Episode episode : allEpisodes()) {
            if (isPicked(episode)) out.add(new int[]{episode.season, episode.number});
        }
        return out;
    }

    private Mark mark(List<Episode> episodes) {
        int count = 0;
        for (Episode episode : episodes) {
            if (isPicked(episode)) count++;
        }
        if (count == 0) return Mark.NONE;
        return count == episodes.size() ? Mark.ALL : Mark.SOME;
    }

    private void setPicked(List<Episode> episodes, boolean pick) {
        for (Episode episode : episodes) {
            if (pick) picked.add(key(episode));
            else picked.remove(key(episode));
        }
    }

    private List<Episode> pickable(List<Episode> episodes) {
        List<Episode> out = new ArrayList<>();
        for (Episode episode : episodes) {
            if (isPickable(episode)) out.add(episode);
        }
        return out;
    }

    private List<Episode> allEpisodes() {
        List<Episode> out = new ArrayList<>();
        for (Season season : seasons) out.addAll(season.episodes);
        return out;
    }

    private static long key(Episode episode) {
        return ((long) episode.season << 32) | episode.number;
    }
}
