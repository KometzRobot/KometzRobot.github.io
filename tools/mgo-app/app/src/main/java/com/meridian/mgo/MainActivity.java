package com.meridian.mgo;

import android.app.Activity;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {

    private static final String CHORUS_URL = "https://meridian-loop.com/chorus/";
    private static final String FALLBACK_URL = "https://meridian-loop.com/";
    private static final int HEARTBEAT_INTERVAL_MS = 30000;

    private WebView webView;
    private TextView statusBar;
    private View statusDot;
    private FrameLayout errorOverlay;
    private TextView errorText;
    private Handler heartbeatHandler;
    private boolean isConnected = true;
    private boolean pageLoaded = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setStatusBarColor(Color.parseColor("#0a0a0a"));
        getWindow().setNavigationBarColor(Color.parseColor("#0a0a0a"));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#0a0a0a"));

        LinearLayout topBar = buildTopBar();
        root.addView(topBar);

        FrameLayout contentFrame = new FrameLayout(this);
        LinearLayout.LayoutParams contentParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f);
        contentFrame.setLayoutParams(contentParams);

        webView = new WebView(this);
        setupWebView();
        contentFrame.addView(webView);

        errorOverlay = buildErrorOverlay();
        errorOverlay.setVisibility(View.GONE);
        contentFrame.addView(errorOverlay);

        root.addView(contentFrame);
        setContentView(root);

        registerNetworkCallback();
        startHeartbeat();
        webView.loadUrl(CHORUS_URL);
    }

    private LinearLayout buildTopBar() {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setBackgroundColor(Color.parseColor("#111111"));
        bar.setPadding(dp(16), dp(8), dp(16), dp(8));
        bar.setGravity(android.view.Gravity.CENTER_VERTICAL);

        TextView title = new TextView(this);
        title.setText("mGO");
        title.setTextColor(Color.parseColor("#00ffc8"));
        title.setTextSize(18);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        title.setLetterSpacing(0.15f);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
            0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f);
        title.setLayoutParams(titleParams);
        bar.addView(title);

        statusDot = new View(this);
        statusDot.setBackgroundColor(Color.parseColor("#00ffc8"));
        LinearLayout.LayoutParams dotParams = new LinearLayout.LayoutParams(dp(8), dp(8));
        dotParams.setMarginEnd(dp(8));
        statusDot.setLayoutParams(dotParams);
        bar.addView(statusDot);

        statusBar = new TextView(this);
        statusBar.setText("connecting...");
        statusBar.setTextColor(Color.parseColor("#888888"));
        statusBar.setTextSize(12);
        bar.addView(statusBar);

        return bar;
    }

    private FrameLayout buildErrorOverlay() {
        FrameLayout overlay = new FrameLayout(this);
        overlay.setBackgroundColor(Color.parseColor("#0a0a0a"));
        overlay.setLayoutParams(new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT));

        LinearLayout inner = new LinearLayout(this);
        inner.setOrientation(LinearLayout.VERTICAL);
        inner.setGravity(android.view.Gravity.CENTER);
        inner.setPadding(dp(32), dp(32), dp(32), dp(32));
        FrameLayout.LayoutParams innerParams = new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT);
        inner.setLayoutParams(innerParams);

        TextView symbol = new TextView(this);
        symbol.setText("◇");
        symbol.setTextColor(Color.parseColor("#00ffc8"));
        symbol.setTextSize(48);
        symbol.setGravity(android.view.Gravity.CENTER);
        inner.addView(symbol);

        errorText = new TextView(this);
        errorText.setText("Meridian unreachable.\nCheck connection and try again.");
        errorText.setTextColor(Color.parseColor("#888888"));
        errorText.setTextSize(14);
        errorText.setGravity(android.view.Gravity.CENTER);
        errorText.setPadding(0, dp(16), 0, dp(24));
        inner.addView(errorText);

        TextView retryBtn = new TextView(this);
        retryBtn.setText("RETRY");
        retryBtn.setTextColor(Color.parseColor("#0a0a0a"));
        retryBtn.setBackgroundColor(Color.parseColor("#00ffc8"));
        retryBtn.setTextSize(14);
        retryBtn.setTypeface(null, android.graphics.Typeface.BOLD);
        retryBtn.setPadding(dp(32), dp(12), dp(32), dp(12));
        retryBtn.setGravity(android.view.Gravity.CENTER);
        retryBtn.setOnClickListener(v -> {
            errorOverlay.setVisibility(View.GONE);
            webView.loadUrl(CHORUS_URL);
        });
        inner.addView(retryBtn);

        overlay.addView(inner);
        return overlay;
    }

    private void setupWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString() + " mGO/1.0");

        webView.setBackgroundColor(Color.parseColor("#0a0a0a"));
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                updateStatus("loading...", "#ffaa00");
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                pageLoaded = true;
                updateStatus("connected", "#00ffc8");
                errorOverlay.setVisibility(View.GONE);
                injectMobileStyles();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                if (request.isForMainFrame()) {
                    pageLoaded = false;
                    updateStatus("offline", "#ff4444");
                    errorOverlay.setVisibility(View.VISIBLE);
                }
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String host = request.getUrl().getHost();
                if (host != null && host.contains("meridian-loop.com")) {
                    return false;
                }
                return true;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage msg) {
                return true;
            }
        });
    }

    private void injectMobileStyles() {
        String css = "body{-webkit-text-size-adjust:100%}" +
            ".chat-container{height:calc(100vh - 60px)!important}" +
            "::-webkit-scrollbar{width:4px}" +
            "::-webkit-scrollbar-thumb{background:#333}";
        String js = "var s=document.createElement('style');" +
            "s.textContent='" + css + "';" +
            "document.head.appendChild(s);";
        webView.evaluateJavascript(js, null);
    }

    private void registerNetworkCallback() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return;

        NetworkRequest request = new NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build();

        cm.registerNetworkCallback(request, new ConnectivityManager.NetworkCallback() {
            @Override
            public void onAvailable(Network network) {
                runOnUiThread(() -> {
                    isConnected = true;
                    if (!pageLoaded) {
                        webView.loadUrl(CHORUS_URL);
                    }
                });
            }

            @Override
            public void onLost(Network network) {
                runOnUiThread(() -> {
                    isConnected = false;
                    updateStatus("offline", "#ff4444");
                });
            }
        });
    }

    private void startHeartbeat() {
        heartbeatHandler = new Handler(Looper.getMainLooper());
        heartbeatHandler.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (pageLoaded && isConnected) {
                    webView.evaluateJavascript(
                        "(function(){return document.readyState;})()",
                        value -> {
                            if (value == null || value.equals("null")) {
                                updateStatus("stale", "#ffaa00");
                            }
                        });
                }
                heartbeatHandler.postDelayed(this, HEARTBEAT_INTERVAL_MS);
            }
        }, HEARTBEAT_INTERVAL_MS);
    }

    private void updateStatus(String text, String color) {
        runOnUiThread(() -> {
            statusBar.setText(text);
            statusBar.setTextColor(Color.parseColor(color));
            statusDot.setBackgroundColor(Color.parseColor(color));
        });
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            moveTaskToBack(true);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        webView.onResume();
        if (isConnected && !pageLoaded) {
            webView.loadUrl(CHORUS_URL);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        webView.onPause();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (heartbeatHandler != null) {
            heartbeatHandler.removeCallbacksAndMessages(null);
        }
        webView.destroy();
    }
}
