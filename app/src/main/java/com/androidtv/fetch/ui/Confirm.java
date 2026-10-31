package com.androidtv.fetch.ui;

import android.app.Activity;
import android.app.Dialog;
import android.widget.TextView;

import com.androidtv.fetch.R;

/**
 * The question before anything is deleted: a paper card with the title, what it frees, and Cancel beside the
 * red action. Cancel has the focus, so pressing OK by habit deletes nothing.
 */
public final class Confirm {

    private Confirm() {
    }

    public static void ask(Activity activity, String title, String message, int action, Runnable onConfirm) {
        Dialog dialog = new Dialog(activity, R.style.Theme_Fetch_Dialog);
        dialog.setContentView(R.layout.dialog_confirm);
        ((TextView) dialog.findViewById(R.id.confirmTitle)).setText(title);
        ((TextView) dialog.findViewById(R.id.confirmBody)).setText(message);
        TextView cancel = dialog.findViewById(R.id.confirmCancel);
        TextView confirm = dialog.findViewById(R.id.confirmAction);
        confirm.setText(action);
        cancel.setOnClickListener(v -> dialog.dismiss());
        confirm.setOnClickListener(v -> {
            dialog.dismiss();
            onConfirm.run();
        });
        Cards.zoomOnFocus(cancel);
        Cards.zoomOnFocus(confirm);
        dialog.setOnShowListener(d -> cancel.requestFocus());
        dialog.show();
    }
}
