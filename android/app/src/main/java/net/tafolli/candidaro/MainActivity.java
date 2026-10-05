package net.tafolli.candidaro;

import android.content.Intent;
import android.os.Bundle;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;
import org.json.JSONObject;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class MainActivity extends BridgeActivity {
    private String pendingJobUrl;
    private boolean pageReady;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        readShareIntent(getIntent());
        getBridge().setWebViewClient(new BridgeWebViewClient(getBridge()) {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                pageReady = true;
                deliverShare();
            }
        });
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        readShareIntent(intent);
        deliverShare();
    }

    private void readShareIntent(Intent intent) {
        if (!Intent.ACTION_SEND.equals(intent.getAction()) || !"text/plain".equals(intent.getType())) return;
        String text = intent.getStringExtra(Intent.EXTRA_TEXT);
        if (text == null || text.length() > 20000) return;
        Matcher matcher = Pattern.compile("https://[^\\s<>\\\"]+").matcher(text);
        if (matcher.find()) pendingJobUrl = matcher.group();
    }

    private void deliverShare() {
        if (!pageReady || pendingJobUrl == null) return;
        getBridge().triggerWindowJSEvent("sharedJob", "{\"url\":" + JSONObject.quote(pendingJobUrl) + "}");
        pendingJobUrl = null;
    }
}
