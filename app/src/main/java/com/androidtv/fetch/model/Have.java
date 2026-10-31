package com.androidtv.fetch.model;

import java.util.List;

/** How much of a season (or a whole show) is downloaded, counting only episodes that have aired. */
public enum Have {
    ALL, SOME, NONE,
    /** Nothing has aired yet: there is nothing to have. */
    NOTHING_AIRED;

    public static Have of(List<Episode> episodes) {
        int aired = aired(episodes), downloaded = downloaded(episodes);
        if (aired == 0) return NOTHING_AIRED;
        if (downloaded == aired) return ALL;
        return downloaded == 0 ? NONE : SOME;
    }

    /** "8/9": downloaded of aired. */
    public static String count(List<Episode> episodes) {
        return downloaded(episodes) + "/" + aired(episodes);
    }

    public static int aired(List<Episode> episodes) {
        int count = 0;
        for (Episode episode : episodes) {
            if (episode.aired) count++;
        }
        return count;
    }

    /** Downloaded episodes that have aired, so the count never exceeds aired(). */
    public static int downloaded(List<Episode> episodes) {
        int count = 0;
        for (Episode episode : episodes) {
            if (episode.aired && episode.downloaded) count++;
        }
        return count;
    }
}
