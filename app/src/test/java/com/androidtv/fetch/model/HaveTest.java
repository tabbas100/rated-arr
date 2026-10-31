package com.androidtv.fetch.model;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

import java.util.Arrays;
import java.util.List;

public class HaveTest {

    private static Episode episode(boolean aired, boolean downloaded) {
        return new Episode(1, 1, "", "", aired, downloaded, false);
    }

    private static List<Episode> season(Episode... episodes) {
        return Arrays.asList(episodes);
    }

    @Test
    public void everyAiredEpisodeDownloadedIsAll() {
        assertEquals(Have.ALL, Have.of(season(episode(true, true), episode(true, true), episode(false, false))));
    }

    @Test
    public void someDownloadedIsSome() {
        assertEquals(Have.SOME, Have.of(season(episode(true, true), episode(true, false))));
    }

    @Test
    public void noneDownloadedIsNone() {
        assertEquals(Have.NONE, Have.of(season(episode(true, false), episode(true, false))));
    }

    @Test
    public void unairedSeasonHasNothingToHave() {
        assertEquals(Have.NOTHING_AIRED, Have.of(season(episode(false, false))));
    }

    @Test
    public void countIsDownloadedOfAired() {
        assertEquals("1/2", Have.count(season(episode(true, true), episode(true, false), episode(false, false))));
    }
}
