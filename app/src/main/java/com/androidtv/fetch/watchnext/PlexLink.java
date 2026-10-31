package com.androidtv.fetch.watchnext;

import com.androidtv.fetch.model.Watching;
import java.util.regex.Pattern;

/**
 * Links that open a film's or an episode's page of the owner's Plex server in the Plex app, with Resume
 * focused. Plex ignores the name part of the path ("x"); the ids find the item.
 */
public final class PlexLink {

    static final String PLEX_PACKAGE = "com.plexapp.android";
    private static final Pattern LINK = Pattern.compile("plex://libraries/[0-9a-f]{40}/"
            + "(movie/x/[0-9]{1,12}|show/x/[0-9]{1,12}/s/[0-9]{1,4}/[0-9]{1,12}/e/[0-9]{1,5}/[0-9]{1,12})");

    private PlexLink() {
    }

    /** The link to this entry; check it with isValid, since the parts come from the gateway. */
    static String to(String server, Watching.Entry entry) {
        String library = "plex://libraries/" + server;
        if (!entry.episode) return library + "/movie/x/" + entry.key;
        return library + "/show/x/" + entry.showKey + "/s/" + entry.season + "/" + entry.seasonKey
                + "/e/" + entry.episodeNumber + "/" + entry.key;
    }

    /** True only for a film or episode link of this shape, so nothing else is ever handed to Plex. */
    static boolean isValid(String link) {
        return link != null && LINK.matcher(link).matches();
    }
}
