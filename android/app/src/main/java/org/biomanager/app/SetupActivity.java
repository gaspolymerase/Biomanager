package org.biomanager.app;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import javax.net.ssl.SSLException;

/** Asks for the lab server's address and checks it is a BioManager server before saving it. */
public class SetupActivity extends Activity {
    private final ExecutorService background = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    private EditText field;
    private TextView message;
    private Button connect;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_setup);
        field = findViewById(R.id.server);
        message = findViewById(R.id.message);
        connect = findViewById(R.id.connect);

        String saved = Server.get(this);
        if (saved != null) field.setText(saved);
        field.requestFocus();

        connect.setOnClickListener(v -> check());
        field.setOnEditorActionListener((v, actionId, event) -> {
            boolean enterKey = event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                    && event.getAction() == KeyEvent.ACTION_DOWN;
            if (actionId == EditorInfo.IME_ACTION_GO || enterKey) {
                check();
                return true;
            }
            return false;
        });
    }

    private void check() {
        String address = Server.normalise(field.getText().toString());
        if (address == null) {
            show(getString(R.string.err_empty));
            return;
        }
        message.setVisibility(View.GONE);
        connect.setEnabled(false);
        connect.setText(R.string.setup_checking);

        background.execute(() -> {
            String problem = probe(address);
            main.post(() -> {
                connect.setEnabled(true);
                connect.setText(R.string.setup_connect);
                if (problem != null) {
                    show(problem);
                    return;
                }
                Server.set(this, address);
                if (address.startsWith("http://")) {
                    Toast.makeText(this, R.string.warn_http, Toast.LENGTH_LONG).show();
                }
                // A fresh task holding only the main screen: nothing (an earlier setup
                // screen, the old server's page) is left underneath for Back to reveal.
                startActivity(new Intent(this, MainActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
                finish();
            });
        });
    }

    /** Null when the address answers /healthz like BioManager does, otherwise why not. */
    private String probe(String address) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(address + "/healthz").openConnection();
            connection.setConnectTimeout(8000);
            connection.setReadTimeout(8000);
            connection.setInstanceFollowRedirects(true);
            int status = connection.getResponseCode();
            String body = "";
            if (status == 200) {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                    String line = reader.readLine();
                    body = line == null ? "" : line.trim();
                }
            }
            return "ok".equals(body) ? null : getString(R.string.err_not_biomanager);
        } catch (SSLException e) {
            return getString(R.string.err_certificate);
        } catch (Exception e) {
            return getString(R.string.err_unreachable, address);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private void show(String text) {
        message.setText(text);
        message.setVisibility(View.VISIBLE);
    }

    @Override
    protected void onDestroy() {
        background.shutdownNow();
        super.onDestroy();
    }
}
