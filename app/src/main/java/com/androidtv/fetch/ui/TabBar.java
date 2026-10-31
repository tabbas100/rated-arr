package com.androidtv.fetch.ui;

import android.content.Context;
import android.util.AttributeSet;
import android.view.View;
import android.widget.LinearLayout;

import java.util.ArrayList;

/**
 * The row of tabs on home. Focus arriving from outside the row lands on the selected tab, so moving
 * up from the cards never switches tabs; it would otherwise land on the nearest tab, often Films.
 */
public final class TabBar extends LinearLayout {

    public TabBar(Context context, AttributeSet attrs) {
        super(context, attrs);
    }

    @Override
    public void addFocusables(ArrayList<View> views, int direction, int focusableMode) {
        View selected = selectedTab();
        if (hasFocus() || selected == null) super.addFocusables(views, direction, focusableMode);
        else selected.addFocusables(views, direction, focusableMode);
    }

    private View selectedTab() {
        for (int i = 0; i < getChildCount(); i++) {
            if (getChildAt(i).isSelected()) return getChildAt(i);
        }
        return null;
    }
}
