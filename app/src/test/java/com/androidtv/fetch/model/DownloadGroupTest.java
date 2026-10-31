package com.androidtv.fetch.model;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class DownloadGroupTest {

    private static Download episode(int showId, String show, String code) {
        return new Download(Item.Kind.SHOW, showId, show, code, 0.5, Download.State.DOWNLOADING, "", "", "");
    }

    private static Download film(int id, String title) {
        return new Download(Item.Kind.FILM, id, title, "Bluray-1080p", 0.2, Download.State.DOWNLOADING, "", "", "");
    }

    private final List<DownloadGroup> groups = DownloadGroup.of(Arrays.asList(
            episode(75897, "South Park", "S10E09"), film(949, "Heat"), episode(75897, "South Park", "S10E10"),
            episode(371980, "Severance", "S02E01")));

    @Test
    public void oneGroupPerTitleInQueueOrder() {
        assertEquals("South Park|Heat|Severance", groups.stream().map(g -> g.title).collect(Collectors.joining("|")));
    }

    @Test
    public void episodesOfAShowShareTheirGroup() {
        assertEquals(2, groups.get(0).downloads.size());
    }

    @Test
    public void groupKeyMatchesTheTitle() {
        assertEquals("SHOW:75897", groups.get(0).key);
    }

    @Test
    public void downloadsWithoutATitleIdGroupByName() {
        List<DownloadGroup> unknown = DownloadGroup.of(Arrays.asList(episode(0, "Mystery", "S01E01"),
                episode(0, "Other", "S01E01")));
        assertEquals(2, unknown.size());
    }
}
