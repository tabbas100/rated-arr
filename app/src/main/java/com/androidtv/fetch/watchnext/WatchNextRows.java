package com.androidtv.fetch.watchnext;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.media.tv.TvContract.WatchNextPrograms;
import android.media.tv.TvContract;

import com.androidtv.fetch.model.Watching;

import java.util.HashMap;
import java.util.Map;

/**
 * Fetch's rows in the TV's Watch Next list, where home screens such as Cosy find what to resume. They
 * mirror Plex's Continue Watching, because Plex itself only tells Google TV's own home screen.
 */
public final class WatchNextRows {

    private WatchNextRows() {
    }

    /** Makes Fetch's rows exactly these entries: known ones are updated, new ones added, gone ones removed. */
    static void replace(Context context, Watching watching) {
        ContentResolver resolver = context.getContentResolver();
        Map<String, Long> rows = rowsByKey(resolver);
        for (Watching.Entry entry : watching.entries) {
            String link = PlexLink.to(watching.server, entry);
            if (!PlexLink.isValid(link)) continue;
            ContentValues values = values(context, link, entry);
            Long row = rows.remove(entry.key);
            if (row == null) resolver.insert(WatchNextPrograms.CONTENT_URI, values);
            else resolver.update(TvContract.buildWatchNextProgramUri(row), values, null, null);
        }
        for (long gone : rows.values()) resolver.delete(TvContract.buildWatchNextProgramUri(gone), null, null);
    }

    /** Fetch's own rows; the TV shows an app only the rows it wrote. */
    private static Map<String, Long> rowsByKey(ContentResolver resolver) {
        Map<String, Long> rows = new HashMap<>();
        String[] columns = {WatchNextPrograms._ID, WatchNextPrograms.COLUMN_INTERNAL_PROVIDER_ID};
        try (Cursor c = resolver.query(WatchNextPrograms.CONTENT_URI, columns, null, null, null)) {
            while (c != null && c.moveToNext()) rows.put(c.isNull(1) ? "" : c.getString(1), c.getLong(0));
        }
        return rows;
    }

    private static ContentValues values(Context context, String link, Watching.Entry entry) {
        ContentValues values = new ContentValues();
        values.put(WatchNextPrograms.COLUMN_INTERNAL_PROVIDER_ID, entry.key);
        values.put(WatchNextPrograms.COLUMN_TYPE, entry.episode ? WatchNextPrograms.TYPE_TV_EPISODE : WatchNextPrograms.TYPE_MOVIE);
        values.put(WatchNextPrograms.COLUMN_WATCH_NEXT_TYPE,
                entry.started() ? WatchNextPrograms.WATCH_NEXT_TYPE_CONTINUE : WatchNextPrograms.WATCH_NEXT_TYPE_NEXT);
        values.put(WatchNextPrograms.COLUMN_TITLE, entry.title);
        if (entry.episode) {
            values.put(WatchNextPrograms.COLUMN_EPISODE_TITLE, entry.episodeTitle);
            values.put(WatchNextPrograms.COLUMN_SEASON_DISPLAY_NUMBER, String.valueOf(entry.season));
            values.put(WatchNextPrograms.COLUMN_EPISODE_DISPLAY_NUMBER, String.valueOf(entry.episodeNumber));
        }
        values.put(WatchNextPrograms.COLUMN_POSTER_ART_URI, entry.art);
        values.put(WatchNextPrograms.COLUMN_POSTER_ART_ASPECT_RATIO, WatchNextPrograms.ASPECT_RATIO_16_9);
        values.put(WatchNextPrograms.COLUMN_INTENT_URI, resumeIntent(context, link));
        values.put(WatchNextPrograms.COLUMN_LAST_PLAYBACK_POSITION_MILLIS, entry.positionMs);
        values.put(WatchNextPrograms.COLUMN_DURATION_MILLIS, entry.durationMs);
        values.put(WatchNextPrograms.COLUMN_LAST_ENGAGEMENT_TIME_UTC_MILLIS, entry.watchedAtMs);
        values.put(WatchNextPrograms.COLUMN_SEARCHABLE, 1);
        return values;
    }

    /** Opens Fetch's ResumeActivity, so a home screen can check that a row opens the app that wrote it. */
    private static String resumeIntent(Context context, String link) {
        return new Intent(context, ResumeActivity.class)
                .putExtra(ResumeActivity.EXTRA_LINK, link)
                .toUri(Intent.URI_INTENT_SCHEME);
    }
}
