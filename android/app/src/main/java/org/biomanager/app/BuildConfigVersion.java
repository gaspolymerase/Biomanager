package org.biomanager.app;

import android.content.Context;
import android.content.pm.PackageManager;

/** The installed version name, for the user agent the server sees. */
final class BuildConfigVersion {
    private BuildConfigVersion() {}

    static String name(Context context) {
        try {
            return context.getPackageManager().getPackageInfo(context.getPackageName(), 0).versionName;
        } catch (PackageManager.NameNotFoundException e) {
            return "unknown";
        }
    }
}
