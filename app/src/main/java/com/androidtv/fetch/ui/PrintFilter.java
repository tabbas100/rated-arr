package com.androidtv.fetch.ui;

import android.graphics.ColorMatrixColorFilter;

/**
 * The Grindhouse look for photos: a light sepia wash and a little more contrast, like a worn print. The same
 * as the UI kit's CSS, sepia(.35) contrast(1.15).
 */
public final class PrintFilter {

    static final float SEPIA = 0.35f;
    static final float CONTRAST = 1.15f;

    private PrintFilter() {
    }

    public static ColorMatrixColorFilter agedPrint() {
        return new ColorMatrixColorFilter(matrix(SEPIA, CONTRAST));
    }

    /** A 4×5 colour matrix doing CSS's sepia(sepia), then contrast(contrast); alpha is left alone. */
    static float[] matrix(float sepia, float contrast) {
        float keep = 1 - sepia;
        float[][] tone = {
                {0.393f + 0.607f * keep, 0.769f - 0.769f * keep, 0.189f - 0.189f * keep},
                {0.349f - 0.349f * keep, 0.686f + 0.314f * keep, 0.168f - 0.168f * keep},
                {0.272f - 0.272f * keep, 0.534f - 0.534f * keep, 0.131f + 0.869f * keep}};
        float offset = 255 * (0.5f - 0.5f * contrast);
        float[] matrix = new float[20];
        for (int row = 0; row < 3; row++) {
            for (int column = 0; column < 3; column++) matrix[row * 5 + column] = tone[row][column] * contrast;
            matrix[row * 5 + 4] = offset;
        }
        matrix[18] = 1;
        return matrix;
    }
}
