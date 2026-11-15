// 0 nose, 1/2 eyes, 3/4 ears, 5/6 shoulders, 7/8 elbows, 9/10 wrists, 11/12 hips, 13/14 knees, 15/16 ankles (odd = left)

export const TICK = 0.5; // seconds between judgements
export const WINDOW = 0.25; // window of time to look for a matching reference frame
const MIN_CONF = 0.4;
const MIN_WEIGHT = 3;
export const POINTS = { SLAY: 100, AWESOME: 80, COOL: 60, SWEET: 40, MEH: 20, MISS: 0 };
const THRESHOLDS = [["SLAY", 0.90], ["AWESOME", 0.80], ["COOL", 0.65], ["SWEET", 0.50], ["MEH", 0.35]];  // similarity thresholds for each judgement

// arms are weighted more
// [a, b, weight]
export const LANDMARKS = [
  [5, 7, 1.5], [7, 9, 1.5], [6, 8, 1.5], [8, 10, 1.5],     // arms
  [11, 13, 1], [13, 15, 1], [12, 14, 1], [14, 16, 1],      // legs
  [5, 6, 0.5], [11, 12, 0.5], [5, 11, 0.7], [6, 12, 0.7],  // torso
];

// mirror
const SWAP = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15];
export const mirror = p => SWAP.map(i => [1 - p[i][0], p[i][1], p[i][2]]);

export function landmarkVecs(pose, aspect) { // returns in vector format
  return LANDMARKS.map(([a, b]) => {
    const pa = pose[a], pb = pose[b]; // the two endpoints
    if (!pa || !pb || pa[2] < MIN_CONF || pb[2] < MIN_CONF) return null; // if missing or low confidence
    const dx = (pb[0] - pa[0]) * aspect // x distance, scaled by aspect ratio
    const dy = pb[1] - pa[1]; // y distance
    const len = Math.hypot(dx, dy); // segment direciton
    return len < 1e-4 ? null : [dx / len, dy / len]; // unit vector
  });
}

// weighted cosine similarity
export function similarity(refVecs, playerVecs) {
  let sum = 0, wsum = 0;
  LANDMARKS.forEach(([, , w], i) => {
    const r = refVecs[i], p = playerVecs[i];
    if (!r || !p) return;
    sum += w * Math.max(0, r[0] * p[0] + r[1] * p[1]);
    wsum += w;
  });
  return wsum >= MIN_WEIGHT ? sum / wsum : null;
}

// pre-compute landmark directions 
export function prepareReference({ aspect, frames }) {
  const empty = LANDMARKS.map(() => null);
  return frames.map(f => ({ t: f.t, v: f.j ? landmarkVecs(f.j, aspect) : empty }));
}

// best similarity within window
export function bestMatch(frames, t, playerVecs) {
  if (!frames.length) return null;
  let lo = 0, hi = frames.length - 1;
  while (lo < hi) { const m = (lo + hi) >> 1; if (frames[m].t < t) lo = m + 1; else hi = m; }
  let best = null;
  const consider = i => {
    const s = similarity(frames[i].v, playerVecs);
    if (s !== null && (best === null || s > best)) best = s;
  };
  for (let i = lo; i >= 0 && frames[i].t >= t - WINDOW; i--) if (frames[i].t <= t + WINDOW) consider(i);
  for (let i = lo + 1; i < frames.length && frames[i].t <= t + WINDOW; i++) consider(i);
  return best;
}

export function judge(similarityValue) {
  if (similarityValue === null) return "MISS";
  for (const [name, min] of THRESHOLDS) if (similarityValue >= min) return name;
  return "MISS";
}

export const stars = accuracy => accuracy >= 0.9 ? 5 : accuracy >= 0.75 ? 4 : accuracy >= 0.6 ? 3 : accuracy >= 0.4 ? 2 : 1;