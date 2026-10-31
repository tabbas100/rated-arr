package com.androidtv.fetch.model;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Everything downloading for one title: a film's one download, or all of a show's episodes. */
public final class DownloadGroup {

    public final String key;
    public final Item.Kind kind;
    public final String title;
    public final String poster;
    public final List<Download> downloads = new ArrayList<>();

    private DownloadGroup(String key, Download first) {
        this.key = key;
        kind = first.kind;
        title = first.title;
        poster = first.poster;
    }

    /** The queue grouped by title, in the order each title first appears. */
    public static List<DownloadGroup> of(List<Download> queue) {
        Map<String, DownloadGroup> groups = new LinkedHashMap<>();
        for (Download download : queue) {
            String key = keyOf(download);
            DownloadGroup group = groups.get(key);
            if (group == null) {
                group = new DownloadGroup(key, download);
                groups.put(key, group);
            }
            group.downloads.add(download);
        }
        return new ArrayList<>(groups.values());
    }

    /** The title's key; a download the server could not tie to a title is grouped by its name instead. */
    public static String keyOf(Download download) {
        return download.id > 0 ? download.key() : download.key() + ":" + download.title;
    }
}
