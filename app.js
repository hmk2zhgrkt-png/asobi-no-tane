const games=[
["どうぶつまねっこ","うさぎ・ぞう・ねこになりきって動いてみよう。","道具なし",1,6,5,"active"],
["色さがし探検","『赤いものはどこ？』と声をかけて部屋の色を探そう。","道具なし",2,6,5,"active"],
["クッション島わたり","滑らない場所にクッションを並べて島を渡ろう。","クッション",3,6,15,"active"],
["お絵かきクイズ","絵を描いて何を描いたか当ててもらおう。","紙・クレヨン",3,6,15,"creative"],
["ぬいぐるみのお店屋さん","ぬいぐるみを並べてお買い物ごっこ。","ぬいぐるみ",2,6,15,"quiet"],
["宝物ならべ","大きめのおもちゃを色や形で並べてみよう。","大きめのおもちゃ",1,6,5,"quiet"],
["新聞紙びりびり","大人と一緒に新聞紙をちぎって音を楽しもう。","新聞紙",2,6,15,"creative"],
["かげまねゲーム","大人のポーズを見て同じ形をまねしてみよう。","道具なし",2,6,5,"active"],
["お話のつづき","『ある日、くまさんが…』の続きを一緒に考えよう。","道具なし",3,6,15,"quiet"],
["紙コップタワー","紙コップを重ねて高い塔をつくろう。","紙コップ",2,6,15,"creative"],
["タオルでいないいないばあ","タオルで顔を隠して、ばあ！","タオル",1,3,5,"quiet"],
["おうちコンサート","手拍子や歌でリズム遊びをしよう。","道具なし",1,6,15,"active"],
["まねっこ体操","ゆっくり伸びたりしゃがんだりしてみよう。","道具なし",2,6,5,"active"],
["絵本の主人公ごっこ","お気に入りの絵本の場面を演じよう。","絵本",3,6,15,"quiet"],
["形さがし","丸・四角・三角のものを探してみよう。","道具なし",3,6,15,"quiet"],
["タオルたたみ競争","小さなタオルを一緒にたたんでみよう。","タオル",2,6,5,"quiet"],
["おもちゃのかくれんぼ","大人が隠したおもちゃを見つけよう。","おもちゃ",2,6,15,"active"],
["紙のお面づくり","紙に動物の顔を描いてお面をつくろう。","紙・クレヨン",4,6,30,"creative"],
["おてて影絵","ライトの前で手の影を動かそう。光を直接見ないように。","ライト",3,6,15,"quiet"],
["おもちゃのパレード","おもちゃを一列に並べて行進させよう。","おもちゃ",1,6,15,"quiet"],
["ふわふわキャッチ","丸めた柔らかいタオルを近くで投げて受け取ろう。","タオル",3,6,15,"active"],
["数字を探そう","部屋や絵本の数字を一緒に見つけよう。","絵本など",4,6,15,"quiet"],
["名前のしりとり","動物や食べ物の名前でしりとりをしよう。","道具なし",4,6,15,"quiet"],
["シールで模様づくり","大きめのシールを紙に貼って模様をつくろう。","大きめのシール・紙",2,6,15,"creative"],
["紙飛行機を飛ばそう","大人と紙飛行機を折って飛ばしてみよう。","紙",4,6,30,"creative"],
["お部屋の天気予報","今日の天気をお天気キャスターになって発表。","道具なし",3,6,5,"quiet"],
["ぬいぐるみのお医者さん","ぬいぐるみを診察するごっこ遊び。","ぬいぐるみ",3,6,15,"quiet"],
["音あてクイズ","目を閉じて手拍子や紙の音を当てよう。","紙など",3,6,5,"quiet"],
["親子じゃんけん","じゃんけんで勝ったら好きなポーズ！","道具なし",4,6,5,"active"],
["おもちゃの色分け","安全な大きさのおもちゃを色別に集めよう。","おもちゃ",2,6,15,"quiet"],
["指でお絵かき","机の上に指で見えない絵を描いて当てよう。","道具なし",2,6,5,"creative"],
["おうち電車","椅子を並べて電車の運転手になろう。","椅子",3,6,15,"quiet"],
["ゆっくり忍者","音を立てずにゆっくり歩いてみよう。","道具なし",3,6,5,"active"],
["お片づけミッション","おもちゃを種類別におうちへ帰してあげよう。","おもちゃ",2,6,15,"active"],
["鏡で変顔","鏡を見ながらいろいろな表情をつくろう。","鏡",2,6,5,"quiet"],
["お話の絵を描こう","今日のお話の好きな場面を描こう。","紙・クレヨン",4,6,30,"creative"],
["手拍子まねっこ","大人の手拍子の回数をまねしよう。","道具なし",2,6,5,"quiet"],
["タオルの形づくり","タオルを丸めて動物や食べ物の形をつくろう。","タオル",2,6,15,"creative"],
["おうち郵便屋さん","紙のお手紙を家族に届けよう。","紙",3,6,15,"creative"],
["指人形のおしゃべり","指に顔を描いた紙を巻き、会話してみよう。","紙・ペン",4,6,30,"creative"],
["絵本さがし","『犬が出てくる本は？』と本棚から探そう。","絵本",2,6,15,"quiet"],
["ポーズでストップ","大人の『ストップ！』でポーズを止めよう。","道具なし",3,6,5,"active"],
["お店のメニューづくり","好きな食べ物の絵でメニューをつくろう。","紙・クレヨン",4,6,30,"creative"],
["紙の冠づくり","紙を飾って自分だけの冠をつくろう。","紙・テープ",4,6,30,"creative"],
["好きなものベスト3","好きな食べ物や動物を3つ選んで発表。","道具なし",3,6,5,"quiet"],
["ゆびで数えよう","歌に合わせて指を一本ずつ動かそう。","道具なし",1,6,5,"quiet"],
["ぬいぐるみの遠足","ぬいぐるみを連れて家の中を探検。","ぬいぐるみ",2,6,15,"active"],
["くるくるダンス","好きな歌で安全なスペースで踊ろう。","音楽（任意）",2,6,15,"active"],
["紙の花をつくろう","紙に花を描いて大人と切り抜こう。","紙・クレヨン・はさみ（大人用）",4,6,30,"creative"],
["ありがとうカード","家族にありがとうの絵や言葉を贈ろう。","紙・クレヨン",3,6,30,"creative"]
];

games.push(...(window.extraGames || []));
const $ = id => document.getElementById(id);
const STORE = "asobi-no-tane-favorites";
const METRICS = "asobi-no-tane-metrics";
let current = null, last = -1;
function load(key, fallback) { try { const x=JSON.parse(localStorage.getItem(key)); return x ?? fallback; } catch { return fallback; } }
function save(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} }
function favorites() { const x=load(STORE,[]); return Array.isArray(x)?x.filter(i=>Number.isInteger(i)&&i>=0&&i<games.length):[]; }
function track(name) {
  const m=load(METRICS,{visits:0,draws:0,shares:0,favorites:0});
  m[name]=(m[name]||0)+1; save(METRICS,m);
  // External traffic analytics is optional and disabled until the owner configures it.
  if (window.ASOBI_ANALYTICS && typeof window.ASOBI_ANALYTICS.track==="function") {
    try { window.ASOBI_ANALYTICS.track(name); } catch {}
  }
}
function eligible() {
  const age=+$("age").value, mins=+$("minutes").value, type=$("type").value;
  const gear=$("gear").value, cleanup=$("cleanup").checked, keyword=$("keyword").value.trim().toLowerCase();
  return games.map((g,i)=>({g,i})).filter(({g})=>
    g[3]<=age && age<=g[4] && g[5]<=mins &&
    (type==="any" || g[6]===type) &&
    (gear!=="none" || g[2]==="道具なし") &&
    (!cleanup || g[2]==="道具なし") &&
    (!keyword || (g[0]+" "+g[1]+" "+g[2]).toLowerCase().includes(keyword))
  );
}
function count() {
  const n=eligible().length;
  $("matches").textContent="条件に合う遊び："+n+"件（全"+games.length+"種類）";
  $("draw").disabled=n===0;
}
function show(i, scroll=true) {
  current=i; last=i;
  const g=games[i]; if(!g)return;
  $("result").classList.remove("hidden");
  $("title").textContent=g[0]; $("description").textContent=g[1];
  $("materials").textContent="用意するもの："+g[2];
  $("details").textContent=g[3]+"〜"+g[4]+"歳向け ・ 約"+g[5]+"分";
  syncFavorite();
  if(scroll)$("result").scrollIntoView({behavior:"smooth",block:"nearest"});
}
function draw() {
  const pool=eligible().filter(x=>x.i!==last);
  const choices=pool.length?pool:eligible();
  if(!choices.length){$("result").classList.add("hidden");return;}
  const item=choices[Math.floor(Math.random()*choices.length)];
  show(item.i); track("draws");
}
function syncFavorite() {
  $("favorite").textContent=favorites().includes(current)?"★ お気に入り解除":"☆ お気に入りに追加";
}
function showFavorites() {
  const ids=favorites(); const root=$("favorites");root.replaceChildren();
  $("favcount").textContent=ids.length+"件";
  if(!ids.length){const p=document.createElement("p");p.className="hint";p.textContent="まだ登録されていません。";root.append(p);return;}
  for(const i of ids) {
    const line=document.createElement("div");line.className="favorite-item";
    const open=document.createElement("button");open.className="favorite-open";open.textContent=games[i][0];
    open.addEventListener("click",()=>show(i));
    const remove=document.createElement("button");remove.className="remove";remove.textContent="削除";remove.setAttribute("aria-label",games[i][0]+"をお気に入りから削除");
    remove.addEventListener("click",()=>{save(STORE,favorites().filter(x=>x!==i));showFavorites();if(current===i)syncFavorite();});
    line.append(open,remove);root.append(line);
  }
}
async function share() {
  if(current===null)return;
  const g=games[current];
  const url=new URL(location.href);url.searchParams.set("play",String(current));
  const data={title:"あそびのタネ｜"+g[0],text:g[0]+"："+g[1],url:url.href};
  try {
    if(navigator.share)await navigator.share(data);
    else if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(data.text+"\n"+data.url);$("share").textContent="✓ コピーしました";}
    else {prompt("このリンクをコピーしてください",data.url);}
    track("shares");
  } catch(e){if(e.name!=="AbortError")$("share").textContent="共有できませんでした";}
}
["age","minutes","type","gear","cleanup","keyword"].forEach(id=>$(id).addEventListener(id==="keyword"?"input":"change",count));
$("draw").addEventListener("click",draw);
$("again").addEventListener("click",draw);
$("share").addEventListener("click",share);
$("favorite").addEventListener("click",()=>{
  if(current===null)return;
  const ids=favorites();save(STORE,ids.includes(current)?ids.filter(i=>i!==current):[...ids,current]);
  track("favorites");syncFavorite();showFavorites();
});
$("reset").addEventListener("click",()=>{
  $("age").value="3";$("minutes").value="15";$("type").value="any";$("gear").value="any";$("cleanup").checked=false;$("keyword").value="";count();
});
const play=new URLSearchParams(location.search).get("play");
if(play!==null && /^\d+$/.test(play) && games[Number(play)])show(Number(play),false);
showFavorites();count();track("visits");
