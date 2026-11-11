// 公開アクセス解析は任意です。Cloudflare Web Analytics のトークンを設定すると
// 実際の訪問数をCloudflareの管理画面で確認できます。
// トークン未設定時は外部にアクセス解析データを送信しません。
const CLOUDFLARE_WEB_ANALYTICS_TOKEN = "";
if (CLOUDFLARE_WEB_ANALYTICS_TOKEN) {
  const script = document.createElement("script");
  script.defer = true;
  script.src = "https://static.cloudflareinsights.com/beacon.min.js";
  script.dataset.cfBeacon = JSON.stringify({token: CLOUDFLARE_WEB_ANALYTICS_TOKEN});
  document.head.appendChild(script);
}
