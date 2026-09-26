package org.biomanager.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;

/** The lab server this phone opens: remembered once it has answered as BioManager. */
final class Server {
    private static final String PREFS = "biomanager";
    private static final String KEY = "server";

    private Server() {}

    /** The saved address, e.g. "https://biomanager.example.edu", or null. */
    static String get(Context context) {
        return prefs(context).getString(KEY, null);
    }

    static void set(Context context, String address) {
        prefs(context).edit().putString(KEY, address).apply();
    }

    /**
     * What someone typed, as an address to try: https:// when no scheme was
     * given, no path, no trailing slash. Null when it cannot be an address.
     */
    static String normalise(String typed) {
        String text = typed == null ? "" : typed.trim();
        if (text.isEmpty()) return null;
        if (!text.contains("://")) text = "https://" + text;
        Uri uri = Uri.parse(text);
        String scheme = uri.getScheme();
        if (uri.getHost() == null || uri.getHost().isEmpty()
                || !("https".equals(scheme) || "http".equals(scheme))) {
            return null;
        }
        String address = scheme + "://" + uri.getHost();
        if (uri.getPort() != -1) address += ":" + uri.getPort();
        return address;
    }

    /** Whether a link belongs to the saved server, so it opens in the app. */
    static boolean owns(String address, Uri link) {
        if (address == null || link == null || link.getHost() == null) return false;
        Uri server = Uri.parse(address);
        return link.getHost().equalsIgnoreCase(server.getHost()) && link.getPort() == server.getPort();
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
