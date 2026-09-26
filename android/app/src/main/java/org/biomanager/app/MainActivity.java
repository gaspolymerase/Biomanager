package org.biomanager.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Rect;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import com.google.mlkit.vision.codescanner.GmsBarcodeScanner;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning;

/**
 * The lab server's BioManager, full screen. Links to the server stay in the
 * app; anything else opens in the browser. A Scan button reads a cage card's
 * QR code and opens the record it points to.
 */
public class MainActivity extends Activity {
    private static final int PICK_FILE = 1;

    private String server;
    private WebView web;
    private ProgressBar progress;
    private View offline;
    private TextView offlineDetail;
    private ValueCallback<Uri[]> pendingFiles;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        server = Server.get(this);
        if (server == null) {
            startActivity(new Intent(this, SetupActivity.class));
            finish();
            return;
        }
        setContentView(R.layout.activity_main);
        web = findViewById(R.id.web);
        progress = findViewById(R.id.progress);
        offline = findViewById(R.id.offline);
        offlineDetail = findViewById(R.id.offline_detail);

        findViewById(R.id.retry).setOnClickListener(v -> {
            offline.setVisibility(View.GONE);
            web.reload();
        });
        findViewById(R.id.change_server).setOnClickListener(v -> changeServer());
        View scanButton = findViewById(R.id.scan);
        scanButton.setOnClickListener(v -> scan());
        hideWhileTyping(scanButton);

        configure(web);
        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(server + "/");
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configure(WebView view) {
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);  // tabs and preferences live in localStorage
        settings.setUserAgentString(settings.getUserAgentString() + " BioManagerAndroid/" + BuildConfigVersion.name(this));

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(view, false);

        view.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest request) {
                Uri link = request.getUrl();
                if (Server.owns(server, link)) return false;
                openElsewhere(link);
                return true;
            }

            @Override
            public void onPageStarted(WebView v, String url, Bitmap favicon) {
                progress.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                progress.setVisibility(View.GONE);
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    offlineDetail.setText(getString(R.string.err_unreachable, server));
                    offline.setVisibility(View.VISIBLE);
                }
            }
        });

        view.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView v, int percent) {
                progress.setProgress(percent);
            }

            // Photos and files for the notebook and records.
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (pendingFiles != null) pendingFiles.onReceiveValue(null);
                pendingFiles = callback;
                try {
                    startActivityForResult(params.createIntent(), PICK_FILE);
                } catch (ActivityNotFoundException e) {
                    pendingFiles = null;
                    return false;
                }
                return true;
            }
        });

        // CSV exports, printed sheets and backups: hand them to the system's downloader,
        // with this session's cookie so the server knows who is asking.
        view.setDownloadListener((url, userAgent, disposition, mimeType, length) -> {
            String name = URLUtil.guessFileName(url, disposition, mimeType);
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url))
                    .addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url))
                    .addRequestHeader("User-Agent", userAgent)
                    .setMimeType(mimeType)
                    .setTitle(name)
                    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                    .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
            DownloadManager downloads = getSystemService(DownloadManager.class);
            if (downloads != null) {
                downloads.enqueue(request);
                Toast.makeText(this, getString(R.string.downloading, name), Toast.LENGTH_SHORT).show();
            }
        });
    }

    /** The Scan button would cover form fields while the keyboard is up. */
    private void hideWhileTyping(View button) {
        View root = findViewById(android.R.id.content);
        root.getViewTreeObserver().addOnGlobalLayoutListener(() -> {
            boolean typing;
            WindowInsets insets = root.getRootWindowInsets();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && insets != null) {
                typing = insets.isVisible(WindowInsets.Type.ime());
            } else {
                Rect visible = new Rect();
                root.getWindowVisibleDisplayFrame(visible);
                typing = visible.height() < root.getRootView().getHeight() * 0.75;
            }
            button.setVisibility(typing ? View.GONE : View.VISIBLE);
        });
    }

    /** Read a cage card and open the record its QR code points to. */
    private void scan() {
        GmsBarcodeScanner scanner = GmsBarcodeScanning.getClient(this);
        scanner.startScan()
                .addOnSuccessListener(barcode -> {
                    String value = barcode.getRawValue();
                    Uri link = value == null ? null : Uri.parse(value.trim());
                    if (link != null && Server.owns(server, link)) {
                        offline.setVisibility(View.GONE);
                        web.loadUrl(link.toString());
                    } else if (link != null && link.getHost() != null) {
                        Toast.makeText(this, getString(R.string.scan_other_server, link.getHost()), Toast.LENGTH_LONG).show();
                    } else {
                        Toast.makeText(this, R.string.scan_not_link, Toast.LENGTH_SHORT).show();
                    }
                })
                .addOnFailureListener(e ->
                        Toast.makeText(this, R.string.scan_unavailable, Toast.LENGTH_LONG).show());
    }

    private void openElsewhere(Uri link) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, link));
        } catch (ActivityNotFoundException ignored) {
            // Nothing on the phone opens it; stay where we are.
        }
    }

    private void changeServer() {
        startActivity(new Intent(this, SetupActivity.class));
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == PICK_FILE && pendingFiles != null) {
            pendingFiles.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            pendingFiles = null;
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        // Back from Change server with a new address: open it.
        String saved = Server.get(this);
        if (saved != null && !saved.equals(server)) {
            server = saved;
            web.clearHistory();
            web.loadUrl(server + "/");
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (web != null) web.saveState(outState);
    }

    @Override
    protected void onPause() {
        CookieManager.getInstance().flush();  // stay signed in after the app is closed
        super.onPause();
    }
}
