package com.androidtv.fetch.gateway;

import com.androidtv.fetch.model.Genre;
import com.androidtv.fetch.model.Pairing;
import com.androidtv.fetch.model.Profiles;

import com.androidtv.fetch.Fixtures;
import com.androidtv.fetch.model.CastMember;
import com.androidtv.fetch.model.Choice;
import com.androidtv.fetch.model.Download;
import com.androidtv.fetch.model.EpisodeList;
import com.androidtv.fetch.model.Item;
import com.androidtv.fetch.model.Library;
import com.androidtv.fetch.model.PersonCredits;
import com.androidtv.fetch.model.SearchResults;
import com.androidtv.fetch.model.Shelf;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import org.json.JSONObject;
import java.util.List;
import org.junit.Test;

public class GatewayJsonTest {

    @Test
    public void searchReadsFilmsAndShows() throws Exception {
        SearchResults results = GatewayJson.search(Fixtures.json("search.json"));
        assertTrue(results.films.stream().anyMatch(i -> i.title.startsWith("El Camino")));
        assertTrue(results.shows.stream().anyMatch(i -> i.id == 81189 && i.kind == Item.Kind.SHOW));
    }

    @Test
    public void showFieldsComeThrough() throws Exception {
        Item show = GatewayJson.search(Fixtures.json("search.json")).shows.stream()
                .filter(i -> i.id == 81189).findFirst().orElseThrow(AssertionError::new);
        assertEquals("Breaking Bad|2008|AMC|5", show.title + "|" + show.year + "|" + show.network + "|" + show.seasons);
    }

    @Test
    public void itemKeepsItsJsonForTheNextScreen() throws Exception {
        Item film = GatewayJson.search(Fixtures.json("search.json")).films.get(0);
        assertEquals(film.key(), GatewayJson.item(film.json).key());
    }

    @Test
    public void addedFilmIsInLibrary() throws Exception {
        assertTrue(GatewayJson.item(Fixtures.json("add-film.json").getJSONObject("item")).inLibrary);
    }

    @Test
    public void aSearchNamingAnActorListsThem() {
        PersonCredits person = GatewayJson.search(Fixtures.json("search-person.json")).people.get(0);
        assertEquals("Steven Seagal, acting", person.name + (person.directing ? ", directing" : ", acting"));
    }

    @Test
    public void anActorsShowsIncludeTheirReality() {
        PersonCredits person = GatewayJson.search(Fixtures.json("search-person.json")).people.get(0);
        assertTrue(person.shows.stream().anyMatch(show -> show.id == 126841));
    }

    @Test
    public void aSurnameSearchPutsThePersonFirst() {
        assertTrue(GatewayJson.search(Fixtures.json("search-person.json")).people.get(0).named);
    }

    @Test
    public void aSearchWithOnlyAPersonIsNotEmpty() {
        assertFalse(GatewayJson.search(Fixtures.json("search-person.json")).isEmpty());
    }

    @Test
    public void aTypoIsSearchedAsTheClosestTitle() {
        SearchResults results = GatewayJson.search(Fixtures.json("search-typo.json"));
        assertEquals("The Glimmer Man: The Glimmer Man", results.suggestion + ": " + results.films.get(0).title);
    }

    @Test
    public void aSearchThatMatchedHasNoSuggestion() {
        assertEquals("", GatewayJson.search(Fixtures.json("search-person.json")).suggestion);
    }

    @Test
    public void filmDetailsCarryTheCastWithTheirParts() {
        CastMember lead = GatewayJson.details(Fixtures.json("details-film.json")).cast.get(0);
        assertEquals("Steven Seagal as Jack Cole", lead.name + " as " + lead.character);
    }

    @Test
    public void castPhotosComeFromTmdb() {
        CastMember lead = GatewayJson.details(Fixtures.json("details-film.json")).cast.get(0);
        assertTrue(lead.photo.startsWith("https://image.tmdb.org/t/p/w185/"));
    }

    @Test
    public void filmGenresStartWithSoBadItsGood() {
        Genre first = GatewayJson.genres(Fixtures.json("genres.json")).films.get(0);
        assertEquals("bad: So bad it's good", first.id + ": " + first.name);
    }

    @Test
    public void showsHaveTheirOwnGenres() {
        assertFalse(GatewayJson.genres(Fixtures.json("genres.json")).shows.stream().anyMatch(g -> g.id.equals("bad")));
    }

    @Test
    public void soBadItsGoodHasItsThreeRows() {
        List<Shelf> rows = GatewayJson.shelves(Fixtures.json("browse-bad.json"));
        assertEquals("soBad bMovies flops", rows.stream().map(r -> r.id).collect(java.util.stream.Collectors.joining(" ")));
    }

    @Test
    public void anOlderReplyWithoutPeopleHasNone() {
        assertTrue(GatewayJson.search(Fixtures.json("search.json")).people.isEmpty());
    }

    @Test
    public void aFilmWithoutItsFileStaysInTheLibrary() throws Exception {
        Item film = GatewayJson.item(Fixtures.json("add-film.json").getJSONObject("item")).withoutFile();
        assertEquals("in library, not downloaded", (film.inLibrary ? "in library" : "gone") + ", "
                + (film.downloaded ? "downloaded" : "not downloaded"));
    }

    @Test
    public void aRemovedTitleIsOutOfTheLibrary() throws Exception {
        assertFalse(GatewayJson.item(Fixtures.json("add-film.json").getJSONObject("item")).removed().inLibrary);
    }

    @Test
    public void profilesFallBackToTheServersDefault() throws Exception {
        Profiles profiles = GatewayJson.profiles(Fixtures.json("profiles.json"), Item.Kind.FILM);
        assertEquals(profiles.defaultId, profiles.pick(0).id);
    }

    @Test
    public void profilesKeepARememberedChoice() throws Exception {
        Profiles profiles = GatewayJson.profiles(Fixtures.json("profiles.json"), Item.Kind.FILM);
        assertEquals("HD-1080p", profiles.pick(4).name);
    }

    @Test
    public void pairingStartAndTokens() throws Exception {
        Pairing pairing = GatewayJson.pairing(Fixtures.json("pair-start.json"));
        assertEquals("PAIRING-ID", pairing.id);
        assertEquals("", GatewayJson.pairingToken(Fixtures.json("pair-pending.json")));
        assertTrue(GatewayJson.pairingToken(Fixtures.json("pair-approved.json")).startsWith("fd1_"));
    }

    @Test
    public void downloadsAreReadAndClamped() throws Exception {
        JSONObject reply = new JSONObject("{\"downloads\":[{\"kind\":\"show\",\"id\":371980,\"title\":\"Severance\",\"detail\":\"S02E05\","
                + "\"progress\":1.7,\"state\":\"downloading\",\"timeLeft\":\"12m\"},{\"kind\":\"film\",\"title\":\"X\","
                + "\"state\":\"something-new\"}]}");
        Download first = GatewayJson.downloads(reply).get(0);
        assertEquals(1.0, first.progress, 0);
        assertEquals("SHOW:371980", first.key());
        assertEquals(Download.State.QUEUED, GatewayJson.downloads(reply).get(1).state);
    }

    @Test
    public void episodesOfANewShowComeFromTheGuide() throws Exception {
        EpisodeList list = GatewayJson.episodes(Fixtures.json("episodes-new.json"));
        assertFalse(list.inLibrary);
        assertEquals(9, list.seasons.get(0).episodes.size());
    }

    @Test
    public void choiceReportsCounts() throws Exception {
        Choice choice = GatewayJson.choice(Fixtures.json("choose.json"));
        assertEquals("3|3|0|true", choice.chosen + "|" + choice.searching + "|" + choice.unmatched + "|" + choice.item.inLibrary);
    }

    @Test
    public void shelvesKeepTheirOrderAndDropEmptyRows() throws Exception {
        JSONObject reply = new JSONObject("{\"rows\":[{\"id\":\"recommended\",\"items\":[{\"kind\":\"film\",\"id\":62,"
                + "\"title\":\"2001: A Space Odyssey\"}]},{\"id\":\"trending\",\"items\":[]},{\"id\":\"popular\","
                + "\"items\":[{\"kind\":\"film\",\"id\":603,\"title\":\"The Matrix\"}]}]}");
        java.util.List<Shelf> shelves = GatewayJson.shelves(reply);
        assertEquals("recommended:62 popular:603", shelves.get(0).id + ":" + shelves.get(0).items.get(0).id + " "
                + shelves.get(1).id + ":" + shelves.get(1).items.get(0).id);
    }

    @Test
    public void tmdbShelfKeepsItsSubjectAndSource() throws Exception {
        JSONObject reply = new JSONObject("{\"rows\":[{\"id\":\"becauseYouHave\",\"subject\":\"Family Guy\","
                + "\"source\":\"tmdb\",\"items\":[{\"kind\":\"show\",\"id\":80379,\"title\":\"American Dad!\"}]}]}");
        Shelf shelf = GatewayJson.shelves(reply).get(0);
        assertEquals("becauseYouHave|Family Guy|true", shelf.id + "|" + shelf.subject + "|" + shelf.fromTmdb());
    }

    @Test
    public void libraryReadsEntriesAndStorage() throws Exception {
        JSONObject reply = new JSONObject("{\"films\":[{\"kind\":\"film\",\"id\":62,\"title\":\"2001\","
                + "\"inLibrary\":true,\"size\":37421776896,\"quality\":\"BR-DISK\",\"problem\":\"discImage\"}],"
                + "\"shows\":[],\"storage\":{\"used\":10,\"limit\":30,\"free\":20,\"source\":\"quota\"}}");
        Library library = GatewayJson.library(reply);
        assertEquals("62 37421776896 true 20", library.films.get(0).item.id + " " + library.films.get(0).size + " "
                + library.problems().get(0).isDiscImage() + " " + library.storage.free);
    }

    @Test
    public void nullFieldsBecomeEmptyText() throws Exception {
        Item item = GatewayJson.item(new JSONObject("{\"kind\":\"film\",\"id\":1,\"title\":null,\"poster\":null}"));
        assertEquals("", item.title + item.poster);
    }

    @Test
    public void errorsMapToReasons() throws Exception {
        assertEquals(FetchException.Reason.NOT_PAIRED, GatewayJson.error(401, Fixtures.text("unauthorized.json")).reason);
        assertEquals(FetchException.Reason.PAIRING_EXPIRED, GatewayJson.error(404, "{\"error\":\"pairing_expired\"}").reason);
        assertEquals(FetchException.Reason.NOT_FOUND, GatewayJson.error(404, "{\"error\":\"not_found\"}").reason);
        assertEquals(FetchException.Reason.BUSY, GatewayJson.error(429, "").reason);
        assertEquals(FetchException.Reason.SERVER, GatewayJson.error(502, "<html>").reason);
    }

    @Test
    public void conflictCarriesTheLibraryItem() throws Exception {
        FetchException error = GatewayJson.error(409, Fixtures.text("add-film-conflict.json"));
        assertEquals(FetchException.Reason.ALREADY_ADDED, error.reason);
        assertNotNull(error.item);
        assertTrue(error.item.inLibrary);
    }

    @Test
    public void rejectionKeepsTheServersReason() throws Exception {
        FetchException error = GatewayJson.error(409, "{\"error\":\"rejected\",\"message\":\"Path is not writable\"}");
        assertEquals("REJECTED|Path is not writable", error.reason + "|" + error.detail);
    }
}
