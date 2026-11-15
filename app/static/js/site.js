/*
  Site-wide JavaScript. Small and optional: every page still works without it.

  1. Marks <html> with class "js" so CSS knows scripts are running.
  2. Mobile menu toggle.
  3. Click-to-load install videos (no YouTube/TikTok requests until tapped).
  4. Cart quantity dropdowns submit as soon as they change.
  5. Vote countdown: ticks every second until the round's close time.
  6. Before / Now comparison slider on the Revival Car page.
*/
document.documentElement.classList.add("js");

document.addEventListener("DOMContentLoaded", function () {
  // ----- 2. Mobile menu -----
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // ----- 3. Click-to-load videos -----
  // Each .video-frame carries the embed URL in data-embed-src (built and
  // checked on the server in services/embeds.py). On click we swap the
  // play button for an <iframe>.
  document.querySelectorAll(".video-frame[data-embed-src]").forEach(function (frame) {
    var button = frame.querySelector(".video-play");
    if (!button) return;
    button.addEventListener("click", function () {
      var iframe = document.createElement("iframe");
      var src = frame.dataset.embedSrc;
      // Ask YouTube to start playing, since the visitor already pressed play.
      if (src.indexOf("youtube-nocookie.com") !== -1) src += "?autoplay=1&rel=0";
      iframe.src = src;
      iframe.title = frame.dataset.embedTitle || "Install video";
      iframe.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
      iframe.allowFullscreen = true;
      iframe.referrerPolicy = "strict-origin-when-cross-origin";
      frame.replaceChildren(iframe);
    });
  });

  // ----- 4. Auto-submit cart quantity -----
  // Without JS the "Update" button does the same job (CSS hides it when JS runs).
  document.querySelectorAll("select.js-autosubmit").forEach(function (select) {
    select.addEventListener("change", function () {
      select.form.submit();
    });
  });

  // ----- 5. Vote countdown -----
  // The server writes the close time (from the database, in UTC) into
  // data-closes-at. We only count down to it; we never invent a date.
  document.querySelectorAll(".countdown[data-closes-at]").forEach(function (box) {
    var closesAt = Date.parse(box.dataset.closesAt);
    if (isNaN(closesAt)) return;
    var parts = {};
    box.querySelectorAll("[data-unit]").forEach(function (el) { parts[el.dataset.unit] = el; });
    var closedText = box.querySelector(".countdown-closed");
    var pad = function (n) { return n < 10 ? "0" + n : String(n); };

    // Show the close time in the visitor's own time zone.
    var when = box.querySelector(".countdown-when time");
    if (when) {
      when.textContent = new Date(closesAt).toLocaleString(undefined, {
        weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
      });
    }

    function tick() {
      var left = Math.max(0, Math.floor((closesAt - Date.now()) / 1000));
      if (left === 0) {
        box.classList.add("is-closed");
        if (closedText) closedText.hidden = false;
        clearInterval(timer);
        return;
      }
      parts.days.textContent = pad(Math.floor(left / 86400));
      parts.hours.textContent = pad(Math.floor(left % 86400 / 3600));
      parts.minutes.textContent = pad(Math.floor(left % 3600 / 60));
      parts.seconds.textContent = pad(left % 60);
    }
    var timer = setInterval(tick, 1000);
    tick();
  });

  // ----- 6. Before / Now slider -----
  // The range input sets a CSS variable (--pos); CSS clips the "now" photo to it.
  document.querySelectorAll(".compare").forEach(function (compare) {
    var range = compare.querySelector(".compare-range");
    if (!range) return;
    var update = function () { compare.style.setProperty("--pos", range.value + "%"); };
    range.addEventListener("input", update);
    update();
    compare.classList.add("is-ready");
  });
});
