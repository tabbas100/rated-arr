package com.androidtv.fetch.watchnext;

import com.androidtv.fetch.Fixtures;
import com.androidtv.fetch.gateway.GatewayJson;
import com.androidtv.fetch.model.Watching;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class PlexLinkTest {

    private static final String SERVER = "0123456789abcdef0123456789abcdef01234567";
    private final Watching watching = GatewayJson.watching(Fixtures.json("watching.json"));

    @Test
    public void aFilmLinksToItsPageOnTheServer() {
        assertEquals("plex://libraries/" + SERVER + "/movie/x/1629", PlexLink.to(SERVER, watching.entries.get(0)));
    }

    @Test
    public void anEpisodeLinksThroughItsShowAndSeason() {
        assertEquals("plex://libraries/" + SERVER + "/show/x/1685/s/2/1686/e/2/1730",
                PlexLink.to(SERVER, watching.entries.get(1)));
    }

    @Test
    public void aBuiltLinkIsValid() {
        assertTrue(PlexLink.isValid(PlexLink.to(SERVER, watching.entries.get(1))));
    }

    @Test
    public void anEpisodeWithoutItsShowIsNotValid() {
        Watching.Entry orphan = new Watching.Entry(true, "1730", "", "", "Columbo", "", 2, 2, 1, 2, 3, "");
        assertFalse(PlexLink.isValid(PlexLink.to(SERVER, orphan)));
    }

    @Test
    public void extraPartsAreNotValid() {
        assertFalse(PlexLink.isValid("plex://libraries/" + SERVER + "/movie/x/1629?autoplay=1"));
    }

    @Test
    public void otherLinksAreNotValid() {
        assertFalse(PlexLink.isValid("https://watch.plex.tv/movie/hard-target"));
    }

    @Test
    public void noLinkIsNotValid() {
        assertFalse(PlexLink.isValid(null));
    }
}
