import { FilesetResolver, PoseLandmarker } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs";

const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const MODEL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
const MP_TO_COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]; // ignores hands and feet as not needed

let landmarker = null, loading = null, lastVideoTime = -1;

async function create() {
  const fileset = await FilesetResolver.forVisionTasks(WASM);
  const make = delegate => PoseLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: MODEL, delegate }, runningMode: "VIDEO", numPoses: 1,
  });
  try { landmarker = await make("GPU"); } catch (e) { landmarker = await make("CPU"); }
}

export function initPose() {
  if (!loading) loading = create().catch(e => { loading = null; throw e; });
  return loading;
}

// Returns 17 x [x, y, conf], or null if there's no new frame / nobody in view.
export function detect(video, nowMs) {
  if (!landmarker || video.readyState < 2 || video.currentTime === lastVideoTime) return null;
  lastVideoTime = video.currentTime;
  const res = landmarker.detectForVideo(video, nowMs);
  const lm = res.landmarks && res.landmarks[0];
  if (!lm) return null;
  return MP_TO_COCO.map(i => [lm[i].x, lm[i].y, lm[i].visibility ?? 1]);
}