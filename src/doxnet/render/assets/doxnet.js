(function () {
  "use strict";
  var root = document.documentElement;
  var sidebar = document.querySelector(".sidebar");
  var search = document.getElementById("search");

  document.getElementById("theme").addEventListener("click", function () {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("doxnet-theme", root.dataset.theme); } catch (e) { /* private mode */ }
  });

  document.getElementById("menu").addEventListener("click", function () {
    sidebar.classList.toggle("open");
    this.setAttribute("aria-expanded", sidebar.classList.contains("open"));
  });
  sidebar.addEventListener("click", function (event) {
    if (event.target.closest("a")) { sidebar.classList.remove("open"); }
  });

  // Every term must appear somewhere in the unit's search text.
  function filter() {
    var terms = search.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
    function matches(text) {
      return terms.every(function (t) { return text.indexOf(t) !== -1; });
    }
    document.querySelectorAll("[data-search]").forEach(function (el) {
      el.hidden = terms.length > 0 && !matches(el.dataset.search);
    });
    document.querySelectorAll(".file-block").forEach(function (block) {
      var units = block.querySelectorAll("article.unit");
      var visible = Array.prototype.some.call(units, function (u) { return !u.hidden; });
      block.hidden = terms.length > 0 && !visible;
    });
  }
  search.addEventListener("input", filter);
  search.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { search.value = ""; filter(); search.blur(); }
    if (event.key === "Enter") {
      var first = document.querySelector("article.unit:not([hidden])");
      if (first) { location.hash = first.id; }
    }
  });
  document.addEventListener("keydown", function (event) {
    var tag = (event.target.tagName || "").toLowerCase();
    if (event.key === "/" && tag !== "input" && tag !== "textarea") {
      event.preventDefault();
      search.focus();
      search.select();
    }
  });

  // Links to source lines point into collapsed <details>; open them first.
  function reveal() {
    if (!location.hash) { return; }
    var target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!target) { return; }
    var details = target.closest("details");
    if (details && !details.open) {
      details.open = true;
      target.scrollIntoView();
    }
  }
  window.addEventListener("hashchange", reveal);
  reveal();

  // Highlight the sidebar entry of the unit currently in view.
  if ("IntersectionObserver" in window) {
    var links = {};
    sidebar.querySelectorAll("a[href^='#unit-']").forEach(function (a) { links[a.getAttribute("href").slice(1)] = a; });
    var current = null;
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && links[entry.target.id]) {
          if (current) { current.classList.remove("active"); }
          current = links[entry.target.id];
          current.classList.add("active");
        }
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    document.querySelectorAll("article.unit").forEach(function (a) { observer.observe(a); });
  }
})();
