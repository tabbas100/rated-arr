package com.androidtv.fetch.gateway;

import com.androidtv.fetch.Fixtures;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import java.io.IOException;

/** The client against a local HTTP server that plays the gateway. */
public class GatewayClientTest {

    private static final String TOKEN = "fd1_" + "T".repeat(43);

    private TinyHttpServer server;
    private String token = TOKEN;

    @Before
    public void startServer() throws IOException {
        server = new TinyHttpServer();
    }

    @After
    public void stopServer() throws IOException {
        server.close();
    }

    private GatewayClient client() {
        return new GatewayClient(server.url(), () -> token);
    }

    private TinyHttpServer.Request firstRequest() {
        return server.requests.get(0);
    }

    private interface ThrowingCall {
        void run() throws FetchException;
    }

    private FetchException.Reason failure(ThrowingCall call) {
        try {
            call.run();
        } catch (FetchException e) {
            return e.reason;
        }
        fail("expected a FetchException");
        return null;
    }

    @Test
    public void signedCallsSendTheBearerToken() throws Exception {
        server.reply = Fixtures.text("search.json");
        client().search("breaking bad");
        assertEquals("Bearer " + TOKEN, firstRequest().headers.get("authorization"));
    }

    @Test
    public void searchEncodesTheQuery() throws Exception {
        server.reply = Fixtures.text("search.json");
        client().search("fast & furious?");
        assertEquals("/v1/search?q=fast%20%26%20furious%3F", firstRequest().target);
    }

    @Test
    public void pairingCallsSendNoToken() throws Exception {
        server.reply = Fixtures.text("pair-start.json");
        client().startPairing("Living Room TV");
        assertNull(firstRequest().headers.get("authorization"));
    }

    @Test
    public void signedCallWithoutTokenFailsBeforeTheNetwork() throws Exception {
        token = "";
        assertEquals(FetchException.Reason.NOT_PAIRED, failure(() -> client().downloads()));
        assertTrue(server.requests.isEmpty());
    }

    @Test
    public void addShowSendsIdSeasonsAndProfile() throws Exception {
        server.reply = Fixtures.text("add-show.json");
        client().addShow(81189, "latest", 4);
        JSONObject sent = new JSONObject(firstRequest().body);
        assertEquals("81189|latest|4", sent.getInt("id") + "|" + sent.getString("seasons") + "|" + sent.getInt("profile"));
    }

    @Test
    public void addFilmLeavesOutAnUnchosenProfile() throws Exception {
        server.reply = Fixtures.text("add-film.json");
        client().addFilm(603, 0);
        assertFalse(firstRequest().body.contains("profile"));
    }

    @Test
    public void chooseEpisodesSendsPairs() throws Exception {
        server.reply = Fixtures.text("choose.json");
        client().chooseEpisodes(81189, java.util.Arrays.asList(new int[]{1, 1}, new int[]{5, 16}), 0);
        JSONObject sent = new JSONObject(firstRequest().body);
        assertEquals("81189 [[1,1],[5,16]]", sent.getInt("show") + " " + sent.getJSONArray("episodes"));
    }

    @Test
    public void episodeListAsksForTheShow() throws Exception {
        server.reply = Fixtures.text("episodes-new.json");
        client().episodes(371980);
        assertEquals("/v1/episodes?show=371980", firstRequest().target);
    }

    @Test
    public void unauthorizedMeansPairAgain() throws Exception {
        server.status = 401;
        server.reply = Fixtures.text("unauthorized.json");
        assertEquals(FetchException.Reason.NOT_PAIRED, failure(() -> client().recent()));
    }

    @Test
    public void conflictIsAlreadyAdded() throws Exception {
        server.status = 409;
        server.reply = Fixtures.text("add-film-conflict.json");
        assertEquals(FetchException.Reason.ALREADY_ADDED, failure(() -> client().addFilm(603, 0)));
    }

    @Test
    public void redirectsAreNotFollowed() throws Exception {
        server.status = 302;
        server.location = "https://evil.example/";
        server.reply = "";
        assertEquals(FetchException.Reason.SERVER, failure(() -> client().recent()));
        assertEquals(1, server.requests.size());
    }

    @Test
    public void oversizedReplyIsRefused() throws Exception {
        server.reply = "{\"items\":\"" + "x".repeat(3 * 1024 * 1024) + "\"}";
        assertEquals(FetchException.Reason.OFFLINE, failure(() -> client().recent()));
    }

    @Test
    public void htmlInsteadOfJsonIsAServerProblem() throws Exception {
        server.reply = "<html>login</html>";
        assertEquals(FetchException.Reason.SERVER, failure(() -> client().recent()));
    }

    @Test
    public void noServerMeansOffline() throws IOException {
        server.close();
        assertEquals(FetchException.Reason.OFFLINE, failure(() -> client().recent()));
    }
}
