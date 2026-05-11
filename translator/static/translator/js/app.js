/* -----------------------------------------------------------------------
 * LLM MT Demo — client-side helpers
 *
 * Currently we only need:
 *   1. Switch button: swap source/target languages and texts in-place,
 *      no server round-trip.
 *
 * Clone-to-Tab is a pure HTML submit (``formtarget="_blank"``) and
 * therefore needs no JS.  The form submits whatever the user currently
 * sees in the DOM, including any unsubmitted edits, so the new tab is
 * an accurate snapshot.
 * --------------------------------------------------------------------- */

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const switchBtn = document.getElementById("btn-switch");
    if (switchBtn) {
      switchBtn.addEventListener("click", swapSourceAndTarget);
    }
  });

  /**
   * Swap source <-> target on both the language selectors and the
   * text panels.  Operates entirely on the live DOM; the form does
   * not need to be submitted.
   */
  function swapSourceAndTarget() {
    const srcLang = document.getElementById("id_source_language");
    const tgtLang = document.getElementById("id_target_language");
    const srcText = document.getElementById("id_source_text");
    const tgtText = document.getElementById("id_target_text");

    if (srcLang && tgtLang) {
      const tmp = srcLang.value;
      srcLang.value = tgtLang.value;
      tgtLang.value = tmp;
    }
    if (srcText && tgtText) {
      const tmp = srcText.value;
      srcText.value = tgtText.value;
      tgtText.value = tmp;
    }
  }
})();
