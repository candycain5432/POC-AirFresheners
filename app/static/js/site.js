/*
  Site-wide JavaScript. Small and optional: every page still works without it.

  1. Marks <html> with class "js" so CSS knows scripts are running.
  2. Mobile menu toggle.
  3. Click-to-load install videos (no YouTube/TikTok requests until tapped).
  4. Cart quantity dropdowns submit as soon as they change.
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
});
