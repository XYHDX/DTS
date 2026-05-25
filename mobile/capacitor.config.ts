import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  // App bundle identifiers — update before release
  appId: 'sy.gov.damascus.transit',
  appName: 'نقل دمشق',

  // Web assets are served from the parent project's public/ directory.
  // Run `npx cap sync` from the mobile/ directory after any web changes.
  webDir: '../public',

  // Serve app locally during development (comment out for production builds)
  // server: {
  //   url: 'http://192.168.1.X:8080',
  //   cleartext: true,
  // },

  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      launchAutoHide: true,
      backgroundColor: '#002623',
      androidSplashResourceName: 'splash',
      androidScaleType: 'CENTER_CROP',
      showSpinner: false,
      iosSpinnerStyle: 'small',
      spinnerColor: '#b9a779',
    },

    StatusBar: {
      style: 'DARK',
      backgroundColor: '#002623',
    },

    // Geolocation — high-accuracy, background-capable for driver app
    Geolocation: {
      // iOS: requires NSLocationAlwaysAndWhenInUseUsageDescription in Info.plist
      // Android: ACCESS_FINE_LOCATION + ACCESS_BACKGROUND_LOCATION in manifest
    },

    // Background geolocation (@capawesome-team/capacitor-background-geolocation)
    BackgroundGeolocation: {
      // Stale-location threshold: 30s
      maximumLocationAge: 30000,
      // Min distance (metres) between updates
      minimumDistanceFilter: 20,
      requestPermissions: true,
    },

    // Push notifications — FCM (Android) and APNs (iOS)
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },

    // Camera — for driver incident photo reporting
    Camera: {
      // iOS: NSCameraUsageDescription in Info.plist
    },

    // Biometric auth
    // Uses 'capacitor-biometric-auth' plugin
    // Android: USE_BIOMETRIC + USE_FINGERPRINT in manifest
    // iOS: NSFaceIDUsageDescription in Info.plist

    Keyboard: {
      resize: 'body',
      resizeOnFullScreen: true,
    },
  },

  android: {
    // Allow cleartext traffic to the local API during development.
    // Remove for production builds pointing at HTTPS endpoints.
    allowMixedContent: false,
    // RTL support is set in AndroidManifest.xml via android:supportsRtl="true"
    // Dark status bar icons on light backgrounds
    backgroundColor: '#002623',
  },

  ios: {
    // Scroll behaviour
    scrollEnabled: false,
    contentInset: 'automatic',
    backgroundColor: '#002623',
    // Prefer dark status-bar style to match dark green header
    preferredContentMode: 'mobile',
  },
};

export default config;
