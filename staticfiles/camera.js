(function () {
  const box = document.getElementById("cam");
  if (!box) return;
  const video = box.querySelector("video");
  const btn = box.querySelector("button");
  const msg = box.querySelector(".cam-msg");
  let stream = null;

  async function start() {
    if (stream) return true;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      msg.textContent = "The camera needs HTTPS (localhost is fine).";
      return false;
    }
    btn.disabled = true;
    msg.textContent = "Asking for your camera...";
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      video.srcObject = stream;
      await video.play();
      box.classList.add("on");
      return true;
    } catch (e) {
      stream = null;
      btn.disabled = false;
      msg.textContent = e.name === "NotAllowedError"
        ? "Camera blocked. Allow it in the address bar, then tap the button."
        : "Couldn't find a camera.";
      return false;
    }
  }

  function stop() {
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
    video.srcObject = null;
    box.classList.remove("on");
    btn.disabled = false;
    msg.textContent = "Check your framing before you dance.";
  }

  btn.addEventListener("click", start);
  window.addEventListener("pagehide", stop);
  const ready = "autostart" in box.dataset ? start() : Promise.resolve(false);
  window.camera = { video, start, stop, ready };
})();