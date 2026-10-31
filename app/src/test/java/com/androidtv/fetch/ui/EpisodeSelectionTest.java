package com.androidtv.fetch.ui;

import com.androidtv.fetch.Fixtures;
import com.androidtv.fetch.gateway.GatewayJson;
import com.androidtv.fetch.model.Episode;
import com.androidtv.fetch.model.Season;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Before;
import org.junit.Test;

import java.util.List;

/** The picker's toggles on Breaking Bad as the gateway lists it with S01E01, S01E02 and S05E16 wanted. */
public class EpisodeSelectionTest {

    private List<Season> seasons;
    private EpisodeSelection selection;

    @Before
    public void load() {
        seasons = GatewayJson.episodes(Fixtures.json("episodes-library.json")).seasons;
        selection = new EpisodeSelection(seasons);
    }

    private Season season(int number) {
        return seasons.stream().filter(s -> s.number == number).findFirst().orElseThrow(AssertionError::new);
    }

    @Test
    public void startsFromWhatSonarrWants() {
        assertEquals(3, selection.pickedCount());
    }

    @Test
    public void partlyPickedSeasonIsSome() {
        assertEquals(EpisodeSelection.Mark.SOME, selection.mark(season(1)));
    }

    @Test
    public void togglingAPartSeasonPicksAllOfIt() {
        selection.toggle(season(1));
        assertEquals(EpisodeSelection.Mark.ALL, selection.mark(season(1)));
    }

    @Test
    public void togglingAFullSeasonClearsIt() {
        selection.toggle(season(2));
        selection.toggle(season(2));
        assertEquals(EpisodeSelection.Mark.NONE, selection.mark(season(2)));
    }

    @Test
    public void toggleAllPicksEverythingThenNothing() {
        selection.toggleAll();
        assertEquals(selection.totalCount(), selection.pickedCount());
        selection.toggleAll();
        assertEquals(0, selection.pickedCount());
    }

    @Test
    public void singleEpisodeToggles() {
        Episode pilot = season(1).episodes.get(0);
        selection.toggle(pilot);
        assertFalse(selection.isPicked(pilot));
        selection.toggle(pilot);
        assertTrue(selection.isPicked(pilot));
    }

    @Test
    public void picksAreSeasonEpisodePairs() {
        List<int[]> picks = selection.picks();
        assertEquals("1x1 1x2 5x16", picks.stream().map(p -> p[0] + "x" + p[1])
                .reduce((a, b) -> a + " " + b).orElse(""));
    }

    @Test
    public void unchangedUntilAPickChanges() {
        assertFalse(selection.isChanged());
        selection.toggle(season(2));
        assertTrue(selection.isChanged());
    }

    @Test
    public void togglingBackIsUnchangedAgain() {
        Episode pilot = season(1).episodes.get(0);
        selection.toggle(pilot);
        selection.toggle(pilot);
        assertFalse(selection.isChanged());
    }

    private static List<Season> downloadedPilotOnly() {
        return java.util.Arrays.asList(new Season(1, java.util.Arrays.asList(
                new Episode(1, 1, "Pilot", "", true, true, true, 1_000_000_000L),
                new Episode(1, 2, "Cat's in the Bag", "", true, false, true, 0))));
    }

    @Test
    public void deletingStartsWithNothingPicked() {
        assertEquals(0, new EpisodeSelection(downloadedPilotOnly(), true).pickedCount());
    }

    @Test
    public void deletingOnlyPicksDownloadedEpisodes() {
        EpisodeSelection deleting = new EpisodeSelection(downloadedPilotOnly(), true);
        deleting.toggleAll();
        assertEquals("1 of 1, 1000000000 bytes", deleting.pickedCount() + " of " + deleting.totalCount() + ", "
                + deleting.pickedSize() + " bytes");
    }

    @Test
    public void deletingIgnoresEpisodesWithoutAFile() {
        List<Season> seasons = downloadedPilotOnly();
        EpisodeSelection deleting = new EpisodeSelection(seasons, true);
        deleting.toggle(seasons.get(0).episodes.get(1));
        assertEquals(0, deleting.pickedCount());
    }

    @Test
    public void aSeasonWithItsOnlyDownloadIsFullyPicked() {
        List<Season> seasons = downloadedPilotOnly();
        EpisodeSelection deleting = new EpisodeSelection(seasons, true);
        deleting.toggle(seasons.get(0));
        assertEquals(EpisodeSelection.Mark.ALL, deleting.mark(seasons.get(0)));
    }

    @Test
    public void aSeasonWithoutDownloadsCannotBePickedForDeleting() {
        List<Season> seasons = java.util.Arrays.asList(new Season(2, java.util.Arrays.asList(
                new Episode(2, 1, "Seven Thirty-Seven", "", true, false, true, 0))));
        assertFalse(new EpisodeSelection(seasons, true).isPickable(seasons.get(0)));
    }

    @Test
    public void aSeasonWithADownloadCanBePickedForDeleting() {
        List<Season> seasons = downloadedPilotOnly();
        assertTrue(new EpisodeSelection(seasons, true).isPickable(seasons.get(0)));
    }

    @Test
    public void specialsAreTheirOwnSeasonAndLast() {
        assertEquals(0, seasons.get(seasons.size() - 1).number);
    }
}
