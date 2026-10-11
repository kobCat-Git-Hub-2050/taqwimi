#!/usr/bin/env python3
"""Creates the Android Studio / Gradle project (folder `android`) that wraps index.html as an app.
Run it in the folder that contains index.html and icon-192.png:   python3 make_project.py
Then open the `android` folder in Android Studio and choose Build > Build APK(s)."""
import os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'android')

FILES = {
    'settings.gradle': r'''pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "TaqwimiMahaam"
include ':app'
''',
    'build.gradle': r'''plugins {
    id 'com.android.application' version '8.5.2' apply false
}
''',
    'gradle.properties': r'''org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=false
android.nonTransitiveRClass=true
''',
    'gradle/wrapper/gradle-wrapper.properties': r'''distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.7-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
''',
    'app/build.gradle': r'''plugins {
    id 'com.android.application'
}

android {
    namespace 'com.taqwimi.mahaam'
    compileSdk 34

    defaultConfig {
        applicationId "com.taqwimi.mahaam"
        minSdk 21
        targetSdk 34
        versionCode 1
        versionName "1.0"
    }

    buildTypes {
        release {
            minifyEnabled false
        }
    }

    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
}
''',
    'app/src/main/AndroidManifest.xml': r'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/AppTheme">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden|screenLayout|smallestScreenSize|uiMode|layoutDirection|locale"
            android:launchMode="singleTask"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
''',
    'app/src/main/res/values/strings.xml': r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">تقويمي</string>
</resources>
''',
    'app/src/main/res/values/styles.xml': r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="android:Theme.Material.NoActionBar">
        <item name="android:statusBarColor">#42124E</item>
        <item name="android:navigationBarColor">#303030</item>
        <item name="android:windowBackground">@android:color/black</item>
    </style>
</resources>
''',
    'app/src/main/java/com/taqwimi/mahaam/MainActivity.java': r'''package com.taqwimi.mahaam;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

import java.io.OutputStream;

/**
 * Thin native shell around the web app in assets/index.html.
 * It adds what a plain WebView lacks: file picking (Excel import), file saving (Excel export),
 * opening tel:/WhatsApp links, and the hardware Back button.
 */
public class MainActivity extends Activity {

    private static final int REQ_PICK_FILE = 1001;
    private static final int REQ_SAVE_FILE = 1002;

    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;
    private byte[] pendingBytes;
    private String pendingName;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.setBackgroundColor(0xFF303030);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handleUrl(request.getUrl());
            }

            @SuppressWarnings("deprecation")
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return handleUrl(Uri.parse(url));
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = callback;
                try {
                    startActivityForResult(params.createIntent(), REQ_PICK_FILE);
                } catch (ActivityNotFoundException e) {
                    filePathCallback = null;
                    return false;
                }
                return true;
            }
        });

        webView.addJavascriptInterface(new Bridge(), "AndroidBridge");
        webView.loadUrl("file:///android_asset/index.html");
    }

    /** Keep the app's own pages inside the WebView; hand everything else (tel:, wa.me, ...) to Android. */
    private boolean handleUrl(Uri uri) {
        if ("file".equals(uri.getScheme())) {
            return false;
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (ActivityNotFoundException ignored) {
            // no app can handle this link
        }
        return true;
    }

    /** Called from JavaScript as window.AndroidBridge.saveFile(name, mime, base64). */
    public class Bridge {
        @JavascriptInterface
        public void saveFile(final String name, final String mime, String base64) {
            try {
                pendingBytes = Base64.decode(base64, Base64.DEFAULT);
            } catch (Exception e) {
                notifyJs(false, "");
                return;
            }
            pendingName = name;
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType((mime == null || mime.length() == 0) ? "application/octet-stream" : mime);
                    intent.putExtra(Intent.EXTRA_TITLE, name);
                    try {
                        startActivityForResult(intent, REQ_SAVE_FILE);
                    } catch (ActivityNotFoundException e) {
                        notifyJs(false, "");
                    }
                }
            });
        }
    }

    private void notifyJs(final boolean ok, final String name) {
        webView.post(new Runnable() {
            @Override
            public void run() {
                webView.evaluateJavascript(
                        "window.__saved && window.__saved(" + ok + "," + JSONObject.quote(name == null ? "" : name) + ")", null);
            }
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQ_PICK_FILE) {
            if (filePathCallback != null) {
                filePathCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
                filePathCallback = null;
            }
            return;
        }
        if (requestCode == REQ_SAVE_FILE) {
            boolean ok = false;
            if (resultCode == RESULT_OK && data != null && data.getData() != null && pendingBytes != null) {
                try {
                    OutputStream out = getContentResolver().openOutputStream(data.getData());
                    if (out != null) {
                        try {
                            out.write(pendingBytes);
                            out.flush();
                            ok = true;
                        } finally {
                            out.close();
                        }
                    }
                } catch (Exception e) {
                    ok = false;
                }
            }
            String name = pendingName;
            pendingBytes = null;
            pendingName = null;
            notifyJs(ok, name);
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    /** Let the web app close its dialogs first; leave the app only when nothing is open. */
    @Override
    public void onBackPressed() {
        webView.evaluateJavascript(
                "(function(){try{return window.__onBack ? window.__onBack() : false;}catch(e){return false;}})()",
                new ValueCallback<String>() {
                    @Override
                    public void onReceiveValue(String value) {
                        if (!"true".equals(value)) {
                            MainActivity.super.onBackPressed();
                        }
                    }
                });
    }

    @Override
    protected void onPause() {
        webView.onPause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        webView.onResume();
    }

    @Override
    protected void onDestroy() {
        webView.destroy();
        super.onDestroy();
    }
}
''',
}


def main():
    for rel, text in FILES.items():
        path = os.path.join(OUT, *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    assets = os.path.join(OUT, 'app', 'src', 'main', 'assets')
    os.makedirs(assets, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, 'index.html'), os.path.join(assets, 'index.html'))
    icon = os.path.join(HERE, 'icon-192.png')
    sizes = {'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}
    res = os.path.join(OUT, 'app', 'src', 'main', 'res')
    try:
        from PIL import Image
        img = Image.open(icon).convert('RGBA')
        for density, size in sizes.items():
            folder = os.path.join(res, 'mipmap-' + density)
            os.makedirs(folder, exist_ok=True)
            img.resize((size, size), Image.LANCZOS).save(os.path.join(folder, 'ic_launcher.png'))
    except ImportError:
        folder = os.path.join(res, 'mipmap-xxxhdpi')
        os.makedirs(folder, exist_ok=True)
        shutil.copyfile(icon, os.path.join(folder, 'ic_launcher.png'))
    print('Android project created in', OUT)


main()
