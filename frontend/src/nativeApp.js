import { Capacitor } from "@capacitor/core";
import { App } from "@capacitor/app";

/** Hardware back button and native chrome for the Capacitor shells. */
export async function initNativeApp() {
  if (!Capacitor.isNativePlatform()) return;

  document.documentElement.classList.add("is-native-app");
  document.body.classList.add("is-native-app");

  App.addListener("backButton", ({ canGoBack }) => {
    if (canGoBack || window.history.length > 1) {
      window.history.back();
      return;
    }
    App.exitApp();
  });
}
