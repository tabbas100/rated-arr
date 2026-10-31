package com.androidtv.fetch.gateway;

import com.androidtv.fetch.Fixtures;
import com.androidtv.fetch.model.Watching;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class WatchingJsonTest {

    private final Watching watching = GatewayJson.watching(Fixtures.json("watching.json"));

    @Test
    public void aFilmKeepsWhereItStopped() {
        Watching.Entry film = watching.entries.get(0);
        assertEquals("1629 Hard Target 2575843/5979008", film.key + " " + film.title + " " + film.positionMs + "/" + film.durationMs);
    }

    @Test
    public void anEpisodeKeepsItsShowAndNumbers() {
        Watching.Entry episode = watching.entries.get(1);
        assertEquals("Columbo S2 E2 The Greenhouse Jungle",
                episode.title + " S" + episode.season + " E" + episode.episodeNumber + " " + episode.episodeTitle);
    }

    @Test
    public void theWatchTimeIsInMilliseconds() {
        assertEquals(1793132410000L, watching.entries.get(0).watchedAtMs);
    }

    @Test
    public void theNextEpisodeIsNotStarted() {
        assertFalse(watching.entries.get(2).started());
    }

    @Test
    public void aHalfWatchedFilmIsStarted() {
        assertTrue(watching.entries.get(0).started());
    }

    @Test
    public void entriesWithoutAKeyAreSkipped() {
        assertEquals(3, watching.entries.size());
    }

    @Test
    public void theServerComesAlong() {
        assertEquals("0123456789abcdef0123456789abcdef01234567", watching.server);
    }
}
