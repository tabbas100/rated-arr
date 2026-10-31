package com.androidtv.fetch.ui;

import com.androidtv.fetch.Fixtures;
import com.androidtv.fetch.gateway.GatewayJson;
import com.androidtv.fetch.model.Choice;
import com.androidtv.fetch.model.Download;
import com.androidtv.fetch.model.Episode;
import com.androidtv.fetch.model.Item;
import com.androidtv.fetch.model.LibraryEntry;
import com.androidtv.fetch.model.Storage;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class LabelsTest {

    private static Item film(int year, int runtime, String genres, double rating) {
        return new Item(Item.Kind.FILM, 1, "Inception", year, "", "", "", runtime, genres, rating, "", 0, false, false, "{}");
    }

    private static Item show(String network, int seasons) {
        return new Item(Item.Kind.SHOW, 2, "Breaking Bad", 2008, "", "", "", 47, "Drama", 9.5, network, seasons,
                false, false, "{}");
    }

    private static Download download(Download.State state, double progress, String timeLeft) {
        return new Download(Item.Kind.FILM, 949, "Heat", "Bluray-1080p", progress, state, "", timeLeft, "");
    }

    @Test
    public void filmDetails() {
        assertEquals("2010 · 2h 28m · Action · ★ 8.8", Labels.details(film(2010, 148, "Action", 8.8)));
    }

    @Test
    public void showDetailsSkipRuntime() {
        assertEquals("2008 · AMC · 5 seasons · Drama · ★ 9.5", Labels.details(show("AMC", 5)));
    }

    @Test
    public void missingFieldsAreLeftOut() {
        assertEquals("", Labels.details(film(0, 0, "", 0)));
    }

    @Test
    public void oneSeasonIsSingular() {
        assertEquals("1 season", Labels.seasons(1));
    }

    @Test
    public void shortRuntimeInMinutes() {
        assertEquals("45m", Labels.runtime(45));
    }

    @Test
    public void downloadingShowsPercentAndTime() {
        assertEquals("Downloading · 75% · 12m left", Labels.downloadStatus(download(Download.State.DOWNLOADING, 0.75, "12m")));
    }

    @Test
    public void problemShowsTheServersReason() {
        Download stalled = new Download(Item.Kind.FILM, 1, "China Salesman", "", 0.97, Download.State.PROBLEM,
                "The download is stalled with no connections", "", "");
        assertEquals("The download is stalled with no connections", Labels.downloadStatus(stalled));
    }

    @Test
    public void problemNamesTheApp() {
        assertEquals("Needs attention in Radarr", Labels.downloadStatus(download(Download.State.PROBLEM, 0, "")));
    }

    private static Download episode(Download.State state, double progress) {
        return new Download(Item.Kind.SHOW, 371980, "Severance", "S02E01", progress, state, "", "", "");
    }

    @Test
    public void oneDownloadUsesItsOwnStatus() {
        assertEquals("Downloading · 50% · 3m left",
                Labels.progressSummary(java.util.Arrays.asList(download(Download.State.DOWNLOADING, 0.5, "3m"))));
    }

    @Test
    public void severalEpisodesShowCountAndAverage() {
        assertEquals("Downloading 2 episodes · 50%", Labels.progressSummary(java.util.Arrays.asList(
                episode(Download.State.DOWNLOADING, 0.25), episode(Download.State.QUEUED, 0.75))));
    }

    @Test
    public void aProblemEpisodeIsShownFirst() {
        assertEquals("Needs attention in Sonarr", Labels.progressSummary(java.util.Arrays.asList(
                episode(Download.State.DOWNLOADING, 0.25), episode(Download.State.PROBLEM, 0))));
    }

    @Test
    public void episodesNotStartedAreWaiting() {
        assertEquals("2 episodes waiting in the queue", Labels.progressSummary(java.util.Arrays.asList(
                episode(Download.State.QUEUED, 0), episode(Download.State.QUEUED, 0))));
    }

    @Test
    public void downloadKeyMatchesItsTitle() {
        assertEquals("FILM:949", download(Download.State.QUEUED, 0, "").key());
    }

    private static Choice choice(int chosen, int searching, int unmatched) {
        return new Choice(new Item(Item.Kind.SHOW, 1, "X", 0, "", "", "", 0, "", 0, "", 0, true, false, "{}"),
                chosen, searching, unmatched);
    }

    @Test
    public void choiceMessages() {
        assertEquals("Added. Sonarr is looking for 14 episodes now.", Labels.choiceMessage(choice(14, 14, 0)));
        assertEquals("Added. Sonarr is looking for 1 episode now.", Labels.choiceMessage(choice(1, 1, 0)));
        assertEquals("Saved. 3 episodes wanted; they download as they air.", Labels.choiceMessage(choice(3, 0, 0)));
        assertEquals("Saved. No episodes are wanted now.", Labels.choiceMessage(choice(0, 0, 0)));
        assertEquals("Added. Sonarr is looking for 2 episodes now. 1 episode didn’t match Sonarr’s list.",
                Labels.choiceMessage(choice(2, 2, 1)));
    }

    private static Episode episode(int season, boolean aired, boolean downloaded) {
        return new Episode(season, 1, "", "", aired, downloaded, false);
    }

    @Test
    public void showStatusCountsDownloadedOfAired() {
        assertEquals("In your library · 2 of 3 episodes", Labels.episodesStatus(java.util.Arrays.asList(
                episode(1, true, true), episode(1, true, true), episode(3, true, false), episode(9, false, false))));
    }

    @Test
    public void showWithNothingAiredSaysSo() {
        assertEquals("In your library · No episodes have aired yet",
                Labels.episodesStatus(java.util.Arrays.asList(episode(1, false, false))));
    }

    @Test
    public void filmStatus() {
        Item film = new Item(Item.Kind.FILM, 949, "Heat", 1995, "", "", "", 170, "", 8.3, "", 0, true, true, "{}");
        assertEquals("In your library · Ready to watch", Labels.libraryStatus(film));
    }

    @Test
    public void sizesUseDecimalUnitsLikeWhatbox() {
        assertEquals("37.4 GB", Labels.size(37_421_776_896L));
        assertEquals("850 MB", Labels.size(850_000_000L));
        assertEquals("3.9 TB", Labels.size(3_900_000_000_000L));
        assertEquals("2 KB", Labels.size(2_000L));
        assertEquals("0 B", Labels.size(0));
    }

    @Test
    public void storageLineMatchesTheWhatboxPage() {
        Storage whatbox = new Storage(1_778_710_340L * 1024, 3_808_593_752L * 1024, (3_808_593_752L - 1_778_710_340L) * 1024);
        assertEquals("1.82 TB of 3.9 TB used · 2.08 TB free", Labels.storage(whatbox));
    }

    @Test
    public void libraryLineFlagsDiscImages() {
        Item film = new Item(Item.Kind.FILM, 62, "2001", 1968, "", "", "", 0, "", 0, "", 0, true, true, "{}");
        assertEquals("37.4 GB · Disc image", Labels.libraryLine(new LibraryEntry(film, 37_421_776_896L, "BR-DISK", "discImage")));
        assertEquals("17.9 GB · Bluray-1080p", Labels.libraryLine(new LibraryEntry(film, 17_900_000_000L, "Bluray-1080p", "")));
    }

    @Test
    public void initials() {
        assertEquals("BB", Labels.initials("Breaking Bad"));
        assertEquals("T", Labels.initials("Tenet"));
        assertEquals("", Labels.initials("   "));
    }

    @Test
    public void filmCreditsNameTheDirectorAndTmdbRating() {
        assertEquals("Directed by John Gray · ★ 5.4 from 454 votes on TMDB",
                Labels.credits(GatewayJson.details(Fixtures.json("details-film.json"))));
    }

    @Test
    public void showCreditsWithoutCreatorsHaveTheRatingOnly() {
        assertEquals("★ 5.4 from 9 votes on TMDB", Labels.credits(GatewayJson.details(Fixtures.json("details-show.json"))));
    }
}
