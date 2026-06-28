package com.zycrypto.app;
import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.*;
import android.webkit.*;
import android.widget.*;

public class MainActivity extends Activity {
    private WebView wv;
    private ProgressBar pb;
    private static final String URL = "https://vantage-platform-gi6p.onrender.com";

    @Override protected void onCreate(Bundle s) {
        super.onCreate(s);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                             WindowManager.LayoutParams.FLAG_FULLSCREEN);
        LinearLayout lay = new LinearLayout(this);
        lay.setOrientation(LinearLayout.VERTICAL);
        lay.setBackgroundColor(Color.parseColor("#07070a"));

        pb = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        pb.setLayoutParams(new LinearLayout.LayoutParams(-1, 6));
        pb.setMax(100);
        pb.setProgressTintList(android.content.res.ColorStateList.valueOf(
            Color.parseColor("#f5c518")));
        lay.addView(pb);

        wv = new WebView(this);
        wv.setLayoutParams(new LinearLayout.LayoutParams(-1, -1));
        lay.addView(wv);
        setContentView(lay);

        WebSettings ws = wv.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setCacheMode(WebSettings.LOAD_DEFAULT);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(wv, true);

        wv.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, String u) {
                v.loadUrl(u); return true;
            }
            @Override public void onPageFinished(WebView v, String u) {
                pb.setVisibility(View.GONE);
            }
        });
        wv.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView v, int p) {
                pb.setVisibility(p < 100 ? View.VISIBLE : View.GONE);
                pb.setProgress(p);
            }
        });
        wv.loadUrl(URL);
    }

    @Override public boolean onKeyDown(int k, KeyEvent e) {
        if (k == KeyEvent.KEYCODE_BACK && wv.canGoBack()) { wv.goBack(); return true; }
        return super.onKeyDown(k, e);
    }
}
