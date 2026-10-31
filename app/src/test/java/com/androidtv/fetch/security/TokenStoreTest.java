package com.androidtv.fetch.security;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;

public class TokenStoreTest {

    private static final String TOKEN = "fd1_abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG";

    /** Stands in for the Keystore: reverses and marks the bytes, and fails on unmarked input. */
    private static final class FakeBox implements SecretBox {
        @Override
        public byte[] seal(byte[] plain) {
            return ("sealed:" + new StringBuilder(new String(plain, StandardCharsets.UTF_8)).reverse())
                    .getBytes(StandardCharsets.UTF_8);
        }

        @Override
        public byte[] open(byte[] sealed) throws GeneralSecurityException {
            String text = new String(sealed, StandardCharsets.UTF_8);
            if (!text.startsWith("sealed:")) throw new GeneralSecurityException("tampered");
            return new StringBuilder(text.substring(7)).reverse().toString().getBytes(StandardCharsets.UTF_8);
        }
    }

    private static final class MemorySlot implements TokenStore.Slot {
        String value = "";

        @Override
        public String read() {
            return value;
        }

        @Override
        public void write(String value) {
            this.value = value;
        }

        @Override
        public void erase() {
            value = "";
        }
    }

    private final MemorySlot slot = new MemorySlot();
    private final TokenStore store = new TokenStore(slot, new FakeBox());

    @Test
    public void savedTokenComesBack() throws GeneralSecurityException {
        store.save(TOKEN);
        assertEquals(TOKEN, store.token());
    }

    @Test
    public void plainTokenIsNeverStored() throws GeneralSecurityException {
        store.save(TOKEN);
        assertFalse(slot.value.contains(TOKEN));
    }

    @Test
    public void emptyStoreHasNoToken() {
        assertFalse(store.hasToken());
    }

    @Test
    public void tamperedValueIsErased() {
        slot.value = "bm90IHNlYWxlZA==";
        assertEquals("", store.token());
        assertEquals("", slot.value);
    }

    @Test
    public void garbageIsErased() {
        slot.value = "%%% not base64 %%%";
        assertEquals("", store.token());
        assertEquals("", slot.value);
    }

    @Test
    public void clearForgetsTheToken() throws GeneralSecurityException {
        store.save(TOKEN);
        store.clear();
        assertTrue(store.token().isEmpty());
    }
}
