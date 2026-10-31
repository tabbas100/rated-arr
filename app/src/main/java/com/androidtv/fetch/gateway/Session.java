package com.androidtv.fetch.gateway;

import android.content.Context;
import android.content.SharedPreferences;

import com.androidtv.fetch.R;
import com.androidtv.fetch.security.KeystoreBox;
import com.androidtv.fetch.security.TokenStore;

/** The app's one gateway client and token store, shared by the screens. */
public final class Session {

    private static final String PREFS = "fetch";
    private static final String TOKEN_KEY = "device_token";
    private static Session instance;

    public final GatewayClient client;
    public final TokenStore tokens;
    public final SharedPreferences prefs;

    private Session(Context app) {
        prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        tokens = new TokenStore(new PrefsSlot(prefs, TOKEN_KEY), new KeystoreBox());
        client = new GatewayClient(app.getString(R.string.gateway_url), tokens);
    }

    public static synchronized Session get(Context context) {
        if (instance == null) instance = new Session(context.getApplicationContext());
        return instance;
    }

    public boolean isPaired() {
        return tokens.hasToken();
    }

    /** The token no longer works (revoked or the gateway was reset): forget it so the TV pairs again. */
    public void forget() {
        tokens.clear();
    }

    /** One preference in the app's private SharedPreferences. */
    private static final class PrefsSlot implements TokenStore.Slot {

        private final SharedPreferences prefs;
        private final String key;

        PrefsSlot(SharedPreferences prefs, String key) {
            this.prefs = prefs;
            this.key = key;
        }

        @Override
        public String read() {
            return prefs.getString(key, "");
        }

        @Override
        public void write(String value) {
            prefs.edit().putString(key, value).apply();
        }

        @Override
        public void erase() {
            prefs.edit().remove(key).apply();
        }
    }
}
