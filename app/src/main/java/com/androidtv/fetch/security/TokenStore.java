package com.androidtv.fetch.security;

import com.androidtv.fetch.gateway.GatewayClient;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.Base64;

/** The device token, sealed by a SecretBox before it is written anywhere. */
public final class TokenStore implements GatewayClient.Tokens {

    /** One stored text value: the app's private preferences on the TV, memory in tests. */
    public interface Slot {
        String read();

        void write(String value);

        void erase();
    }

    private final Slot slot;
    private final SecretBox box;

    public TokenStore(Slot slot, SecretBox box) {
        this.slot = slot;
        this.box = box;
    }

    /** The token, or "" when none is stored or it cannot be opened (then it is erased). */
    @Override
    public String token() {
        String stored = slot.read();
        if (stored.isEmpty()) return "";
        try {
            return new String(box.open(Base64.getDecoder().decode(stored)), StandardCharsets.UTF_8);
        } catch (GeneralSecurityException | IllegalArgumentException e) {
            slot.erase();
            return "";
        }
    }

    public boolean hasToken() {
        return !token().isEmpty();
    }

    public void save(String token) throws GeneralSecurityException {
        slot.write(Base64.getEncoder().encodeToString(box.seal(token.getBytes(StandardCharsets.UTF_8))));
    }

    public void clear() {
        slot.erase();
    }
}
