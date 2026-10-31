package com.androidtv.fetch;

import org.json.JSONObject;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/** Real gateway replies saved in fixtures/gateway (see tools/local-gateway.sh). */
public final class Fixtures {

    private Fixtures() {
    }

    public static String text(String name) {
        Path path = Paths.get("..", "fixtures", "gateway", name);
        try {
            return new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new IllegalStateException("missing fixture " + path.toAbsolutePath(), e);
        }
    }

    public static JSONObject json(String name) {
        try {
            return new JSONObject(text(name));
        } catch (org.json.JSONException e) {
            throw new IllegalStateException("fixture " + name + " is not JSON", e);
        }
    }
}
