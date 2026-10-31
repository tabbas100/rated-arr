package com.androidtv.fetch.security;

import java.security.GeneralSecurityException;

/** Seals and opens small secrets, such as the device token. */
public interface SecretBox {

    byte[] seal(byte[] plain) throws GeneralSecurityException;

    byte[] open(byte[] sealed) throws GeneralSecurityException;
}
