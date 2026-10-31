package com.androidtv.fetch.ui;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ImageHostsTest {

    @Test
    public void tmdbAndTvdbOverHttpsAreAllowed() {
        assertTrue(ImageHosts.isAllowed("https://image.tmdb.org/t/p/w342/x.jpg"));
        assertTrue(ImageHosts.isAllowed("https://artworks.thetvdb.com/banners/posters/81189-10.jpg"));
    }

    @Test
    public void everythingElseIsRefused() {
        String[] refused = {
            "http://image.tmdb.org/t/p/w342/x.jpg",
            "https://image.tmdb.org.evil.example/x.jpg",
            "https://user@image.tmdb.org/x.jpg",
            "https://image.tmdb.org:8443/x.jpg",
            "file:///data/data/com.androidtv.fetch/shared_prefs/fetch.xml",
            "javascript:alert(1)",
            "",
        };
        for (String url : refused) assertFalse(url, ImageHosts.isAllowed(url));
    }
}
