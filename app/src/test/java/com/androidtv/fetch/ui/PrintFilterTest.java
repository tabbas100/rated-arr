package com.androidtv.fetch.ui;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class PrintFilterTest {

    @Test
    public void noSepiaAndNoContrastChangesNothing() {
        float[] identity = {1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0};
        assertArrayEquals(identity, PrintFilter.matrix(0, 1), 1e-6f);
    }

    @Test
    public void moreContrastDarkensTheMidpointOffset() {
        assertEquals(-19.125f, PrintFilter.matrix(0, 1.15f)[4], 1e-3f);
    }

    @Test
    public void fullSepiaMatchesTheCssMatrix() {
        assertEquals(0.769f, PrintFilter.matrix(1, 1)[1], 1e-6f);
    }

    @Test
    public void alphaIsLeftAlone() {
        assertEquals(1f, PrintFilter.matrix(PrintFilter.SEPIA, PrintFilter.CONTRAST)[18], 0f);
    }
}
