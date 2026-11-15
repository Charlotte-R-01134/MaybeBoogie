import { detect, initPose } from "./pose.js";
import { POINTS, TICK, bestMatch, judge, landmarkVecs, mirror, prepareReference, stars } from "./scoring.js";

const $ = id => document.getElementById(id);
const stage = $("stage"), song = $("song"), overlay = $("overlay"), msg = $("msg"), count = $("count");
const actions = $("overlay-actions"), go = $("go"), results = $("results"), fill = $("songfill");
const scoreEl = $("score"), comboEl = $("combo"), judgeEl = $("judge");
const judgeImage = $("judge-image"), noteEl = $("note");
const cam = window.camera;
const skel = document.querySelector("#cam canvas"), sctx = skel.getContext("2d");
const wait = ms => new Promise(r => setTimeout(r, ms));
const DRAW = [[5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [11, 12], [5, 11], [6, 12], [11, 13], [13, 15], [12, 14], [14, 16]];
const imageBase = stage.dataset.scoreImageBase;
const judgeImageUrls = Object.fromEntries(
  ["SLAY", "AWESOME", "COOL", "SWEET", "MEH", "MISS"].map(result => [
    result,
    imageBase + result.toLowerCase() + ".PNG",
  ]),
);
Object.values(judgeImageUrls).forEach(url => {
  const image = new Image();
  image.src = url;
});

let ref = null, scoring = false, running = false, raf = 0, goAction = null;
let points = 0, combo = 0, maxCombo = 0, ticks = 0, expectedTicks = 1, lastTick = 0;
let lastPose = 0, lastPlayer = null, lastPlayerAt = 0;
let displayedJudge = null;
const counts = { SLAY: 0, AWESOME: 0, COOL: 0, SWEET: 0, MEH: 0, MISS: 0 } ;

// ---------- reference choreography ----------
async function loadReference(url) {
  if (url) {
    try {
      const data = await (await fetch(url)).json();
      return { frames: prepareReference({ aspect: data.aspect || 16 / 9, frames: data.frames }), aspect: data.aspect || 16 / 9, demo: false };
    } catch (e) {  }
  }
  return null; 
}

// ---------- game flow ----------
async function start() {
  running = false; cancelAnimationFrame(raf);
  points = combo = maxCombo = ticks = lastTick = 0;
  Object.keys(counts).forEach(k => counts[k] = 0);
  lastPlayer = null; displayedJudge = null; render();
  results.hidden = true; $("game-over").hidden = true; actions.hidden = true; overlay.hidden = false; count.textContent = "";
  stage.hidden = false; document.body.classList.add("playing");
  msg.textContent = "Allow your camera to start...";

  const info = window.trackInfo || {};
  if (song.getAttribute("src") !== info.video) song.src = info.video;
  // Unlock sound while we still have the click, so the browser lets us play it after the countdown
  song.volume = 0;
  try { await song.play(); song.pause(); } catch (e) { /* handled below */ }
  song.currentTime = 0; song.volume = 1;

  const [camOk, poseOk] = await Promise.all([cam.start(), initPose().then(() => true, () => false)]);
  ref = await loadReference(info.keypoints);
  scoring = camOk && poseOk;
  noteEl.textContent = !camOk ? "No camera: practice mode, no score"
    : !poseOk ? "Pose tracking didn't load: practice mode, no score"
    : ref === null ? "No reference: practice mode, no score" : "";
  noteEl.hidden = !noteEl.textContent;
  expectedTicks = Math.max(1, Math.floor((song.duration || 1) / TICK));

  msg.textContent = "Here we go...";
  for (const n of [3, 2, 1]) {
    count.textContent = n;
    count.classList.remove("pop"); void count.offsetWidth; count.classList.add("pop");
    await wait(1000);
  }
  count.textContent = "";
  try { await beginPlayback(); }
  catch (e) {                                   // sound autoplay blocked: ask for one tap
    msg.textContent = "Ready?"; go.textContent = "Start"; goAction = beginPlayback; actions.hidden = false;
  }
}

async function beginPlayback() {
  await song.play();
  overlay.hidden = true; actions.hidden = true;
  running = true; raf = requestAnimationFrame(loop);
}

function loop(now) {
  if (!running) return;
  raf = requestAnimationFrame(loop);
  const t = song.currentTime;
  fill.style.width = song.duration ? (t / song.duration * 100) + "%" : "0%";
  if (!scoring) return;

  if (now - lastPose > 50) {                    // ~20 pose checks a second is plenty
    lastPose = now;
    const p = detect(cam.video, now);
    if (p) { lastPlayer = p; lastPlayerAt = now; drawSkeleton(p); }
    else if (now - lastPlayerAt > 500) drawSkeleton(null);
  }
  if (t - lastTick >= TICK) { lastTick = t; tick(t, now); }
}

function tick(t, now) {
  let result = "MISS";
  if (lastPlayer && now - lastPlayerAt < 500) {
    const aspect = cam.video.videoWidth / cam.video.videoHeight;
    result = judge(bestMatch(ref.frames, t, landmarkVecs(mirror(lastPlayer), aspect)));
  }
  ticks++; counts[result]++; points += POINTS[result];
  combo = result === "MISS" ? 0 : combo + 1;
  maxCombo = Math.max(maxCombo, combo);
  judgeEl.className = "judge"; void judgeEl.offsetWidth;
  judgeEl.className = "judge pop " + result.toLowerCase();
  if (result !== displayedJudge) {
    displayedJudge = result;
    judgeImage.src = judgeImageUrls[result];
    judgeImage.alt = result;
    judgeImage.hidden = false;
  }
  render();
}

const liveScore = () => Math.round(points / (expectedTicks * POINTS.SLAY) * 10000);
function render() {
  scoreEl.textContent = liveScore().toLocaleString();
  comboEl.textContent = combo > 1 ? combo + " combo" : "";
}

function finish() {
  running = false; cancelAnimationFrame(raf); drawSkeleton(null);
  count.textContent = ""; judgeEl.className = "judge";
  msg.textContent = scoring ? "Nice moves!" : "That's the song!";
  const final = liveScore(), accuracy = ticks ? points / (ticks * POINTS.SLAY) : 0, n = stars(accuracy);
  $("r-stars").textContent = "★".repeat(n) + "☆".repeat(5 - n);
  $("r-score").textContent = final.toLocaleString();
  $("r-acc").textContent = Math.round(accuracy * 100) + "%";
  $("r-combo").textContent = maxCombo;
  $("r-counts").textContent = Object.entries(counts).map(([k, v]) => k.toLowerCase() + " " + v).join("  ");
  results.removeAttribute("hidden");
  if (scoring) {
    saveScore(final, accuracy);
  }
  const gameOver = $("game-over");
  gameOver.removeAttribute("hidden");
  go.textContent = "Dance again"; goAction = start;
  actions.removeAttribute("hidden");
  overlay.removeAttribute("hidden");
}

async function saveScore(score, accuracy) {
  const url = stage.dataset.scoreUrl;
  if (!url || ref.demo) return;
  const tokenEl = document.querySelector("[name=csrfmiddlewaretoken]");
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": tokenEl ? tokenEl.value : "" },
      body: JSON.stringify({ score, accuracy, max_combo: maxCombo }),
    });
  } catch (e) { /* the results screen still shows */ }
}

function drawSkeleton(p) {
  const w = skel.width = cam.video.videoWidth || 640, h = skel.height = cam.video.videoHeight || 480;
  sctx.clearRect(0, 0, w, h);
  if (!p) return;
  sctx.lineWidth = Math.max(3, w / 100); sctx.lineCap = "round"; sctx.strokeStyle = "#ff5d8f";
  for (const [a, b] of DRAW) {
    if (p[a][2] < 0.4 || p[b][2] < 0.4) continue;
    sctx.beginPath(); sctx.moveTo(p[a][0] * w, p[a][1] * h); sctx.lineTo(p[b][0] * w, p[b][1] * h); sctx.stroke();
  }
  sctx.fillStyle = "#ffd166";
  for (const [x, y, c] of p) if (c >= 0.4) { sctx.beginPath(); sctx.arc(x * w, y * h, sctx.lineWidth * 0.9, 0, 7); sctx.fill(); }
}

function leave() {
  running = false; cancelAnimationFrame(raf); song.pause();
  cam.stop(); drawSkeleton(null);
  stage.hidden = true; document.body.classList.remove("playing");
}

$("play").addEventListener("click", start);
$("quit").addEventListener("click", leave);
$("leave").addEventListener("click", leave);
go.addEventListener("click", () => goAction && goAction());
song.addEventListener("ended", finish);