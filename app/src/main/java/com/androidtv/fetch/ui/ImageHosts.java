package com.androidtv.fetch.ui;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/** The only places the app loads images from: TMDB and TVDB, over https. */
public final class ImageHosts {

    static final Set<String> ALLOWED =
            Collections.unmodifiableSet(new HashSet<>(Arrays.asList("image.tmdb.org", "artworks.thetvdb.com")));

    private ImageHosts() {
    }

    static boolean isAllowed(String url) {
        try {
            URL parsed = new URL(url);
            return "https".equals(parsed.getProtocol()) && ALLOWED.contains(parsed.getHost())
                    && parsed.getUserInfo() == null && (parsed.getPort() == -1 || parsed.getPort() == 443);
        } catch (MalformedURLException e) {
            return false;
        }
    }
}
