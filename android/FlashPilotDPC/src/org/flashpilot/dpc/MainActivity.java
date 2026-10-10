package org.flashpilot.dpc;

import android.app.Activity;
import android.app.admin.DevicePolicyManager;
import android.content.Context;
import android.os.Bundle;
import android.os.PersistableBundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Launcher activity: email-gated "fake login". Entering the access email
 * (baked at build time, pre-filled from the provisioning extras when the
 * QR carries it) unlocks the "Complete setup" button, which runs the same
 * writes as the provisioning receiver.
 * Built with framework widgets only — no resources, no support libs.
 * Works from API 26 (Android 8) through 34 (Android 14).
 */
public class MainActivity extends Activity {

    private TextView status;
    private EditText email;
    private Button go;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);

        status = new TextView(this);
        status.setTextSize(16);
        root.addView(status);

        email = new EditText(this);
        email.setHint("Access email");
        email.setSingleLine(true);
        // Pre-fill from the provisioning extras bundle when present.
        try {
            PersistableBundle extras = getIntent().getParcelableExtra(
                    "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE");
            if (extras != null) {
                String pre = extras.getString("fp_email", "");
                if (pre != null && !pre.isEmpty()) {
                    email.setText(pre);
                }
            }
        } catch (Exception e) {
            // extras are a hint only
        }
        root.addView(email);

        final Button check = new Button(this);
        check.setText("Unlock with email");
        check.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String want = AccessConfig.ACCESS_EMAIL;
                String got = email.getText().toString().trim();
                if (!want.isEmpty() && want.equalsIgnoreCase(got)) {
                    go.setEnabled(true);
                    refresh("Email accepted - provisioning unlocked.");
                } else {
                    go.setEnabled(false);
                    refresh("Unknown email - enter the email given by your technician.");
                }
            }
        });
        root.addView(check);

        go = new Button(this);
        go.setText("Complete setup (fake login)");
        go.setEnabled(false);
        go.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String r = FpAdminReceiver.completeSetup(MainActivity.this);
                refresh("Last run: " + r);
            }
        });
        root.addView(go);

        setContentView(root);
        // Device-owner auto-run (post-QR) skips the gate: enrollment itself
        // is the authorization, so run once immediately when owner.
        DevicePolicyManager dpm =
                (DevicePolicyManager) getSystemService(Context.DEVICE_POLICY_SERVICE);
        boolean owner = false;
        try {
            owner = dpm.isDeviceOwnerApp(getPackageName());
        } catch (Exception e) {
            owner = false;
        }
        if (owner) {
            String r = FpAdminReceiver.completeSetup(this);
            go.setEnabled(true);
            refresh("Enrolled as device owner - setup completed automatically.\n" + r);
        } else {
            refresh(null);
        }
    }

    private void refresh(String extra) {
        DevicePolicyManager dpm =
                (DevicePolicyManager) getSystemService(Context.DEVICE_POLICY_SERVICE);
        boolean owner = false;
        try {
            owner = dpm.isDeviceOwnerApp(getPackageName());
        } catch (Exception e) {
            owner = false;
        }
        StringBuilder sb = new StringBuilder();
        sb.append("FlashPilot Setup\n");
        sb.append("Device owner: ").append(owner ? "YES" : "NO").append("\n");
        sb.append(owner
                ? "Enrolled. Unlock with the access email, then finish setup."
                : "Not enrolled. Scan the provisioning QR in the setup wizard first.");
        if (extra != null) {
            sb.append("\n").append(extra);
        }
        status.setText(sb.toString());
    }
}
