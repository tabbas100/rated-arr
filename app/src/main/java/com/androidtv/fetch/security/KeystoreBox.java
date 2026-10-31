package com.androidtv.fetch.security;

import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;

import java.security.GeneralSecurityException;
import java.security.KeyStore;
import java.util.Arrays;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * AES-256-GCM with a key that lives in the Android Keystore: it cannot be read out of the TV, and
 * a copy of the app's files without it is useless. Sealed bytes are the 12-byte IV and the ciphertext.
 */
public final class KeystoreBox implements SecretBox {

    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String ALIAS = "fetch-device-token";
    private static final String CIPHER = "AES/GCM/NoPadding";
    private static final int IV_BYTES = 12;
    private static final int TAG_BITS = 128;

    @Override
    public byte[] seal(byte[] plain) throws GeneralSecurityException {
        Cipher cipher = Cipher.getInstance(CIPHER);
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] iv = cipher.getIV();
        byte[] body = cipher.doFinal(plain);
        byte[] sealed = Arrays.copyOf(iv, iv.length + body.length);
        System.arraycopy(body, 0, sealed, iv.length, body.length);
        return sealed;
    }

    @Override
    public byte[] open(byte[] sealed) throws GeneralSecurityException {
        if (sealed.length <= IV_BYTES) throw new GeneralSecurityException("sealed value too short");
        Cipher cipher = Cipher.getInstance(CIPHER);
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(TAG_BITS, sealed, 0, IV_BYTES));
        return cipher.doFinal(sealed, IV_BYTES, sealed.length - IV_BYTES);
    }

    // Purpose: the Keystore key, created on first use; the Keystore picks a random IV for every seal.
    private static SecretKey key() throws GeneralSecurityException {
        KeyStore keyStore = KeyStore.getInstance(KEYSTORE);
        try {
            keyStore.load(null);
        } catch (java.io.IOException e) {
            throw new GeneralSecurityException("Android Keystore unavailable", e);
        }
        KeyStore.Entry entry = keyStore.getEntry(ALIAS, null);
        if (entry instanceof KeyStore.SecretKeyEntry) return ((KeyStore.SecretKeyEntry) entry).getSecretKey();

        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE);
        generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }
}
