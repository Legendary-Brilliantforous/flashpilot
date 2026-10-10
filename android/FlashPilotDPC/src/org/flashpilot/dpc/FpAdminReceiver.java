package org.flashpilot.dpc;

import android.app.admin.DeviceAdminReceiver;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.provider.Settings;

/**
 * Device-owner receiver. On provisioning completion (QR enrollment) it
 * performs the "fake login": marks setup complete + provisioned, enables
 * ADB, and hides the setup wizards — the same end state TestDPC-based
 * flows reach, with our own component.
 */
public class FpAdminReceiver extends DeviceAdminReceiver {

    public static ComponentName admin(Context ctx) {
        return new ComponentName(ctx, FpAdminReceiver.class);
    }

    /** Idempotent: safe to call from the receiver and the activity. */
    public static String completeSetup(Context ctx) {
        StringBuilder log = new StringBuilder();
        try {
            ContentResolver cr = ctx.getContentResolver();
            Settings.Secure.putInt(cr, Settings.Secure.USER_SETUP_COMPLETE, 1);
            log.append("user_setup_complete=1; ");
        } catch (Exception e) {
            log.append("user_setup_complete FAILED: ").append(e.getMessage()).append("; ");
        }
        try {
            ContentResolver cr = ctx.getContentResolver();
            Settings.Global.putInt(cr, Settings.Global.DEVICE_PROVISIONED, 1);
            log.append("device_provisioned=1; ");
        } catch (Exception e) {
            log.append("device_provisioned FAILED: ").append(e.getMessage()).append("; ");
        }
        try {
            ContentResolver cr = ctx.getContentResolver();
            Settings.Global.putInt(cr, Settings.Global.ADB_ENABLED, 1);
            log.append("adb_enabled=1; ");
        } catch (Exception e) {
            log.append("adb_enabled FAILED: ").append(e.getMessage()).append("; ");
        }
        try {
            android.app.admin.DevicePolicyManager dpm =
                    (android.app.admin.DevicePolicyManager)
                            ctx.getSystemService(Context.DEVICE_POLICY_SERVICE);
            ComponentName a = admin(ctx);
            // Kill the setup wizards so the FRP gate never shows again.
            // suspend (API 24+) first, hidden-setting as fallback — both
            // are attempted on every version from 8 through 14.
            for (String pkg : new String[]{
                    "com.google.android.setupwizard",
                    "com.motorola.setupwizard"}) {
                boolean done = false;
                try {
                    String[] r = dpm.setPackagesSuspended(a, new String[]{pkg}, true);
                    if (r != null && r.length == 0) {
                        log.append(pkg).append(" suspended; ");
                        done = true;
                    }
                } catch (Exception e) {
                    // fall through to setApplicationHidden
                }
                if (!done) {
                    try {
                        dpm.setApplicationHidden(a, pkg, true);
                        log.append(pkg).append(" hidden; ");
                    } catch (Exception e) {
                        log.append(pkg).append(" hide FAILED; ");
                    }
                }
            }
            try {
                dpm.setGlobalSetting(a, Settings.Global.ADB_ENABLED, "1");
                log.append("dpm adb_enabled=1; ");
            } catch (Exception e) {
                log.append("dpm adb FAILED; ");
            }
            // setUserSetupComplete exists from API 28; guarded for 26/27.
            if (android.os.Build.VERSION.SDK_INT >= 28) {
                try {
                    dpm.setUserSetupComplete();
                    log.append("dpm.setUserSetupComplete; ");
                } catch (Exception e) {
                    log.append("setUserSetupComplete FAILED; ");
                }
            }
        } catch (Exception e) {
            log.append("dpm FAILED: ").append(e.getMessage()).append("; ");
        }
        return log.toString();
    }

    @Override
    public void onProfileProvisioningComplete(Context context, Intent intent) {
        completeSetup(context);
    }
}
